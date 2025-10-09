"""Example: query Ad Library by page IDs."""

from __future__ import annotations

import asyncio
import json
import os

from mcp_meta_sdk import MetaMcpSdk
from meta_mcp.meta_client import AdLibraryByPage


async def main() -> None:
    base_url = os.getenv("META_MCP_BASE_URL", "http://localhost:8000")
    access_token = os.environ["META_MCP_ACCESS_TOKEN"]

    page_ids = json.loads(os.environ.get("META_MCP_ADLIB_PAGE_IDS", '["1234567890"]'))
    countries = json.loads(os.environ.get("META_MCP_ADLIB_COUNTRIES", '["US"]'))
    fields = json.loads(os.environ.get("META_MCP_ADLIB_FIELDS", '["ad_creative_body", "ad_delivery_start_time"]'))

    request = AdLibraryByPage(
        page_ids=page_ids,
        ad_type=os.environ.get("META_MCP_ADLIB_TYPE", "POLITICAL_AND_ISSUE_ADS"),
        ad_reached_countries=countries,
        fields=fields,
    )

    async with MetaMcpSdk(base_url=base_url, access_token=access_token) as sdk:
        results = await sdk.ad_library_search_by_pages(request)
        print(results)


if __name__ == "__main__":
    asyncio.run(main())
