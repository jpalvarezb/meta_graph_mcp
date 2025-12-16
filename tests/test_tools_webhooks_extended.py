import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request

from meta_mcp.config import get_settings
from meta_mcp.mcp_tools.common import ToolEnvironment
from meta_mcp.mcp_tools.webhooks import register
from meta_mcp.storage.queue import WebhookEventQueue


def create_request(method="GET", query_params=None, headers=None, body=b""):
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}
    
    scope = {
        "type": "http",
        "method": method,
        "query_string": b"" if not query_params else "&".join([f"{k}={v}" for k,v in query_params.items()]).encode(),
        "headers": [(k.lower().encode(), v.encode()) for k,v in (headers or {}).items()],
    }
    return Request(scope, receive)

@pytest.fixture
def tool_env():
    settings = get_settings()
    settings.verify_token = "my_token"
    settings.app_secret.get_secret_value = lambda: "my_secret"
    
    event_queue = AsyncMock(spec=WebhookEventQueue)
    
    env = MagicMock(spec=ToolEnvironment)
    env.settings = settings
    env.event_queue = event_queue
    return env

@pytest.fixture
def webhook_handlers(tool_env):
    server = MagicMock()
    handlers = {}
    
    def route_decorator(path, methods=None, name=None):
        def wrapper(func):
            handlers[name] = func
            return func
        return wrapper
        
    server.custom_route.side_effect = route_decorator
    register(server, tool_env)
    return handlers

@pytest.mark.asyncio
async def test_webhook_verify_success(webhook_handlers):
    verify = webhook_handlers["meta_webhook_verify"]
    req = create_request(
        method="GET",
        query_params={
            "hub.mode": "subscribe",
            "hub.verify_token": "my_token",
            "hub.challenge": "12345"
        }
    )
    resp = await verify(req)
    assert resp.status_code == 200
    assert resp.body == b"12345"

@pytest.mark.asyncio
async def test_webhook_verify_fail(webhook_handlers):
    verify = webhook_handlers["meta_webhook_verify"]
    req = create_request(
        method="GET",
        query_params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "12345"
        }
    )
    resp = await verify(req)
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_webhook_handle_success(webhook_handlers, tool_env):
    handle = webhook_handlers["meta_webhook_handler"]
    
    payload = {
        "entry": [
            {
                "time": 1234567890,
                "changes": [
                    {"field": "feed", "value": {"item": "post", "verb": "add"}}
                ]
            }
        ]
    }
    body = json.dumps(payload).encode()
    
    # Calculate signature
    secret = b"my_secret"
    sig = hmac.new(secret, body, hashlib.sha256).hexdigest()
    
    req = create_request(
        method="POST",
        headers={"X-Hub-Signature-256": f"sha256={sig}"},
        body=body
    )
    
    resp = await handle(req)
    assert resp.status_code == 200
    
    # Verify event recorded
    assert tool_env.event_queue.record_delivery.called

@pytest.mark.asyncio
async def test_webhook_handle_invalid_sig(webhook_handlers):
    handle = webhook_handlers["meta_webhook_handler"]
    req = create_request(
        method="POST",
        headers={"X-Hub-Signature-256": "sha256=invalid"},
        body=b"{}"
    )
    resp = await handle(req)
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_webhook_handle_invalid_json(webhook_handlers):
    handle = webhook_handlers["meta_webhook_handler"]
    
    body = b"not json"
    secret = b"my_secret"
    sig = hmac.new(secret, body, hashlib.sha256).hexdigest()
    
    req = create_request(
        method="POST",
        headers={"X-Hub-Signature-256": f"sha256={sig}"},
        body=body
    )
    
    resp = await handle(req)
    assert resp.status_code == 400
