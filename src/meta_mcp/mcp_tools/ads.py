"""Marketing API (Ads) tools."""

from __future__ import annotations

from typing import Mapping

from mcp.server.fastmcp import Context, FastMCP

from ..errors import MCPException
from ..meta_client import (
    AdsAdsCreate,
    AdsAdsList,
    AdsAdsUpdate,
    AdsAdsetCreate,
    AdsAdsetList,
    AdsAdsetUpdate,
    AdsCalendarNotePut,
    AdsCampaignCreate,
    AdsCampaignList,
    AdsCampaignUpdate,
    AdsCreativeCreate,
)
from ..storage import CalendarNote, TokenType, session_scope
from .common import ToolEnvironment, failure, perform_graph_call

ADS_MANAGEMENT_SCOPES = (
    "ads_management",
    "ads_read",
    "business_management",
)


def register(server: FastMCP, env: ToolEnvironment) -> None:
    version = env.settings.marketing_api_version or env.settings.graph_api_version

    @server.tool(name="ads.campaigns.create", structured_output=True, description="Create a new ad campaign.")
    async def campaigns_create(args: AdsCampaignCreate, ctx: Context) -> Mapping[str, object]:
        try:
            body = {
                "name": args.name,
                "objective": args.objective,
                "status": args.status,
            }
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="POST",
                path=f"/{version}/act_{args.ad_account_id}/campaigns",
                query=None,
                body=body,
                form=None,
                files=None,
                required_scopes=ADS_MANAGEMENT_SCOPES,
                token_hint=TokenType.AD_ACCOUNT,
                idempotency=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="ads.campaigns.list", structured_output=True, description="List ad campaigns for an ad account.")
    async def campaigns_list(args: AdsCampaignList, ctx: Context) -> Mapping[str, object]:
        try:
            query = {
                "fields": ",".join(args.fields),
                "limit": args.limit,
                "after": args.after,
            }
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="GET",
                path=f"/{version}/act_{args.ad_account_id}/campaigns",
                query=query,
                body=None,
                required_scopes=ADS_MANAGEMENT_SCOPES,
                token_hint=TokenType.AD_ACCOUNT,
                use_cache=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="ads.campaigns.update", structured_output=True, description="Update an existing ad campaign.")
    async def campaigns_update(args: AdsCampaignUpdate, ctx: Context) -> Mapping[str, object]:
        try:
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="POST",
                path=f"/{version}/{args.campaign_id}",
                query=None,
                body=args.patch,
                form=None,
                files=None,
                required_scopes=ADS_MANAGEMENT_SCOPES,
                token_hint=TokenType.AD_ACCOUNT,
                idempotency=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="ads.adsets.create", structured_output=True, description="Create a new ad set.")
    async def adsets_create(args: AdsAdsetCreate, ctx: Context) -> Mapping[str, object]:
        try:
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="POST",
                path=f"/{version}/act_{args.ad_account_id}/adsets",
                query=None,
                body=args.spec,
                form=None,
                files=None,
                required_scopes=ADS_MANAGEMENT_SCOPES,
                token_hint=TokenType.AD_ACCOUNT,
                idempotency=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="ads.adsets.list", structured_output=True, description="List ad sets for an ad account.")
    async def adsets_list(args: AdsAdsetList, ctx: Context) -> Mapping[str, object]:
        try:
            query = {
                "fields": ",".join(args.fields),
                "limit": args.limit,
                "after": args.after,
            }
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="GET",
                path=f"/{version}/act_{args.ad_account_id}/adsets",
                query=query,
                body=None,
                required_scopes=ADS_MANAGEMENT_SCOPES,
                token_hint=TokenType.AD_ACCOUNT,
                use_cache=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="ads.adsets.update", structured_output=True, description="Update an existing ad set.")
    async def adsets_update(args: AdsAdsetUpdate, ctx: Context) -> Mapping[str, object]:
        try:
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="POST",
                path=f"/{version}/{args.adset_id}",
                query=None,
                body=args.patch,
                form=None,
                files=None,
                required_scopes=ADS_MANAGEMENT_SCOPES,
                token_hint=TokenType.AD_ACCOUNT,
                idempotency=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="ads.creatives.create", structured_output=True, description="Create a new ad creative.")
    async def creatives_create(args: AdsCreativeCreate, ctx: Context) -> Mapping[str, object]:
        try:
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="POST",
                path=f"/{version}/act_{args.ad_account_id}/adcreatives",
                query=None,
                body=args.creative,
                form=None,
                files=None,
                required_scopes=ADS_MANAGEMENT_SCOPES,
                token_hint=TokenType.AD_ACCOUNT,
                idempotency=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="ads.ads.create", structured_output=True, description="Create a new ad.")
    async def ads_create(args: AdsAdsCreate, ctx: Context) -> Mapping[str, object]:
        try:
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="POST",
                path=f"/{version}/act_{args.ad_account_id}/ads",
                query=None,
                body=args.spec,
                form=None,
                files=None,
                required_scopes=ADS_MANAGEMENT_SCOPES,
                token_hint=TokenType.AD_ACCOUNT,
                idempotency=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="ads.ads.list", structured_output=True, description="List ads for an ad account.")
    async def ads_list(args: AdsAdsList, ctx: Context) -> Mapping[str, object]:
        try:
            query = {
                "fields": ",".join(args.fields),
                "limit": args.limit,
                "after": args.after,
            }
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="GET",
                path=f"/{version}/act_{args.ad_account_id}/ads",
                query=query,
                body=None,
                required_scopes=ADS_MANAGEMENT_SCOPES,
                token_hint=TokenType.AD_ACCOUNT,
                use_cache=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="ads.ads.update", structured_output=True, description="Update an existing ad.")
    async def ads_update(args: AdsAdsUpdate, ctx: Context) -> Mapping[str, object]:
        try:
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="POST",
                path=f"/{version}/{args.ad_id}",
                query=None,
                body=args.patch,
                form=None,
                files=None,
                required_scopes=ADS_MANAGEMENT_SCOPES,
                token_hint=TokenType.AD_ACCOUNT,
                idempotency=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="ads.calendar.note.put", structured_output=True, description="Create or update a calendar note.")
    async def calendar_note_put(args: AdsCalendarNotePut, ctx: Context) -> Mapping[str, object]:
        note = CalendarNote(
            idempotency_key=args.idempotency_key,
            subject=args.subject,
            when=args.when,
            related_ids=list(args.related_ids),
        )
        async with session_scope() as session:
            existing = await session.get(CalendarNote, args.idempotency_key)
            if existing:
                existing.subject = args.subject
                existing.when = args.when
                existing.related_ids = list(args.related_ids)
            else:
                session.add(note)
        return {
            "ok": True,
            "data": {
                "idempotency_key": args.idempotency_key,
                "subject": args.subject,
                "when": args.when.isoformat(),
                "related_ids": list(args.related_ids),
            },
            "meta": {},
        }


__all__ = ["register"]
