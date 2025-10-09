"""Async client for Meta Graph + Marketing APIs with retry, rate limiting, and batching."""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, AsyncIterator, MutableMapping

import httpx
from cachetools import LRUCache

from ..config import get_settings
from ..errors import MCPException, McpError, McpErrorCode
from ..logging import get_logger

logger = get_logger(__name__)


class SlidingWindowRateLimiter:
    """Simple sliding-window limiter per key."""

    def __init__(self, capacity: int, window_seconds: float = 60.0) -> None:
        self.capacity = capacity
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def acquire(self, key: str = "global") -> None:
        async with self._lock:
            now = time.monotonic()
            queue = self._events[key]
            while queue and now - queue[0] >= self.window_seconds:
                queue.popleft()
            if len(queue) >= self.capacity:
                wait_time = self.window_seconds - (now - queue[0])
                await asyncio.sleep(max(wait_time, 0))
                return await self.acquire(key)
            queue.append(now)


class BackoffStrategy:
    def __init__(self, factor: float, maximum: float) -> None:
        self.factor = factor
        self.maximum = maximum

    async def sleep(self, attempt: int) -> None:
        delay = min(self.maximum, (2**attempt) * self.factor)
        jitter = random.random() * 0.1 * delay
        await asyncio.sleep(delay + jitter)


