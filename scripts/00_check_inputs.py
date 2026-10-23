"""
00 – Check inputs
Lists every raw input from config.INPUTS: exists?, CRS, geometry type,
feature count and attribute fields (with a few example values).
Use the output to fill in config.FIELDS and config.LANDUSE_CLASSES.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geopandas as gpd  # noqa: E402
import pyogrio  # noqa: E402

import config as cfg  # noqa: E402
from peatsh.common import ensure_dirs, get_logger, write_report  # noqa: E402

log = get_logger("00")


def describe(name: str, path: Path) -> list[str]:
    if not path.exists():
        log.warning("%s: MISSING (%s)", name, path)
        return [f"## {name}", f"- **missing** – expected at `{path}`", ""]
    gdf = gpd.read_file(path, rows=500)  # sample is enough for field names
    n = pyogrio.read_info(path)["features"]  # fast count without reading data
    crs = gdf.crs.to_string() if gdf.crs else "NONE"
    flag = "" if crs == cfg.TARGET_CRS else f"  ⚠ differs from {cfg.TARGET_CRS}"
    log.info("%s: %d features, CRS %s", name, n, crs)
    lines = [f"## {name}", f"- file: `{path.name}`", f"- features: {n:,}",
             f"- CRS: {crs}{flag}",
             f"- geometry: {', '.join(gdf.geom_type.unique())}", "",
             "| field | dtype | examples |", "|---|---|---|"]
    for col in gdf.columns.drop("geometry"):
        ex = ", ".join(map(str, gdf[col].dropna().unique()[:5]))
        lines.append(f"| {col} | {gdf[col].dtype} | {ex} |")
    return lines + [""]


def main() -> None:
    ensure_dirs()
    lines = []
    for name, path in cfg.INPUTS.items():
        lines += describe(name, path)
    tiles = sorted(cfg.DGM1_TIF_DIR.glob("dgm1_32_*.tif"))
    lines += ["## dgm1", f"- converted GeoTIFF tiles (step 01): {len(tiles)}", ""]
    rep = write_report("00_check_inputs", "Input check", lines)
    log.info("Report: %s", rep)


if __name__ == "__main__":
    main()
