from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import Response

from meta_mcp.config import get_settings
from meta_mcp.mcp_tools.assets import (
    AssetsPageMediaList,
    AssetsVideoSubtitlesUpload,
    AssetsVideoUploadChunk,
    AssetsVideoUploadFinish,
    AssetsVideoUploadInit,
    IgMediaCreate,
    PagePhotosCreate,
    PageVideosCreate,
    register,
)
from meta_mcp.mcp_tools.common import ToolEnvironment
from meta_mcp.meta_client import MetaGraphApiClient, TokenService
from meta_mcp.storage.queue import WebhookEventQueue


@pytest.fixture
async def tool_env():
    settings = get_settings()
    # Use real client
    client = MetaGraphApiClient(
    )
    # Mock token service for permissions checks
    token_service = AsyncMock(spec=TokenService)
    # Mock successful permission check returning dummy metadata
    metadata_mock = MagicMock()
    metadata_mock.subject_id = "123"
    metadata_mock.type.value = "page"
    token_service.ensure_permissions.return_value = metadata_mock
    token_service.ensure_instagram_business.return_value = None
    
    event_queue = MagicMock(spec=WebhookEventQueue)
    
    return ToolEnvironment(
        settings=settings,
        client=client,
        token_service=token_service,
        event_queue=event_queue,
    )

@pytest.fixture
def registered_tools(tool_env):
    server = MagicMock()
    tools = {}
    def tool_decorator(name=None, **kwargs):
        def wrapper(func):
            tools[name] = func
            return func
        return wrapper
    server.tool.side_effect = tool_decorator
    
    register(server, tool_env)
    return tools

@pytest.fixture
def ctx():
    c = MagicMock()
    # Simulate a request with an access token in the meta
    c.request_context.meta = {"access_token": "token123"}
    return c

@pytest.mark.asyncio
async def test_page_media_list(registered_tools, ctx, respx_mock):
    # Setup mock
    route = respx_mock.get("https://example.com/v18.0/123/photos").mock(
        return_value=Response(200, json={"data": [{"id": "media1"}]}, headers={"x-app-usage": "5%"})
    )
    
    func = registered_tools["assets.page.media.list"]
    args = AssetsPageMediaList(page_id="123", kind="photos", limit=10)
    
    result = await func(args, ctx)
    
    assert result["ok"] is True
    assert result["data"]["data"]["data"][0]["id"] == "media1"
    assert result["meta"]["x-app-usage"] == "5%"
    
    # Verify request
    assert route.called
    request = route.calls.last.request
    assert request.url.params["limit"] == "10"
    assert request.headers["Authorization"] == "Bearer token123"

@pytest.mark.asyncio
async def test_video_upload_init(registered_tools, ctx, respx_mock):
    route = respx_mock.post("https://example.com/v18.0/123/videos").mock(
        return_value=Response(200, json={"upload_session_id": "sess_123"})
    )
    
    func = registered_tools["assets.video.upload.init"]
    args = AssetsVideoUploadInit(page_id="123", file_size=1000, file_name="vid.mp4")
    
    result = await func(args, ctx)
    
    assert result["ok"] is True
    assert result["data"]["data"]["upload_session_id"] == "sess_123"
    
    assert route.called
    request = route.calls.last.request
    # Check form data
    assert b"upload_phase=start" in request.content
    assert b"file_size=1000" in request.content

@pytest.mark.asyncio
async def test_ig_media_create(registered_tools, ctx, respx_mock):
    route = respx_mock.post("https://example.com/v18.0/ig_user/media").mock(
        return_value=Response(200, json={"id": "container_123"})
    )
    
    func = registered_tools["ig.media.create"]
    args = IgMediaCreate(
        ig_user_id="ig_user",
        media_type="IMAGE",
        image_url="https://site.com/img.jpg",
        caption="Hello"
    )
    
    result = await func(args, ctx)
    
    assert result["ok"] is True
    assert result["data"]["data"]["id"] == "container_123"
    
    assert route.called
    request = route.calls.last.request
    import json
    body = json.loads(request.content)
    assert body["media_type"] == "IMAGE"
    assert body["image_url"] == "https://site.com/img.jpg"
    assert body["caption"] == "Hello"

@pytest.mark.asyncio
async def test_video_upload_chunk(registered_tools, ctx, respx_mock):
    route = respx_mock.post("https://example.com/v18.0/sess_123").mock(
        return_value=Response(200, json={"success": True})
    )
    
    func = registered_tools["assets.video.upload.chunk"]
    args = AssetsVideoUploadChunk(
        upload_session_id="sess_123",
        start_offset=0,
        chunk=b"binarydata"
    )
    
    result = await func(args, ctx)
    
    assert result["ok"] is True
    
    assert route.called
    request = route.calls.last.request
    # Verify multipart/form-data
    assert b"Content-Disposition: form-data; name=\"upload_phase\"" in request.content
    assert b"transfer" in request.content

@pytest.mark.asyncio
async def test_video_upload_finish(registered_tools, ctx, respx_mock):
    route = respx_mock.post("https://example.com/v18.0/sess_123").mock(
        return_value=Response(200, json={"success": True})
    )
    
    func = registered_tools["assets.video.upload.finish"]
    args = AssetsVideoUploadFinish(upload_session_id="sess_123")
    
    result = await func(args, ctx)
    
    assert result["ok"] is True
    assert b"finish" in route.calls.last.request.content

@pytest.mark.asyncio
async def test_video_subtitles_upload(registered_tools, ctx, respx_mock):
    route = respx_mock.post("https://example.com/v18.0/vid_123/captions").mock(
        return_value=Response(200, json={"success": True})
    )
    
    func = registered_tools["assets.video.subtitles.upload"]
    args = AssetsVideoSubtitlesUpload(
        video_id="vid_123",
        lang="en_US",
        srt_buffer=b"1\n00:00:01 -> 00:00:02\nHello"
    )
    
    result = await func(args, ctx)
    assert result["ok"] is True

@pytest.mark.asyncio
async def test_page_photos_create(registered_tools, ctx, respx_mock):
    route = respx_mock.post("https://example.com/v18.0/page_123/photos").mock(
        return_value=Response(200, json={"id": "photo_123"})
    )
    
    func = registered_tools["page.photos.create"]
    args = PagePhotosCreate(
        page_id="page_123",
        url="https://site.com/img.jpg",
        caption="Hello"
    )
    
    result = await func(args, ctx)
    assert result["ok"] is True
    assert route.called
    req = route.calls.last.request
    assert b"url" in req.content

@pytest.mark.asyncio
async def test_page_videos_create(registered_tools, ctx, respx_mock):
    route = respx_mock.post("https://example.com/v18.0/page_123/videos").mock(
        return_value=Response(200, json={"id": "video_123"})
    )
    
    func = registered_tools["page.videos.create"]
    args = PageVideosCreate(
        page_id="page_123",
        url="https://site.com/vid.mp4",
        description="Desc"
    )
    
    result = await func(args, ctx)
    assert result["ok"] is True

@pytest.mark.asyncio
async def test_page_media_list_error(registered_tools, ctx, respx_mock):
    respx_mock.get("https://example.com/v18.0/123/photos").mock(
        return_value=Response(400, json={"error": {"message": "Bad Request", "code": 100}})
    )
    
    func = registered_tools["assets.page.media.list"]
    args = AssetsPageMediaList(page_id="123", kind="photos", limit=10)
    
    result = await func(args, ctx)
    assert result["ok"] is False
    assert result["error"]["code"] == "VALIDATION"  # 400 maps to VALIDATION or similar
