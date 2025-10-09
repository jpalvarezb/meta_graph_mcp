"""Webhook ingestion endpoint."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from ..logging import get_logger
from .common import ToolEnvironment

logger = get_logger(__name__)


def register(server: FastMCP, env: ToolEnvironment) -> None:
    secret = env.settings.app_secret.get_secret_value()
    verify_token = env.settings.verify_token

    @server.custom_route("/webhooks/meta", methods=["GET"], name="meta_webhook_verify")
    async def verify(request: Request) -> Response:  # pragma: no cover - exercised via integration tests
        params = request.query_params
        mode = params.get("hub.mode")
        token = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")
        if mode == "subscribe" and token == verify_token and challenge:
            logger.info("webhook_verified")
            return PlainTextResponse(challenge)
        logger.warning("webhook_verification_failed", mode=mode, token=token)
        return JSONResponse({"ok": False, "reason": "verification_failed"}, status_code=403)

    @server.custom_route("/webhooks/meta", methods=["POST"], name="meta_webhook_handler")
    async def handle(request: Request) -> Response:
        raw_body = await request.body()
        if not _validate_signature(request.headers, raw_body, secret):
            logger.error("webhook_signature_invalid")
            return JSONResponse({"ok": False, "reason": "invalid_signature"}, status_code=403)

        try:
            payload = json.loads(raw_body.decode())
        except json.JSONDecodeError:
            logger.error("webhook_invalid_json")
            return JSONResponse({"ok": False, "reason": "invalid_json"}, status_code=400)

        entries = payload.get("entry", [])
        normalized_count = 0
        for entry in entries:
            topic = entry.get("object", "unknown")
            delivered_at = datetime.fromtimestamp(entry.get("time", datetime.now(timezone.utc).timestamp()), tz=timezone.utc)
            for change in entry.get("changes", []) or []:
                object_id = change.get("value", {}).get("id") or entry.get("id", "unknown")
                event_payload = {
                    "topic": topic,
                    "object_id": object_id,
                    "change": change,
                }
                await env.event_queue.record_delivery(
                    topic=topic,
                    object_id=str(object_id),
                    payload=event_payload,
                    delivered_at=delivered_at,
                )
                normalized_count += 1

        logger.info("webhook_ingested", entries=len(entries), normalized=normalized_count)
        return JSONResponse({"ok": True, "ingested": normalized_count})


def _validate_signature(headers: Any, body: bytes, secret: str) -> bool:
    signature = headers.get("X-Hub-Signature-256") or headers.get("X-Hub-Signature")
    if not signature:
        return False
    try:
        scheme, value = signature.split("=", 1)
    except ValueError:
        return False
    scheme = scheme.lower()
    if scheme not in {"sha1", "sha256"}:
        return False
    digestmod = hashlib.sha1 if scheme == "sha1" else hashlib.sha256
    expected = hmac.new(secret.encode(), body, digestmod).hexdigest()
    return hmac.compare_digest(expected, value)


__all__ = ["register"]
