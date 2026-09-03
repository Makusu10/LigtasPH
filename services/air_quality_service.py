"""Air-quality service for LigtasPH.

Primary provider:
    Open-Meteo Air Quality API, which requires no API key.

Optional fallback:
    OpenWeather Air Pollution API, when OPENWEATHER_API_KEY is configured.

Classification:
    PM2.5 concentrations are classified using the Philippine categories defined
    in DENR Administrative Order No. 2020-14.

Important:
    Provider-specific AQI values remain separate. Open-Meteo's US AQI is labeled
    as "US EPA AQI", while OpenWeather's 1-5 index remains labeled as
    "OpenWeather AQI". Neither value is converted into the other.
"""

from __future__ import annotations

import json
import math
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from flask import current_app

from utils.environment import classify_pm25


OPEN_METEO_AQ_ENDPOINT = (
    "https://air-quality-api.open-meteo.com/v1/air-quality"
)

OPENWEATHER_AQ_ENDPOINT = (
    "https://api.openweathermap.org/data/2.5/air_pollution"
)

OPEN_METEO_CURRENT_FIELDS = (
    "us_aqi",
    "pm2_5",
    "pm10",
    "carbon_monoxide",
    "nitrogen_dioxide",
    "ozone",
    "sulphur_dioxide",
)

CACHE_SOURCE = "air-quality"
DEFAULT_CACHE_MAX_AGE_SECONDS = 10 * 60
DEFAULT_STALE_MAX_AGE_SECONDS = 60 * 60
DEFAULT_REQUEST_TIMEOUT_SECONDS = 5
MAX_RESPONSE_BYTES = 1_000_000


class AirQualityServiceError(Exception):
    """Base exception for air-quality service failures."""


class AirQualityProviderError(AirQualityServiceError):
    """Raised when an external provider returns unusable data."""


def _validate_coordinates(lat: Any, lon: Any) -> tuple[float, float]:
    """Validate and normalize geographic coordinates."""

    try:
        normalized_lat = float(lat)
        normalized_lon = float(lon)
    except (TypeError, ValueError) as exc:
        raise ValueError("Latitude and longitude must be numbers.") from exc

    if not math.isfinite(normalized_lat):
        raise ValueError("Latitude must be a finite number.")

    if not math.isfinite(normalized_lon):
        raise ValueError("Longitude must be a finite number.")

    if not -90 <= normalized_lat <= 90:
        raise ValueError("Latitude must be between -90 and 90.")

    if not -180 <= normalized_lon <= 180:
        raise ValueError("Longitude must be between -180 and 180.")

    # Rounding prevents tiny coordinate differences from creating duplicate
    # cache entries for effectively identical locations.
    return round(normalized_lat, 5), round(normalized_lon, 5)


def _optional_number(value: Any) -> float | int | None:
    """Return a finite numerical value or None."""

    if value is None or isinstance(value, bool):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    if number.is_integer():
        return int(number)

    return number


