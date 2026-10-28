"""
06w – Download the 1878–80 map from the Chronologen WCS at its native resolution

Large areas cannot be exported from QGIS in one request: the server returns an
empty image (all zero) if the request is too big. GDAL's WCS driver asks for
the coverage in blocks, so any size works.

Run in the OSGeo4W Shell:
    python scripts\\06w_download_wcs.py block            one area (see config.YOLO_AREAS)
    python scripts\\06w_download_wcs.py block fiel aoi   several

Writes the area's "native_tif" (e.g. data/raw/historical/chronologen_1880_block_native.tif)
and checks that it is not empty.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from osgeo import gdal  # noqa: E402

import config as cfg  # noqa: E402
from peatsh.common import get_logger  # noqa: E402

log = get_logger("06w")
gdal.UseExceptions()
gdal.SetConfigOption("GDAL_HTTP_TIMEOUT", "120")
gdal.SetConfigOption("GDAL_HTTP_MAX_RETRY", "3")
gdal.SetConfigOption("GDAL_HTTP_RETRY_DELAY", "5")


def open_wcs():
    base, cov = cfg.WCS["url"], cfg.WCS["coverage"]
    tried = []
    for q in (f"version=2.0.1&coverage={cov}", f"version=1.0.0&coverage={cov}",
              f"version=1.1.0&coverage={cov}"):
        name = f"WCS:{base}?{q}"
        try:
            ds = gdal.Open(name)
            if ds is not None:
                gt = ds.GetGeoTransform()
                log.info("WCS opened (%s): %d × %d px, %.4f m", q.split("&")[0], ds.RasterXSize,
                         ds.RasterYSize, gt[1])
                return ds
        except RuntimeError as e:
            tried.append(f"{q}: {str(e)[:200]}")
    sys.exit("Could not open the WCS:\n" + "\n".join(tried))


def check(path: Path) -> float:
    ds = gdal.Open(str(path))
    b = ds.GetRasterBand(1)
    W, H = ds.RasterXSize, ds.RasterYSize
    ys = np.linspace(0, H - 512, 6).astype(int)
    xs = np.linspace(0, W - 512, 6).astype(int)
    vals = np.concatenate([b.ReadAsArray(int(x), int(y), 512, 512).ravel() for y in ys for x in xs])
    u = np.unique(vals)
    if len(u) < 2:
        sys.exit(f"{path.name} contains only the value {u[0]} – the download is empty.")
    return float((vals == vals.min()).mean())


def main() -> None:
    areas = sys.argv[1:] or ["block"]
    src = open_wcs()
    res = src.GetGeoTransform()[1]
    for area in areas:
        A = cfg.YOLO_AREAS.get(area)
        if A is None or "extent" not in A:
            sys.exit(f"Unknown area {area} or no extent in config.YOLO_AREAS")
        xmin, ymin, xmax, ymax = A["extent"]
        out = A["native_tif"]
        log.info("%s: %.0f × %.0f m at %.3f m → %s", area, xmax - xmin, ymax - ymin, res, out.name)

        def progress(f, msg, data):
            if int(f * 100) % 10 == 0 and int(f * 100) != progress.last:
                progress.last = int(f * 100)
                log.info("  %d %%", progress.last)
            return 1
        progress.last = -1
        gdal.Translate(str(out), src, projWin=[xmin, ymax, xmax, ymin], projWinSRS="EPSG:25832",
                       creationOptions=["COMPRESS=DEFLATE", "TILED=YES", "BIGTIFF=IF_SAFER"],
                       callback=progress)
        ink = check(out)
        log.info("%s done – ink share in a sample %.1f %%", out.name, 100 * ink)


if __name__ == "__main__":
    main()
