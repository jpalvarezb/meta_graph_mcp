"""Shared helpers for MCP tools."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from mcp.server.fastmcp import Context

from ..auth import MetaOAuthClient, generate_state
from ..config import MetaMcpSettings
from ..errors import MCPException, McpError, McpErrorCode, error_response
from ..logging import get_logger
from ..meta_client import MetaGraphApiClient, TokenMetadata, TokenService
from ..storage import TokenType
from ..storage.queue import WebhookEventQueue

logger = get_logger(__name__)

USAGE_HEADER_KEYS = [
    "x-app-usage",
    "x-business-use-case-usage",
    "x-ad-account-usage",
    "fbtrace_id",
]


@dataclass(slots=True)
class ToolEnvironment:
    settings: MetaMcpSettings
    client: MetaGraphApiClient
    token_service: TokenService
    event_queue: WebhookEventQueue


def success(data: Any, *, meta: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    return {
        "ok": True,
        "data": data,
        "meta": dict(meta or {}),
    }


def failure(error: McpError, *, meta: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    return error_response(error, meta=meta)


def extract_meta(response_headers: Mapping[str, Any]) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    for key in USAGE_HEADER_KEYS:
        value = response_headers.get(key)
        if value:
            meta[key] = value
    return meta


def datetime_to_timestamp(value: datetime | None) -> int | None:
    if value is None:
        return None
    return int(value.timestamp())


def compute_idempotency_key(*, method: str, path: str, payload: Mapping[str, Any] | None) -> str:
    raw = json.dumps(
        {
            "method": method,
            "path": path,
            "payload": payload or {},
        },
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def resolve_access_token(ctx: Context, *, provided: str | None = None, settings: MetaMcpSettings | None = None) -> str:
    if provided:
        return provided

    meta = ctx.request_context.meta if ctx.request_context else None  # type: ignore[truthy-function]
    if meta is not None:
        meta_dict = getattr(meta, "model_dump", None)
        if callable(meta_dict):
            meta_payload = meta_dict(mode="json")
        else:
            meta_payload = dict(meta) if isinstance(meta, Mapping) else {}
        for key in ("access_token", "accessToken", "authorization"):
            token = meta_payload.get(key)
            if isinstance(token, str) and token:
                return token

    request = ctx.request_context.request
    if request is not None:
        arguments = getattr(request.params, "arguments", None)
        if isinstance(arguments, Mapping):
            for key in ("access_token", "accessToken"):
                token = arguments.get(key)
                if isinstance(token, str) and token:
                    return token

    if settings and settings.system_user_access_token:
        return settings.system_user_access_token.get_secret_value()

    raise MCPException(
        McpError(
            code=McpErrorCode.AUTH,
            message="Access token required in arguments meta or server configuration",
        )
    )


async def ensure_scopes(
    *,
    env: ToolEnvironment,
    ctx: Context,
    required_scopes: Sequence[str],
    require_ppca: bool = False,
    token_hint: TokenType | None = None,
    provided_token: str | None = None,
) -> tuple[str, TokenMetadata]:
    import traceback
    access_token: str | None = None
    
    # First, try to resolve from request context or env
    try:
        access_token = resolve_access_token(ctx, provided=provided_token, settings=env.settings)
    except MCPException:
        # Token not found in context/env, try session token from DB
        try:
            access_token = await env.token_service.get_session_token_for_scopes(
                required_scopes=list(required_scopes)
            )
        except Exception as e:
            logger.error("error_getting_session_token", error=str(e), traceback=traceback.format_exc())
            raise
    
    if not access_token:
        # No token available anywhere, generate auth URL for user
        oauth_client = MetaOAuthClient(env.settings)
        state = generate_state(16)
        redirect_uri = str(env.settings.oauth_redirect_uri)
        url = oauth_client.build_authorization_url(
            scopes=list(required_scopes),
            redirect_uri=redirect_uri,
            state=state,
        )
        raise MCPException(
            McpError(
                code=McpErrorCode.AUTH,
                message=f"Authentication required. Please login at: {url}",
                details={
                    "authorization_url": url,
                    "state": state,
                    "instructions": "1. Open the URL. 2. Authorize the app. 3. Copy the 'code' from the redirect. 4. Use 'auth.login.complete' with the code."
                },
            )
        )

    metadata = await env.token_service.ensure_permissions(
        access_token=access_token,
        required_scopes=list(required_scopes),
        require_ppca=require_ppca,
        token_hint=token_hint,
    )
    return access_token, metadata


async def perform_graph_call(
    *,
    env: ToolEnvironment,
    ctx: Context,
    method: str,
    path: str,
    query: dict[str, Any] | None,
    body: dict[str, Any] | None,
    form: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    required_scopes: Sequence[str],
    require_ppca: bool = False,
    token_hint: TokenType | None = None,
    use_cache: bool = False,
    idempotency: bool = False,
    provided_token: str | None = None,
) -> Mapping[str, Any]:
    access_token, metadata = await ensure_scopes(
        env=env,
        ctx=ctx,
        required_scopes=required_scopes,
        require_ppca=require_ppca,
        token_hint=token_hint,
        provided_token=provided_token,
    )
    if body is not None:
        body = {k: v for k, v in body.items() if v is not None}
    if form is not None:
        form = {k: v for k, v in form.items() if v is not None}
    idempotency_key = None
    if idempotency:
        idempotency_key = compute_idempotency_key(method=method, path=path, payload=body or {})

    response = await env.client.request(
        access_token=access_token,
        method=method,
        path=path,
        query=query,
        json_body=body,
        form_body=form,
        files=files,
        idempotency_key=idempotency_key,
        use_cache=use_cache,
    )

    response_meta = extract_meta(response.headers)
    response_meta["token_subject_id"] = metadata.subject_id
    response_meta["token_type"] = metadata.type.value

    payload = {
        "status": response.status_code,
        "headers": dict(response.headers),
    }
    try:
        payload['data'] = response.json()
    except ValueError:
        payload['data'] = response.content.decode(errors='ignore')
    return success(payload, meta=response_meta)


__all__ = [
    "ToolEnvironment",
    "success",
    "failure",
    "perform_graph_call",
    "ensure_scopes",
    "resolve_access_token",
    "extract_meta",
    "compute_idempotency_key",
    "datetime_to_timestamp",
]