def _fetch_json(
    endpoint: str,
    params: dict[str, Any],
    timeout: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Request and decode a JSON object from an HTTP endpoint."""

    query = urllib.parse.urlencode(params, safe=",")
    url = f"{endpoint}?{query}"

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "LigtasPH/1.0 (air-quality service)",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)

            if not 200 <= status < 300:
                raise AirQualityProviderError(
                    f"Air-quality provider returned HTTP {status}."
                )

            raw = response.read(MAX_RESPONSE_BYTES + 1)

    except urllib.error.HTTPError as exc:
        raise AirQualityProviderError(
            f"Air-quality provider returned HTTP {exc.code}."
        ) from exc

    except urllib.error.URLError as exc:
        raise AirQualityProviderError(
            f"Could not connect to the air-quality provider: {exc.reason}"
        ) from exc

    except TimeoutError as exc:
        raise AirQualityProviderError(
            "The air-quality provider request timed out."
        ) from exc

    if len(raw) > MAX_RESPONSE_BYTES:
        raise AirQualityProviderError(
            "The air-quality provider response was unexpectedly large."
        )

    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AirQualityProviderError(
            "The air-quality provider returned invalid JSON."
        ) from exc

    if not isinstance(result, dict):
        raise AirQualityProviderError(
            "The air-quality provider returned an unexpected response."
        )

    if result.get("error") is True:
        reason = result.get("reason") or "Unknown provider error."
        raise AirQualityProviderError(str(reason))

    return result


def _get_cached_row(
    db: sqlite3.Connection,
    lat: float,
    lon: float,
    city: str | None,
) -> sqlite3.Row | None:
    """Return the newest matching air-quality cache row."""

    # Coordinates identify the actual reading location more reliably than a
    # city name. City remains stored for display purposes.
    row = db.execute(
        """
        SELECT
            id,
            city,
            lat,
            lng,
            source,
            payload,
            fetched_at,
            (julianday('now') - julianday(fetched_at)) * 86400 AS age_seconds
        FROM weather_cache
        WHERE source = ?
          AND ABS(lat - ?) < 0.00001
          AND ABS(lng - ?) < 0.00001
        ORDER BY fetched_at DESC
        LIMIT 1
        """,
        (CACHE_SOURCE, lat, lon),
    ).fetchone()

    if row is not None or not city:
        return row

    # This fallback supports older cache records that may not have reliable
    # coordinates. COLLATE NOCASE avoids duplicate misses caused by casing.
    return db.execute(
        """
        SELECT
            id,
            city,
            lat,
            lng,
            source,
            payload,
            fetched_at,
            (julianday('now') - julianday(fetched_at)) * 86400 AS age_seconds
        FROM weather_cache
        WHERE source = ?
          AND city = ? COLLATE NOCASE
        ORDER BY fetched_at DESC
        LIMIT 1
        """,
        (CACHE_SOURCE, city.strip()),
    ).fetchone()


def get_cached_aq(
    db: sqlite3.Connection,
    lat: float,
    lon: float,
    city: str | None = None,
    max_age_sec: int = DEFAULT_CACHE_MAX_AGE_SECONDS,
) -> dict[str, Any] | None:
    """Return cached air-quality data when it is within the allowed age."""

    try:
        row = _get_cached_row(db, lat, lon, city)

        if row is None:
            return None

        age_seconds = row["age_seconds"]

        if age_seconds is None:
            return None

        if float(age_seconds) < 0:
            current_app.logger.warning(
                "Air-quality cache row %s has a future fetched_at value.",
                row["id"],
            )
            return None

        if float(age_seconds) > max_age_sec:
            return None

        payload = json.loads(row["payload"])

        if not isinstance(payload, dict):
            return None

        result = dict(payload)
        result["_cached"] = True
        result["_cache_age_seconds"] = round(float(age_seconds))
        return result

    except (
        sqlite3.Error,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        current_app.logger.warning(
            "Could not read the air-quality cache: %s",
            exc,
        )
        return None


def cache_aq(
    db: sqlite3.Connection,
    lat: float,
    lon: float,
    city: str | None,
    payload: dict[str, Any],
) -> None:
    """Store a successful air-quality response."""

    try:
        db.execute(
            """
            INSERT INTO weather_cache (
                city,
                lat,
                lng,
                source,
                payload
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                city or f"{lat},{lon}",
                lat,
                lon,
                CACHE_SOURCE,
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            ),
        )
        db.commit()

    except (sqlite3.Error, TypeError, ValueError) as exc:
        current_app.logger.warning(
            "Could not cache air-quality data: %s",
            exc,
        )


