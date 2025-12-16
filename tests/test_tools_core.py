from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import Response

from meta_mcp.config import get_settings
from meta_mcp.mcp_tools.common import ToolEnvironment
from meta_mcp.mcp_tools.core import (
    EventsDequeueRequest,
    GraphRequestInput,
    PermissionsCheckRequest,
    register,
)
from meta_mcp.meta_client import MetaGraphApiClient, TokenService
from meta_mcp.storage.queue import WebhookEventQueue


@pytest.fixture
async def tool_env():
    settings = get_settings()
    client = MetaGraphApiClient()
    token_service = AsyncMock(spec=TokenService)
    metadata_mock = MagicMock()
    metadata_mock.subject_id = "123"
    metadata_mock.app_id = "app_1"
    metadata_mock.type.value = "page"
    metadata_mock.scopes = ["public_profile"]
    metadata_mock.expires_at = datetime(2025, 1, 1)
    metadata_mock.is_expired = False
    metadata_mock.token_hash = "hash"
    token_service.ensure_permissions.return_value = metadata_mock
    
    event_queue = AsyncMock(spec=WebhookEventQueue)
    event_queue.dequeue.return_value = [{"id": "evt_1"}]
    
    return ToolEnvironment(
        settings=settings,
        client=client,
        token_service=token_service,
        event_queue=event_queue,
    )

@pytest.fixture
def registered_tools(tool_env):
    server = MagicMock()
    tools = {}
    def tool_decorator(name=None, **kwargs):
        def wrapper(func):
            tools[name] = func
            return func
        return wrapper
    server.tool.side_effect = tool_decorator
    register(server, tool_env)
    return tools

@pytest.fixture
def ctx():
    c = MagicMock()
    c.request_context.meta = {"access_token": "token123"}
    return c

@pytest.mark.asyncio
async def test_graph_request(registered_tools, ctx, respx_mock):
    route = respx_mock.get("https://example.com/v18.0/me").mock(
        return_value=Response(200, json={"id": "123"})
    )
    
    func = registered_tools["graph.request"]
    args = GraphRequestInput(method="GET", path="/v18.0/me")
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert result["data"]["data"]["id"] == "123"

@pytest.mark.asyncio
async def test_permissions_check(registered_tools, ctx):
    func = registered_tools["auth.permissions.check"]
    args = PermissionsCheckRequest(access_token="token123")
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert result["data"]["app_id"] == "app_1"
    assert result["data"]["valid"] is True

@pytest.mark.asyncio
async def test_events_dequeue(registered_tools, ctx):
    func = registered_tools["events.dequeue"]
    args = EventsDequeueRequest(max=10)
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert result["data"]["events"][0]["id"] == "evt_1"
