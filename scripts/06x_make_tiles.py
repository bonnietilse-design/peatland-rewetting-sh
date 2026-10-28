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

import numpy as np  # noqa: E402
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


def read_index(idx_path):
    """Existing tile footprints: tile_id, row, col, use, bounds."""
    ds = ogr.Open(str(idx_path))
    out = []
    for f in ds.GetLayer(0):
        mnx, mxx, mny, mxy = f.GetGeometryRef().GetEnvelope()
        out.append({"tile_id": f.GetField("tile_id"), "row": f.GetField("row"),
                    "col": f.GetField("col"), "use": f.GetField("use"),
                    "x0": mnx, "y1": mxy})
    return out


def make_native(area, A) -> None:
    """Tiles from the WCS at its native resolution (~0.78 m), resampled to
    0.5 m bilinearly and thresholded at half - thin strokes survive, while
    nearest neighbour from a 1 m export drops whole pixel rows.
    If the area already has a tile index, the same footprints (and tile ids,
    'use' flags) are rendered again, so all labels and flags stay valid."""
    src_path = A.get("native_tif")
    if src_path is None or not src_path.exists():
        sys.exit(f"Missing {src_path} – export the WCS for the {area} at its native resolution "
                 "('Layer Resolution' in the export dialog).")
    src = gdal.Open(str(src_path))
    gt = src.GetGeoTransform()
    W, H = src.RasterXSize, src.RasterYSize
    sample = src.GetRasterBand(1).ReadAsArray(W // 4, H // 4, min(2000, W // 2), min(2000, H // 2))
    if len(np.unique(sample)) < 2:
        sys.exit(f"{src_path.name} looks empty (only the value {sample.flat[0]}) – the export failed. "
                 f"Download it with:  python scripts\\06w_download_wcs.py {area}")
    tm, px = Y["tile_m"], Y["tile_px"]
    idx_path = A["tile_index"]
    if idx_path.exists():
        tiles = read_index(idx_path)
        log.info("%s: re-rendering %d existing tiles from %s (%.3f m)", area, len(tiles),
                 src_path.name, gt[1])
        new_index = False
    else:
        x0, y1 = float(np.floor(gt[0])), float(np.ceil(gt[3]))
        n_c = int(np.ceil((gt[0] + W * gt[1] - x0) / tm))
        n_r = int(np.ceil((y1 - (gt[3] + H * gt[5])) / tm))
        fmt = "r{:02d}_c{:02d}" if n_r <= 100 and n_c <= 100 else "r{:03d}_c{:03d}"
        tiles = [{"tile_id": fmt.format(r, c), "row": r, "col": c, "use": None,
                  "x0": x0 + c * tm, "y1": y1 - r * tm} for r in range(n_r) for c in range(n_c)]
        log.info("%s: new grid of %d × %d tiles from %s (%.3f m)", area, n_r, n_c, src_path.name, gt[1])
        new_index = True
    out_dir = cfg.tile_dir(A)
    out_dir.mkdir(parents=True, exist_ok=True)
    png = gdal.GetDriverByName("PNG")
    for i, t in enumerate(tiles, 1):
        x0, y1 = t["x0"], t["y1"]
        tmp = gdal.Warp("", src, format="MEM", outputBounds=(x0, y1 - tm, x0 + tm, y1),
                        width=px, height=px, resampleAlg="bilinear", outputType=gdal.GDT_Float32,
                        warpOptions=["INIT_DEST=1"])          # outside the map = paper
        a = tmp.GetRasterBand(1).ReadAsArray()
        ink = a < 0.5
        t["ink_share"] = float(ink.mean())
        mem = gdal.GetDriverByName("MEM").Create("", px, px, 1, gdal.GDT_Byte)
        mem.SetGeoTransform((x0, tm / px, 0, y1, 0, -tm / px))
        mem.SetProjection(src.GetProjection())
        mem.GetRasterBand(1).WriteArray(np.where(ink, 0, 255).astype(np.uint8))
        png.CreateCopy(str(out_dir / f"{t['tile_id']}.png"), mem, options=["WORLDFILE=YES"])
        tmp = mem = None
        if i % 250 == 0:
            log.info("%d / %d tiles", i, len(tiles))
    if new_index:
        drv = ogr.GetDriverByName("GPKG")
        ds = drv.CreateDataSource(str(idx_path))
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(25832)
        lyr = ds.CreateLayer("tiles", srs, ogr.wkbPolygon)
        for name, typ in (("tile_id", ogr.OFTString), ("row", ogr.OFTInteger),
                          ("col", ogr.OFTInteger), ("use", ogr.OFTString),
                          ("ink_share", ogr.OFTReal)):
            lyr.CreateField(ogr.FieldDefn(name, typ))
        for t in tiles:
            ring = ogr.Geometry(ogr.wkbLinearRing)
            for x, y in ((t["x0"], t["y1"] - tm), (t["x0"] + tm, t["y1"] - tm), (t["x0"] + tm, t["y1"]),
                         (t["x0"], t["y1"]), (t["x0"], t["y1"] - tm)):
                ring.AddPoint_2D(x, y)
            poly = ogr.Geometry(ogr.wkbPolygon)
            poly.AddGeometry(ring)
            f = ogr.Feature(lyr.GetLayerDefn())
            f.SetGeometry(poly)
            for k in ("tile_id", "row", "col"):
                f.SetField(k, t[k])
            f.SetField("ink_share", round(t["ink_share"], 4))
            lyr.CreateFeature(f)
        ds = None
    write_report("06x_make_tiles" + A["suffix"] + "_native", f"Native-resolution map tiles ({area})", [
        f"- source: `{src_path.name}`, {W} × {H} px at {gt[1]:.3f} m",
        f"- tiles: **{len(tiles)}** ({'new grid' if new_index else 'same footprints and ids as before'}), "
        f"{tm} m → {px} px, bilinear + threshold",
        f"- images: `{out_dir.relative_to(cfg.ROOT)}`",
        "", "Map: Preußische Landesaufnahme 1878–80, © GeoBasis-DE/LVermGeo SH/CC BY 4.0",
    ])
    log.info("%d tiles written to %s", len(tiles), out_dir)


def main() -> None:
    area, A = cfg.yolo_area(sys.argv)
    if Y.get("tile_variant") == "native":
        make_native(area, A)
        return
    src_path = A["map_tif"]
    if not src_path.exists():
        sys.exit(f"Missing {src_path} – export the WCS layer for the {area} first.")
    aoi = aoi_geometry() if area == "aoi" else None
    src = gdal.Open(str(src_path))
    gt = src.GetGeoTransform()
    if abs(gt[1] - 1) > 1e-6 or abs(gt[5] + 1) > 1e-6:
        # e.g. a WCS export with a "map canvas" extent: pixels of 1.00004 m.
        # Snap to an exact 1 m grid (nearest neighbour, no new values).
        fixed = src_path.with_name(src_path.stem + "_1m.tif")
        log.info("pixel size %.6f × %.6f m – resampling to exactly 1 m: %s", gt[1], -gt[5], fixed.name)
        gdal.Warp(str(fixed), src, xRes=1, yRes=1, targetAlignedPixels=True, resampleAlg="near",
                  creationOptions=["COMPRESS=DEFLATE", "TILED=YES"])
        src = gdal.Open(str(fixed))
        gt = src.GetGeoTransform()
    res = gt[1]
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
