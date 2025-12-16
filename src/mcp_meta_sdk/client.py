"""Async client for interacting with the Meta MCP server over MCP Streamable HTTP."""

from __future__ import annotations

from contextlib import AsyncExitStack
from datetime import datetime, timedelta
from importlib import metadata as importlib_metadata
from typing import Any, Callable, Mapping, MutableMapping, TypeVar

from mcp import types
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from pydantic import BaseModel

from meta_mcp.meta_client import (
    AdsAdsCreate,
    AdsAdsList,
    AdsAdsUpdate,
    AdsCalendarNotePut,
    AdsAdsetCreate,
    AdsAdsetList,
    AdsAdsetUpdate,
    AdsCampaignCreate,
    AdsCampaignList,
    AdsCampaignUpdate,
    AdsCreativeCreate,
    AdLibraryByPage,
    AssetsPageMediaList,
    AuthLoginBeginRequest,
    AuthLoginCompleteRequest,
    AssetsVideoSubtitlesUpload,
    AssetsVideoUploadChunk,
    AssetsVideoUploadFinish,
    AssetsVideoUploadInit,
    AdLibrarySearch,
    GraphRequestInput, PermissionsCheckRequest, EventsDequeueRequest,
    InsightsAdsAccount,
    PagesPostsPublish,
    PagePhotosCreate,
    PageVideosCreate,
)
from meta_mcp.meta_client.models import (
    ToolResponse,
    PermissionsCheckResponse,
    EventsDequeueResponse,
    AuthLoginBeginResponse,
    AuthLoginCompleteResponse,
)

from meta_mcp.meta_client import (  # type: ignore[attr-defined]
    IgCarouselPublish,
    IgMediaCreate,
    IgMediaPublish,
    InsightsIgAccount,
    InsightsIgMedia,
    InsightsPageAccount,
    ResearchObjectReactions,
    ResearchPublicIgMediaCommentsList,
    ResearchPublicIgMediaList,
    ResearchPublicPagesPostCommentsList,
    ResearchPublicPagesPostsList,
)


TModel = TypeVar("TModel", bound=BaseModel)


class ToolResponseError(RuntimeError):
    """Base exception for tool response errors."""

    def __init__(self, message: str, *, response: ToolResponse | None = None) -> None:
        super().__init__(message)
        self.response = response


class ToolExecutionError(ToolResponseError):
    """Raised when the server returns {"ok": false}."""

    def __init__(self, response: ToolResponse) -> None:
        error = response.error or {}
        code = error.get("code", "UNKNOWN")
        message = error.get("message", "Tool execution failed")
        super().__init__(f"[{code}] {message}", response=response)
        self.code = code
        self.details = error.get("details")
        self.retry_after = error.get("retry_after")

