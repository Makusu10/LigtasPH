"""One-time converter: Project NOAH shapefiles (in NOAH/*.zip) -> simplified GeoJSON.

Build-only tool — NOT used at runtime. Requires: pip install pyshp shapely
(dev machines only; these are intentionally NOT in requirements.txt so the
deployed app stays dependency-free and serves pre-built static files).

Usage:
    .venv/bin/python scripts/convert_noah.py
    .venv/bin/python scripts/convert_noah.py --tol-flood 0.0006 --min-area 1e-8

Notes:
- All NOAH sources here are already EPSG:4326 (WGS84), Metro Manila bbox.
- Each source has exactly 3 polygon records with a numeric class field
  (Var / LH / HAZ) valued 1/2/3, mapped to low/moderate/high per the NOAH
  Low-Moderate-High hazard legend.
- pyshp POLYGON parts mix outer rings and holes; holes are rendered as
  filled rings (precautionary: never understate a hazard on a civic map).
- Simplification: shapely simplify() per ring + drop of sub-threshold
  slivers + coordinate rounding. Tuned so each output stays ~<=2MB.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

LEVELS = {1: "low", 2: "moderate", 3: "high"}

LAYERS = {
    # out_name: (zip_relpath, hazard_label, advisory, tolerance, min_area, decimals)
    "flood_mm_5yr": (
        "NOAH/Flood/Metro Manila.zip", "flood", "5-year return", 0.0008, 5e-8, 4,
    ),
    "landslide_mm": (
        "NOAH/Landslide/MetroManila.zip", "landslide", None, 0.0003, 1e-9, 5,
    ),
    "stormsurge_ssa1": (
        "NOAH/Storm Surge/StormSurgeAdvisory1/MetroManila.zip",
        "storm-surge", "SSA1", 0.0003, 1e-9, 5,
    ),
    "stormsurge_ssa2": (
        "NOAH/Storm Surge/StormSurgeAdvisory2/MetroManila.zip",
        "storm-surge", "SSA2", 0.0003, 1e-9, 5,
    ),
    "stormsurge_ssa3": (
        "NOAH/Storm Surge/StormSurgeAdvisory3/MetroManila.zip",
        "storm-surge", "SSA3", 0.0003, 1e-9, 5,
    ),
    "stormsurge_ssa4": (
        "NOAH/Storm Surge/StormSurgeAdvisory4/MetroManila.zip",
        "storm-surge", "SSA4", 0.0003, 1e-9, 5,
    ),
}


def convert_one(zip_path: Path, tol: float, min_area: float, decimals: int,
                hazard: str, advisory: str | None) -> dict:
    import shapefile  # pyshp, build-only
    from shapely.geometry import Polygon

    with zipfile.ZipFile(zip_path) as z:
        base = next(n[:-4] for n in z.namelist() if n.endswith(".shp"))
        with tempfile.TemporaryDirectory() as td:
            for ext in (".shp", ".shx", ".dbf"):
                Path(td, "t" + ext).write_bytes(z.read(base + ext))
            reader = shapefile.Reader(str(Path(td, "t")))

            buckets: dict[str, list] = {"low": [], "moderate": [], "high": []}
            for shape, record in zip(reader.shapes(), reader.records()):
                level = LEVELS.get(int(float(record[0])), "moderate")
                idx = list(shape.parts) + [len(shape.points)]
                for i in range(len(shape.parts)):
                    ring = shape.points[idx[i]:idx[i + 1]]
                    if len(ring) < 4:
                        continue
                    try:
                        poly = Polygon(ring)
                    except Exception:
                        continue
                    if poly.is_empty or poly.area < min_area:
                        continue
                    if not poly.is_valid:
                        poly = poly.buffer(0)
                        if poly.is_empty:
                            continue
                    simp = poly.simplify(tol, preserve_topology=True)
                    if simp.is_empty or simp.area < min_area:
                        continue
                    geom = simp
                    if geom.geom_type == "Polygon":
                        polys = [geom]
                    elif geom.geom_type == "MultiPolygon":
                        polys = list(geom.geoms)
                    else:
                        continue
                    for p in polys:
                        if p.area < min_area:
                            continue
                        coords = [
                            [round(x, decimals), round(y, decimals)]
                            for x, y in p.exterior.coords
                        ]
                        if len(coords) < 4:
                            continue
                        buckets[level].append([coords])

    features = []
    for level, polys in buckets.items():
        if not polys:
            continue
        props = {"hazard": hazard, "level": level}
        if advisory:
            props["advisory"] = advisory
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": {"type": "MultiPolygon", "coordinates": polys},
        })
    return {"type": "FeatureCollection", "features": features,
            "properties": {"source": "Project NOAH (DOST)", "hazard": hazard,
                           "advisory": advisory}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tol-flood", type=float, default=None)
    ap.add_argument("--min-area", type=float, default=None)
    args = ap.parse_args()

    out_dir = ROOT / "static" / "noah"
    out_dir.mkdir(parents=True, exist_ok=True)

    for name, (rel, hazard, advisory, tol, min_area, dec) in LAYERS.items():
        if name == "flood_mm_5yr":
            if args.tol_flood is not None:
                tol = args.tol_flood
            if args.min_area is not None:
                min_area = args.min_area
        src = ROOT / rel
        if not src.exists():
            print(f"SKIP {name}: missing {rel}")
            continue
        print(f"Converting {name} from {rel} ...", flush=True)
        fc = convert_one(src, tol, min_area, dec, hazard, advisory)
        dest = out_dir / f"{name}.geojson"
        dest.write_text(json.dumps(fc, separators=(",", ":")))
        kb = dest.stat().st_size / 1024
        n_poly = sum(len(f["geometry"]["coordinates"]) for f in fc["features"])
        print(f"  wrote {dest.relative_to(ROOT)} ({kb:.0f} KB, "
              f"{len(fc['features'])} levels, {n_poly} polygons)")


if __name__ == "__main__":
    main()
