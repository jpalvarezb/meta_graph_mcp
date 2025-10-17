"""Meta OAuth login helpers."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Sequence

import httpx

from ..config import MetaMcpSettings


def generate_state(length: int = 32) -> str:
    """Generate a URL-safe state token."""

    return secrets.token_urlsafe(length)


class MetaOAuthClient:
    """Handle Meta OAuth login flows."""

    def __init__(self, settings: MetaMcpSettings) -> None:
        self._settings = settings

    def build_authorization_url(
        self,
        *,
        scopes: Sequence[str],
        redirect_uri: str,
        state: str,
    ) -> str:
        base = self._settings.facebook_oauth_base_url.rstrip("/")
        version = self._settings.graph_api_version
        scope_value = ",".join(sorted(set(scopes)))
        params = {
            "client_id": self._settings.app_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": scope_value,
            "response_type": "code",
        }
        url = httpx.URL(f"{base}/{version}/dialog/oauth")
        return str(url.copy_with(params=params))

    async def exchange_code(
        self,
        *,
        code: str,
        redirect_uri: str,
    ) -> dict[str, object]:
        params = {
            "client_id": self._settings.app_id,
            "client_secret": self._settings.app_secret.get_secret_value(),
            "redirect_uri": redirect_uri,
            "code": code,
        }
        async with httpx.AsyncClient(timeout=self._settings.default_timeout_seconds) as client:
            response = await client.get(
                f"{self._settings.graph_api_base_url}/{self._settings.graph_api_version}/oauth/access_token",
                params=params,
            )
            response.raise_for_status()
            payload = response.json()

        access_token = payload.get("access_token")
        token_type = payload.get("token_type", "bearer")
        expires_in = payload.get("expires_in")
        expires_at = None
        if isinstance(expires_in, (int, float)):
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=float(expires_in))

        return {
            "access_token": access_token,
            "token_type": token_type,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "raw": payload,
        }
