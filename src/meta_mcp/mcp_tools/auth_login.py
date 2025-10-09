"""OAuth login tools for generating login URLs and exchanging codes."""

from __future__ import annotations

from datetime import datetime
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


def register(server: FastMCP, env: ToolEnvironment) -> None:
    oauth_client = MetaOAuthClient(env.settings)

    @server.tool(name="auth.login.begin", structured_output=True)
    async def login_begin(args: AuthLoginBeginRequest, ctx: Context) -> Mapping[str, object]:
        del ctx
        redirect_uri = str(args.redirect_uri or env.settings.oauth_redirect_uri)
        state = args.state or generate_state(16)
        scopes = list(args.scopes)
        url = oauth_client.build_authorization_url(scopes=scopes, redirect_uri=redirect_uri, state=state)
        response = AuthLoginBeginResponse(
            authorization_url=url,
            state=state,
            redirect_uri=redirect_uri,
            scopes=scopes,
        )
        return success(response.model_dump(mode="json"))

    @server.tool(name="auth.login.complete", structured_output=True)
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
        token_expires = token_info.get("expires_at")
        if expires_at is None and isinstance(token_expires, str):
            try:
                expires_at = datetime.fromisoformat(token_expires)
            except ValueError:
                expires_at = None

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
