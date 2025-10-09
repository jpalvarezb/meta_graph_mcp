from __future__ import annotations

try:
    import pytest_asyncio  # type: ignore  # noqa: F401
    pytest_plugins = ("pytest_asyncio",)
except ModuleNotFoundError:  # pragma: no cover
    pytest_plugins: tuple[str, ...] = tuple()

import asyncio
import os
from collections.abc import AsyncIterator

import pytest

from meta_mcp.config import get_settings
from meta_mcp.storage.db import init_models


@pytest.fixture(autouse=True)
async def configure_settings(tmp_path) -> AsyncIterator[None]:
    """Configure test database and reset cached settings."""

    db_path = tmp_path / "test.db"
    os.environ["META_MCP_DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    os.environ["META_MCP_GRAPH_API_BASE_URL"] = "https://example.com"
    os.environ["META_MCP_APP_ID"] = "app"
    os.environ["META_MCP_APP_SECRET"] = "secret"
    os.environ["META_MCP_VERIFY_TOKEN"] = "verify"
    os.environ["META_MCP_FACEBOOK_OAUTH_BASE_URL"] = "https://example.com"
    os.environ["META_MCP_OAUTH_REDIRECT_URI"] = "https://client.example.com/callback"

    get_settings.cache_clear()
    _ = get_settings()
    await init_models()
    yield
    get_settings.cache_clear()
    os.environ.pop("META_MCP_DATABASE_URL", None)
    os.environ.pop("META_MCP_GRAPH_API_BASE_URL", None)
    os.environ.pop("META_MCP_APP_ID", None)
    os.environ.pop("META_MCP_APP_SECRET", None)
    os.environ.pop("META_MCP_VERIFY_TOKEN", None)
    os.environ.pop("META_MCP_FACEBOOK_OAUTH_BASE_URL", None)
    os.environ.pop("META_MCP_OAUTH_REDIRECT_URI", None)



def pytest_configure(config) -> None:
    config.addinivalue_line("markers", "asyncio: mark async tests")
