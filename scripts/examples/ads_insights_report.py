"""Example: fetch Ads insights with breakdowns."""

from __future__ import annotations

import asyncio
import json
import os

from mcp_meta_sdk import MetaMcpSdk
from meta_mcp.meta_client import InsightsAdsAccount


async def main() -> None:
    base_url = os.getenv("META_MCP_BASE_URL", "http://localhost:8000")
    access_token = os.environ["META_MCP_ACCESS_TOKEN"]
    ad_account_id = os.environ["META_MCP_AD_ACCOUNT_ID"]

    fields = json.loads(os.environ.get("META_MCP_INSIGHTS_FIELDS", '["impressions", "spend"]'))
    breakdowns = json.loads(os.environ.get("META_MCP_INSIGHTS_BREAKDOWNS", '["age", "gender"]'))
    time_range = json.loads(os.environ.get("META_MCP_INSIGHTS_RANGE", '{"since": "2024-01-01", "until": "2024-01-31"}'))

    request = InsightsAdsAccount(
        ad_account_id=ad_account_id,
        fields=fields,
        level=os.environ.get("META_MCP_INSIGHTS_LEVEL", "ad"),
        time_range=time_range,
        breakdowns=breakdowns,
    )

    async with MetaMcpSdk(base_url=base_url, access_token=access_token) as sdk:
        report = await sdk.ads_insights_report(request)
        print(report)


if __name__ == "__main__":
    asyncio.run(main())
