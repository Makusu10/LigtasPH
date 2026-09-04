"""Static Project NOAH overlay contract — simplified GeoJSON in static/noah/.

Built once via scripts/convert_noah.py from the local NOAH/*.zip sources
(Metro Manila flood 5-yr, landslide, storm-surge SSA1-4). The map page
loads these as static files, so these tests guard the files the frontend
depends on: presence, valid GeoJSON, Metro Manila bbox, level legend.
"""

import json
from pathlib import Path

import pytest

NOAH_DIR = Path(__file__).resolve().parent.parent / "static" / "noah"

EXPECTED = [
    "flood_mm_5yr.geojson",
    "landslide_mm.geojson",
    "stormsurge_ssa1.geojson",
    "stormsurge_ssa2.geojson",
    "stormsurge_ssa3.geojson",
    "stormsurge_ssa4.geojson",
]

MAX_BYTES = 2 * 1024 * 1024  # map must stay fast on mobile data


@pytest.mark.parametrize("name", EXPECTED)
def test_noah_file_present_and_small(name):
    p = NOAH_DIR / name
    assert p.exists(), f"missing {p} — run scripts/convert_noah.py"
    assert p.stat().st_size < MAX_BYTES, f"{name} too large for browsers"


@pytest.mark.parametrize("name", EXPECTED)
def test_noah_valid_featurecollection_with_levels(name):
    fc = json.loads((NOAH_DIR / name).read_text(encoding="utf-8"))
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 3  # low / moderate / high
    levels = sorted(f["properties"]["level"] for f in fc["features"])
    assert levels == ["high", "low", "moderate"]
    for feat in fc["features"]:
        assert feat["geometry"]["type"] == "MultiPolygon"
        assert len(feat["geometry"]["coordinates"]) > 0


@pytest.mark.parametrize("name", EXPECTED)
def test_noah_bbox_inside_ph(name):
    fc = json.loads((NOAH_DIR / name).read_text(encoding="utf-8"))
    xs, ys = [], []
    for feat in fc["features"]:
        for poly in feat["geometry"]["coordinates"]:
            for ring in poly:
                for x, y in ring:
                    xs.append(x)
                    ys.append(y)
    assert xs and ys
    assert 116.0 <= min(xs) and max(xs) <= 127.0
    assert 4.0 <= min(ys) and max(ys) <= 22.0
    # Metro Manila focus — not an empty/world-wide dump
    assert max(xs) - min(xs) < 3.0
    assert max(ys) - min(ys) < 3.0


def test_map_page_references_noah_overlays():
    html = (Path(__file__).resolve().parent.parent
            / "templates" / "public" / "map.html").read_text(encoding="utf-8")
    for token in ("hzFlood", "hzSlide", "hzSurge", "hzSSA",
                  "stormsurge_", "flood_mm_5yr", "landslide_mm"):
        assert token in html, f"map.html missing {token}"


def test_map_hazard_visibility_helpers():
    # Detections often sit far outside the viewport while counts look
    # healthy: Show-hazards button, dot floor, and in-view hints.
    root = Path(__file__).resolve().parent.parent
    html = (root / "templates" / "public" / "map.html").read_text(encoding="utf-8")
    for token in ("showHazardsBtn", "zoomToHazards", "zoomToHazardsFb",
                  "inViewCount", "inViewCountFb", "in view",
                  "'max', 6", "quake-pulse"):
        assert token in html, f"map.html missing visibility token {token}"
    css = (root / "static" / "css" / "main.css").read_text(encoding="utf-8")
    assert ".quake-pulse" in css
    assert "#9333ea" in css  # quake purple matches Mapbox markers


def test_map_hazard_area_overlays():
    # Detected hazards (quakes/fires) render estimated affected-area rings
    # in both engines, with popups disclosing the estimate.
    html = (Path(__file__).resolve().parent.parent
            / "templates" / "public" / "map.html").read_text(encoding="utf-8")
    for token in ("circlePolygon", "quakeRadiusKm", "fireRadiusKm",
                  "hz-quake-area-layer", "hz-fire-area-layer",
                  "hz-quake-area", "hz-fire-area",
                  "QUAKE_RING_NOTE", "FIRE_RING_NOTE",
                  "L.circle", "Est. felt radius"):
        assert token in html, f"map.html missing area-overlay token {token}"


def test_map_page_has_panel_tabs():
    html = (Path(__file__).resolve().parent.parent
            / "templates" / "public" / "map.html").read_text(encoding="utf-8")
    for token in ("panelTabs", "tabBtnCenters", "tabBtnHazards",
                  "tabBtnRoutes", "tabCenters", "tabHazards",
                  "tabRoutes", "hzBadge", "switchPanelTab",
                  "hazardSelection", "setStatus"):
        assert token in html, f"map.html missing tab/dedup token {token}"
    # Single location entry lives in the Routes tab next to GPS status.
    assert html.count('id="locBtn"') == 1
    assert html.index('id="gpsStatus"') < html.index('id="locBtn"') < html.index('id="routeStatus"')
    # Centers list lives inside the Centers tab panel.
    assert html.index('id="tabCenters"') < html.index('id="list"') < html.index('id="tabRoutes"')
