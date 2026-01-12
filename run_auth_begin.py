import asyncio
import os
from mcp_meta_sdk import MetaMcpSdk
from meta_mcp.meta_client import AuthLoginBeginRequest

async def main():
    base_url = "http://localhost:8000"
    # We don't have a token yet, so we don't pass one.
    # The auth.login.begin endpoint should be public or not require a Meta token yet.
    async with MetaMcpSdk(base_url=base_url) as sdk:
        print("Calling auth.login.begin...")
        # Scopes are now optional/defaulted in the server, so we can omit them or pass None
        request = AuthLoginBeginRequest(scopes=None) 
        response = await sdk.auth_login_begin(request)
        print(f"Authorization URL: {response.authorization_url}")
        print(f"State: {response.state}")

if __name__ == "__main__":
    asyncio.run(main())
