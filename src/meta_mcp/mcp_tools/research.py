"""Research and ingestion related tools."""

from __future__ import annotations

from typing import Mapping

from mcp.server.fastmcp import Context, FastMCP

from ..errors import MCPException
from ..meta_client import (
    AdLibraryByPage,
    AdLibrarySearch,
    ResearchObjectReactions,
    ResearchPublicIgMediaCommentsList,
    ResearchPublicIgMediaList,
    ResearchPublicPagesPostCommentsList,
    ResearchPublicPagesPostsList,
)
from ..storage import TokenType
from .common import ToolEnvironment, datetime_to_timestamp, failure, perform_graph_call

PAGE_RESEARCH_SCOPES = (
    "pages_read_engagement",
    "pages_read_user_content",
    "pages_read_insights",
    "pages_manage_engagement",
    "pages_manage_posts",
    "pages_manage_metadata",
)

IG_RESEARCH_SCOPES = (
    "instagram_basic",
    "instagram_manage_insights",
    "instagram_manage_comments",
    "pages_show_list",
    "business_management",
)

ADS_LIBRARY_SCOPES = (
    "ads_read",
    "business_management",
)


def register(server: FastMCP, env: ToolEnvironment) -> None:
    """Register research tools."""

    version = env.settings.graph_api_version

    @server.tool(name="research.public_pages.posts.list", structured_output=True)
    async def public_pages_posts(args: ResearchPublicPagesPostsList, ctx: Context) -> Mapping[str, object]:
        try:
            query = {
                "since": datetime_to_timestamp(args.since),
                "until": datetime_to_timestamp(args.until),
                "after": args.after,
                "limit": args.limit,
            }
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="GET",
                path=f"/{version}/{args.page_id}/posts",
                query=query,
                body=None,
                required_scopes=PAGE_RESEARCH_SCOPES,
                require_ppca=True,
                token_hint=TokenType.PAGE,
                use_cache=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="research.public_pages.post_comments.list", structured_output=True)
    async def public_pages_comments(args: ResearchPublicPagesPostCommentsList, ctx: Context) -> Mapping[str, object]:
        try:
            query = {
                "after": args.after,
                "limit": args.limit,
            }
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="GET",
                path=f"/{version}/{args.post_id}/comments",
                query=query,
                body=None,
                required_scopes=PAGE_RESEARCH_SCOPES,
                require_ppca=True,
                token_hint=TokenType.PAGE,
                use_cache=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="research.public_ig.media.list", structured_output=True)
    async def public_ig_media(args: ResearchPublicIgMediaList, ctx: Context) -> Mapping[str, object]:
        try:
            query = {
                "after": args.after,
                "limit": args.limit,
            }
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="GET",
                path=f"/{version}/{args.ig_user_id}/media",
                query=query,
                body=None,
                required_scopes=IG_RESEARCH_SCOPES,
                token_hint=TokenType.INSTAGRAM,
                use_cache=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="research.public_ig.media_comments.list", structured_output=True)
    async def public_ig_media_comments(args: ResearchPublicIgMediaCommentsList, ctx: Context) -> Mapping[str, object]:
        try:
            query = {
                "after": args.after,
                "limit": args.limit,
            }
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="GET",
                path=f"/{version}/{args.ig_media_id}/comments",
                query=query,
                body=None,
                required_scopes=IG_RESEARCH_SCOPES,
                token_hint=TokenType.INSTAGRAM,
                use_cache=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="research.object.reactions", structured_output=True)
    async def object_reactions(args: ResearchObjectReactions, ctx: Context) -> Mapping[str, object]:
        try:
            query = {
                "summary": str(args.summary).lower(),
            }
            path = f"/{version}/{args.object_id}/reactions"
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="GET",
                path=path,
                query=query,
                body=None,
                required_scopes=PAGE_RESEARCH_SCOPES,
                require_ppca=True,
                token_hint=TokenType.PAGE,
                use_cache=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="research.ad_library.search", structured_output=True)
    async def ad_library_search(args: AdLibrarySearch, ctx: Context) -> Mapping[str, object]:
        try:
            query = {
                "ad_type": args.ad_type,
                "search_terms": args.search_terms,
                "ad_reached_countries": ",".join(args.ad_reached_countries),
                "search_page_ids": ",".join(args.search_page_ids) if args.search_page_ids else None,
                "fields": ",".join(args.fields),
                "limit": args.limit,
                "after": args.after,
            }
            path = f"/{version}/ads_archive"
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="GET",
                path=path,
                query=query,
                body=None,
                required_scopes=ADS_LIBRARY_SCOPES,
                token_hint=TokenType.AD_ACCOUNT,
                use_cache=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="research.ad_library.by_page", structured_output=True)
    async def ad_library_by_page(args: AdLibraryByPage, ctx: Context) -> Mapping[str, object]:
        try:
            query = {
                "ad_type": args.ad_type,
                "ad_reached_countries": ",".join(args.ad_reached_countries),
                "search_page_ids": ",".join(args.page_ids),
                "fields": ",".join(args.fields),
                "limit": args.limit,
                "after": args.after,
            }
            path = f"/{version}/ads_archive"
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="GET",
                path=path,
                query=query,
                body=None,
                required_scopes=ADS_LIBRARY_SCOPES,
                token_hint=TokenType.AD_ACCOUNT,
                use_cache=True,
            )
        except MCPException as exc:
            return failure(exc.error)


__all__ = ["register"]
