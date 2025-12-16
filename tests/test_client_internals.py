from unittest.mock import AsyncMock

import httpx
import pytest

from meta_mcp.errors import McpErrorCode, MCPException
from meta_mcp.meta_client.client import MetaGraphApiClient


@pytest.fixture
async def client():
    c = MetaGraphApiClient()
    yield c
    await c.aclose()

@pytest.mark.asyncio
async def test_request_success(client, respx_mock):
    respx_mock.get("https://example.com/me").mock(
        return_value=httpx.Response(200, json={"id": "123"}, headers={"x-app-usage": "10%"})
    )
    
    resp = await client.request(access_token="tok", method="GET", path="/me")
    assert resp.status_code == 200
    assert resp.json()["id"] == "123"

@pytest.mark.asyncio
async def test_request_retry_on_500(client, respx_mock):
    # Fail twice with 500, then succeed
    route = respx_mock.get("https://example.com/me")
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(500),
        httpx.Response(200, json={"ok": True})
    ]
    
    # Speed up backoff
    client._backoff.sleep = AsyncMock()
    
    resp = await client.request(access_token="tok", method="GET", path="/me")
    assert resp.status_code == 200
    assert route.call_count == 3

@pytest.mark.asyncio
async def test_request_retry_exhausted(client, respx_mock):
    respx_mock.get("https://example.com/me").mock(
        return_value=httpx.Response(500)
    )
    client._backoff.sleep = AsyncMock()
    
    with pytest.raises(MCPException) as exc:
        await client.request(access_token="tok", method="GET", path="/me")
    
    assert exc.value.error.code == McpErrorCode.REMOTE_5XX

@pytest.mark.asyncio
async def test_request_rate_limit(client, respx_mock):
    # 429 then success
    route = respx_mock.get("https://example.com/me")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "0.1"}),
        httpx.Response(200, json={"ok": True})
    ]
    
    client._backoff.sleep = AsyncMock()
    
    resp = await client.request(access_token="tok", method="GET", path="/me")
    assert resp.status_code == 200
    assert route.call_count == 2

@pytest.mark.asyncio
async def test_error_mapping_auth(client, respx_mock):
    respx_mock.get("https://example.com/me").mock(
        return_value=httpx.Response(401, json={"error": {"message": "Bad token", "code": 190}})
    )
    
    with pytest.raises(MCPException) as exc:
        await client.request(access_token="tok", method="GET", path="/me")
    
    assert exc.value.error.code == McpErrorCode.AUTH

@pytest.mark.asyncio
async def test_error_mapping_permission(client, respx_mock):
    respx_mock.get("https://example.com/me").mock(
        return_value=httpx.Response(403, json={"error": {"message": "No perm", "code": 200}})
    )
    
    with pytest.raises(MCPException) as exc:
        await client.request(access_token="tok", method="GET", path="/me")
    
    assert exc.value.error.code == McpErrorCode.PERMISSION

@pytest.mark.asyncio
async def test_batch_request(client, respx_mock):
    respx_mock.post("https://example.com/v18.0/batch").mock(
        return_value=httpx.Response(200, json=[{"code": 200, "body": "{}"}])
    )
    
    results = await client.batch(access_token="tok", operations=[{"method": "GET", "relative_url": "me"}])
    assert len(results) == 1
    assert results[0]["code"] == 200

@pytest.mark.asyncio
async def test_paginate(client, respx_mock):
    # First page
    respx_mock.get("https://example.com/me/feed").mock(side_effect=[
        httpx.Response(200, json={
            "data": [{"id": "1"}],
            "paging": {"cursors": {"after": "abc"}}
        }),
        httpx.Response(200, json={
            "data": [{"id": "2"}],
            "paging": {}
        })
    ])
    
    items = []
    async for page in client.paginate(access_token="tok", method="GET", path="/me/feed"):
        items.extend(page["data"])
        
    assert len(items) == 2
    assert items[0]["id"] == "1"
    assert items[1]["id"] == "2"

@pytest.mark.asyncio
async def test_debug_token(client, respx_mock):
    respx_mock.get("https://example.com/v18.0/debug_token").mock(
        return_value=httpx.Response(200, json={"data": {"is_valid": True, "app_id": "123"}})
    )
    
    result = await client.debug_token(access_token="tok")
    assert result["is_valid"] is True
    assert result["app_id"] == "123"
