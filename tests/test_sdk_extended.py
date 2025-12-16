from collections.abc import Callable
from datetime import datetime
from typing import Any

import pytest
from mcp import types

from mcp_meta_sdk import MetaMcpSdk
from meta_mcp.meta_client import (
    AdLibraryByPage,
    AdLibrarySearch,
    AdsAdsCreate,
    AdsAdsetCreate,
    AdsAdsetList,
    AdsAdsetUpdate,
    AdsAdsList,
    AdsAdsUpdate,
    AdsCalendarNotePut,
    AdsCampaignCreate,
    AdsCampaignList,
    AdsCampaignUpdate,
    AdsCreativeCreate,
    AssetsPageMediaList,
    AssetsVideoSubtitlesUpload,
    AssetsVideoUploadChunk,
    AssetsVideoUploadFinish,
    AssetsVideoUploadInit,
    AuthLoginBeginRequest,
    AuthLoginCompleteRequest,
    GraphRequestInput,
    IgCarouselPublish,
    IgMediaCreate,
    IgMediaPublish,
    InsightsAdsAccount,
    InsightsIgAccount,
    InsightsIgMedia,
    InsightsPageAccount,
    PagePhotosCreate,
    PagesPostsPublish,
    PageVideosCreate,
    ResearchObjectReactions,
    ResearchPublicIgMediaCommentsList,
    ResearchPublicIgMediaList,
    ResearchPublicPagesPostCommentsList,
    ResearchPublicPagesPostsList,
)


class DummySession:
    def __init__(self, factory: Callable[[str], dict[str, Any]]) -> None:
        self.factory = factory
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None, **_: Any) -> types.CallToolResult:
        self.calls.append((name, arguments))
        return types.CallToolResult(content=[], structuredContent=self.factory(name), isError=False)

