from __future__ import annotations

import hmac
from datetime import datetime, timezone

import pytest

from meta_mcp.errors import MCPException
from meta_mcp.mcp_tools.webhooks import _validate_signature
from meta_mcp.storage.queue import WebhookEventQueue


def test_validate_signature() -> None:
    secret = "secret"
    body = b"payload"
    digest = hmac.new(secret.encode(), body, "sha256").hexdigest()
    headers = {"X-Hub-Signature-256": f"sha256={digest}"}
    assert _validate_signature(headers, body, secret)
    assert not _validate_signature({}, body, secret)


@pytest.mark.asyncio
async def test_webhook_queue_roundtrip() -> None:
    queue = WebhookEventQueue()
    await queue.record_delivery(
        topic="feed",
        object_id="123",
        payload={"foo": "bar"},
        delivered_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    events = await queue.dequeue(maximum=10)
    assert events
    assert events[0]["topic"] == "feed"
    assert events[0]["object_id"] == "123"
    assert "processed_at" in events[0]


@pytest.mark.asyncio
async def test_webhook_queue_invalid_max() -> None:
    queue = WebhookEventQueue()
    with pytest.raises(MCPException):
        await queue.dequeue(maximum=0)
