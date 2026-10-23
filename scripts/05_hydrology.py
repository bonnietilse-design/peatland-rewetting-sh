"""
05 – Hydrology from DGM1 with GRASS r.watershed (run through qgis_process)

  1. mosaic the 1 m tiles from step 01 and resample to HYDRO["resample_m"]
     (GDAL; "min" by default, so narrow ditches survive the coarser grid)
  2. GRASS r.watershed: flow direction, flow accumulation, streams and
     sub-catchments. r.watershed routes water through depressions with a
     least-cost search, so no separate "fill sinks" step is needed - which
     suits flat fen terrain, where filling would create large artificial flats.
  3. vectorise the sub-catchments and compute how much of each is organic
     soil: which peat areas form their own hydrological unit?

Run in the OSGeo4W Shell (it provides qgis_process and GDAL). The GRASS
provider must be active in QGIS (Settings → Options → Processing).
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geopandas as gpd  # noqa: E402
from osgeo import gdal, ogr, osr  # noqa: E402

import config as cfg  # noqa: E402
from peatsh.common import add_area_ha, get_logger, load_aoi, read_layer, write_layer, write_report  # noqa: E402

log = get_logger("05")
gdal.UseExceptions()
H = cfg.HYDRO
OUT = cfg.DATA_INTERIM / "hydro" / cfg.aoi_label()
ALG_IDS = ("grass:r.watershed", "grass7:r.watershed")   # QGIS ≥3.36 / older


# --- qgis_process helpers ------------------------------------------------------
def find_qgis_process() -> str:
    if H.get("qgis_process"):
        return H["qgis_process"]
    for name in ("qgis_process-qgis.bat", "qgis_process-qgis-ltr.bat",
                 "qgis_process.exe", "qgis_process"):
        path = shutil.which(name)
        if path:
            return path
    sys.exit("qgis_process not found – run this script in the OSGeo4W Shell, "
             "or set HYDRO['qgis_process'] in config.py to its full path.")


def find_alg(qp: str) -> str:
    last = None
    for alg in ALG_IDS:
        r = subprocess.run([qp, "help", alg], capture_output=True, text=True)
        if r.returncode == 0:
            return alg
        last = r
    log.error("qgis_process said:\n%s\n%s", last.stdout[-1500:], last.stderr[-1500:])
    sys.exit(f"GRASS r.watershed not available in qgis_process ({qp}).\n"
             "qgis_process loads plugins separately from QGIS desktop. Try:\n"
             f'  "{qp}" plugins\n'
             f'  "{qp}" plugins enable grassprovider\n'
             "then re-run this script.")


def run_alg(qp: str, alg: str, inputs: dict) -> dict:
    """Run a Processing algorithm, parameters passed as JSON on stdin."""
    r = subprocess.run([qp, "--json", "run", alg, "-"],
                       input=json.dumps({"inputs": inputs}),
                       capture_output=True, text=True)
    if r.returncode != 0:
        log.error(r.stdout[-3000:])
        log.error(r.stderr[-3000:])
        sys.exit(f"{alg} failed (exit code {r.returncode}) – see messages above.")
    start = r.stdout.find("{")          # skip any banner text before the JSON
    return json.loads(r.stdout[start:]).get("results", {})


# --- steps ---------------------------------------------------------------------
def build_dem(tiles: list[Path], aoi: gpd.GeoDataFrame) -> Path:
    """Mosaic 1 m tiles and resample to the working resolution (HYDRO["resample_alg"])."""
    res = H["resample_m"]
    alg = H.get("resample_alg", "average")
    dem = OUT / f"dem_{res}m_{alg}.tif"
    if dem.exists():
        log.info("reuse %s", dem.name)
        return dem
    vrt = OUT / "dgm1_mosaic.vrt"
    v = gdal.BuildVRT(str(vrt), [str(t) for t in tiles])
    gt, nx, ny = v.GetGeoTransform(), v.RasterXSize, v.RasterYSize
    v = None
    # work on the area covered by BOTH the tiles and the AOI bounding box, so a
    # partial download (e.g. a focus window) still gives a compact DEM
    axmin, aymin, axmax, aymax = aoi.total_bounds
    xmin, xmax = max(gt[0], axmin), min(gt[0] + nx * gt[1], axmax)
    ymin, ymax = max(gt[3] + ny * gt[5], aymin), min(gt[3], aymax)
    gdal.Warp(str(dem), str(vrt), xRes=res, yRes=res, resampleAlg=alg,
              outputBounds=(xmin // res * res, ymin // res * res,
                            -(-xmax // res) * res, -(-ymax // res) * res),
              dstNodata=-9999, creationOptions=["COMPRESS=DEFLATE", "PREDICTOR=3", "TILED=YES"])
    log.info("DEM %s m (%s of the 1 m cells) written", res, alg)
    return dem


def polygonize(raster: Path, out_gpkg: Path) -> gpd.GeoDataFrame:
    src = gdal.Open(str(raster))
    band = src.GetRasterBand(1)
    drv = ogr.GetDriverByName("GPKG")
    if out_gpkg.exists():
        drv.DeleteDataSource(str(out_gpkg))
    ds = drv.CreateDataSource(str(out_gpkg))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(25832)
    lyr = ds.CreateLayer("basins", srs=srs, geom_type=ogr.wkbPolygon)
    lyr.CreateField(ogr.FieldDefn("basin_id", ogr.OFTInteger))
    gdal.Polygonize(band, band.GetMaskBand(), lyr, 0)
    ds = src = None
    gdf = gpd.read_file(out_gpkg, layer="basins")
    gdf = gdf[gdf.basin_id > 0]
    return gdf.dissolve(by="basin_id", as_index=False)


def main() -> None:
    tiles = sorted(cfg.DGM1_TIF_DIR.glob("dgm1_32_*.tif"))
    if not tiles:
        sys.exit("No DGM1 GeoTIFFs – run 01_prepare_dgm1.py first.")
    OUT.mkdir(parents=True, exist_ok=True)
    aoi = load_aoi()

    dem = build_dem(tiles, aoi)
    res = H["resample_m"]
    threshold = int(H["basin_threshold_ha"] * 10_000 / res**2)

    qp = find_qgis_process()
    alg = find_alg(qp)
    log.info("running %s (threshold %d cells = %s ha) ...", alg, threshold,
             H["basin_threshold_ha"])
    # file names carry the resampling method, so runs can be compared in QGIS
    tag = H.get("resample_alg", "average")
    outs = {k: str(OUT / f"{k}_{tag}.tif") for k in ("accumulation", "drainage", "basin", "stream")}
    run_alg(qp, alg, {
        "elevation": str(dem),
        "threshold": threshold,
        "memory": H["memory_mb"],
        "-s": bool(H["single_flow"]),
        **outs,
        "GRASS_REGION_CELLSIZE_PARAMETER": res,
    })

    basins = add_area_ha(polygonize(Path(outs["basin"]), OUT / f"basins_raw_{tag}.gpkg"))
    # the DEM is the AOI's bounding box; drop catchments in its corners that
    # don't reach into the AOI at all (no soil / land-use data there)
    basins = basins[basins.intersects(aoi.union_all())].reset_index(drop=True)
    soils = read_layer("organic_soils")[["geometry"]]
    inter = add_area_ha(gpd.overlay(basins[["basin_id", "geometry"]], soils,
                                    how="intersection", keep_geom_type=True), "peat_ha")
    basins = basins.merge(inter.groupby("basin_id").peat_ha.sum(), on="basin_id", how="left")
    basins["peat_ha"] = basins.peat_ha.fillna(0)
    basins["peat_share"] = basins.peat_ha / basins.area_ha
    # Sub-catchments touching the edge of the DEM are cut off: water from
    # outside is missing, so their area and flow accumulation are incomplete.
    dem_ds = gdal.Open(str(dem))
    g, nx, ny = dem_ds.GetGeoTransform(), dem_ds.RasterXSize, dem_ds.RasterYSize
    dem_ds = None
    from shapely.geometry import box  # local import keeps the header short
    inner = box(g[0], g[3] + ny * g[5], g[0] + nx * g[1], g[3]).buffer(-2 * res)
    edge = aoi.union_all().boundary.buffer(2 * res).union(inner.exterior.buffer(2 * res))
    basins["complete"] = (~basins.intersects(edge)).astype(int)
    write_layer(basins, "subbasins")

    dom = basins[(basins.peat_share >= 0.5) & (basins.complete == 1)]
    n_edge = int((basins.complete == 0).sum())
    tiny = (basins.area_ha < H["basin_threshold_ha"] / 2).sum()
    write_report("05_hydrology", "Sub-catchments from DGM1 (GRASS r.watershed)", [
        f"- DGM1 tiles: {len(tiles)}, working resolution {res} m "
        f"({H.get('resample_alg', 'average')} of the 1 m cells)",
        f"- algorithm: {alg}, {'single (D8)' if H['single_flow'] else 'multiple'} flow direction",
        f"- min. sub-catchment size: {H['basin_threshold_ha']} ha ({threshold:,} cells)",
        f"- sub-catchments: {len(basins)} (of which {tiny} small pieces)",
        f"- touching the AOI/DEM edge (field `complete` = 0, incomplete – water "
        f"from outside missing): {n_edge}",
        f"- complete sub-catchments ≥ 50 % organic soil: **{len(dom)}** "
        f"({dom.area_ha.sum():,.0f} ha, {dom.peat_ha.sum():,.0f} ha of it peat)", "",
        "The AOI is a hand-drawn test polygon, not a real catchment: the Treene,",
        "Sorge and Eider drain much larger areas. Interpret only complete",
        "sub-catchments.", "",
        "Rasters (accumulation, drainage direction, streams, basins) are in",
        f"`data/interim/hydro/{cfg.aoi_label()}/` – load them in QGIS to check.", "",
        "Limitations: the DEM does not show pipe drains, culverts or pumping",
        "stations, which control water in fen landscapes; drainage there is",
        "largely artificial. Compare the streams with the official water-body",
        "network before interpreting. Tiles from different survey years can",
        "create small steps at tile edges (see report 01).",
    ])
    log.info("done: %d sub-catchments, %d peat-dominated", len(basins), len(dom))


if __name__ == "__main__":
    main()
