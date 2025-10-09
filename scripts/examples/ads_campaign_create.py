"""Example: create a Campaign → AdSet → Creative → Ad stack."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from mcp_meta_sdk import MetaMcpSdk
from meta_mcp.meta_client import (
    AdsAdsCreate,
    AdsAdsetCreate,
    AdsCampaignCreate,
    AdsCreativeCreate,
)


def _loads_env(key: str, default: str) -> dict[str, Any]:
    return json.loads(os.environ.get(key, default))


async def main() -> None:
    base_url = os.getenv("META_MCP_BASE_URL", "http://localhost:8000")
    access_token = os.environ["META_MCP_ACCESS_TOKEN"]
    ad_account_id = os.environ["META_MCP_AD_ACCOUNT_ID"]

    campaign = AdsCampaignCreate(
        ad_account_id=ad_account_id,
        name=os.environ.get("META_MCP_CAMPAIGN_NAME", "MCP Campaign"),
        objective=os.environ.get("META_MCP_CAMPAIGN_OBJECTIVE", "LINK_CLICKS"),
        status=os.environ.get("META_MCP_CAMPAIGN_STATUS", "PAUSED"),
    )

    default_adset_spec = json.dumps(
        {
            "name": "MCP Ad Set",
            "daily_budget": "1000",
            "billing_event": "IMPRESSIONS",
            "optimization_goal": "LINK_CLICKS",
            "targeting": {
                "geo_locations": {"countries": ["US"]},
            },
        }
    )
    adset = AdsAdsetCreate(
        ad_account_id=ad_account_id,
        spec=_loads_env("META_MCP_ADSET_SPEC", default_adset_spec),
    )

    default_creative = json.dumps(
        {
            "name": "MCP Creative",
            "object_story_spec": {
                "page_id": os.environ.get("META_MCP_PAGE_ID", ""),
                "link_data": {
                    "message": "Check out our offer",
                    "link": os.environ.get("META_MCP_CREATIVE_LINK", "https://www.meta.com"),
                },
            },
        }
    )
    creative = AdsCreativeCreate(
        ad_account_id=ad_account_id,
        creative=_loads_env("META_MCP_CREATIVE", default_creative),
    )

    default_ad_spec = json.dumps(
        {
            "name": "MCP Ad",
            "status": "PAUSED",
        }
    )
    ad = AdsAdsCreate(
        ad_account_id=ad_account_id,
        spec=_loads_env("META_MCP_AD_SPEC", default_ad_spec),
    )

    async with MetaMcpSdk(base_url=base_url, access_token=access_token) as sdk:
        result = await sdk.create_campaign_stack(
            campaign=campaign,
            adset=adset,
            creative=creative,
            ad=ad,
        )
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
