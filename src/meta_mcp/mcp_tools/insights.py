"""Insights and analytics tools."""

from __future__ import annotations

from typing import Mapping

from mcp.server.fastmcp import Context, FastMCP

from ..errors import MCPException
from ..meta_client import (
    InsightsAdsAccount,
    InsightsIgAccount,
    InsightsIgMedia,
    InsightsPageAccount,
)
from ..storage import TokenType
from .common import ToolEnvironment, failure, perform_graph_call

PAGE_INSIGHTS_SCOPES = (
    "pages_read_engagement",
    "pages_read_insights",
    "pages_manage_metadata",
)

IG_INSIGHTS_SCOPES = (
    "instagram_basic",
    "instagram_manage_insights",
    "pages_show_list",
    "business_management",
)

ADS_INSIGHTS_SCOPES = (
    "ads_read",
    "business_management",
)


def register(server: FastMCP, env: ToolEnvironment) -> None:
    version = env.settings.graph_api_version

    @server.tool(name="insights.page.account", structured_output=True, description="Get insights/metrics for a Facebook Page.")
    async def page_account_insights(args: InsightsPageAccount, ctx: Context) -> Mapping[str, object]:
        try:
            query = {
                "metric": ",".join(args.metrics),
                "period": args.period,
                "since": int(args.since.timestamp()) if args.since else None,
                "until": int(args.until.timestamp()) if args.until else None,
            }
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="GET",
                path=f"/{version}/{args.page_id}/insights",
                query=query,
                body=None,
                required_scopes=PAGE_INSIGHTS_SCOPES,
                token_hint=TokenType.PAGE,
                use_cache=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="insights.ig.account", structured_output=True, description="Get insights/metrics for an Instagram Business Account.")
    async def ig_account_insights(args: InsightsIgAccount, ctx: Context) -> Mapping[str, object]:
        try:
            query = {
                "metric": ",".join(args.metrics),
                "period": args.period,
                "breakdowns": ",".join(args.breakdowns) if args.breakdowns else None,
            }
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="GET",
                path=f"/{version}/{args.ig_user_id}/insights",
                query=query,
                body=None,
                required_scopes=IG_INSIGHTS_SCOPES,
                token_hint=TokenType.INSTAGRAM,
                use_cache=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="insights.ig.media", structured_output=True, description="Get insights/metrics for a specific Instagram media object.")
    async def ig_media_insights(args: InsightsIgMedia, ctx: Context) -> Mapping[str, object]:
        try:
            query = {
                "metric": ",".join(args.metrics),
            }
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="GET",
                path=f"/{version}/{args.ig_media_id}/insights",
                query=query,
                body=None,
                required_scopes=IG_INSIGHTS_SCOPES,
                token_hint=TokenType.INSTAGRAM,
                use_cache=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="insights.ads.account", structured_output=True, description="Get insights/metrics for an ad account.")
    async def ads_account_insights(args: InsightsAdsAccount, ctx: Context) -> Mapping[str, object]:
        try:
            query = {
                "fields": ",".join(args.fields),
                "level": args.level,
                "time_range": args.time_range,
                "breakdowns": ",".join(args.breakdowns) if args.breakdowns else None,
                "filtering": args.filtering,
                "limit": args.limit,
                "after": args.after,
            }
            path = f"/{version}/act_{args.ad_account_id}/insights"
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="GET",
                path=path,
                query=query,
                body=None,
                required_scopes=ADS_INSIGHTS_SCOPES,
                token_hint=TokenType.AD_ACCOUNT,
                use_cache=True,
            )
        except MCPException as exc:
            return failure(exc.error)


__all__ = ["register"]
