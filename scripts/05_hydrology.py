"""
05 – Hydrology from DGM1 with GRASS r.watershed (run through qgis_process)

  1. mosaic the 1 m tiles from step 01 and resample to HYDRO["resample_m"]
     (GDAL; "min" by default, so narrow ditches survive the coarser grid)
  1b. stream burning (HYDRO["burn"]): lower the DEM by HYDRO["burn_depth_m"]
     along the official water-body network (INPUTS["water_network"]). In flat
     fen land many ditches are narrower than a cell or run through culverts
     the DEM cannot see; burning makes the modelled flow follow them.
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
import numpy as np  # noqa: E402
from shapely.geometry import box  # noqa: E402
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


def burn_dem(dem: Path, aoi: gpd.GeoDataFrame) -> tuple[Path, Path, float]:
    """Cut the water-body network HYDRO["burn_depth_m"] into the DEM.

    Returns the burned DEM and a raster of the network on the DEM grid
    (1 = water body), which is also used for the stream comparison.
    """
    src_path = cfg.INPUTS["water_network"]
    if not src_path.exists():
        sys.exit(f"Missing {src_path} – save the water-body network from the WFS there "
                 "(see DATA_SOURCES.md), or set HYDRO['burn'] = False in config.py.")
    depth = H["burn_depth_m"]
    burned = dem.with_name(dem.stem + "_burn.tif")
    net_tif = OUT / "water_network.tif"
    ds = gdal.Open(str(dem))
    gt, proj, nx, ny = ds.GetGeoTransform(), ds.GetProjection(), ds.RasterXSize, ds.RasterYSize
    x0, y1 = gt[0], gt[3]
    bounds = box(x0, y1 + ny * gt[5], x0 + nx * gt[1], y1)
    lines = gpd.read_file(src_path, bbox=tuple(bounds.bounds))
    if lines.crs is None:
        sys.exit(f"{src_path} has no CRS – set it in QGIS first.")
    lines = lines.to_crs(cfg.TARGET_CRS)
    lines = lines[lines.geometry.notna() & lines.geom_type.isin(["LineString", "MultiLineString"])]
    if lines.empty:
        sys.exit(f"No lines from {src_path.name} inside the DEM – wrong file or extent?")
    tmp = OUT / "water_network_clip.gpkg"
    lines[["geometry"]].to_file(tmp, layer="lines", driver="GPKG")

    mem = gdal.GetDriverByName("MEM").Create("", nx, ny, 1, gdal.GDT_Byte)
    mem.SetGeoTransform(gt)
    mem.SetProjection(proj)
    vec = ogr.Open(str(tmp))                   # keep a reference while rasterising
    opts = ["ALL_TOUCHED=TRUE"] if H.get("burn_all_touched", True) else []
    gdal.RasterizeLayer(mem, [1], vec.GetLayer(0), burn_values=[1], options=opts)
    vec = None
    net = mem.GetRasterBand(1).ReadAsArray().astype(bool)
    gdal.GetDriverByName("GTiff").CreateCopy(str(net_tif), mem, options=["COMPRESS=DEFLATE"])
    mem = None

    band = ds.GetRasterBand(1)
    z = band.ReadAsArray().astype("float32")
    nodata = band.GetNoDataValue()
    valid = z != nodata if nodata is not None else np.ones_like(net)
    z[net & valid] -= depth
    out = gdal.GetDriverByName("GTiff").Create(
        str(burned), nx, ny, 1, gdal.GDT_Float32,
        options=["COMPRESS=DEFLATE", "PREDICTOR=3", "TILED=YES"])
    out.SetGeoTransform(gt)
    out.SetProjection(proj)
    ob = out.GetRasterBand(1)
    if nodata is not None:
        ob.SetNoDataValue(nodata)
    ob.WriteArray(z)
    out = ds = None
    km = lines.length.sum() / 1000
    log.info("burned %.0f km of water bodies (%d cells) %.1f m into the DEM",
             km, int((net & valid).sum()), depth)
    return burned, net_tif, km


def stream_agreement(stream_tif: Path, net_tif: Path, tol_cells: int = 2) -> float | None:
    """Share of official water-body cells within tol_cells of a modelled stream."""
    if not stream_tif.exists() or not net_tif.exists():
        return None
    from scipy.ndimage import binary_dilation
    s_ds, n_ds = gdal.Open(str(stream_tif)), gdal.Open(str(net_tif))   # keep references
    sb = s_ds.GetRasterBand(1)
    s, s_nd = sb.ReadAsArray(), sb.GetNoDataValue()
    n = n_ds.GetRasterBand(1).ReadAsArray().astype(bool)
    s_ds = n_ds = sb = None
    if s.shape != n.shape:
        return None
    is_stream = s > 0
    if s_nd is not None:                       # GRASS writes "no stream" as nodata
        is_stream &= s != s_nd
    near = binary_dilation(is_stream, iterations=tol_cells)
    return float((near & n).sum() / max(n.sum(), 1))


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
    burn = bool(H.get("burn"))
    net_tif, burn_km = None, 0.0
    if burn:
        dem, net_tif, burn_km = burn_dem(dem, aoi)
    res = H["resample_m"]
    threshold = int(H["basin_threshold_ha"] * 10_000 / res**2)

    qp = find_qgis_process()
    alg = find_alg(qp)
    log.info("running %s (threshold %d cells = %s ha) ...", alg, threshold,
             H["basin_threshold_ha"])
    # file names carry the resampling method, so runs can be compared in QGIS
    tag = H.get("resample_alg", "average")
    base_tag = tag
    if burn:
        tag += "_burn"
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
    inner = box(g[0], g[3] + ny * g[5], g[0] + nx * g[1], g[3]).buffer(-2 * res)
    edge = aoi.union_all().boundary.buffer(2 * res).union(inner.exterior.buffer(2 * res))
    basins["complete"] = (~basins.intersects(edge)).astype(int)
    write_layer(basins, "subbasins")

    # before/after comparison with the run without burning (if it exists)
    cmp_lines = []
    if burn:
        old_raw = OUT / f"basins_raw_{base_tag}.gpkg"
        agree_new = stream_agreement(Path(outs["stream"]), net_tif)
        agree_old = stream_agreement(OUT / f"stream_{base_tag}.tif", net_tif)
        cmp_lines = ["", "### Stream burning",
                     f"- water-body network: `{cfg.INPUTS['water_network'].name}`, "
                     f"{burn_km:,.0f} km of lines inside the DEM, burned "
                     f"{H['burn_depth_m']:g} m deep",
                     "- official water bodies within 10 m of a modelled stream: "
                     + (f"{agree_old:.0%} without burning → " if agree_old is not None else "")
                     + (f"**{agree_new:.0%}** with burning" if agree_new is not None else "n/a"),
                     "  (modelled streams only start above the sub-catchment threshold, so",
                     "  small ditches stay below 100 % – what matters is the change)"]
        if old_raw.exists():
            old = gpd.read_file(old_raw)
            old = old[old.basin_id > 0].dissolve(by="basin_id", as_index=False)
            old = old[old.intersects(aoi.union_all())]
            cmp_lines.append(f"- sub-catchments reaching into the AOI: {len(old)} without "
                             f"burning → {len(basins)} with burning")
        cmp_lines.append(f"- compare `stream_{base_tag}.tif` and `stream_{tag}.tif` in QGIS "
                         "with the water-body network")

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
        f"({dom.area_ha.sum():,.0f} ha, {dom.peat_ha.sum():,.0f} ha of it peat)",
        *cmp_lines, "",
        "The AOI is a hand-drawn test polygon, not a real catchment: the Treene,",
        "Sorge and Eider drain much larger areas. Interpret only complete",
        "sub-catchments.", "",
        "Rasters (accumulation, drainage direction, streams, basins) are in",
        f"`data/interim/hydro/{cfg.aoi_label()}/` – load them in QGIS to check.", "",
        "Limitations: the DEM does not show pipe drains, culverts or pumping",
        "stations, which control water in fen landscapes; drainage there is",
        "largely artificial. "
        + ("Burning the official water-body network corrects the main ditches "
           "and culverted streams, but not pipe drains or pumps. " if burn else
           "Compare the streams with the official water-body network before "
           "interpreting. ")
        + "Tiles from different survey years can",
        "create small steps at tile edges (see report 01).",
    ])
    log.info("done: %d sub-catchments, %d peat-dominated", len(basins), len(dom))


if __name__ == "__main__":
    main()
