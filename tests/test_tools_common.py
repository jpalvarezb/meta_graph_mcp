from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from meta_mcp.errors import MCPException
from meta_mcp.mcp_tools.common import (
    ToolEnvironment,
    compute_idempotency_key,
    datetime_to_timestamp,
    ensure_scopes,
    extract_meta,
    perform_graph_call,
    resolve_access_token,
)


def test_compute_idempotency_key():
    key1 = compute_idempotency_key(method="POST", path="/me/feed", payload={"message": "hello"})
    key2 = compute_idempotency_key(method="POST", path="/me/feed", payload={"message": "hello"})
    key3 = compute_idempotency_key(method="POST", path="/me/feed", payload={"message": "world"})
    
    assert key1 == key2
    assert key1 != key3

def test_datetime_to_timestamp():
    assert datetime_to_timestamp(None) is None
    dt = datetime(2023, 1, 1, 12, 0, 0)
    assert datetime_to_timestamp(dt) == int(dt.timestamp())

def test_extract_meta():
    headers = {
        "x-app-usage": "10%",
        "other-header": "value",
        "fbtrace_id": "trace123"
    }
    meta = extract_meta(headers)
    assert meta["x-app-usage"] == "10%"
    assert meta["fbtrace_id"] == "trace123"
    assert "other-header" not in meta

def test_resolve_access_token_provided():
    ctx = MagicMock()
    token = resolve_access_token(ctx, provided="token123")
    assert token == "token123"

def test_resolve_access_token_from_meta():
    ctx = MagicMock()
    # Mock request_context.meta as a dict-like object
    ctx.request_context.meta = {"access_token": "meta_token"}
    token = resolve_access_token(ctx)
    assert token == "meta_token"

def test_resolve_access_token_from_meta_model():
    ctx = MagicMock()
    # Mock request_context.meta as a Pydantic-like model
    meta_mock = MagicMock()
    meta_mock.model_dump.return_value = {"accessToken": "model_token"}
    ctx.request_context.meta = meta_mock
    token = resolve_access_token(ctx)
    assert token == "model_token"

def test_resolve_access_token_from_args():
    ctx = MagicMock()
    ctx.request_context.meta = {}
    ctx.request_context.request.params.arguments = {"access_token": "arg_token"}
    token = resolve_access_token(ctx)
    assert token == "arg_token"

def test_resolve_access_token_system_user():
    ctx = MagicMock()
    # Fix: Ensure request_context is not None, but has empty/None attributes
    ctx.request_context = MagicMock()
    ctx.request_context.meta = None
    ctx.request_context.request = None
    
    settings = MagicMock()
    settings.system_user_access_token.get_secret_value.return_value = "system_token"
    token = resolve_access_token(ctx, settings=settings)
    assert token == "system_token"

def test_resolve_access_token_missing():
    ctx = MagicMock()
    ctx.request_context = MagicMock()
    ctx.request_context.meta = None
    ctx.request_context.request = None
    
    settings = MagicMock()
    settings.system_user_access_token = None
    with pytest.raises(MCPException):
        resolve_access_token(ctx, settings=settings)

@pytest.mark.asyncio
async def test_ensure_scopes():
    env = MagicMock(spec=ToolEnvironment)
    env.settings = MagicMock()
    env.token_service = AsyncMock()
    env.token_service.ensure_permissions.return_value = Mock(subject_id="123", type=Mock(value="page"))
    
    ctx = MagicMock()
    ctx.request_context.meta = {"access_token": "token123"}
    
    token, metadata = await ensure_scopes(env=env, ctx=ctx, required_scopes=["scope1"])
    
    assert token == "token123"
    assert metadata.subject_id == "123"
    env.token_service.ensure_permissions.assert_awaited_once()

@pytest.mark.asyncio
async def test_perform_graph_call_success():
    env = MagicMock(spec=ToolEnvironment)
    env.settings = MagicMock()
    env.token_service = AsyncMock()
    metadata_mock = Mock(subject_id="123", type=Mock(value="page"))
    env.token_service.ensure_permissions.return_value = metadata_mock
    
    env.client = AsyncMock()
    response_mock = MagicMock()
    response_mock.status_code = 200
    response_mock.headers = {"x-app-usage": "5%"}
    response_mock.json.return_value = {"id": "456"}
    env.client.request.return_value = response_mock
    
    ctx = MagicMock()
    ctx.request_context.meta = {"access_token": "token123"}
    
    result = await perform_graph_call(
        env=env,
        ctx=ctx,
        method="POST",
        path="/me/feed",
        query=None,
        body={"message": "hello"},
        required_scopes=["publish"],
    )
    
    assert result["ok"] is True
    assert result["data"]["data"] == {"id": "456"}
    assert result["meta"]["x-app-usage"] == "5%"
    assert result["meta"]["token_subject_id"] == "123"
    
    env.client.request.assert_awaited_once()
    call_args = env.client.request.await_args
    assert call_args.kwargs["json_body"] == {"message": "hello"}
    assert call_args.kwargs["method"] == "POST"

@pytest.mark.asyncio
async def test_perform_graph_call_idempotency():
    env = MagicMock(spec=ToolEnvironment)
    env.settings = MagicMock()
    env.token_service = AsyncMock()
    env.token_service.ensure_permissions.return_value = Mock(subject_id="123", type=Mock(value="page"))
    
    env.client = AsyncMock()
    response_mock = MagicMock()
    response_mock.status_code = 200
    response_mock.headers = {}
    response_mock.json.return_value = {}
    env.client.request.return_value = response_mock
    
    ctx = MagicMock()
    ctx.request_context.meta = {"access_token": "token123"}
    
    await perform_graph_call(
        env=env,
        ctx=ctx,
        method="POST",
        path="/me/feed",
        query=None,
        body={"message": "hello"},
        required_scopes=["publish"],
        idempotency=True,
    )
    
    call_args = env.client.request.await_args
    assert call_args.kwargs["idempotency_key"] is not None
