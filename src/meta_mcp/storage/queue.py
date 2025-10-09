"""Webhook event queue backed by SQLite."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import McpError, McpErrorCode, MCPException
from .db import session_scope
from .models import WebhookEvent


class WebhookEventQueue:
    """Persist webhook deliveries and surface them to MCP tools."""

    async def record_delivery(
        self,
        *,
        topic: str,
        object_id: str,
        payload: dict[str, Any],
        delivered_at: datetime | None = None,
    ) -> None:
        delivered = delivered_at or datetime.now(timezone.utc)
        async with session_scope() as session:
            session.add(
                WebhookEvent(
                    topic=topic,
                    object_id=object_id,
                    payload=payload,
                    delivered_at=delivered,
                )
            )

    async def dequeue(self, *, maximum: int = 50) -> list[dict[str, Any]]:
        if maximum <= 0:
            raise MCPException(
                McpError(
                    code=McpErrorCode.VALIDATION,
                    message="maximum must be greater than zero",
                    details={"maximum": maximum},
                )
            )

        async with session_scope() as session:
            rows = await self._fetch_unprocessed(session=session, maximum=maximum)
            events: list[dict[str, Any]] = []
            now = datetime.now(timezone.utc)
            for row in rows:
                row.processed_at = now
                events.append(
                    {
                        "id": row.id,
                        "topic": row.topic,
                        "object_id": row.object_id,
                        "payload": row.payload,
                        "delivered_at": row.delivered_at.isoformat(),
                        "processed_at": now.isoformat(),
                    }
                )
        return events

    async def _fetch_unprocessed(
        self, *, session: AsyncSession, maximum: int
    ) -> list[WebhookEvent]:
        stmt = (
            select(WebhookEvent)
            .where(WebhookEvent.processed_at.is_(None))
            .order_by(WebhookEvent.delivered_at.asc())
            .limit(maximum)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


__all__ = ["WebhookEventQueue"]
