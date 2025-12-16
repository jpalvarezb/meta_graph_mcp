from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import Response

from meta_mcp.config import get_settings
from meta_mcp.mcp_tools.common import ToolEnvironment
from meta_mcp.mcp_tools.insights import (
    InsightsAdsAccount,
    InsightsIgAccount,
    InsightsIgMedia,
    InsightsPageAccount,
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
async def test_page_account_insights(registered_tools, ctx, respx_mock):
    route = respx_mock.get("https://example.com/v18.0/page_123/insights").mock(
        return_value=Response(200, json={"data": [{"name": "page_impressions"}]})
    )
    
    func = registered_tools["insights.page.account"]
    args = InsightsPageAccount(
        page_id="page_123",
        metrics=["page_impressions", "page_fans"],
        period="day"
    )
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert result["data"]["data"]["data"][0]["name"] == "page_impressions"
    
    req = route.calls.last.request
    assert req.url.params["metric"] == "page_impressions,page_fans"
    assert req.url.params["period"] == "day"

@pytest.mark.asyncio
async def test_ig_account_insights(registered_tools, ctx, respx_mock):
    route = respx_mock.get("https://example.com/v18.0/ig_user_123/insights").mock(
        return_value=Response(200, json={"data": [{"name": "impressions"}]})
    )
    
    func = registered_tools["insights.ig.account"]
    args = InsightsIgAccount(
        ig_user_id="ig_user_123",
        metrics=["impressions"],
        period="day"
    )
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert result["data"]["data"]["data"][0]["name"] == "impressions"

@pytest.mark.asyncio
async def test_ig_media_insights(registered_tools, ctx, respx_mock):
    route = respx_mock.get("https://example.com/v18.0/media_123/insights").mock(
        return_value=Response(200, json={"data": [{"name": "engagement"}]})
    )
    
    func = registered_tools["insights.ig.media"]
    args = InsightsIgMedia(
        ig_media_id="media_123",
        metrics=["engagement"]
    )
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert result["data"]["data"]["data"][0]["name"] == "engagement"

@pytest.mark.asyncio
async def test_ads_account_insights(registered_tools, ctx, respx_mock):
    route = respx_mock.get("https://example.com/v18.0/act_act_123/insights").mock(
        return_value=Response(200, json={"data": [{"spend": "100"}]})
    )
    
    func = registered_tools["insights.ads.account"]
    args = InsightsAdsAccount(
        ad_account_id="act_123",
        fields=["spend", "impressions"],
        level="campaign",
        time_range={"since": "2023-01-01", "until": "2023-01-31"}
    )
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert result["data"]["data"]["data"][0]["spend"] == "100"
    
    # Check how time_range was serialized. Httpx might have exploded it or not.
    # We verify that 'fields' is correct at least.
    req = route.calls.last.request
    assert req.url.params["fields"] == "spend,impressions"
    assert req.url.params["level"] == "campaign"
