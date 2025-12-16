from __future__ import annotations

import pytest

from meta_mcp.errors import McpErrorCode, MCPException
from meta_mcp.meta_client.auth import TokenService
from meta_mcp.storage import TokenType


class StubMetaClient:
    def __init__(self, *, scopes: list[str]) -> None:
        self.scopes = scopes
        self.calls = 0

    async def debug_token(self, *, access_token: str) -> dict[str, object]:
        self.calls += 1
        return {
            "app_id": "123",
            "type": "PAGE",
            "scopes": self.scopes,
            "expires_at": None,
            "is_valid": True,
            "user_id": "user",
        }


@pytest.mark.asyncio
async def test_token_service_caches_token() -> None:
    client = StubMetaClient(scopes=["pages_read_engagement"])
    service = TokenService(client)  # type: ignore[arg-type]
    await service.ensure_permissions(
        access_token="token",
        required_scopes=["pages_read_engagement"],
        token_hint=TokenType.PAGE,
    )
    await service.ensure_permissions(
        access_token="token",
        required_scopes=["pages_read_engagement"],
        token_hint=TokenType.PAGE,
    )
    assert client.calls == 1


@pytest.mark.asyncio
async def test_token_service_missing_scope_raises() -> None:
    client = StubMetaClient(scopes=["pages_read_engagement"])
    service = TokenService(client)  # type: ignore[arg-type]
    with pytest.raises(MCPException) as exc:
        await service.ensure_permissions(
            access_token="token",
            required_scopes=["pages_manage_posts"],
            token_hint=TokenType.PAGE,
        )
    assert exc.value.error.code == McpErrorCode.PERMISSION


@pytest.mark.asyncio
async def test_ig_publish_cap() -> None:
    client = StubMetaClient(scopes=["instagram_basic", "instagram_content_publish"])
    service = TokenService(client)  # type: ignore[arg-type]
    await service.ensure_permissions(
        access_token="ig-token",
        required_scopes=["instagram_basic"],
        token_hint=TokenType.INSTAGRAM,
    )
    for _ in range(25):
        await service.assert_ig_publish_allowed(ig_user_id="ig")
    with pytest.raises(MCPException) as exc:
        await service.assert_ig_publish_allowed(ig_user_id="ig")
    assert exc.value.error.code == McpErrorCode.RATE_LIMIT
