"""Token inspection, scope enforcement, and posting guardrails."""

from __future__ import annotations

import asyncio
import hashlib
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import MCPException, McpError, McpErrorCode
from ..logging import get_logger
from ..storage import Token, TokenType, session_scope
from .client import MetaGraphApiClient

logger = get_logger(__name__)

REQUIRED_PPCA_SCOPE = "page_public_content_access"
IG_BUSINESS_SCOPE = "instagram_basic"
IG_PUBLISH_CAP = 25


@dataclass(slots=True)
class TokenMetadata:
    token_hash: str
    type: TokenType
    subject_id: str
    scopes: list[str]
    app_id: str
    issued_at: datetime
    expires_at: datetime | None
    metadata: dict[str, object]

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) >= self.expires_at


class TokenService:
    """Manages token inspection and authorization checks."""

    def __init__(self, client: MetaGraphApiClient) -> None:
        self._client = client
        self._lock = asyncio.Lock()
        self._ig_publish_history: defaultdict[str, deque[datetime]] = defaultdict(deque)

    async def ensure_permissions(
        self,
        *,
        access_token: str,
        required_scopes: Sequence[str],
        require_ppca: bool = False,
        token_hint: TokenType | None = None,
    ) -> TokenMetadata:
        metadata = await self.inspect_token(access_token=access_token, token_hint=token_hint)
        missing = [scope for scope in required_scopes if scope not in metadata.scopes]
        if missing:
            raise MCPException(
                McpError(
                    code=McpErrorCode.PERMISSION,
                    message="Access token missing required scopes",
                    details={"missing_scopes": missing},
                )
            )

        if require_ppca and REQUIRED_PPCA_SCOPE not in metadata.scopes:
            raise MCPException(
                McpError(
                    code=McpErrorCode.PERMISSION,
                    message="PPCA scope required for this operation",
                    details={"required_scope": REQUIRED_PPCA_SCOPE},
                )
            )

        if metadata.is_expired:
            raise MCPException(
                McpError(
                    code=McpErrorCode.AUTH,
                    message="Access token expired",
                    details={"expires_at": metadata.expires_at.isoformat() if metadata.expires_at else None},
                )
            )

        return metadata

    async def inspect_token(
        self,
        *,
        access_token: str,
        token_hint: TokenType | None = None,
    ) -> TokenMetadata:
        token_hash = self._hash_token(access_token)

        async with session_scope() as session:
            row = await session.get(Token, token_hash)
            if row and not self._needs_refresh(row):
                logger.debug("token_cache_hit", token_hash=token_hash, type=row.type.value)
                return self._row_to_metadata(row)

        async with self._lock:
            async with session_scope() as session:
                # Re-check inside lock
                row = await session.get(Token, token_hash)
                if row and not self._needs_refresh(row):
                    return self._row_to_metadata(row)

                logger.info("debug_token_lookup", token_hash=token_hash)
                debug_info = await self._client.debug_token(access_token=access_token)
                if not debug_info.get("is_valid", False):
                    raise MCPException(
                        McpError(
                            code=McpErrorCode.AUTH,
                            message="Invalid access token",
                            details={"fbtrace_id": debug_info.get("fbtrace_id")},
                        )
                    )

                scopes = sorted(set(debug_info.get("scopes") or []))
                expires_at = debug_info.get("expires_at")
                if isinstance(expires_at, datetime):
                    expiry = expires_at
                elif isinstance(expires_at, (int, float)):
                    expiry = datetime.fromtimestamp(float(expires_at), tz=timezone.utc)
                else:
                    expiry = None

                raw_type = (debug_info.get("type") or "user").upper()
                token_type = self._map_type(raw_type, token_hint)

                stored_metadata = {
                    key: (value.isoformat() if isinstance(value, datetime) else value)
                    for key, value in debug_info.items()
                }
                orm_token = Token(
                    id=token_hash,
                    type=token_type,
                    subject_id=str(debug_info.get("user_id") or debug_info.get("profile_id") or "unknown"),
                    scopes=scopes,
                    app_id=str(debug_info.get("app_id") or ""),
                    issued_at=datetime.now(timezone.utc),
                    expires_at=expiry,
                    raw_metadata=stored_metadata,
                )
                await self._upsert(session=session, token=orm_token)
                return self._row_to_metadata(orm_token)

    async def ensure_instagram_business(self, metadata: TokenMetadata) -> None:
        if IG_BUSINESS_SCOPE not in metadata.scopes:
            raise MCPException(
                McpError(
                    code=McpErrorCode.PERMISSION,
                    message="Instagram Business scope required",
                    details={"required_scope": IG_BUSINESS_SCOPE},
                )
            )

    async def assert_ig_publish_allowed(self, *, ig_user_id: str) -> None:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=24)
        history = self._ig_publish_history[ig_user_id]
        while history and history[0] < window_start:
            history.popleft()
        if len(history) >= IG_PUBLISH_CAP:
            raise MCPException(
                McpError(
                    code=McpErrorCode.RATE_LIMIT,
                    message="IG publish limit reached for 24h window",
                    details={"ig_user_id": ig_user_id, "limit": IG_PUBLISH_CAP},
                    retry_after=24 * 3600,
                )
            )
        history.append(now)

    async def record_ig_publish(self, *, ig_user_id: str) -> None:
        await self.assert_ig_publish_allowed(ig_user_id=ig_user_id)

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def _needs_refresh(self, token: Token) -> bool:
        if token.expires_at is None:
            return False
        return token.expires_at <= datetime.now(timezone.utc) + timedelta(minutes=5)

    def _row_to_metadata(self, row: Token) -> TokenMetadata:
        return TokenMetadata(
            token_hash=row.id,
            type=row.type,
            subject_id=row.subject_id,
            scopes=list(row.scopes),
            app_id=row.app_id,
            issued_at=row.issued_at,
            expires_at=row.expires_at,
            metadata=dict(row.raw_metadata or {}),
        )

    async def _upsert(self, *, session: AsyncSession, token: Token) -> None:
        existing = await session.get(Token, token.id)
        if existing:
            existing.type = token.type
            existing.subject_id = token.subject_id
            existing.scopes = token.scopes
            existing.app_id = token.app_id
            existing.issued_at = token.issued_at
            existing.expires_at = token.expires_at
            existing.raw_metadata = token.raw_metadata
        else:
            session.add(token)

    def _map_type(self, raw_type: str, token_hint: TokenType | None) -> TokenType:
        mapping = {
            "PAGE": TokenType.PAGE,
            "IG_USER": TokenType.INSTAGRAM,
            "INSTAGRAM": TokenType.INSTAGRAM,
            "BUSINESS": TokenType.SYSTEM_USER,
            "USER": TokenType.SYSTEM_USER,
            "ADACCOUNT": TokenType.AD_ACCOUNT,
            "AD_ACCOUNT": TokenType.AD_ACCOUNT,
            "SYSTEM_USER": TokenType.SYSTEM_USER,
        }
        if token_hint:
            return token_hint
        if raw_type in mapping:
            return mapping[raw_type]
        return TokenType.SYSTEM_USER


async def ensure_required_scopes(
    *,
    token_service: TokenService,
    access_token: str,
    scopes: Iterable[str],
    require_ppca: bool = False,
    token_hint: TokenType | None = None,
) -> TokenMetadata:
    return await token_service.ensure_permissions(
        access_token=access_token,
        required_scopes=list(scopes),
        require_ppca=require_ppca,
        token_hint=token_hint,
    )


__all__ = ["TokenService", "TokenMetadata", "ensure_required_scopes"]