@pytest.mark.asyncio
async def test_all_wrappers(monkeypatch):
    sdk = MetaMcpSdk(base_url="http://localhost")
    
    def response_factory(name: str) -> dict[str, Any]:
        if name == "auth.permissions.check":
            return {"ok": True, "data": {"app_id": "123", "type": "page", "scopes": [], "expires_at": None, "valid": True}, "meta": {}}
        elif name == "events.dequeue":
            return {"ok": True, "data": {"events": []}, "meta": {}}
        elif name == "auth.login.begin":
            return {"ok": True, "data": {"authorization_url": "http://a", "state": "s", "redirect_uri": "http://r", "scopes": []}, "meta": {}}
        elif name == "auth.login.complete":
            return {"ok": True, "data": {"access_token": "tok", "token_type": "bearer"}, "meta": {}}
        else:
            return {"ok": True, "data": {"id": "123"}, "meta": {}}
    
    sdk._session = DummySession(response_factory)
    
    # Auth
    await sdk.auth_permissions_check("tok")
    await sdk.events_dequeue()
    await sdk.auth_login_begin(AuthLoginBeginRequest(scopes=["a"]))
    await sdk.auth_login_complete(AuthLoginCompleteRequest(code="c"))
    
    # Core
    await sdk.graph_request(GraphRequestInput(method="GET", path="me"))
    
    # Research
    await sdk.research_public_pages_posts(ResearchPublicPagesPostsList(page_id="p"))
    await sdk.research_public_pages_comments(ResearchPublicPagesPostCommentsList(post_id="p"))
    await sdk.research_public_ig_media(ResearchPublicIgMediaList(ig_user_id="u"))
    await sdk.research_public_ig_media_comments(ResearchPublicIgMediaCommentsList(ig_media_id="m"))
    await sdk.research_object_reactions(ResearchObjectReactions(object_id="o"))
    
    # Insights
    await sdk.insights_page_account(InsightsPageAccount(page_id="p", metrics=["m"], period="day"))
    await sdk.insights_ig_account(InsightsIgAccount(ig_user_id="u", metrics=["m"], period="day"))
    await sdk.insights_ig_media(InsightsIgMedia(ig_media_id="m", metrics=["m"]))
    await sdk.insights_ads_account(InsightsAdsAccount(ad_account_id="a", fields=["f"], level="campaign", time_range={"since":"a","until":"b"}))
    
    # Assets
    await sdk.assets_page_media_list(AssetsPageMediaList(page_id="p", kind="photos"))
    await sdk.assets_video_upload_init(AssetsVideoUploadInit(page_id="p", file_size=1, file_name="f"))
    await sdk.assets_video_upload_chunk(AssetsVideoUploadChunk(upload_session_id="s", start_offset=0, chunk=b""))
    await sdk.assets_video_upload_finish(AssetsVideoUploadFinish(upload_session_id="s"))
    await sdk.assets_video_subtitles_upload(AssetsVideoSubtitlesUpload(video_id="v", lang="en", srt_buffer=b""))
    
    # Publish / Create
    await sdk.ig_media_create_tool(IgMediaCreate(ig_user_id="u", media_type="IMAGE"))
    await sdk.ig_media_publish_tool(IgMediaPublish(ig_user_id="u", creation_id="c"))
    await sdk.ig_carousel_publish_tool(IgCarouselPublish(ig_user_id="u", creation_id="c"))
    await sdk.page_photos_create(PagePhotosCreate(page_id="p"))
    await sdk.page_videos_create(PageVideosCreate(page_id="p"))
    await sdk.pages_posts_publish(PagesPostsPublish(page_id="p"))
    
    # Ads
    await sdk.ads_campaigns_create(AdsCampaignCreate(ad_account_id="a", name="n", objective="o", status="s"))
    await sdk.ads_campaigns_list(AdsCampaignList(ad_account_id="a", fields=["f"]))
    await sdk.ads_campaigns_update(AdsCampaignUpdate(campaign_id="c", patch={}))
    await sdk.ads_adsets_create(AdsAdsetCreate(ad_account_id="a", spec={}))
    await sdk.ads_adsets_list(AdsAdsetList(ad_account_id="a", fields=["f"]))
    await sdk.ads_adsets_update(AdsAdsetUpdate(adset_id="a", patch={}))
    await sdk.ads_creatives_create(AdsCreativeCreate(ad_account_id="a", creative={}))
    await sdk.ads_ads_create(AdsAdsCreate(ad_account_id="a", spec={}))
    await sdk.ads_ads_list(AdsAdsList(ad_account_id="a", fields=["f"]))
    await sdk.ads_ads_update(AdsAdsUpdate(ad_id="a", patch={}))
    await sdk.ads_calendar_note_put(AdsCalendarNotePut(idempotency_key="k", subject="s", when=datetime.now(), related_ids=[]))
    
    # Helpers
    await sdk.ad_library_search(AdLibrarySearch(ad_type="a", ad_reached_countries=["US"], fields=["f"]))
    await sdk.ad_library_search_by_pages(AdLibraryByPage(page_ids=["p"], ad_type="a", ad_reached_countries=["US"], fields=["f"]))

@pytest.mark.asyncio
async def test_create_campaign_stack(monkeypatch):
    sdk = MetaMcpSdk(base_url="http://localhost")
    responses = {
        "ads.campaigns.create": {"data": {"id": "camp_1"}},
        "ads.adsets.create": {"data": {"id": "adset_1"}},
        "ads.creatives.create": {"data": {"id": "creative_1"}},
        "ads.ads.create": {"data": {"id": "ad_1"}},
    }
    def response_factory(name: str) -> dict[str, Any]:
        data = responses.get(name, {})
        return {"ok": True, "data": data, "meta": {}}
    sdk._session = DummySession(response_factory)
    
    await sdk.create_campaign_stack(
        campaign=AdsCampaignCreate(ad_account_id="1", name="C", objective="O", status="P"),
        adset=AdsAdsetCreate(ad_account_id="1", spec={"name": "A"}),
        creative=AdsCreativeCreate(ad_account_id="1", creative={"name": "Cr"}),
        ad=AdsAdsCreate(ad_account_id="1", spec={"name": "Ad"})
    )
