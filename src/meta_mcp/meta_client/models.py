"""Pydantic models describing tool inputs and outputs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Sequence

from pydantic import BaseModel, Field, HttpUrl, RootModel


class GraphRequestInput(BaseModel):
    method: Literal["GET", "POST", "DELETE", "PUT", "PATCH"]
    path: str = Field(..., description="Graph API path including version prefix")
    query: dict[str, Any] | None = None
    body: dict[str, Any] | None = None


class GraphRequestOutput(BaseModel):
    status: int
    headers: dict[str, Any]
    data: Any


class PermissionsCheckRequest(BaseModel):
    access_token: str


class PermissionMetadata(BaseModel):
    app_id: str
    type: str
    scopes: list[str]
    expires_at: datetime | None
    valid: bool


class PermissionsCheckResponse(BaseModel):
    app_id: str
    type: str
    scopes: list[str]
    expires_at: datetime | None
    valid: bool


class AuthLoginBeginRequest(BaseModel):
    scopes: Sequence[str]
    redirect_uri: HttpUrl | None = None
    state: str | None = None


class AuthLoginBeginResponse(BaseModel):
    authorization_url: HttpUrl
    state: str
    redirect_uri: HttpUrl
    scopes: list[str]


class AuthLoginCompleteRequest(BaseModel):
    code: str
    redirect_uri: HttpUrl | None = None
    expected_state: str | None = None
    state: str | None = None


class AuthLoginCompleteResponse(BaseModel):
    access_token: str
    token_type: str
    expires_at: datetime | None = None
    app_id: str | None = None
    subject_id: str | None = None
    scopes: list[str] = Field(default_factory=list)


class EventsDequeueRequest(BaseModel):
    max: int = Field(default=50, ge=1, le=200)


class EventsDequeueResponse(BaseModel):
    events: list[dict[str, Any]]


class PaginationParams(BaseModel):
    after: str | None = None
    limit: int | None = Field(default=None, ge=1, le=100)
    since: datetime | None = None
    until: datetime | None = None


class ResearchPublicPagesPostsList(BaseModel):
    page_id: str
    since: datetime | None = None
    until: datetime | None = None
    after: str | None = None
    limit: int | None = Field(default=None, ge=1, le=100)


class ResearchPublicPagesPostCommentsList(BaseModel):
    post_id: str
    after: str | None = None
    limit: int | None = Field(default=None, ge=1, le=100)


class ResearchPublicIgMediaList(BaseModel):
    ig_user_id: str
    after: str | None = None
    limit: int | None = Field(default=None, ge=1, le=100)


class ResearchPublicIgMediaCommentsList(BaseModel):
    ig_media_id: str
    after: str | None = None
    limit: int | None = Field(default=None, ge=1, le=100)


class ResearchObjectReactions(BaseModel):
    object_id: str
    summary: bool = True


class InsightsPageAccount(BaseModel):
    page_id: str
    metrics: Sequence[str]
    period: str
    since: datetime | None = None
    until: datetime | None = None


class InsightsIgAccount(BaseModel):
    ig_user_id: str
    metrics: Sequence[str]
    period: str
    breakdowns: Sequence[str] | None = None


class InsightsIgMedia(BaseModel):
    ig_media_id: str
    metrics: Sequence[str]


class InsightsAdsAccount(BaseModel):
    ad_account_id: str
    fields: Sequence[str]
    level: str
    time_range: dict[str, str]
    breakdowns: Sequence[str] | None = None
    filtering: list[dict[str, Any]] | None = None
    limit: int | None = Field(default=None, ge=1, le=500)
    after: str | None = None


class AdLibrarySearch(BaseModel):
    ad_type: str
    search_terms: str | None = None
    ad_reached_countries: Sequence[str]
    search_page_ids: Sequence[str] | None = None
    fields: Sequence[str]
    limit: int | None = Field(default=None, ge=1, le=100)
    after: str | None = None


class AdLibraryByPage(BaseModel):
    page_ids: Sequence[str]
    ad_type: str
    ad_reached_countries: Sequence[str]
    fields: Sequence[str]
    limit: int | None = Field(default=None, ge=1, le=100)
    after: str | None = None


class AssetsPageMediaList(BaseModel):
    page_id: str
    kind: Literal["photos", "videos"]
    after: str | None = None
    limit: int | None = Field(default=None, ge=1, le=100)


class AssetsVideoUploadInit(BaseModel):
    page_id: str
    file_name: str
    file_size: int = Field(..., ge=1)


class AssetsVideoUploadChunk(BaseModel):
    upload_session_id: str
    start_offset: int
    chunk: bytes


class AssetsVideoUploadFinish(BaseModel):
    upload_session_id: str


class AssetsVideoSubtitlesUpload(BaseModel):
    video_id: str
    lang: str
    srt_buffer: bytes


class IgMediaCreate(BaseModel):
    ig_user_id: str
    media_type: Literal["IMAGE", "VIDEO", "CAROUSEL"]
    items: list[dict[str, Any]] | None = None
    image_url: HttpUrl | None = None
    video_url: HttpUrl | None = None
    caption: str | None = None


class PagePhotosCreate(BaseModel):
    page_id: str
    url: HttpUrl | None = None
    file: bytes | None = None
    caption: str | None = None
    published: bool | None = None
    scheduled_publish_time: datetime | None = None


class PageVideosCreate(BaseModel):
    page_id: str
    url: HttpUrl | None = None
    file: bytes | None = None
    description: str | None = None
    title: str | None = None
    published: bool | None = None
    scheduled_publish_time: datetime | None = None


class PagesPostsPublish(BaseModel):
    page_id: str
    message: str | None = None
    link: HttpUrl | None = None
    attached_media: list[dict[str, Any]] | None = None
    published: bool | None = None
    scheduled_publish_time: datetime | None = None


class IgMediaPublish(BaseModel):
    ig_user_id: str
    creation_id: str


class IgCarouselPublish(BaseModel):
    ig_user_id: str
    creation_id: str


class AdsCampaignCreate(BaseModel):
    ad_account_id: str
    name: str
    objective: str
    status: str


class AdsCampaignList(BaseModel):
    ad_account_id: str
    fields: Sequence[str]
    limit: int | None = Field(default=None, ge=1, le=100)
    after: str | None = None


class AdsCampaignUpdate(BaseModel):
    campaign_id: str
    patch: dict[str, Any]


class AdsAdsetCreate(BaseModel):
    ad_account_id: str
    spec: dict[str, Any]


class AdsAdsetList(BaseModel):
    ad_account_id: str
    fields: Sequence[str]
    limit: int | None = Field(default=None, ge=1, le=100)
    after: str | None = None


class AdsAdsetUpdate(BaseModel):
    adset_id: str
    patch: dict[str, Any]


class AdsCreativeCreate(BaseModel):
    ad_account_id: str
    creative: dict[str, Any]


class AdsAdsCreate(BaseModel):
    ad_account_id: str
    spec: dict[str, Any]


class AdsAdsList(BaseModel):
    ad_account_id: str
    fields: Sequence[str]
    limit: int | None = Field(default=None, ge=1, le=100)
    after: str | None = None


class AdsAdsUpdate(BaseModel):
    ad_id: str
    patch: dict[str, Any]


class AdsCalendarNotePut(BaseModel):
    idempotency_key: str
    subject: str
    when: datetime
    related_ids: Sequence[str]


class ToolResponse(BaseModel):
    ok: bool
    data: Any = None
    meta: dict[str, Any]
    error: dict[str, Any] | None = None


class ToolResponseRoot(RootModel[ToolResponse]):
    root: ToolResponse


__all__ = tuple(name for name in globals() if name[0].isupper())
