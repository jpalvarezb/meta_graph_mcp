from __future__ import annotations

import httpx
import pytest

respx = pytest.importorskip("respx")

from meta_mcp.config import get_settings
from meta_mcp.errors import McpErrorCode, MCPException
from meta_mcp.meta_client.client import MetaGraphApiClient


@pytest.mark.asyncio
@respx.mock
async def test_request_retries_on_500(monkeypatch) -> None:
    monkeypatch.setenv("META_MCP_MAX_RETRIES", "1")
    monkeypatch.setenv("META_MCP_GRAPH_API_VERSION", "v1.0")
    get_settings.cache_clear()

    route = respx.get("https://example.com/v1.0/test").mock(
        side_effect=[
            httpx.Response(500, json={"error": {"message": "fail"}}),
            httpx.Response(200, json={"success": True}),
        ]
    )

    client = MetaGraphApiClient()
    response = await client.request(access_token="token", method="GET", path="/v1.0/test")
    await client.aclose()

    assert response.json()["success"] is True
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_request_maps_permission_errors(monkeypatch) -> None:
    monkeypatch.setenv("META_MCP_MAX_RETRIES", "0")
    monkeypatch.setenv("META_MCP_GRAPH_API_VERSION", "v1.0")
    get_settings.cache_clear()

    respx.get("https://example.com/v1.0/test").mock(
        return_value=httpx.Response(
            403,
            json={"error": {"message": "denied", "code": 190}},
        )
    )

    client = MetaGraphApiClient()
    with pytest.raises(MCPException) as exc:
        await client.request(access_token="token", method="GET", path="/v1.0/test")
    await client.aclose()

    assert exc.value.error.code == McpErrorCode.PERMISSION
