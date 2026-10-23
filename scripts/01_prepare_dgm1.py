"""
01 – Prepare DGM1 tiles: completeness check + XYZ -> GeoTIFF

DGM1 Schleswig-Holstein, © GeoBasis-DE/LVermGeo SH/CC BY 4.0

Download: uses the portal's official bulk-download index
("Massendownload - GeoJSON" on the DGM1 page of the OpenGBD portal,
https://geodaten.schleswig-holstein.de/gaialight-sh/_apps/dladownload/).
Save it as config.DGM1_INDEX. Each feature = one 1 km tile with its survey
date and a direct link. config.DGM1_SCOPE picks "focus" (49 tiles) or "aoi".

What this script does:
  - finds which 1 km tiles are needed (focus window or whole AOI)
  - downloads the missing ones from the index links, one at a time with a
    pause; handles a zip or plain XYZ text answer
  - converts each XYZ tile (1 line per 1 m cell: x y z, cell centres) to a
    compressed 1 m GeoTIFF in data/interim/dgm1_tif/ - the 28 MB text files
    are never kept on disk
  - also converts any Mehrfachdownload_*.zip from the manual download client
    found in data/raw/dgm1/
  - records survey years and writes a tile layer (present / missing, year)
    to the GeoPackage for mapping
Safe to re-run: finished tiles are skipped.
"""
import io
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from osgeo import gdal, osr  # noqa: E402  (comes with QGIS)
from shapely.geometry import box  # noqa: E402

import config as cfg  # noqa: E402
from peatsh.common import ensure_dirs, get_logger, load_aoi, write_layer, write_report  # noqa: E402

log = get_logger("01")
gdal.UseExceptions()
NAME_RE = re.compile(r"dgm1_32_(\d{3})_(\d{4})_\d+_sh_(\d{4})\.xyz$", re.I)
NODATA = -9999.0


