from __future__ import annotations

import asyncio
from typing import Any, Callable

import pytest

from meta_mcp.meta_client import GraphRequestInput, AuthLoginBeginRequest, AuthLoginCompleteRequest
from meta_mcp.meta_client.models import ToolResponse
from mcp_meta_sdk import MetaMcpSdk, ToolExecutionError, ToolResponseError
from mcp import types


class DummySession:
    def __init__(self, factory: Callable[[str], dict[str, Any]]) -> None:
        self.factory = factory
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None, **_: Any) -> types.CallToolResult:
        self.calls.append((name, arguments))
        return types.CallToolResult(content=[], structuredContent=self.factory(name), isError=False)


@pytest.mark.asyncio
async def test_sdk_call_tool_raw_normalizes_models(monkeypatch) -> None:
    sdk = MetaMcpSdk(base_url="http://localhost")
    response_payload = {"ok": True, "data": {"result": True}, "meta": {}}
    sdk._session = DummySession(lambda _: response_payload)  # type: ignore[assignment]
    request = GraphRequestInput(method="GET", path="/v18.0/test")
    result = await sdk.call_tool_raw("graph.request", request)
    assert result.data["result"] is True
    assert sdk._session.calls[0][1]["method"] == "GET"  # type: ignore[index]


@pytest.mark.asyncio
async def test_sdk_raises_on_error_response() -> None:
    sdk = MetaMcpSdk(base_url="http://localhost")
    error_payload = {"ok": False, "error": {"code": "AUTH", "message": "nope"}, "meta": {}}
    sdk._session = DummySession(lambda _: error_payload)  # type: ignore[assignment]
    with pytest.raises(ToolExecutionError):
        await sdk.call_tool_raw("graph.request", None)


@pytest.mark.asyncio
async def test_publish_ig_image_requires_creation_id(monkeypatch) -> None:
    sdk = MetaMcpSdk(base_url="http://localhost")

    async def fake_call(name: str, *_args: Any, **_kwargs: Any) -> ToolResponse:
        if name == "ig.media.create":
            return ToolResponse(ok=True, data={"data": {}}, meta={})
        return ToolResponse(ok=True, data={"data": {"id": "published"}}, meta={})

    monkeypatch.setattr(sdk, "call_tool_raw", fake_call)  # type: ignore[arg-type]
    with pytest.raises(ToolResponseError):
        await sdk.publish_ig_image(ig_user_id="123", image_url="https://example.com/img.jpg")


@pytest.mark.asyncio
async def test_sdk_auth_login_methods() -> None:
    begin_payload = {"ok": True, "data": {"authorization_url": "https://example.com/oauth", "state": "state123", "redirect_uri": "https://client.example.com/callback", "scopes": ["pages_manage_posts"]}, "meta": {}}
    complete_payload = {"ok": True, "data": {"access_token": "token123", "token_type": "bearer", "expires_at": "2024-01-01T00:00:00+00:00", "app_id": "app", "subject_id": "sub", "scopes": ["pages_manage_posts"]}, "meta": {}}
    sdk = MetaMcpSdk(base_url="http://localhost")
    sdk._session = DummySession(lambda name: begin_payload if name == "auth.login.begin" else complete_payload)  # type: ignore[assignment]
    begin_response = await sdk.auth_login_begin(AuthLoginBeginRequest(scopes=["pages_manage_posts"]))
    assert str(begin_response.authorization_url) == "https://example.com/oauth"
    complete_response = await sdk.auth_login_complete(AuthLoginCompleteRequest(code="CODE"))
    assert complete_response.access_token == "token123"
