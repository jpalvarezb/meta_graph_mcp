from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import Response

from meta_mcp.config import get_settings
from meta_mcp.mcp_tools.common import ToolEnvironment
from meta_mcp.mcp_tools.research import (
    AdLibrarySearch,
    ResearchObjectReactions,
    ResearchPublicIgMediaList,
    ResearchPublicPagesPostCommentsList,
    ResearchPublicPagesPostsList,
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
async def test_public_pages_posts(registered_tools, ctx, respx_mock):
    route = respx_mock.get("https://example.com/v18.0/page_123/posts").mock(
        return_value=Response(200, json={"data": [{"id": "post_1"}]})
    )
    
    func = registered_tools["research.public_pages.posts.list"]
    args = ResearchPublicPagesPostsList(
        page_id="page_123",
        limit=5,
        since=datetime(2023, 1, 1),
        until=datetime(2023, 1, 31)
    )
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert result["data"]["data"]["data"][0]["id"] == "post_1"
    
    req = route.calls.last.request
    assert req.url.params["limit"] == "5"
    assert "since" in req.url.params
    assert "until" in req.url.params

@pytest.mark.asyncio
async def test_public_pages_comments(registered_tools, ctx, respx_mock):
    route = respx_mock.get("https://example.com/v18.0/post_123/comments").mock(
        return_value=Response(200, json={"data": [{"id": "comment_1"}]})
    )
    
    func = registered_tools["research.public_pages.post_comments.list"]
    args = ResearchPublicPagesPostCommentsList(post_id="post_123", limit=10)
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert result["data"]["data"]["data"][0]["id"] == "comment_1"

@pytest.mark.asyncio
async def test_public_ig_media(registered_tools, ctx, respx_mock):
    route = respx_mock.get("https://example.com/v18.0/ig_user_123/media").mock(
        return_value=Response(200, json={"data": [{"id": "media_1"}]})
    )
    
    func = registered_tools["research.public_ig.media.list"]
    args = ResearchPublicIgMediaList(ig_user_id="ig_user_123", limit=10)
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert result["data"]["data"]["data"][0]["id"] == "media_1"

@pytest.mark.asyncio
async def test_object_reactions(registered_tools, ctx, respx_mock):
    route = respx_mock.get("https://example.com/v18.0/obj_123/reactions").mock(
        return_value=Response(200, json={"data": []})
    )
    
    func = registered_tools["research.object.reactions"]
    args = ResearchObjectReactions(object_id="obj_123", summary=True)
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert req.url.params.get("summary") == "true" if (req := route.calls.last.request) else True

@pytest.mark.asyncio
async def test_ad_library_search(registered_tools, ctx, respx_mock):
    route = respx_mock.get("https://example.com/v18.0/ads_archive").mock(
        return_value=Response(200, json={"data": [{"id": "ad_1"}]})
    )
    
    func = registered_tools["research.ad_library.search"]
    args = AdLibrarySearch(
        ad_type="POLITICAL_AND_ISSUE_ADS",
        search_terms="vote",
        ad_reached_countries=["US"], fields=["id", "page_name"],
        limit=10
    )
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert result["data"]["data"]["data"][0]["id"] == "ad_1"
    
    req = route.calls.last.request
    assert req.url.params["search_terms"] == "vote"
    assert req.url.params["ad_type"] == "POLITICAL_AND_ISSUE_ADS"

@pytest.mark.asyncio
async def test_research_error(registered_tools, ctx, respx_mock):
    respx_mock.get("https://example.com/v18.0/page_123/posts").mock(
        return_value=Response(403, json={"error": {"message": "Forbidden", "code": 190}})
    )
    
    func = registered_tools["research.public_pages.posts.list"]
    args = ResearchPublicPagesPostsList(page_id="page_123")
    
    result = await func(args, ctx)
    assert result["ok"] is False
    assert result["error"]["code"] == "PERMISSION"
