"""MCP server bootstrap for Meta Graph + Marketing API."""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from typing import AsyncIterator

from mcp.server.fastmcp import FastMCP

from .config import MetaMcpSettings, get_settings
from .logging import configure_logging
from .meta_client import MetaGraphApiClient
from .meta_client.auth import TokenService
from .mcp_tools import ads, assets, auth_login, core, insights, publish, research, webhooks
from .mcp_tools.common import ToolEnvironment
from .storage.db import init_models
from .storage.queue import WebhookEventQueue

DEFAULT_TRANSPORT = "stdio"


def create_server(settings: MetaMcpSettings | None = None) -> FastMCP:
    settings = settings or get_settings()
    configure_logging()

    client = MetaGraphApiClient()
    token_service = TokenService(client)
    event_queue = WebhookEventQueue()
    environment = ToolEnvironment(
        settings=settings,
        client=client,
        token_service=token_service,
        event_queue=event_queue,
    )

    @asynccontextmanager
    async def lifespan(app: FastMCP) -> AsyncIterator[None]:
        await init_models()
        try:
            yield
        finally:
            await client.aclose()

    server = FastMCP(name="meta-mcp", lifespan=lambda _app: lifespan(_app))

    core.register(server, environment)
    research.register(server, environment)
    insights.register(server, environment)
    assets.register(server, environment)
    publish.register(server, environment)
    auth_login.register(server, environment)
    ads.register(server, environment)
    webhooks.register(server, environment)

    return server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the Meta Graph MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default=DEFAULT_TRANSPORT,
        help="Transport protocol to use",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    args = parser.parse_args(argv)

    server = create_server()
    
    if args.transport == "streamable-http":
        import uvicorn
        # FastMCP exposes the Starlette app via streamable_http_app
        uvicorn.run(server.streamable_http_app, host=args.host, port=args.port)
    elif args.transport == "sse":
        import uvicorn
        uvicorn.run(server.sse_app, host=args.host, port=args.port)
    else:
        server.run(transport="stdio")


if __name__ == "__main__":
    main()


__all__ = ["create_server", "main"]
