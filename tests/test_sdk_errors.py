from typing import Any

import pytest
from mcp import types

from mcp_meta_sdk import MetaMcpSdk, ToolExecutionError, ToolResponseError


class ErrorSession:
    def __init__(self, mode="ok"):
        self.mode = mode

    async def call_tool(self, name: str, arguments: dict | None = None, **_: Any) -> types.CallToolResult:
        if self.mode == "no_content":
            return types.CallToolResult(content=[], structuredContent=None, isError=False)
        if self.mode == "error_response":
            return types.CallToolResult(content=[], structuredContent={"ok": False, "error": {"code": "ERR"}, "meta": {}}, isError=False)
        if self.mode == "success_false":
            return types.CallToolResult(content=[], structuredContent={"ok": False, "meta": {}}, isError=False)
        return types.CallToolResult(content=[], structuredContent={"ok": True, "data": {}, "meta": {}}, isError=False)

@pytest.mark.asyncio
async def test_sdk_no_content():
    sdk = MetaMcpSdk(base_url="http://localhost")
    sdk._session = ErrorSession("no_content")
    with pytest.raises(ToolResponseError, match="returned no structured content"):
        await sdk.call_tool_raw("test")

@pytest.mark.asyncio
async def test_sdk_error_response():
    sdk = MetaMcpSdk(base_url="http://localhost")
    sdk._session = ErrorSession("error_response")
    with pytest.raises(ToolExecutionError) as exc:
        await sdk.call_tool_raw("test")
    assert exc.value.code == "ERR"

@pytest.mark.asyncio
async def test_sdk_success_false():
    sdk = MetaMcpSdk(base_url="http://localhost")
    sdk._session = ErrorSession("success_false")
    with pytest.raises(ToolExecutionError):
        await sdk.call_tool_raw("test")

@pytest.mark.asyncio
async def test_sdk_normalize_arguments():
    sdk = MetaMcpSdk(base_url="http://localhost")
    assert sdk._normalize_arguments(None) is None
    assert sdk._normalize_arguments({"a": 1}) == {"a": 1}
    
    from pydantic import BaseModel
    class M(BaseModel):
        x: int
    assert sdk._normalize_arguments(M(x=1)) == {"x": 1}
    
    with pytest.raises(TypeError):
        sdk._normalize_arguments("invalid")
