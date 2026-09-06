"""Boundary validation utilities for LigtasPH API endpoints.

Validates external inputs (coordinates, query parameters, pagination) at the
system boundary before passing typed, sanitized values into internal handlers.
"""

from __future__ import annotations

import math
from typing import Any, Mapping


def validate_coordinates(
    lat_val: Any,
    lon_val: Any,
    required: bool = False,
) -> tuple[float | None, float | None, str | None]:
    """Validate latitude and longitude inputs.

    Accepts numbers or string numbers. Enforces valid WGS84 ranges:
      - Latitude: -90.0 to 90.0
      - Longitude: -180.0 to 180.0

    Returns:
        (lat_float, lon_float, error_message)
        If valid, error_message is None.
        If invalid, lat_float and lon_float are None and error_message is a string.
    """
    has_lat = lat_val not in (None, "")
    has_lon = lon_val not in (None, "")

    if not has_lat and not has_lon:
        if required:
            return None, None, "Both lat and lon are required"
        return None, None, None

    if has_lat != has_lon:
        return None, None, "Both lat and lon are required"

    try:
        lat = float(lat_val)
        lon = float(lon_val)
        if math.isnan(lat) or math.isnan(lon) or math.isinf(lat) or math.isinf(lon):
            return None, None, "Invalid coordinates"
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return None, None, "Invalid coordinates"
        return lat, lon, None
    except (TypeError, ValueError):
        return None, None, "Invalid coordinates"


def parse_pagination(
    args: Mapping[str, Any],
    default_limit: int | None = None,
    max_limit: int = 200,
) -> tuple[int | None, int | None, int, bool]:
    """Extract pagination parameters from query string.

    Supports:
      - limit / pageSize
      - page (1-indexed) / offset

    Returns:
        (limit, offset, page, is_paginated)
        If no pagination parameters were requested and default_limit is None,
        returns (None, None, 1, False) to preserve backward compatibility (Hyrum's Law).
    """
    limit_raw = args.get("limit") or args.get("pageSize")
    page_raw = args.get("page")
    offset_raw = args.get("offset")

    is_paginated = bool(limit_raw or page_raw or offset_raw or default_limit is not None)
    if not is_paginated:
        return None, None, 1, False

    try:
        limit = int(limit_raw) if limit_raw is not None else (default_limit or 50)
        limit = max(1, min(limit, max_limit))
    except (TypeError, ValueError):
        limit = default_limit or 50

    try:
        if page_raw is not None:
            page = max(1, int(page_raw))
            offset = (page - 1) * limit
        elif offset_raw is not None:
            offset = max(0, int(offset_raw))
            page = (offset // limit) + 1
        else:
            page = 1
            offset = 0
    except (TypeError, ValueError):
        page = 1
        offset = 0

    return limit, offset, page, True
