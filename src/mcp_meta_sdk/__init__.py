"""Thin client SDK for the Meta MCP server."""

from __future__ import annotations

from importlib import metadata as _metadata

from .client import MetaMcpSdk, ToolExecutionError, ToolResponseError

try:
    __version__ = _metadata.version("meta-mcp")
except _metadata.PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

__all__ = ["MetaMcpSdk", "ToolExecutionError", "ToolResponseError", "__version__"]
