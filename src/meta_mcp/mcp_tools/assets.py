"""Asset management tools for pages and Instagram."""

from __future__ import annotations

from typing import Mapping

from mcp.server.fastmcp import Context, FastMCP

from ..errors import MCPException
from ..meta_client import (
    AssetsPageMediaList,
    AssetsVideoSubtitlesUpload,
    AssetsVideoUploadChunk,
    AssetsVideoUploadFinish,
    AssetsVideoUploadInit,
    IgMediaCreate,
    PagePhotosCreate,
    PageVideosCreate,
)
from ..storage import TokenType
from .common import ToolEnvironment, ensure_scopes, failure, perform_graph_call

PAGE_CONTENT_SCOPES = (
    "pages_manage_posts",
    "pages_manage_engagement",
    "pages_read_engagement",
    "pages_read_user_content",
    "pages_manage_metadata",
)

IG_CONTENT_SCOPES = (
    "instagram_basic",
    "instagram_content_publish",
    "instagram_manage_comments",
    "pages_show_list",
    "business_management",
)


def register(server: FastMCP, env: ToolEnvironment) -> None:
    version = env.settings.graph_api_version

    @server.tool(name="assets.page.media.list", structured_output=True)
    async def page_media_list(args: AssetsPageMediaList, ctx: Context) -> Mapping[str, object]:
        try:
            path = f"/{version}/{args.page_id}/{args.kind}"
            query = {
                "after": args.after,
                "limit": args.limit,
            }
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="GET",
                path=path,
                query=query,
                body=None,
                required_scopes=PAGE_CONTENT_SCOPES,
                token_hint=TokenType.PAGE,
                use_cache=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="assets.video.upload.init", structured_output=True)
    async def video_upload_init(args: AssetsVideoUploadInit, ctx: Context) -> Mapping[str, object]:
        try:
            path = f"/{version}/{args.page_id}/videos"
            form = {
                "upload_phase": "start",
                "file_size": args.file_size,
                "file_name": args.file_name,
            }
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="POST",
                path=path,
                query=None,
                body=None,
                form=form,
                files=None,
                required_scopes=PAGE_CONTENT_SCOPES,
                token_hint=TokenType.PAGE,
                idempotency=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="assets.video.upload.chunk", structured_output=True)
    async def video_upload_chunk(args: AssetsVideoUploadChunk, ctx: Context) -> Mapping[str, object]:
        try:
            path = f"/{version}/{args.upload_session_id}"
            form = {
                "upload_phase": "transfer",
                "start_offset": args.start_offset,
            }
            files = {
                "video_file_chunk": ("chunk.bin", args.chunk, "application/octet-stream"),
            }
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="POST",
                path=path,
                query=None,
                body=None,
                form=form,
                files=files,
                required_scopes=PAGE_CONTENT_SCOPES,
                token_hint=TokenType.PAGE,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="assets.video.upload.finish", structured_output=True)
    async def video_upload_finish(args: AssetsVideoUploadFinish, ctx: Context) -> Mapping[str, object]:
        try:
            path = f"/{version}/{args.upload_session_id}"
            form = {
                "upload_phase": "finish",
            }
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="POST",
                path=path,
                query=None,
                body=None,
                form=form,
                files=None,
                required_scopes=PAGE_CONTENT_SCOPES,
                token_hint=TokenType.PAGE,
                idempotency=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="assets.video.subtitles.upload", structured_output=True)
    async def video_subtitles_upload(args: AssetsVideoSubtitlesUpload, ctx: Context) -> Mapping[str, object]:
        try:
            path = f"/{version}/{args.video_id}/captions"
            form = {
                "language": args.lang,
                "is_draft": False,
            }
            files = {
                "file": (f"captions_{args.lang}.srt", args.srt_buffer, "text/plain"),
            }
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="POST",
                path=path,
                query=None,
                body=None,
                form=form,
                files=files,
                required_scopes=PAGE_CONTENT_SCOPES,
                token_hint=TokenType.PAGE,
                idempotency=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="ig.media.create", structured_output=True)
    async def ig_media_create(args: IgMediaCreate, ctx: Context) -> Mapping[str, object]:
        try:
            access_token, metadata = await ensure_scopes(
                env=env,
                ctx=ctx,
                required_scopes=IG_CONTENT_SCOPES,
                token_hint=TokenType.INSTAGRAM,
            )
            await env.token_service.ensure_instagram_business(metadata)
            body = {
                "media_type": args.media_type,
            }
            if args.caption is not None:
                body["caption"] = args.caption
            if args.items is not None:
                body["children"] = args.items
            if args.image_url is not None:
                body["image_url"] = str(args.image_url)
            if args.video_url is not None:
                body["video_url"] = str(args.video_url)
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="POST",
                path=f"/{version}/{args.ig_user_id}/media",
                query=None,
                body=body,
                form=None,
                files=None,
                required_scopes=IG_CONTENT_SCOPES,
                token_hint=TokenType.INSTAGRAM,
                idempotency=True,
                provided_token=access_token,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="page.photos.create", structured_output=True)
    async def page_photos_create(args: PagePhotosCreate, ctx: Context) -> Mapping[str, object]:
        try:
            form: dict[str, object] = {}
            files = None
            if args.url is not None:
                form["url"] = str(args.url)
            if args.file is not None:
                files = {"source": ("photo.jpg", args.file, "image/jpeg")}
            if args.caption is not None:
                form["caption"] = args.caption
            if args.published is not None:
                form["published"] = args.published
            if args.scheduled_publish_time is not None:
                form["scheduled_publish_time"] = int(args.scheduled_publish_time.timestamp())
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="POST",
                path=f"/{version}/{args.page_id}/photos",
                query=None,
                body=None,
                form=form if form else None,
                files=files,
                required_scopes=PAGE_CONTENT_SCOPES,
                token_hint=TokenType.PAGE,
                idempotency=True,
            )
        except MCPException as exc:
            return failure(exc.error)

    @server.tool(name="page.videos.create", structured_output=True)
    async def page_videos_create(args: PageVideosCreate, ctx: Context) -> Mapping[str, object]:
        try:
            form: dict[str, object] = {}
            files = None
            if args.url is not None:
                form["file_url"] = str(args.url)
            if args.file is not None:
                files = {"source": ("video.mp4", args.file, "video/mp4")}
            if args.description is not None:
                form["description"] = args.description
            if args.title is not None:
                form["title"] = args.title
            if args.published is not None:
                form["published"] = args.published
            if args.scheduled_publish_time is not None:
                form["scheduled_publish_time"] = int(args.scheduled_publish_time.timestamp())
            return await perform_graph_call(
                env=env,
                ctx=ctx,
                method="POST",
                path=f"/{version}/{args.page_id}/videos",
                query=None,
                body=None,
                form=form if form else None,
                files=files,
                required_scopes=PAGE_CONTENT_SCOPES,
                token_hint=TokenType.PAGE,
                idempotency=True,
            )
        except MCPException as exc:
            return failure(exc.error)


__all__ = ["register"]
