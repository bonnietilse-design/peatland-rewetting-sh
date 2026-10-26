"""
06x – Cut the 1878–80 map into georeferenced image tiles for YOLO

Input : config.YOLO["map_tif"] – 1 m GeoTIFF of the block (WCS Chronologen,
        values 0 = black ink, 1 = white paper)
Output: data/interim/yolo/tiles/<tile_id>.png  (+ .wld world file, 640 × 640 px)
        data/interim/yolo/tiles.gpkg, layer "tiles" – one polygon per tile with
        tile_id, row, col and an empty field "use" for choosing labelling tiles

Each tile covers tile_m × tile_m metres and is enlarged to tile_px pixels with
nearest-neighbour resampling (no new detail, but symbols get more pixels).
Run in the OSGeo4W Shell (needs GDAL):
    python scripts\\06x_make_tiles.py          the hand-digitised block (default)
    python scripts\\06x_make_tiles.py aoi      the whole test area – only tiles that
                                              touch the AOI polygon are written
Paths per area: config.YOLO_AREAS.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from osgeo import gdal, ogr, osr  # noqa: E402

import config as cfg  # noqa: E402
from peatsh.common import get_logger, write_report  # noqa: E402

log = get_logger("06x")
Y = cfg.YOLO
gdal.UseExceptions()


def aoi_geometry():
    """AOI polygon (OGR geometry in EPSG:25832) for skipping tiles outside it."""
    ds = ogr.Open(str(cfg.TEST_AOI))
    lyr = ds.GetLayer(0)
    geom = None
    for f in lyr:
        g = f.GetGeometryRef().Clone()
        geom = g if geom is None else geom.Union(g)
    return geom


def main() -> None:
    area, A = cfg.yolo_area(sys.argv)
    src_path = A["map_tif"]
    if not src_path.exists():
        sys.exit(f"Missing {src_path} – export the WCS layer for the {area} first.")
    aoi = aoi_geometry() if area == "aoi" else None
    src = gdal.Open(str(src_path))
    gt = src.GetGeoTransform()
    res = gt[1]
    if abs(gt[5] + res) > 1e-6:
        sys.exit("Expected square pixels, north-up.")
    x0, y1 = gt[0], gt[3]
    w_px, h_px = src.RasterXSize, src.RasterYSize
    step_px = round(Y["tile_m"] / res)                 # source pixels per tile
    n_cols = -(-w_px // step_px)                       # ceiling division
    n_rows = -(-h_px // step_px)
    log.info("source %d × %d px at %.2f m → %d × %d tiles of %d m",
             w_px, h_px, res, n_cols, n_rows, Y["tile_m"])

    out_dir = A["tile_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    # tile index (GeoPackage)
    idx_path = A["tile_index"]
    drv = ogr.GetDriverByName("GPKG")
    if idx_path.exists():
        drv.DeleteDataSource(str(idx_path))
    ds = drv.CreateDataSource(str(idx_path))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(25832)
    lyr = ds.CreateLayer("tiles", srs, ogr.wkbPolygon)
    for name, typ in (("tile_id", ogr.OFTString), ("row", ogr.OFTInteger),
                      ("col", ogr.OFTInteger), ("use", ogr.OFTString),
                      ("ink_share", ogr.OFTReal)):
        lyr.CreateField(ogr.FieldDefn(name, typ))

    band = src.GetRasterBand(1)
    n_written = n_skipped = 0
    for r in range(n_rows):
        for c in range(n_cols):
            xoff, yoff = c * step_px, r * step_px
            xs, ys = min(step_px, w_px - xoff), min(step_px, h_px - yoff)
            tile_id = f"r{r:02d}_c{c:02d}" if n_rows <= 100 and n_cols <= 100 else f"r{r:03d}_c{c:03d}"
            tx0 = x0 + xoff * res
            ty1 = y1 - yoff * res
            if aoi is not None:
                ring = ogr.Geometry(ogr.wkbLinearRing)
                for x, y in ((tx0, ty1 - Y["tile_m"]), (tx0 + Y["tile_m"], ty1 - Y["tile_m"]),
                             (tx0 + Y["tile_m"], ty1), (tx0, ty1), (tx0, ty1 - Y["tile_m"])):
                    ring.AddPoint_2D(x, y)
                fp = ogr.Geometry(ogr.wkbPolygon)
                fp.AddGeometry(ring)
                if not fp.Intersects(aoi):
                    n_skipped += 1
                    continue
            # partial tiles at the right/bottom edge are padded with white
            # paper, so every tile has the same size and pixel spacing
            out = out_dir / f"{tile_id}.png"
            px = Y["tile_px"]
            scale = px / step_px                       # e.g. 640 / 320 = 2
            tmp = gdal.Translate(
                "", src, format="MEM", srcWin=[xoff, yoff, xs, ys],
                width=round(xs * scale), height=round(ys * scale),
                resampleAlg="nearest", scaleParams=[[0, 1, 0, 255]],
                outputType=gdal.GDT_Byte)
            mem = gdal.GetDriverByName("MEM").Create("", px, px, 1, gdal.GDT_Byte)
            mem.GetRasterBand(1).Fill(255)
            mem.GetRasterBand(1).WriteArray(tmp.GetRasterBand(1).ReadAsArray(), 0, 0)
            mem.SetGeoTransform((tx0, res / scale, 0, ty1, 0, -res / scale))
            mem.SetProjection(src.GetProjection())
            gdal.GetDriverByName("PNG").CreateCopy(str(out), mem,
                                                   options=["WORLDFILE=YES"])
            ink = float((band.ReadAsArray(xoff, yoff, xs, ys) == 0).mean())
            tmp = mem = None

            # tile footprint (full tile_m square, incl. padding)
            ring = ogr.Geometry(ogr.wkbLinearRing)
            tx1, ty0 = tx0 + Y["tile_m"], ty1 - Y["tile_m"]
            for x, y in ((tx0, ty0), (tx1, ty0), (tx1, ty1), (tx0, ty1), (tx0, ty0)):
                ring.AddPoint_2D(x, y)
            poly = ogr.Geometry(ogr.wkbPolygon)
            poly.AddGeometry(ring)
            f = ogr.Feature(lyr.GetLayerDefn())
            f.SetGeometry(poly)
            f.SetField("tile_id", tile_id)
            f.SetField("row", r)
            f.SetField("col", c)
            f.SetField("ink_share", round(ink, 4))
            lyr.CreateFeature(f)
            n_written += 1
            if n_written % 500 == 0:
                log.info("%d tiles written", n_written)
    ds = None
    src = None

    write_report("06x_make_tiles" + A["suffix"], f"Map tiles for YOLO ({area})", [
        f"- source: `{src_path.name}`, {w_px} × {h_px} px at {res:g} m",
        f"- tiles: **{n_written}** of {n_rows} rows × {n_cols} columns"
        + (f" ({n_skipped} outside the AOI skipped)" if n_skipped else "") + ", "
        f"{Y['tile_m']} m → {Y['tile_px']} px ({Y['tile_m'] / Y['tile_px']:g} m/px)",
        f"- images: `{out_dir.relative_to(cfg.ROOT)}` (PNG + world file .wld)",
        f"- index: `{idx_path.relative_to(cfg.ROOT)}`, layer `tiles` – set field "
        "`use` = `label` for the tiles you label",
        "",
        "Map: Preußische Landesaufnahme 1878–80, © GeoBasis-DE/LVermGeo SH/CC BY 4.0",
    ])
    log.info("%d tiles written to %s", n_written, out_dir)


if __name__ == "__main__":
    main()
