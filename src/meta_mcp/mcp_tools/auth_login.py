"""OAuth login tools for generating login URLs and exchanging codes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping

import httpx
from mcp.server.fastmcp import Context, FastMCP

from ..auth import MetaOAuthClient, generate_state
from ..errors import McpError, McpErrorCode
from ..meta_client import (
    AuthLoginBeginRequest,
    AuthLoginBeginResponse,
    AuthLoginCompleteRequest,
    AuthLoginCompleteResponse,
)
from .common import ToolEnvironment, failure, success


DEFAULT_SCOPES = [
    "pages_read_engagement",
    "pages_read_user_content",
    "pages_manage_posts",
    "pages_manage_engagement",
    "pages_read_insights",
    "pages_manage_metadata",
    "instagram_basic",
    "instagram_manage_insights",
    "instagram_content_publish",
    "instagram_manage_comments",
    "pages_show_list",
    "business_management",
    "ads_management",
    "ads_read",
    # "page_public_content_access",  # Requires App Review
]


def register(server: FastMCP, env: ToolEnvironment) -> None:
    oauth_client = MetaOAuthClient(env.settings)

    @server.tool(name="auth.login.begin", structured_output=True, description="Start the OAuth login flow to get an authorization URL. If scopes are not provided, defaults to a comprehensive set for Pages, Instagram, and Ads.")
    async def login_begin(args: AuthLoginBeginRequest, ctx: Context) -> Mapping[str, object]:
        del ctx
        redirect_uri = str(args.redirect_uri or env.settings.oauth_redirect_uri)
        state = args.state or generate_state(16)
        scopes = list(args.scopes) if args.scopes is not None else DEFAULT_SCOPES
        url = oauth_client.build_authorization_url(scopes=scopes, redirect_uri=redirect_uri, state=state)
        response = AuthLoginBeginResponse(
            authorization_url=url,
            state=state,
            redirect_uri=redirect_uri,
            scopes=scopes,
        )
        return success(response.model_dump(mode="json"))

    @server.tool(name="auth.login.complete", structured_output=True, description="Complete the OAuth login flow by exchanging the code for a token.")
    async def login_complete(args: AuthLoginCompleteRequest, ctx: Context) -> Mapping[str, object]:
        del ctx
        if args.expected_state:
            if args.state is None or args.expected_state != args.state:
                return failure(
                    McpError(
                        code=McpErrorCode.VALIDATION,
                        message="State mismatch during OAuth completion",
                        details={"expected_state": args.expected_state, "state": args.state},
                    )
                )

        redirect_uri = str(args.redirect_uri or env.settings.oauth_redirect_uri)
        try:
            token_info = await oauth_client.exchange_code(code=args.code, redirect_uri=redirect_uri)
        except httpx.HTTPStatusError as exc:  # pragma: no cover - exercised in integration tests
            return failure(
                McpError(
                    code=McpErrorCode.AUTH,
                    message="Failed to exchange authorization code",
                    details={"status": exc.response.status_code, "body": exc.response.text},
                )
            )
        except httpx.HTTPError as exc:  # pragma: no cover
            return failure(
                McpError(
                    code=McpErrorCode.REMOTE_5XX,
                    message="Network error during code exchange",
                    details={"error": str(exc)},
                )
            )

        access_token = token_info.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            return failure(
                McpError(
                    code=McpErrorCode.AUTH,
                    message="Token exchange response missing access_token",
                )
            )

        metadata = await env.token_service.inspect_token(access_token=access_token)
        expires_at = metadata.expires_at
        if expires_at is None:
            token_expires = token_info.get("expires_at")
            if isinstance(token_expires, (int, float)):
                expires_at = datetime.fromtimestamp(float(token_expires), tz=timezone.utc)
            elif isinstance(token_expires, str):
                try:
                    dt = datetime.fromisoformat(token_expires)
                    expires_at = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
                except ValueError:
                    expires_at = None

        # Persist the raw token for session reuse
        await env.token_service.save_session_token(
            access_token=access_token,
            scopes=list(metadata.scopes),
            expires_at=expires_at,
        )

        response = AuthLoginCompleteResponse(
            access_token=access_token,
            token_type=str(token_info.get("token_type", "bearer")),
            expires_at=expires_at,
            app_id=metadata.app_id,
            subject_id=metadata.subject_id,
            scopes=list(metadata.scopes),
        )

        meta = {
            "token_subject_id": metadata.subject_id,
            "token_type": metadata.type.value,
        }
        return success(response.model_dump(mode="json"), meta=meta)


__all__ = ["register"]