def needed_tiles(aoi: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """All 1 km tiles intersecting the AOI, with tile_id like '325306029'."""
    km = cfg.DGM1_TILE_KM * 1000
    xmin, ymin, xmax, ymax = aoi.total_bounds
    rows = []
    for e in range(int(xmin // km), int(np.ceil(xmax / km))):
        for n in range(int(ymin // km), int(np.ceil(ymax / km))):
            rows.append({"tile_id": f"32{e:03d}{n:04d}", "e_km": e, "n_km": n,
                         "geometry": box(e * km, n * km, (e + 1) * km, (n + 1) * km)})
    grid = gpd.GeoDataFrame(rows, crs=cfg.TARGET_CRS)
    return grid[grid.intersects(aoi.union_all())].reset_index(drop=True)


def xyz_to_tif(fh, out: Path) -> tuple[int, float, float]:
    """Grid an XYZ stream (cell centres, 1 m) into a compressed GeoTIFF.
    Returns (n_cells, z_min, z_max)."""
    df = pd.read_csv(fh, sep=r"\s+", header=None, names=["x", "y", "z"],
                     dtype="float64", engine="c")
    x, y, z = df.x.to_numpy(), df.y.to_numpy(), df.z.to_numpy()
    res = float(np.median(np.diff(np.unique(x[:2000])))) or 1.0
    x0, y1 = x.min() - res / 2, y.max() + res / 2          # upper-left corner
    ncol = int(round((x.max() - x.min()) / res)) + 1
    nrow = int(round((y.max() - y.min()) / res)) + 1
    grid = np.full((nrow, ncol), NODATA, dtype="float32")
    col = np.rint((x - x.min()) / res).astype(int)
    row = np.rint((y.max() - y) / res).astype(int)
    grid[row, col] = z

    drv = gdal.GetDriverByName("GTiff")
    ds = drv.Create(str(out), ncol, nrow, 1, gdal.GDT_Float32,
                    options=["COMPRESS=DEFLATE", "PREDICTOR=3", "TILED=YES"])
    ds.SetGeoTransform((x0, res, 0, y1, 0, -res))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(25832)
    ds.SetProjection(srs.ExportToWkt())
    band = ds.GetRasterBand(1)
    band.SetNoDataValue(NODATA)
    band.WriteArray(grid)
    band.FlushCache()
    ds = None
    return len(z), float(z.min()), float(z.max())


def tif_path(tile_id: str, year) -> Path:
    return cfg.DGM1_TIF_DIR / f"dgm1_32_{tile_id[2:5]}_{tile_id[5:9]}_{year}.tif"


def have_tif(tile_id: str) -> bool:
    return any(cfg.DGM1_TIF_DIR.glob(f"dgm1_32_{tile_id[2:5]}_{tile_id[5:9]}_*.tif"))


def ssl_context() -> ssl.SSLContext:
    """Verify HTTPS certificates against the Windows certificate store.

    QGIS's Python ships its own OpenSSL, which does not use the Windows store
    and can fail with CERTIFICATE_VERIFY_FAILED where the browser works.
    'truststore' (pip install --user truststore) makes Python use the system
    store - verification stays ON. Never switch verification off instead.
    """
    try:
        import truststore
        log.info("certificates: Windows/system store (truststore)")
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        log.warning("truststore not installed – using Python's own certificates. "
                    "If downloads fail with CERTIFICATE_VERIFY_FAILED, run: "
                    "python -m pip install --user truststore")
        return ssl.create_default_context()


def download_tiles(tiles: gpd.GeoDataFrame, index: gpd.GeoDataFrame) -> tuple[int, list]:
    """Fetch tiles via the official bulk-download links; convert on the fly."""
    ctx = ssl_context()
    links = index.set_index("kachel")
    todo = [t for t in tiles.tile_id if not have_tif(t) and t in links.index]
    log.info("%d tiles to download", len(todo))
    done, failed = 0, []
    for i, tid in enumerate(todo, 1):
        url = links.at[tid, "link_data"]
        year = str(links.at[tid, "datum"])[:4]
        req = urllib.request.Request(url, headers={"User-Agent": "peatland-rewetting-sh (portfolio project)"})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=180, context=ctx) as r:
                    data = r.read()
                break
            except urllib.error.URLError as exc:
                if isinstance(exc.reason, ssl.SSLCertVerificationError):
                    # same problem for every tile - stop instead of retrying 49×3
                    sys.exit(f"Certificate check failed ({exc.reason.verify_message}).\n"
                             "Fix: python -m pip install --user truststore   then re-run.")
                log.warning("%s attempt %d failed: %s", tid, attempt + 1, exc)
                time.sleep(5 * (attempt + 1))
            except Exception as exc:  # network hiccup: wait and retry
                log.warning("%s attempt %d failed: %s", tid, attempt + 1, exc)
                time.sleep(5 * (attempt + 1))
        else:
            failed.append(tid)
            continue
        try:
            if data[:2] == b"PK":                       # zip archive
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    name = next(n for n in zf.namelist() if n.lower().endswith(".xyz"))
                    with zf.open(name) as fh:
                        xyz_to_tif(fh, tif_path(tid, year))
            else:                                       # plain XYZ text
                xyz_to_tif(io.BytesIO(data), tif_path(tid, year))
            done += 1
            log.info("[%d/%d] %s (%s) ok", i, len(todo), tid, year)
        except Exception as exc:
            log.error("%s: could not read the answer (%s) – first bytes: %r",
                      tid, exc, data[:80])
            failed.append(tid)
        time.sleep(cfg.DGM1_PAUSE_S)
    return done, failed


def main() -> None:
    ensure_dirs()
    cfg.DGM1_TIF_DIR.mkdir(parents=True, exist_ok=True)
    tiles = needed_tiles(load_aoi())
    if cfg.DGM1_SCOPE == "focus":
        (e0, e1), (n0, n1) = cfg.DGM1_FOCUS_KM["e"], cfg.DGM1_FOCUS_KM["n"]
        tiles = tiles[tiles.e_km.between(e0, e1) & tiles.n_km.between(n0, n1)].reset_index(drop=True)
    need = set(tiles.tile_id)
    log.info("%d tiles needed (scope: %s)", len(need), cfg.DGM1_SCOPE)

    years: dict[str, int] = {}
    downloaded, failed = 0, []
    if cfg.DGM1_INDEX.exists():
        index = gpd.read_file(cfg.DGM1_INDEX, ignore_geometry=True)
        years.update({k: int(str(d)[:4]) for k, d in zip(index.kachel, index.datum)})
        downloaded, failed = download_tiles(tiles, index)
    else:
        log.warning("no bulk-download index at %s – only local zips are used", cfg.DGM1_INDEX)

    # --- convert manual downloads found in the zips (and loose .xyz files) ---
    converted = skipped = outside = 0
    sources = sorted(cfg.DGM1_DIR.glob("*.zip")) + sorted(cfg.DGM1_DIR.glob("*.xyz"))
    for src in sources:
        members = (zipfile.ZipFile(src).namelist() if src.suffix == ".zip" else [src.name])
        for name in members:
            m = NAME_RE.search(Path(name).name)
            if not m:
                continue
            e, n, year = m.groups()
            tid = f"32{e}{n}"
            years[tid] = int(year)
            if tid not in need:
                outside += 1
                continue
            out = tif_path(tid, year)
            if have_tif(tid):
                skipped += 1
                continue
            if src.suffix == ".zip":
                with zipfile.ZipFile(src) as zf, zf.open(name) as fh:
                    cells, zmin, zmax = xyz_to_tif(fh, out)
            else:
                cells, zmin, zmax = xyz_to_tif(src, out)
            converted += 1
            log.info("%s (%s): %d cells, %.2f–%.2f m", tid, year, cells, zmin, zmax)

    # --- what is there now? ---------------------------------------------------
    tif_re = re.compile(r"dgm1_32_(\d{3})_(\d{4})_(\d{4})\.tif$")
    present = set()
    for p in cfg.DGM1_TIF_DIR.glob("dgm1_32_*.tif"):
        m = tif_re.match(p.name)
        if m:
            present.add(f"32{m.group(1)}{m.group(2)}")
            years.setdefault(f"32{m.group(1)}{m.group(2)}", int(m.group(3)))
    tiles["status"] = np.where(tiles.tile_id.isin(present), "present", "missing")
    tiles["year"] = tiles.tile_id.map(years).astype("Int64")
    write_layer(tiles, "dgm1_tiles")

    missing = tiles.loc[tiles.status == "missing", "tile_id"].tolist()
    (cfg.DGM1_DIR / "dgm1_tiles_missing.txt").write_text("\n".join(missing) + "\n")
    yr = tiles.loc[tiles.status == "present", "year"].value_counts().sort_index()

    write_report("01_prepare_dgm1", "DGM1 tiles", [
        f"- scope: **{cfg.DGM1_SCOPE}**, tiles needed: {len(tiles)}",
        f"- present: **{len(tiles) - len(missing)}**, missing: **{len(missing)}**"
        + ("  → list in `data/raw/dgm1/dgm1_tiles_missing.txt`" if missing else ""),
        f"- this run: {downloaded} downloaded via bulk links"
        + (f", {len(failed)} failed ({', '.join(failed[:10])})" if failed else "")
        + f"; {converted} converted from local zips, {skipped} already done, "
        f"{outside} in local zips but outside the scope", "",
        "### Survey year of the tiles present", "",
        "| year | tiles |", "|---|---|", *[f"| {y} | {c} |" for y, c in yr.items()], "",
        "Tiles from different years meet at tile edges. Drained peat subsides",
        "(order of 1 cm/yr), so tiles years apart can show a step of",
        "centimetres to decimetres - relevant in flat fen terrain. Map the",
        "layer `dgm1_tiles` by `year` to show this.", "",
        "Source: DGM1, © GeoBasis-DE/LVermGeo SH/CC BY 4.0",
    ])
    if missing:
        log.warning("%d tiles still missing – download them and re-run", len(missing))


if __name__ == "__main__":
    main()
