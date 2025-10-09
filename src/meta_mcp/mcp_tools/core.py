"""Core MCP tools including raw Graph requests and auth utilities."""

from __future__ import annotations

from typing import Mapping

from mcp.server.fastmcp import Context, FastMCP

from ..errors import MCPException, McpError, McpErrorCode
from ..logging import get_logger
from ..meta_client import (
    EventsDequeueRequest,
    EventsDequeueResponse,
    GraphRequestInput,
    PermissionsCheckRequest,
    PermissionsCheckResponse,
)
from ..meta_client.models import ToolResponse
from .common import ToolEnvironment, ensure_scopes, failure, perform_graph_call, success

logger = get_logger(__name__)


def register(server: FastMCP, env: ToolEnvironment) -> None:
    """Register core tool handlers."""

    @server.tool(name="graph.request", structured_output=True)
    async def graph_request(args: GraphRequestInput, ctx: Context) -> Mapping[str, object]:
        try:
            use_cache = args.method.upper() == "GET"
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method=args.method,
                path=args.path,
                query=args.query,
                body=args.body,
                required_scopes=[],
                token_hint=None,
                use_cache=use_cache,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="auth.permissions.check", structured_output=True)
    async def permissions_check(args: PermissionsCheckRequest, ctx: Context) -> Mapping[str, object]:
        try:
            access_token, metadata = await ensure_scopes(
                env=env,
                ctx=ctx,
                required_scopes=[],
                token_hint=None,
                provided_token=args.access_token,
            )
            response = PermissionsCheckResponse(
                app_id=metadata.app_id,
                type=metadata.type.value,
                scopes=metadata.scopes,
                expires_at=metadata.expires_at,
                valid=not metadata.is_expired,
            )
            meta = {
                "token_hash": metadata.token_hash,
                "subject_id": metadata.subject_id,
            }
            return success(response.model_dump(mode="json"), meta=meta)
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="events.dequeue", structured_output=True)
    async def events_dequeue(args: EventsDequeueRequest, ctx: Context) -> Mapping[str, object]:
        queue = env.event_queue
        events = await queue.dequeue(maximum=args.max)
        response = EventsDequeueResponse(events=events)
        return success(response.model_dump(mode="json"))


__all__ = ["register"]
