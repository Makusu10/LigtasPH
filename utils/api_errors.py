"""Standardized API error formatting for LigtasPH.

Follows the One-Version Rule & Hyrum's Law:
Retains top-level 'error' string and 'retry' boolean for backward compatibility
with existing tests and frontends, while providing machine-readable 'code'
and structured 'details'.
"""

from __future__ import annotations

from typing import Any
from flask import jsonify, Response


def api_error(
    message: str,
    status_code: int = 400,
    code: str = "BAD_REQUEST",
    retry: bool = False,
    details: dict[str, Any] | None = None,
) -> tuple[Response, int]:
    """Return a consistent API error tuple (response, status_code)."""
    payload: dict[str, Any] = {
        "error": message,
        "code": code,
        "retry": retry,
        "details": details if details is not None else {},
    }
    return jsonify(payload), status_code