class MetaGraphApiClient:
    """HTTP client with resiliency decorators for Meta APIs."""

    def __init__(self) -> None:
        self.settings = get_settings()
        timeout = httpx.Timeout(self.settings.default_timeout_seconds)
        self._client = httpx.AsyncClient(
            base_url=self.settings.graph_api_base_url,
            timeout=timeout,
            headers={"Accept": "application/json"},
        )
        self._backoff = BackoffStrategy(
            factor=self.settings.retry_backoff_factor,
            maximum=self.settings.retry_backoff_max,
        )
        self._global_limiter = SlidingWindowRateLimiter(self.settings.rate_limit_per_app)
        self._token_limiter = SlidingWindowRateLimiter(self.settings.rate_limit_per_token)
        self._cache: LRUCache[str, Any] | None = None
        if self.settings.cache_maxsize:
            self._cache = LRUCache(maxsize=self.settings.cache_maxsize)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "MetaGraphApiClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    async def request(
        self,
        *,
        access_token: str,
        method: str,
        path: str,
        query: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        form_body: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        use_cache: bool = False,
    ) -> httpx.Response:
        if not path.startswith("/"):
            path = f"/{path}"

        if query:
            query = {k: v for k, v in query.items() if v is not None}
        cache_key = self._cache_key(method, path, query, json_body)
        if json_body is not None and (form_body is not None or files is not None):
            raise ValueError("Cannot send both JSON and form data in the same request")

        if use_cache and self._cache and cache_key in self._cache:
            logger.debug("cache_hit", path=path)
            return self._build_cached_response(method=method, path=path, query=query, cached=self._cache[cache_key])

        headers = {
            "Authorization": f"Bearer {access_token}",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        for attempt in range(self.settings.max_retries + 1):
            await self._global_limiter.acquire()
            await self._token_limiter.acquire(self._hash_token(access_token))
            try:
                response = await self._client.request(
                    method=method,
                    url=path,
                    params=query,
                    json=json_body,
                    data=form_body,
                    files=files,
                    headers=headers,
                )
                await response.aread()
            except httpx.RequestError as exc:  # pragma: no cover - network failure
                if attempt == self.settings.max_retries:
                    raise MCPException(
                        McpError(
                            code=McpErrorCode.REMOTE_5XX,
                            message="HTTP request failed",
                            details={"error": str(exc)},
                        )
                    ) from exc
                await self._backoff.sleep(attempt)
                continue

            if response.status_code == 429 or response.status_code >= 500:
                if attempt == self.settings.max_retries:
                    raise self._map_error(response)
                await self._respect_retry_after(response)
                await self._backoff.sleep(attempt)
                continue

            if response.is_success:
                if use_cache and self._cache is not None:
                    self._cache[cache_key] = {
                        "status": response.status_code,
                        "headers": dict(response.headers),
                        "json": response.json(),
                    }
                return response

            raise self._map_error(response)

        raise MCPException(
            McpError(
                code=McpErrorCode.REMOTE_5XX,
                message="Max retries exceeded",
                details={"path": path},
            )
        )

    async def batch(
        self,
        *,
        access_token: str,
        operations: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if len(operations) > 50:
            raise MCPException(
                McpError(
                    code=McpErrorCode.VALIDATION,
                    message="Batch operations cannot exceed 50",
                )
            )
        response = await self.request(
            access_token=access_token,
            method="POST",
            path=f"/{self.settings.graph_api_version}/batch",
            json_body={"batch": operations},
        )
        return response.json()

    async def paginate(
        self,
        *,
        access_token: str,
        method: str,
        path: str,
        query: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        params = dict(query or {})
        while True:
            response = await self.request(
                access_token=access_token,
                method=method,
                path=path,
                query=params,
            )
            payload = response.json()
            yield payload
            paging = payload.get("paging") or {}
            cursors = paging.get("cursors") or {}
            if "after" not in cursors:
                break
            params["after"] = cursors["after"]

    def _build_cached_response(
        self,
        *,
        method: str,
        path: str,
        query: dict[str, Any] | None,
        cached: dict[str, Any],
    ) -> httpx.Response:
        request = httpx.Request(
            method=method,
            url=self._client.base_url.join(path),
            params=query,
        )
        return httpx.Response(
            status_code=cached["status"],
            headers=cached["headers"],
            json=cached["json"],
            request=request,
        )

    async def _respect_retry_after(self, response: httpx.Response) -> None:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                delay = float(retry_after)
            except ValueError:  # pragma: no cover - seconds since date format
                delay = 0.0
            await asyncio.sleep(delay)

    def _cache_key(
        self,
        method: str,
        path: str,
        query: dict[str, Any] | None,
        json_body: dict[str, Any] | None,
    ) -> str:
        data = json.dumps(
            {
                "method": method,
                "path": path,
                "query": query or {},
                "json": json_body or {},
            },
            sort_keys=True,
        )
        return hashlib.sha1(data.encode()).hexdigest()

    def _hash_token(self, token: str) -> str:
        return hashlib.sha1(token.encode()).hexdigest()

    def _map_error(self, response: httpx.Response) -> MCPException:
        meta: MutableMapping[str, Any] = {}
        for header in [
            "x-app-usage",
            "x-business-use-case-usage",
            "x-ad-account-usage",
            "fbtrace_id",
        ]:
            value = response.headers.get(header)
            if value:
                meta[header] = value

        retry_after = None
        if "Retry-After" in response.headers:
            try:
                retry_after = float(response.headers["Retry-After"])
            except ValueError:
                retry_after = None

        try:
            payload = response.json()
        except json.JSONDecodeError:
            payload = {"error": {"message": response.text}}

        err = payload.get("error", {})
        message = err.get("message", "Unknown error")
        type_ = err.get("type")
        code = err.get("code")
        subcode = err.get("error_subcode")

        error_code = self._classify_error(response.status_code, int(code) if code else None)

        details: dict[str, Any] = {"status": response.status_code}
        if type_:
            details["type"] = type_
        if code is not None:
            details["code"] = code
        if subcode is not None:
            details["error_subcode"] = subcode
        if fbtrace := err.get("fbtrace_id"):
            meta["fbtrace_id"] = fbtrace
        if meta_headers := payload.get("__debug__", {}).get("messages"):
            details["debug_messages"] = meta_headers

        if err.get("error_user_title"):
            details["user_title"] = err["error_user_title"]
        if err.get("error_user_msg"):
            details["user_message"] = err["error_user_msg"]

        return MCPException(
            McpError(
                code=error_code,
                message=message,
                details=details | {"meta": dict(meta)},
                retry_after=retry_after,
            )
        )

    def _classify_error(self, status: int, code: int | None) -> McpErrorCode:
        if status == 401 or (code == 190):
            return McpErrorCode.AUTH
        if status == 403:
            return McpErrorCode.PERMISSION
        if status == 404:
            return McpErrorCode.NOT_FOUND
        if status == 409:
            return McpErrorCode.CONFLICT
        if status == 429:
            return McpErrorCode.RATE_LIMIT
        if 500 <= status < 600:
            return McpErrorCode.REMOTE_5XX
        return McpErrorCode.VALIDATION

    async def debug_token(self, *, access_token: str) -> dict[str, Any]:
        response = await self.request(
            access_token=self.settings.system_user_access_token.get_secret_value()
            if self.settings.system_user_access_token
            else access_token,
            method="GET",
            path=f"/{self.settings.graph_api_version}/debug_token",
            query={
                "input_token": access_token,
                "access_token": f"{self.settings.app_id}|{self.settings.app_secret.get_secret_value()}",
            },
        )
        data = response.json().get("data", {})
        expires_at = None
        if exp := data.get("expires_at"):
            expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
        return {
            "app_id": data.get("app_id"),
            "type": data.get("type"),
            "scopes": data.get("scopes", []),
            "expires_at": expires_at,
            "is_valid": data.get("is_valid", False),
            "user_id": data.get("user_id"),
        }


__all__ = ["MetaGraphApiClient"]
