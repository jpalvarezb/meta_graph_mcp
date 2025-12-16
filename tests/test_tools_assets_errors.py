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
    client = MetaGraphApiClient()
    token_service = AsyncMock(spec=TokenService)
    token_service.ensure_permissions.return_value = MagicMock(subject_id="123", type=MagicMock(value="page"))
    # Mock ensure_instagram_business to pass or fail? We want perform_graph_call to fail.
    token_service.ensure_instagram_business.return_value = None
    
    event_queue = MagicMock(spec=WebhookEventQueue)
    return ToolEnvironment(settings, client, token_service, event_queue)

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
    c.request_context.meta = {"access_token": "token123"}
    return c

@pytest.mark.asyncio
async def test_all_assets_tools_errors(registered_tools, ctx, respx_mock):
    # Mock all to fail
    respx_mock.route().mock(return_value=Response(400, json={"error": {"message": "Fail", "code": 100}}))
    
    tools_args = [
        ("assets.page.media.list", AssetsPageMediaList(page_id="1", kind="photos")),
        ("assets.video.upload.init", AssetsVideoUploadInit(page_id="1", file_size=1, file_name="f")),
        ("assets.video.upload.chunk", AssetsVideoUploadChunk(upload_session_id="1", start_offset=0, chunk=b"")),
        ("assets.video.upload.finish", AssetsVideoUploadFinish(upload_session_id="1")),
        ("assets.video.subtitles.upload", AssetsVideoSubtitlesUpload(video_id="1", lang="en", srt_buffer=b"")),
        ("ig.media.create", IgMediaCreate(ig_user_id="1", media_type="IMAGE")),
        ("page.photos.create", PagePhotosCreate(page_id="1")),
        ("page.videos.create", PageVideosCreate(page_id="1")),
    ]
    
    for name, args in tools_args:
        func = registered_tools[name]
        result = await func(args, ctx)
        assert result["ok"] is False, f"{name} should have failed"
        assert result["error"]["code"] == "VALIDATION"
