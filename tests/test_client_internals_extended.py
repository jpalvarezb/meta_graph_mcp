from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from meta_mcp.errors import MCPException
from meta_mcp.meta_client.client import MetaGraphApiClient


@pytest.fixture
async def client():
    c = MetaGraphApiClient()
    yield c
    await c.aclose()

@pytest.mark.asyncio
async def test_batch_validation(client):
    with pytest.raises(MCPException):
        await client.batch(access_token="tok", operations=[{}] * 51)

@pytest.mark.asyncio
async def test_cache_hit(client):
    # Enable cache
    client.settings.cache_maxsize = 100
    from cachetools import LRUCache
    client._cache = LRUCache(maxsize=100)
    
    key = client._cache_key(method="GET", path="/me", query=None, json_body=None)
    client._cache[key] = {"status": 200, "headers": {}, "json": {"cached": True}}
    
    resp = await client.request(access_token="tok", method="GET", path="/me", use_cache=True)
    assert resp.json()["cached"] is True

@pytest.mark.asyncio
async def test_retry_after_parsing_error(client):
    # Mock _respect_retry_after calling sleep
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        resp = MagicMock()
        resp.headers = {"Retry-After": "invalid"}
        await client._respect_retry_after(resp)
        mock_sleep.assert_awaited_with(0.0)

@pytest.mark.asyncio
async def test_map_error_complex(client):
    resp = MagicMock()
    resp.status_code = 400
    resp.headers = {}
    resp.json.return_value = {
        "error": {
            "message": "msg",
            "type": "OAuthException",
            "code": 100,
            "error_subcode": 33,
            "fbtrace_id": "trace",
            "error_user_title": "Title",
            "error_user_msg": "User Msg"
        }
    }
    
    exc = client._map_error(resp)
    details = exc.error.details
    assert details["type"] == "OAuthException"
    assert details["code"] == 100
    assert details["error_subcode"] == 33
    assert details["user_title"] == "Title"
    assert details["user_message"] == "User Msg"