def fetch_open_meteo_aq(
    lat: float,
    lon: float,
    city: str | None = None,
    timeout: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Fetch current air-quality conditions from Open-Meteo."""

    data = _fetch_json(
        OPEN_METEO_AQ_ENDPOINT,
        {
            "latitude": lat,
            "longitude": lon,
            "current": ",".join(OPEN_METEO_CURRENT_FIELDS),
            "timezone": "Asia/Manila",
        },
        timeout=timeout,
    )

    current = data.get("current")

    if not isinstance(current, dict) or not current:
        raise AirQualityProviderError(
            "Open-Meteo did not provide current air-quality data."
        )

    us_aqi = _optional_number(current.get("us_aqi"))
    pm25 = _optional_number(current.get("pm2_5"))
    pm10 = _optional_number(current.get("pm10"))

    if us_aqi is None and pm25 is None and pm10 is None:
        raise AirQualityProviderError(
            "Open-Meteo returned no usable AQI or particulate readings."
        )

    # DENR classification is based specifically on PM2.5 concentration.
    # PM2.5 is therefore the classification pollutant, not automatically the
    # dominant pollutant among every pollutant reported by the provider.
    classification = classify_pm25(pm25)

    provider_lat = _optional_number(data.get("latitude"))
    provider_lon = _optional_number(data.get("longitude"))

    return {
        "source": "open-meteo-air",
        "provider": "Open-Meteo",
        "city": city or "",
        "lat": provider_lat if provider_lat is not None else lat,
        "lon": provider_lon if provider_lon is not None else lon,
        "timezone": data.get("timezone") or "Asia/Manila",

        # Provider-supplied numerical AQI. It remains explicitly labeled.
        "aqi": us_aqi,
        "aqi_scale": "US EPA AQI" if us_aqi is not None else None,

        # Philippine public-health classification based on PM2.5.
        "pm25": pm25,
        "pm25_unit": "µg/m³",
        "pm10": pm10,
        "pm10_unit": "µg/m³",
        "classification_pollutant": "PM2.5" if pm25 is not None else None,
        "classification_scale": (
            "DENR DAO 2020-14 PM2.5"
            if pm25 is not None
            else None
        ),
        "category": classification["category"],
        "color": classification["color"],
        "recommendation": classification["recommendation"],
        "severity": classification["severity"],
        "colors": classification["colors"],

        # A true dominant pollutant requires comparing pollutant-specific
        # sub-indices. Do not infer one merely from field availability.
        "dominant_pollutant": None,

        "details": {
            "carbon_monoxide": _optional_number(
                current.get("carbon_monoxide")
            ),
            "nitrogen_dioxide": _optional_number(
                current.get("nitrogen_dioxide")
            ),
            "ozone": _optional_number(current.get("ozone")),
            "sulphur_dioxide": _optional_number(
                current.get("sulphur_dioxide")
            ),
        },
        "detail_units": {
            "carbon_monoxide": "µg/m³",
            "nitrogen_dioxide": "µg/m³",
            "ozone": "µg/m³",
            "sulphur_dioxide": "µg/m³",
        },
        "fetched_at": current.get("time")
        or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "_cached": False,
        "_stale": False,
    }


def fetch_openweather_aq(
    lat: float,
    lon: float,
    key: str,
    city: str | None = None,
    timeout: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Fetch fallback air-quality conditions from OpenWeather."""

    if not key or key == "YOUR_OPENWEATHER_API_KEY":
        raise AirQualityServiceError(
            "A valid OpenWeather API key is required."
        )

    data = _fetch_json(
        OPENWEATHER_AQ_ENDPOINT,
        {
            "lat": lat,
            "lon": lon,
            "appid": key,
        },
        timeout=timeout,
    )

    items = data.get("list")

    if not isinstance(items, list) or not items:
        raise AirQualityProviderError(
            "OpenWeather did not provide current air-quality data."
        )

    item = items[0]

    if not isinstance(item, dict):
        raise AirQualityProviderError(
            "OpenWeather returned an unexpected air-quality response."
        )

    main = item.get("main") or {}
    components = item.get("components") or {}

    if not isinstance(main, dict) or not isinstance(components, dict):
        raise AirQualityProviderError(
            "OpenWeather returned malformed air-quality data."
        )

    openweather_aqi = _optional_number(main.get("aqi"))
    pm25 = _optional_number(components.get("pm2_5"))
    pm10 = _optional_number(components.get("pm10"))

    if openweather_aqi is None and pm25 is None and pm10 is None:
        raise AirQualityProviderError(
            "OpenWeather returned no usable air-quality readings."
        )

    classification = classify_pm25(pm25)

    observed_timestamp = _optional_number(item.get("dt"))

    if observed_timestamp is not None:
        fetched_at = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(observed_timestamp),
        )
    else:
        fetched_at = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(),
        )

    # OpenWeather AQI is a categorical 1-5 index. It is intentionally not
    # converted into a US EPA AQI value.
    return {
        "source": "openweather-air",
        "provider": "OpenWeather",
        "city": city or "",
        "lat": lat,
        "lon": lon,
        "timezone": "UTC",

        "aqi": openweather_aqi,
        "aqi_scale": (
            "OpenWeather AQI 1-5"
            if openweather_aqi is not None
            else None
        ),

        "pm25": pm25,
        "pm25_unit": "µg/m³",
        "pm10": pm10,
        "pm10_unit": "µg/m³",
        "classification_pollutant": "PM2.5" if pm25 is not None else None,
        "classification_scale": (
            "DENR DAO 2020-14 PM2.5"
            if pm25 is not None
            else None
        ),
        "category": classification["category"],
        "color": classification["color"],
        "recommendation": classification["recommendation"],
        "severity": classification["severity"],
        "colors": classification["colors"],
        "dominant_pollutant": None,

        "details": {
            name: _optional_number(value)
            for name, value in components.items()
        },
        "detail_units": {
            name: "µg/m³"
            for name in components
        },
        "fetched_at": fetched_at,
        "_cached": False,
        "_stale": False,
    }

