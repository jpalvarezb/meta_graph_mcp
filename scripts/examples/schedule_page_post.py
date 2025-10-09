"""Example: schedule a Facebook Page post via the SDK helper."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any

from mcp_meta_sdk import MetaMcpSdk


async def main() -> None:
    base_url = os.getenv("META_MCP_BASE_URL", "http://localhost:8000")
    access_token = os.environ["META_MCP_ACCESS_TOKEN"]
    page_id = os.environ["META_MCP_PAGE_ID"]
    message = os.environ.get("META_MCP_POST_MESSAGE", "Scheduled post from Meta MCP")
    link = os.getenv("META_MCP_POST_LINK")
    schedule_iso = os.environ.get("META_MCP_POST_TIME", (datetime.now(timezone.utc).isoformat()))
    schedule_time = datetime.fromisoformat(schedule_iso)

    async with MetaMcpSdk(base_url=base_url, access_token=access_token) as sdk:
        result: dict[str, Any] = await sdk.schedule_page_post(
            page_id=page_id,
            message=message,
            schedule_time=schedule_time,
            link=link,
        )
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
