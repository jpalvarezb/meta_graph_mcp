"""Example: generate a login URL and exchange a code using the SDK."""

from __future__ import annotations

import asyncio
import os

from mcp_meta_sdk import MetaMcpSdk
from meta_mcp.meta_client import AuthLoginBeginRequest, AuthLoginCompleteRequest


async def main() -> None:
    base_url = os.getenv("META_MCP_BASE_URL", "http://localhost:8000")
    scope_env = os.getenv("META_MCP_LOGIN_SCOPES", "pages_manage_posts,pages_read_engagement")
    scopes = [scope.strip() for scope in scope_env.split(",") if scope.strip()]

    async with MetaMcpSdk(base_url=base_url) as sdk:
        begin = await sdk.auth_login_begin(AuthLoginBeginRequest(scopes=scopes))
        print("Login URL:", begin.authorization_url)
        print("State:", begin.state)
        # In a real app, redirect the user to begin.authorization_url and capture the 'code'.
        code = os.environ.get("META_MCP_LOGIN_CODE")
        if not code:
            print("Set META_MCP_LOGIN_CODE with the authorization code to complete the flow.")
            return
        complete = await sdk.auth_login_complete(
            AuthLoginCompleteRequest(code=code, expected_state=begin.state)
        )
        print("Access token:", complete.access_token)
        print("Scopes:", complete.scopes)


if __name__ == "__main__":
    asyncio.run(main())
