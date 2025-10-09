from __future__ import annotations

import httpx
import pytest

respx = pytest.importorskip("respx")

from meta_mcp.auth import MetaOAuthClient
from meta_mcp.config import get_settings
from meta_mcp.meta_client import AuthLoginCompleteRequest
from meta_mcp.meta_client.client import MetaGraphApiClient
from meta_mcp.meta_client.auth import TokenService
from meta_mcp.mcp_tools import auth_login
from meta_mcp.mcp_tools.common import ToolEnvironment
from meta_mcp.storage.queue import WebhookEventQueue


class _StubServer:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, name: str, structured_output: bool = True):  # pragma: no cover - decorator wrapper
        def decorator(fn):
            self.tools[name] = fn
            return fn

        return decorator


@pytest.mark.asyncio
async def test_build_authorization_url_includes_scopes() -> None:
    settings = get_settings()
    client = MetaOAuthClient(settings)
    url = client.build_authorization_url(
        scopes=["pages_manage_posts", "pages_read_engagement"],
        redirect_uri="https://client.example.com/callback",
        state="abc",
    )
    assert "scope=" in url
    assert "pages_manage_posts" in url
    assert url.startswith(f"{settings.facebook_oauth_base_url.rstrip('/')}/{settings.graph_api_version}/dialog/oauth")


@pytest.mark.asyncio
@respx.mock
async def test_login_complete_flow() -> None:
    settings = get_settings()
    server = _StubServer()
    client = MetaGraphApiClient()
    token_service = TokenService(client)
    env = ToolEnvironment(settings=settings, client=client, token_service=token_service, event_queue=WebhookEventQueue())
    auth_login.register(server, env)

    respx.get(f"{settings.graph_api_base_url}/{settings.graph_api_version}/oauth/access_token").mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "token123", "token_type": "bearer", "expires_in": 3600},
        )
    )
    respx.get(f"{settings.graph_api_base_url}/{settings.graph_api_version}/debug_token").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "app_id": "app",
                    "type": "PAGE",
                    "scopes": ["pages_manage_posts"],
                    "is_valid": True,
                    "user_id": "123",
                }
            },
        )
    )

    args = AuthLoginCompleteRequest(code="CODE", redirect_uri=settings.oauth_redirect_uri)
    handler = server.tools["auth.login.complete"]  # type: ignore[index]
    result = await handler(args, None)

    assert result["ok"] is True
    assert result["data"]["access_token"] == "token123"
    assert result["meta"]["token_subject_id"] == "123"

    await client.aclose()
