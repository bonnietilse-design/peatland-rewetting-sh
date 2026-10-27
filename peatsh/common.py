"""Shared helpers used by all numbered scripts."""
from __future__ import annotations

import datetime as dt
import logging
import sys
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config as cfg  # noqa: E402


def get_logger(name: str) -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger(name)


def ensure_dirs() -> None:
    for d in (cfg.DATA_RAW, cfg.DATA_INTERIM, cfg.DATA_PROCESSED,
              cfg.OUTPUTS, cfg.REPORTS):
        d.mkdir(parents=True, exist_ok=True)


def read_vector(path: Path, to_crs: str = cfg.TARGET_CRS,
                mask: gpd.GeoDataFrame | None = None) -> gpd.GeoDataFrame:
    """Read a vector file and reproject to the project CRS if needed.

    mask: only read features intersecting this polygon (much faster for
    Germany-wide files). GeoPandas handles a different file CRS itself.
    """
    if not Path(path).exists():
        raise FileNotFoundError(f"Missing input: {path} (see config.INPUTS)")
    gdf = gpd.read_file(path, mask=mask)
    if gdf.crs is None:
        raise ValueError(f"{path} has no CRS - set it in QGIS first.")
    if gdf.crs.to_string() != to_crs:
        gdf = gdf.to_crs(to_crs)
    return gdf


def load_aoi() -> gpd.GeoDataFrame:
    """Return the study area polygon (test catchment or whole state)."""
    if cfg.TEST_MODE:
        aoi = read_vector(cfg.TEST_AOI)
    else:
        f = cfg.FIELDS
        land = read_vector(cfg.INPUTS["vg250_land"])
        aoi = land[(land[f["vg250_state_key"]] == f["vg250_state_value"])
                   & (land[f["vg250_gf"]] == 4)]
    return aoi.dissolve()[["geometry"]]


def clip_to_aoi(gdf: gpd.GeoDataFrame, aoi: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf[gdf.geometry.notna()].copy()
    gdf["geometry"] = gdf.geometry.make_valid()
    # keep_geom_type drops stray lines/points that clipping can create,
    # so the GeoPackage layer stays pure (Multi)Polygon
    return gpd.clip(gdf, aoi, keep_geom_type=True)


def add_area_ha(gdf: gpd.GeoDataFrame, col: str = "area_ha") -> gpd.GeoDataFrame:
    """(Re)compute area in ha from the geometry.

    Drops any existing column with the same name in other capitalisation
    (e.g. Thünen's AREA_HA): GeoPackage field names are case-insensitive,
    and the old value is wrong after clipping anyway.
    """
    dupes = [c for c in gdf.columns if c.lower() == col.lower() and c != col]
    gdf = gdf.drop(columns=dupes)
    gdf[col] = gdf.geometry.area / 10_000
    return gdf


def write_layer(gdf: gpd.GeoDataFrame, layer: str) -> None:
    """Write a layer into the project GeoPackage (overwrites the layer)."""
    cfg.GPKG.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(cfg.GPKG, layer=f"{layer}_{cfg.aoi_label()}", driver="GPKG")


def read_layer(layer: str) -> gpd.GeoDataFrame:
    return gpd.read_file(cfg.GPKG, layer=f"{layer}_{cfg.aoi_label()}")


def write_report(step: str, title: str, lines: list[str]) -> Path:
    """Write a short markdown report for one step into docs/reports/."""
    cfg.REPORTS.mkdir(parents=True, exist_ok=True)
    path = cfg.REPORTS / f"{step}_{cfg.aoi_label()}.md"
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    mode = f"TEST MODE ({cfg.TEST_AOI_NAME})" if cfg.TEST_MODE else "Whole state"
    body = [f"# {step} – {title}", "", f"_Run: {stamp} · {mode}_", "", *lines, ""]
    path.write_text("\n".join(body), encoding="utf-8")
    return path


def ef_ready(*classes: str) -> bool:
    """True only if every requested emission factor has a cited mean value."""
    return all(cfg.EMISSION_FACTORS[c]["mean"] is not None for c in classes)
