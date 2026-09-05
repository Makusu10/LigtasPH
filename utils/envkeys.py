"""Admin-side provider API key management (.env file).

Only ever shows masked values to the browser — full secrets stay on disk.
Placeholders (YOUR_*, MY_*) and blanks count as "not set".
"""
from pathlib import Path

from dotenv import set_key, dotenv_values

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

# key -> (label, help)
MANAGED_KEYS = {
    "OPENWEATHER_API_KEY": (
        "OpenWeather",
        "Live weather + air-quality fallback. Empty = Open-Meteo only (no key needed).",
    ),
    "MAPBOX_TOKEN": (
        "Mapbox (public pk.*)",
        "2D/3D maps, search + routing. Must start with pk. — never use a secret sk.* token. Empty = OSM fallback.",
    ),
    "FIRMS_MAP_KEY": (
        "NASA FIRMS",
        "Active-fire layer. Free at firms.modaps.eosdis.nasa.gov/api. Empty = /api/fires returns 503.",
    ),
    "GEMINI_API_KEY": (
        "Gemini AI",
        "Reserved for future AI assistance. Unused by current features.",
    ),
}

_PLACEHOLDER_PREFIXES = ("YOUR_", "MY_")


def _raw(key):
    import os
    # .env file value wins for display; fall back to process env so
    # container-injected keys (Render, etc.) still show as configured.
    try:
        vals = dotenv_values(ENV_PATH)
        v = (vals.get(key) or "").strip().strip("\"").strip("'")
        if v:
            return v
    except Exception:
        pass
    import os as _os
    return (_os.getenv(key, "") or "").strip()


def is_set(value):
    v = (value or "").strip()
    return bool(v) and not v.startswith(_PLACEHOLDER_PREFIXES)


def mask(value):
    v = (value or "").strip()
    if not is_set(v):
        return ""
    tail = v[-4:] if len(v) >= 4 else "••••"
    return "••••••••" + tail


def entries(overrides=None):
    """Build display rows. overrides (e.g. live app.config) win so the page
    reflects what the server is actually using right now."""
    overrides = overrides or {}
    out = []
    for key, (label, help_text) in MANAGED_KEYS.items():
        raw = (overrides.get(key, "") or "").strip() or _raw(key)
        out.append({
            "key": key, "label": label, "help": help_text,
            "configured": is_set(raw), "masked": mask(raw),
        })
    return out


def save(updates):
    """Persist non-empty values to .env. Returns list of keys changed."""
    changed = []
    for key in MANAGED_KEYS:
        v = (updates.get(key, "") or "").strip()
        if not v:
            continue  # empty = keep current
        set_key(str(ENV_PATH), key, v)
        changed.append(key)
    return changed