def fetch_air_quality(
    db: sqlite3.Connection,
    lat: float = 14.6308,
    lon: float = 121.0968,
    city: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Return air-quality conditions from cache or an external provider.

    Provider order:
        1. Fresh cache
        2. Open-Meteo
        3. OpenWeather, when configured
        4. Stale cache
        5. Unavailable response

    Returns:
        A two-item tuple containing the payload and an error message.
    """

    try:
        lat, lon = _validate_coordinates(lat, lon)
    except ValueError as exc:
        return None, str(exc)

    normalized_city = city.strip() if city and city.strip() else None

    cache_max_age = current_app.config.get(
        "AIR_QUALITY_CACHE_SECONDS",
        DEFAULT_CACHE_MAX_AGE_SECONDS,
    )
    stale_max_age = current_app.config.get(
        "AIR_QUALITY_STALE_SECONDS",
        DEFAULT_STALE_MAX_AGE_SECONDS,
    )
    request_timeout = current_app.config.get(
        "AIR_QUALITY_REQUEST_TIMEOUT",
        DEFAULT_REQUEST_TIMEOUT_SECONDS,
    )

    try:
        cache_max_age = max(0, int(cache_max_age))
        stale_max_age = max(cache_max_age, int(stale_max_age))
        request_timeout = max(1, int(request_timeout))
    except (TypeError, ValueError):
        cache_max_age = DEFAULT_CACHE_MAX_AGE_SECONDS
        stale_max_age = DEFAULT_STALE_MAX_AGE_SECONDS
        request_timeout = DEFAULT_REQUEST_TIMEOUT_SECONDS

    fresh = get_cached_aq(
        db,
        lat,
        lon,
        normalized_city,
        max_age_sec=cache_max_age,
    )

    if fresh is not None:
        return fresh, None

    provider_errors: list[str] = []

    # Open-Meteo is the primary provider because it requires no account or key.
    try:
        payload = fetch_open_meteo_aq(
            lat,
            lon,
            normalized_city,
            timeout=request_timeout,
        )
        cache_aq(db, lat, lon, normalized_city, payload)
        return payload, None

    except (
        AirQualityServiceError,
        urllib.error.URLError,
        TimeoutError,
        ValueError,
    ) as exc:
        current_app.logger.warning(
            "Open-Meteo air-quality request failed: %s",
            exc,
        )
        provider_errors.append(f"Open-Meteo: {exc}")

    # OpenWeather is an optional fallback only.
    openweather_key = str(
        current_app.config.get("OPENWEATHER_API_KEY", "")
    ).strip()

    if (
        openweather_key
        and openweather_key != "YOUR_OPENWEATHER_API_KEY"
    ):
        try:
            payload = fetch_openweather_aq(
                lat,
                lon,
                openweather_key,
                normalized_city,
                timeout=request_timeout,
            )
            cache_aq(db, lat, lon, normalized_city, payload)
            return payload, None

        except (
            AirQualityServiceError,
            urllib.error.URLError,
            TimeoutError,
            ValueError,
        ) as exc:
            current_app.logger.warning(
                "OpenWeather air-quality fallback failed: %s",
                exc,
            )
            provider_errors.append(f"OpenWeather: {exc}")

    stale = get_cached_aq(
        db,
        lat,
        lon,
        normalized_city,
        max_age_sec=stale_max_age,
    )

    if stale is not None:
        stale = dict(stale)
        stale["_stale"] = True
        return stale, None

    if current_app.debug and provider_errors:
        current_app.logger.debug(
            "Air-quality provider failures: %s",
            "; ".join(provider_errors),
        )

    return None, "Air quality is currently unavailable for this location."