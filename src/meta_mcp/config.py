"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MetaMcpSettings(BaseSettings):
    """Configuration for the Meta MCP server."""

    model_config = SettingsConfigDict(env_prefix="META_MCP_", extra="ignore")

    graph_api_base_url: str = Field(
        default="https://graph.facebook.com",
        description="Base URL of the Meta Graph API",
    )
    facebook_oauth_base_url: str = Field(
        default="https://www.facebook.com",
        description="Base URL for Meta OAuth dialog",
    )
    graph_api_version: str = Field(
        default="v18.0",
        description="Graph API version to target",
    )
    marketing_api_version: str = Field(
        default="v18.0",
        description="Marketing API version to target",
    )
    app_id: str = Field(..., description="Meta App ID")
    app_secret: SecretStr = Field(..., description="Meta App secret for signature verification")
    verify_token: str = Field(..., description="Webhook verification token")
    oauth_redirect_uri: str = Field(
        default="http://localhost:8000/oauth/callback",
        description="Default OAuth redirect URI used during login flow",
    )
    system_user_access_token: SecretStr | None = Field(
        default=None,
        description="System user token used for app-level actions",
    )
    default_timeout_seconds: float = Field(default=30.0, ge=1.0, description="HTTP request timeout")
    max_retries: int = Field(default=5, ge=0, le=10, description="Maximum HTTP retry attempts")
    retry_backoff_factor: float = Field(default=0.5, description="Base backoff factor in seconds")
    retry_backoff_max: float = Field(default=30.0, description="Maximum backoff in seconds")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./meta_mcp.db",
        description="SQLAlchemy database URL",
    )
    cache_maxsize: int = Field(default=256, ge=0, description="Maximum entries for in-memory caches")
    rate_limit_per_app: int = Field(default=90, ge=1, description="Requests per minute allowance")
    rate_limit_per_token: int = Field(default=30, ge=1, description="Per-token requests per minute")
    webhook_queue_workers: int = Field(default=2, ge=1, description="Webhook worker concurrency")
    enable_request_logging: bool = Field(default=False, description="Emit request/response logs")
    pii_redaction_keys: Sequence[str] = Field(
        default=("access_token", "authorization", "password"),
        description="Keys that should be redacted in logs",
    )

    @field_validator("graph_api_version", "marketing_api_version")
    def _validate_version(cls, value: str) -> str:
        if not value.startswith("v"):
            msg = "Graph/Marketing API versions must be prefixed with 'v'"
            raise ValueError(msg)
        return value


@lru_cache(maxsize=1)
def get_settings() -> MetaMcpSettings:
    """Return cached settings instance."""

    return MetaMcpSettings()  # type: ignore[call-arg]


__all__ = ["MetaMcpSettings", "get_settings"]
