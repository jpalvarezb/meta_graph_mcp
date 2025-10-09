"""Error definitions mapping Graph errors to MCP error model."""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping

from pydantic import BaseModel, Field


class McpErrorCode(str, Enum):
    AUTH = "AUTH"
    PERMISSION = "PERMISSION"
    RATE_LIMIT = "RATE_LIMIT"
    VALIDATION = "VALIDATION"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    REMOTE_5XX = "REMOTE_5XX"
    UNSUPPORTED = "UNSUPPORTED"


class McpError(BaseModel):
    """Typed error returned to MCP clients."""

    code: McpErrorCode
    message: str
    details: Mapping[str, Any] | None = None
    retry_after: float | None = Field(default=None, description="Retry hint in seconds")

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "code": self.code.value,
            "message": self.message,
        }
        if self.details:
            payload["details"] = dict(self.details)
        if self.retry_after is not None:
            payload["retry_after"] = self.retry_after
        return payload


class MCPException(RuntimeError):
    """Internal exception carrying an MCP error payload."""

    def __init__(self, error: McpError):
        super().__init__(error.message)
        self.error = error


def error_response(error: McpError, *, meta: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    """Build a JSON error response."""

    return {
        "ok": False,
        "error": error.to_dict(),
        "meta": meta or {},
    }


__all__ = ["McpError", "McpErrorCode", "MCPException", "error_response"]