class MetaMcpSdk:
    """Thin async SDK wrapping MCP tool calls exposed by the Meta server."""

    def __init__(
        self,
        *,
        base_url: str,
        access_token: str | None = None,
        headers: Mapping[str, str] | None = None,
        timeout_seconds: float = 30.0,
        sse_read_timeout_seconds: float = 60.0 * 5,
        mcp_path: str = "/mcp",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers: MutableMapping[str, str] = dict(headers or {})
        if access_token:
            self._headers.setdefault("Authorization", f"Bearer {access_token}")
        self._timeout = timedelta(seconds=timeout_seconds)
        self._sse_timeout = timedelta(seconds=sse_read_timeout_seconds)
        self._mcp_path = mcp_path if mcp_path.startswith("/") else f"/{mcp_path}"
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._get_session_id: Callable[[], str | None] | None = None
        self._version = self._detect_version()

    async def __aenter__(self) -> "MetaMcpSdk":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    @property
    def session_id(self) -> str | None:
        if self._get_session_id is None:
            return None
        return self._get_session_id()

    def _detect_version(self) -> str:
        try:
            return importlib_metadata.version("meta-mcp")
        except importlib_metadata.PackageNotFoundError:  # pragma: no cover
            return "0.0.0"

    async def connect(self) -> None:
        if self._session is not None:
            return
        stack = AsyncExitStack()
        read_stream, write_stream, get_session_id = await stack.enter_async_context(
            streamablehttp_client(
                url=f"{self._base_url}{self._mcp_path}",
                headers=dict(self._headers),
                timeout=self._timeout,
                sse_read_timeout=self._sse_timeout,
            )
        )
        client_info = types.Implementation(name="mcp-meta-sdk", version=self._version)
        session = ClientSession(read_stream, write_stream, client_info=client_info)
        await session.initialize()
        self._stack = stack
        self._session = session
        self._get_session_id = get_session_id

    async def close(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._session = None
        self._get_session_id = None

    def _require_session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError("SDK is not connected. Call connect() first or use async context manager.")
        return self._session

    def _normalize_arguments(self, arguments: BaseModel | Mapping[str, Any] | None) -> dict[str, Any] | None:
        if arguments is None:
            return None
        if isinstance(arguments, BaseModel):
            return arguments.model_dump(mode="json", exclude_none=True)
        if isinstance(arguments, Mapping):
            return {k: v for k, v in arguments.items() if v is not None}
        raise TypeError("Tool arguments must be a Pydantic model or mapping")

    async def call_tool_raw(
        self,
        name: str,
        arguments: BaseModel | Mapping[str, Any] | None = None,
    ) -> ToolResponse:
        session = self._require_session()
        normalized = self._normalize_arguments(arguments)
        result = await session.call_tool(name, normalized)
        if result.structuredContent is None:
            raise ToolResponseError(
                f"Tool '{name}' returned no structured content",
            )
        # Validate the response structure
        if not isinstance(result.structuredContent, dict):
            raise ToolResponseError(
                f"Tool '{name}' returned invalid structured content type",
            )
        # Check if it's an error response before full validation
        if result.structuredContent.get("ok") is False:
            # For error responses, data field might be missing
            response = ToolResponse.model_validate(result.structuredContent)
            raise ToolExecutionError(response)
        # For success responses, validate normally
        response = ToolResponse.model_validate(result.structuredContent)
        if not response.ok:
            raise ToolExecutionError(response)
        return response

    async def call_tool_data(
        self,
        name: str,
        arguments: BaseModel | Mapping[str, Any] | None,
        response_model: type[TModel],
    ) -> TModel:
        response = await self.call_tool_raw(name, arguments)
        if not issubclass(response_model, BaseModel):
            raise TypeError("response_model must be a subclass of pydantic.BaseModel")
        return response_model.model_validate(response.data)

    # --- Typed wrappers -------------------------------------------------

    async def auth_permissions_check(self, access_token: str) -> PermissionsCheckResponse:
        response = await self.call_tool_raw("auth.permissions.check", PermissionsCheckRequest(access_token=access_token))
        return PermissionsCheckResponse.model_validate(response.data)

    async def events_dequeue(self, max_events: int = 50) -> EventsDequeueResponse:
        response = await self.call_tool_raw("events.dequeue", EventsDequeueRequest(max=max_events))
        return EventsDequeueResponse.model_validate(response.data)

    async def auth_login_begin(self, request: AuthLoginBeginRequest) -> AuthLoginBeginResponse:
        response = await self.call_tool_raw("auth.login.begin", request)
        return AuthLoginBeginResponse.model_validate(response.data)

    async def auth_login_complete(self, request: AuthLoginCompleteRequest) -> AuthLoginCompleteResponse:
        response = await self.call_tool_raw("auth.login.complete", request)
        return AuthLoginCompleteResponse.model_validate(response.data)

    async def graph_request(self, request: GraphRequestInput) -> ToolResponse:
        return await self.call_tool_raw("graph.request", request)

    async def research_public_pages_posts(self, request: ResearchPublicPagesPostsList) -> ToolResponse:
        return await self.call_tool_raw("research.public_pages.posts.list", request)

    async def research_public_pages_comments(self, request: ResearchPublicPagesPostCommentsList) -> ToolResponse:
        return await self.call_tool_raw("research.public_pages.post_comments.list", request)

    async def research_public_ig_media(self, request: ResearchPublicIgMediaList) -> ToolResponse:
        return await self.call_tool_raw("research.public_ig.media.list", request)

    async def research_public_ig_media_comments(self, request: ResearchPublicIgMediaCommentsList) -> ToolResponse:
        return await self.call_tool_raw("research.public_ig.media_comments.list", request)

    async def research_object_reactions(self, request: ResearchObjectReactions) -> ToolResponse:
        return await self.call_tool_raw("research.object.reactions", request)

    async def insights_page_account(self, request: InsightsPageAccount) -> ToolResponse:
        return await self.call_tool_raw("insights.page.account", request)

    async def insights_ig_account(self, request: InsightsIgAccount) -> ToolResponse:
        return await self.call_tool_raw("insights.ig.account", request)

    async def insights_ig_media(self, request: InsightsIgMedia) -> ToolResponse:
        return await self.call_tool_raw("insights.ig.media", request)

    async def insights_ads_account(self, request: InsightsAdsAccount) -> ToolResponse:
        return await self.call_tool_raw("insights.ads.account", request)

    async def assets_page_media_list(self, request: AssetsPageMediaList) -> ToolResponse:
        return await self.call_tool_raw("assets.page.media.list", request)

    async def assets_video_upload_init(self, request: AssetsVideoUploadInit) -> ToolResponse:
        return await self.call_tool_raw("assets.video.upload.init", request)

    async def assets_video_upload_chunk(self, request: AssetsVideoUploadChunk) -> ToolResponse:
        return await self.call_tool_raw("assets.video.upload.chunk", request)

    async def assets_video_upload_finish(self, request: AssetsVideoUploadFinish) -> ToolResponse:
        return await self.call_tool_raw("assets.video.upload.finish", request)

    async def assets_video_subtitles_upload(self, request: AssetsVideoSubtitlesUpload) -> ToolResponse:
        return await self.call_tool_raw("assets.video.subtitles.upload", request)

    async def ig_media_create_tool(self, request: IgMediaCreate) -> ToolResponse:
        return await self.call_tool_raw("ig.media.create", request)

    async def ig_media_publish_tool(self, request: IgMediaPublish) -> ToolResponse:
        return await self.call_tool_raw("ig.media.publish", request)

    async def ig_carousel_publish_tool(self, request: IgCarouselPublish) -> ToolResponse:
        return await self.call_tool_raw("ig.carousel.publish", request)

    async def page_photos_create(self, request: PagePhotosCreate) -> ToolResponse:
        return await self.call_tool_raw("page.photos.create", request)

    async def page_videos_create(self, request: PageVideosCreate) -> ToolResponse:
        return await self.call_tool_raw("page.videos.create", request)

    async def pages_posts_publish(self, request: PagesPostsPublish) -> ToolResponse:
        return await self.call_tool_raw("pages.posts.publish", request)

    async def ads_campaigns_create(self, request: AdsCampaignCreate) -> ToolResponse:
        return await self.call_tool_raw("ads.campaigns.create", request)

    async def ads_campaigns_list(self, request: AdsCampaignList) -> ToolResponse:
        return await self.call_tool_raw("ads.campaigns.list", request)

    async def ads_campaigns_update(self, request: AdsCampaignUpdate) -> ToolResponse:
        return await self.call_tool_raw("ads.campaigns.update", request)

    async def ads_adsets_create(self, request: AdsAdsetCreate) -> ToolResponse:
        return await self.call_tool_raw("ads.adsets.create", request)

    async def ads_adsets_list(self, request: AdsAdsetList) -> ToolResponse:
        return await self.call_tool_raw("ads.adsets.list", request)

    async def ads_adsets_update(self, request: AdsAdsetUpdate) -> ToolResponse:
        return await self.call_tool_raw("ads.adsets.update", request)

    async def ads_creatives_create(self, request: AdsCreativeCreate) -> ToolResponse:
        return await self.call_tool_raw("ads.creatives.create", request)

    async def ads_ads_create(self, request: AdsAdsCreate) -> ToolResponse:
        return await self.call_tool_raw("ads.ads.create", request)

    async def ads_ads_list(self, request: AdsAdsList) -> ToolResponse:
        return await self.call_tool_raw("ads.ads.list", request)

    async def ads_calendar_note_put(self, request: AdsCalendarNotePut) -> ToolResponse:
        return await self.call_tool_raw("ads.calendar.note.put", request)

    async def ads_ads_update(self, request: AdsAdsUpdate) -> ToolResponse:
        return await self.call_tool_raw("ads.ads.update", request)

    # --- High-level helpers --------------------------------------------

    async def publish_ig_image(
        self,
        *,
        ig_user_id: str,
        image_url: str,
        caption: str | None = None,
    ) -> dict[str, Any]:
        creation_response = await self.call_tool_raw(
            "ig.media.create",
            IgMediaCreate(ig_user_id=ig_user_id, media_type="IMAGE", image_url=image_url, caption=caption),
        )
        creation_data = creation_response.data or {}
        creation_id = creation_data.get("data", {}).get("id")
        if not creation_id:
            raise ToolResponseError("Creation response missing id", response=creation_response)
        publish_response = await self.call_tool_raw(
            "ig.media.publish",
            IgMediaPublish(ig_user_id=ig_user_id, creation_id=creation_id),
        )
        return {
            "creation_id": creation_id,
            "creation": creation_data,
            "publish": publish_response.data,
            "meta": publish_response.meta,
        }

    async def schedule_page_post(
        self,
        *,
        page_id: str,
        message: str,
        schedule_time: datetime,
        link: str | None = None,
    ) -> dict[str, Any]:
        response = await self.call_tool_raw(
            "pages.posts.publish",
            PagesPostsPublish(
                page_id=page_id,
                message=message,
                link=link,
                published=False,
                scheduled_publish_time=schedule_time,
            ),
        )
        return {
            "post": response.data,
            "meta": response.meta,
        }

    async def create_campaign_stack(
        self,
        *,
        campaign: AdsCampaignCreate,
        adset: AdsAdsetCreate,
        creative: AdsCreativeCreate,
        ad: AdsAdsCreate,
    ) -> dict[str, Any]:
        campaign_resp = await self.ads_campaigns_create(campaign)
        campaign_id = (campaign_resp.data or {}).get("data", {}).get("id")
        if not campaign_id:
            raise ToolResponseError("Campaign creation missing id", response=campaign_resp)

        adset_payload = adset.model_copy(update={"spec": {**adset.spec, "campaign_id": campaign_id}})
        adset_resp = await self.ads_adsets_create(adset_payload)
        adset_id = (adset_resp.data or {}).get("data", {}).get("id")
        if not adset_id:
            raise ToolResponseError("Ad set creation missing id", response=adset_resp)

        creative_resp = await self.ads_creatives_create(creative)
        creative_id = (creative_resp.data or {}).get("data", {}).get("id")
        if not creative_id:
            raise ToolResponseError("Creative creation missing id", response=creative_resp)

        ad_payload = ad.model_copy(update={"spec": {**ad.spec, "adset_id": adset_id, "creative": {"creative_id": creative_id}}})
        ad_resp = await self.ads_ads_create(ad_payload)

        return {
            "campaign": campaign_resp.data,
            "adset": adset_resp.data,
            "creative": creative_resp.data,
            "ad": ad_resp.data,
        }

    async def ads_insights_report(
        self,
        request: InsightsAdsAccount,
    ) -> dict[str, Any]:
        response = await self.insights_ads_account(request)
        return response.data

    async def ad_library_search_by_pages(self, request: AdLibraryByPage) -> dict[str, Any]:
        response = await self.call_tool_raw("research.ad_library.by_page", request)
        return response.data

    async def ad_library_search(self, request: AdLibrarySearch) -> dict[str, Any]:
        response = await self.call_tool_raw("research.ad_library.search", request)
        return response.data


__all__ = ["MetaMcpSdk", "ToolExecutionError", "ToolResponseError"]
