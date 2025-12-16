from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import Response

from meta_mcp.config import get_settings
from meta_mcp.mcp_tools.ads import (
    AdsAdsCreate,
    AdsAdsetCreate,
    AdsAdsetList,
    AdsAdsetUpdate,
    AdsAdsList,
    AdsAdsUpdate,
    AdsCampaignList,
    AdsCampaignUpdate,
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
    token_service.ensure_permissions.return_value = MagicMock(subject_id="123", type=MagicMock(value="ad_account"))
    event_queue = MagicMock(spec=WebhookEventQueue)
    return ToolEnvironment(settings, client, token_service, event_queue)

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
async def test_all_ads_tools_errors(registered_tools, ctx, respx_mock):
    # Mock all to fail
    respx_mock.route().mock(return_value=Response(400, json={"error": {"message": "Fail", "code": 100}}))
    
    tools_args = [
        ("ads.campaigns.list", AdsCampaignList(ad_account_id="1", fields=["name"])),
        ("ads.campaigns.update", AdsCampaignUpdate(campaign_id="1", patch={})),
        ("ads.adsets.create", AdsAdsetCreate(ad_account_id="1", spec={})),
        ("ads.adsets.list", AdsAdsetList(ad_account_id="1", fields=["name"])),
        ("ads.adsets.update", AdsAdsetUpdate(adset_id="1", patch={})),
        ("ads.creatives.create", AdsCreativeCreate(ad_account_id="1", creative={})),
        ("ads.ads.create", AdsAdsCreate(ad_account_id="1", spec={})),
        ("ads.ads.list", AdsAdsList(ad_account_id="1", fields=["name"])),
        ("ads.ads.update", AdsAdsUpdate(ad_id="1", patch={})),
    ]
    
    for name, args in tools_args:
        func = registered_tools[name]
        result = await func(args, ctx)
        assert result["ok"] is False, f"{name} should have failed"
        assert result["error"]["code"] == "VALIDATION"
