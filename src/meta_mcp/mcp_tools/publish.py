"""Publishing tools for pages and Instagram."""

from __future__ import annotations

from typing import Mapping

from mcp.server.fastmcp import Context, FastMCP

from ..errors import MCPException
from ..meta_client import IgCarouselPublish, IgMediaPublish, PagesPostsPublish
from ..storage import TokenType
from .common import ToolEnvironment, ensure_scopes, failure, perform_graph_call

PAGE_PUBLISH_SCOPES = (
    "pages_manage_posts",
    "pages_manage_engagement",
    "pages_manage_metadata",
)

IG_PUBLISH_SCOPES = (
    "instagram_basic",
    "instagram_content_publish",
    "pages_show_list",
    "business_management",
)


def register(server: FastMCP, env: ToolEnvironment) -> None:
    version = env.settings.graph_api_version

    @server.tool(name="pages.posts.publish", structured_output=True, description="Publish a text post (status update) or link to a Facebook Page.")
    async def pages_posts_publish(args: PagesPostsPublish, ctx: Context) -> Mapping[str, object]:
        try:
            body = {
                "message": args.message,
                "link": str(args.link) if args.link else None,
                "attached_media": args.attached_media,
                "published": args.published,
                "scheduled_publish_time": int(args.scheduled_publish_time.timestamp())
                if args.scheduled_publish_time
                else None,
            }
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="POST",
                path=f"/{version}/{args.page_id}/feed",
                query=None,
                body=body,
                form=None,
                files=None,
                required_scopes=PAGE_PUBLISH_SCOPES,
                token_hint=TokenType.PAGE,
                idempotency=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="ig.media.publish", structured_output=True, description="Publish an Instagram media container.")
    async def ig_media_publish(args: IgMediaPublish, ctx: Context) -> Mapping[str, object]:
        try:
            access_token, metadata = await ensure_scopes(
                env=env,
                ctx=ctx,
                required_scopes=IG_PUBLISH_SCOPES,
                token_hint=TokenType.INSTAGRAM,
            )
            await env.token_service.assert_ig_publish_allowed(ig_user_id=args.ig_user_id)
            body = {"creation_id": args.creation_id}
            response = await perform_graph_call(
                env=env,
                ctx=ctx,
                method="POST",
                path=f"/{version}/{args.ig_user_id}/media_publish",
                query=None,
                body=body,
                form=None,
                files=None,
                required_scopes=IG_PUBLISH_SCOPES,
                token_hint=TokenType.INSTAGRAM,
                idempotency=True,
                provided_token=access_token,
            )
            return response
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="ig.carousel.publish", structured_output=True, description="Publish an Instagram carousel container.")
    async def ig_carousel_publish(args: IgCarouselPublish, ctx: Context) -> Mapping[str, object]:
        try:
            access_token, _metadata = await ensure_scopes(
                env=env,
                ctx=ctx,
                required_scopes=IG_PUBLISH_SCOPES,
                token_hint=TokenType.INSTAGRAM,
            )
            await env.token_service.assert_ig_publish_allowed(ig_user_id=args.ig_user_id)
            body = {"creation_id": args.creation_id}
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="POST",
                path=f"/{version}/{args.ig_user_id}/media_publish",
                query=None,
                body=body,
                form=None,
                files=None,
                required_scopes=IG_PUBLISH_SCOPES,
                token_hint=TokenType.INSTAGRAM,
                idempotency=True,
                provided_token=access_token,
            )
        except MCPException as exc:
            return failure(exc.error)


__all__ = ["register"]
