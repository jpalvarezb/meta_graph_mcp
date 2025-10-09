"""Example: create + publish an Instagram image via the SDK helper."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from mcp_meta_sdk import MetaMcpSdk


async def main() -> None:
    base_url = os.getenv("META_MCP_BASE_URL", "http://localhost:8000")
    access_token = os.environ["META_MCP_ACCESS_TOKEN"]
    ig_user_id = os.environ["META_MCP_IG_USER_ID"]
    image_url = os.environ["META_MCP_IMAGE_URL"]
    caption = os.getenv("META_MCP_IMAGE_CAPTION")

    async with MetaMcpSdk(base_url=base_url, access_token=access_token) as sdk:
        result: dict[str, Any] = await sdk.publish_ig_image(
            ig_user_id=ig_user_id,
            image_url=image_url,
            caption=caption,
        )
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
