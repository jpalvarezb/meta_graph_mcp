from datetime import UTC
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import Response

from meta_mcp.config import get_settings
from meta_mcp.mcp_tools.ads import (
    AdsAdsCreate,
    AdsAdsetCreate,
    AdsCampaignCreate,
    AdsCampaignList,
    AdsCreativeCreate,
    register,
)
from meta_mcp.mcp_tools.common import ToolEnvironment
from meta_mcp.meta_client import MetaGraphApiClient, TokenService
from meta_mcp.storage.queue import WebhookEventQueue


@pytest.fixture
async def tool_env():
    settings = get_settings()
    client = MetaGraphApiClient()
    token_service = AsyncMock(spec=TokenService)
    metadata_mock = MagicMock()
    metadata_mock.subject_id = "123"
    metadata_mock.type.value = "ad_account"
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
async def test_campaigns_create(registered_tools, ctx, respx_mock):
    route = respx_mock.post("https://example.com/v18.0/act_act_123/campaigns").mock(
        return_value=Response(200, json={"id": "camp_123"})
    )
    
    func = registered_tools["ads.campaigns.create"]
    args = AdsCampaignCreate(
        ad_account_id="act_123",
        name="New Campaign",
        objective="OUTCOME_TRAFFIC",
        status="PAUSED"
    )
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert result["data"]["data"]["id"] == "camp_123"
    
    req = route.calls.last.request
    assert b"OUTCOME_TRAFFIC" in req.content

@pytest.mark.asyncio
async def test_campaigns_list(registered_tools, ctx, respx_mock):
    route = respx_mock.get("https://example.com/v18.0/act_act_123/campaigns").mock(
        return_value=Response(200, json={"data": [{"id": "camp_1"}]})
    )
    
    func = registered_tools["ads.campaigns.list"]
    args = AdsCampaignList(ad_account_id="act_123", fields=["name", "status"], limit=5)
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert result["data"]["data"]["data"][0]["id"] == "camp_1"
    
    req = route.calls.last.request
    assert req.url.params["limit"] == "5"
    assert req.url.params["fields"] == "name,status"

@pytest.mark.asyncio
async def test_adsets_create(registered_tools, ctx, respx_mock):
    route = respx_mock.post("https://example.com/v18.0/act_act_123/adsets").mock(
        return_value=Response(200, json={"id": "adset_123"})
    )
    
    func = registered_tools["ads.adsets.create"]
    args = AdsAdsetCreate(
        ad_account_id="act_123",
        spec={"campaign_id": "camp_123", "name": "AdSet 1"}
    )
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert result["data"]["data"]["id"] == "adset_123"

@pytest.mark.asyncio
async def test_creatives_create(registered_tools, ctx, respx_mock):
    route = respx_mock.post("https://example.com/v18.0/act_act_123/adcreatives").mock(
        return_value=Response(200, json={"id": "creative_123"})
    )
    
    func = registered_tools["ads.creatives.create"]
    args = AdsCreativeCreate(
        ad_account_id="act_123",
        creative={"name": "Creative 1"}
    )
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert result["data"]["data"]["id"] == "creative_123"

@pytest.mark.asyncio
async def test_ads_create(registered_tools, ctx, respx_mock):
    route = respx_mock.post("https://example.com/v18.0/act_act_123/ads").mock(
        return_value=Response(200, json={"id": "ad_123"})
    )
    
    func = registered_tools["ads.ads.create"]
    args = AdsAdsCreate(
        ad_account_id="act_123",
        spec={"adset_id": "adset_123", "creative": {"creative_id": "creative_123"}, "name": "Ad 1"}
    )
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert result["data"]["data"]["id"] == "ad_123"

@pytest.mark.asyncio
async def test_campaigns_update(registered_tools, ctx, respx_mock):
    route = respx_mock.post("https://example.com/v18.0/camp_123").mock(
        return_value=Response(200, json={"success": True})
    )
    
    func = registered_tools["ads.campaigns.update"]
    from meta_mcp.mcp_tools.ads import AdsCampaignUpdate
    args = AdsCampaignUpdate(campaign_id="camp_123", patch={"status": "ACTIVE"})
    
    result = await func(args, ctx)
    assert result["ok"] is True
    
    req = route.calls.last.request
    assert b"ACTIVE" in req.content

@pytest.mark.asyncio
async def test_adsets_list(registered_tools, ctx, respx_mock):
    route = respx_mock.get("https://example.com/v18.0/act_act_123/adsets").mock(
        return_value=Response(200, json={"data": [{"id": "adset_1"}]})
    )
    
    func = registered_tools["ads.adsets.list"]
    from meta_mcp.mcp_tools.ads import AdsAdsetList
    args = AdsAdsetList(ad_account_id="act_123", fields=["name"], limit=5)
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert result["data"]["data"]["data"][0]["id"] == "adset_1"

@pytest.mark.asyncio
async def test_adsets_update(registered_tools, ctx, respx_mock):
    route = respx_mock.post("https://example.com/v18.0/adset_123").mock(
        return_value=Response(200, json={"success": True})
    )
    
    func = registered_tools["ads.adsets.update"]
    from meta_mcp.mcp_tools.ads import AdsAdsetUpdate
    args = AdsAdsetUpdate(adset_id="adset_123", patch={"name": "New Name"})
    
    result = await func(args, ctx)
    assert result["ok"] is True

@pytest.mark.asyncio
async def test_ads_list(registered_tools, ctx, respx_mock):
    route = respx_mock.get("https://example.com/v18.0/act_act_123/ads").mock(
        return_value=Response(200, json={"data": [{"id": "ad_1"}]})
    )
    
    func = registered_tools["ads.ads.list"]
    from meta_mcp.mcp_tools.ads import AdsAdsList
    args = AdsAdsList(ad_account_id="act_123", fields=["name"], limit=5)
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert result["data"]["data"]["data"][0]["id"] == "ad_1"

@pytest.mark.asyncio
async def test_ads_update(registered_tools, ctx, respx_mock):
    route = respx_mock.post("https://example.com/v18.0/ad_123").mock(
        return_value=Response(200, json={"success": True})
    )
    
    func = registered_tools["ads.ads.update"]
    from meta_mcp.mcp_tools.ads import AdsAdsUpdate
    args = AdsAdsUpdate(ad_id="ad_123", patch={"name": "New Name"})
    
    result = await func(args, ctx)
    assert result["ok"] is True

@pytest.mark.asyncio
async def test_calendar_note_put(registered_tools, ctx, tool_env):
    # This uses DB, not Graph API
    func = registered_tools["ads.calendar.note.put"]
    from datetime import datetime

    from meta_mcp.mcp_tools.ads import AdsCalendarNotePut
    args = AdsCalendarNotePut(
        idempotency_key="key1",
        subject="Meeting",
        when=datetime(2023, 1, 1, tzinfo=UTC),
        related_ids=["1", "2"]
    )
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert result["data"]["idempotency_key"] == "key1"

@pytest.mark.asyncio
async def test_campaigns_create_error(registered_tools, ctx, respx_mock):
    respx_mock.post("https://example.com/v18.0/act_act_123/campaigns").mock(
        return_value=Response(500, json={"error": {"message": "Server Error"}})
    )
    
    func = registered_tools["ads.campaigns.create"]
    args = AdsCampaignCreate(ad_account_id="act_123", name="n", objective="o", status="s")
    
    result = await func(args, ctx)
    assert result["ok"] is False
    assert result["error"]["code"] == "REMOTE_5XX"
