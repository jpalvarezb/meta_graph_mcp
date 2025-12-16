from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import Response

from meta_mcp.config import get_settings
from meta_mcp.mcp_tools.common import ToolEnvironment
from meta_mcp.mcp_tools.publish import (
    IgCarouselPublish,
    IgMediaPublish,
    PagesPostsPublish,
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
    metadata_mock.type.value = "page"
    token_service.ensure_permissions.return_value = metadata_mock
    # Mock assertion check
    token_service.assert_ig_publish_allowed.return_value = None
    
    event_queue = MagicMock(spec=WebhookEventQueue)
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
async def test_pages_posts_publish(registered_tools, ctx, respx_mock):
    route = respx_mock.post("https://example.com/v18.0/page_123/feed").mock(
        return_value=Response(200, json={"id": "post_123"})
    )
    
    func = registered_tools["pages.posts.publish"]
    args = PagesPostsPublish(
        page_id="page_123",
        message="Hello world",
        link="https://example.com/",
        published=True
    )
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert result["data"]["data"]["id"] == "post_123"
    
    import json
    req = route.calls.last.request
    body = json.loads(req.content)
    assert body["message"] == "Hello world"
    assert body["link"] == "https://example.com/"

@pytest.mark.asyncio
async def test_ig_media_publish(registered_tools, ctx, respx_mock):
    route = respx_mock.post("https://example.com/v18.0/ig_user_123/media_publish").mock(
        return_value=Response(200, json={"id": "pub_123"})
    )
    
    func = registered_tools["ig.media.publish"]
    args = IgMediaPublish(ig_user_id="ig_user_123", creation_id="create_123")
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert result["data"]["data"]["id"] == "pub_123"
    
    import json
    req = route.calls.last.request
    body = json.loads(req.content)
    assert body["creation_id"] == "create_123"

@pytest.mark.asyncio
async def test_ig_carousel_publish(registered_tools, ctx, respx_mock):
    route = respx_mock.post("https://example.com/v18.0/ig_user_123/media_publish").mock(
        return_value=Response(200, json={"id": "pub_123"})
    )
    
    func = registered_tools["ig.carousel.publish"]
    args = IgCarouselPublish(ig_user_id="ig_user_123", creation_id="create_123")
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert result["data"]["data"]["id"] == "pub_123"

@pytest.mark.asyncio
async def test_publish_error(registered_tools, ctx, respx_mock):
    respx_mock.post("https://example.com/v18.0/page_123/feed").mock(
        return_value=Response(429, json={"error": {"message": "Rate Limit"}})
    )
    
    func = registered_tools["pages.posts.publish"]
    args = PagesPostsPublish(page_id="page_123", message="hi")
    
    result = await func(args, ctx)
    assert result["ok"] is False
    assert result["error"]["code"] == "RATE_LIMIT"
