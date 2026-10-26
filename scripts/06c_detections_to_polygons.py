"""
06c – From YOLO detections to 1880 classes, compared with the hand digitising

Runs in the OSGeo4W Shell (needs GDAL, GeoPandas, SciPy):
    python scripts\\06c_detections_to_polygons.py

Inputs
  data/interim/yolo/detections.csv   tufts + Torfstich in map coordinates (step 06b)
  config.YOLO["map_tif"]             1 m map, for the dash filter
  peat_1880 (hand digitising)        reference, only used for tuning + checking

Method (on a 25 m grid over the block)
  1. Dashes: connected ink components that are flat (≤ 3 m high) and 5–40 m
     long – the dashes of Bruch and nasse Wiese. Dotted Hutung rows, lettering,
     buildings and field lines fall outside these limits. Count per cell,
     averaged over a moving window → dash density.
  2. Tufts: detections per cell, summed over a 3 × 3 window (75 m).
  3. Torfstich: "recurring" = at least 2 chains within 275 m; cells within
     ~60 m of such a chain become Moor.
  4. Rules (as for the hand digitising):
       Moor        tufts ≥ T and dashes ≥ D   (Bruch)  –  or recurring Torfstich
       Heide       tufts ≥ T and dashes <  D
       nasse Wiese dashes ≥ D, no tufts
       –           otherwise
  5. 3 × 3 majority filter.
  6. Heath in a moor (digitising rule "heath tufts count as Moor only with moor
     context"): a Heide patch that touches Moor or lies within ~110 m of a
     recurring Torfstich becomes Moor. Bog heath on a drained raised bog has
     tufts but few dashes; on its own it would be read as Heide.
  The thresholds T and D and the Torfstich distance are tuned on the WEST half
  of the block; the result is checked on the EAST half, which the tuning never
  saw. (Rule 6 was added after a first run showed 174 ha "Heide" in the
  Königsmoor – it comes from the digitising rules, not from the check data.)

Outputs
  layers yolo_detections_<area>, yolo_1880_<area> in the project GeoPackage
  data/interim/yolo/yolo_classes.tif, outputs/06c_yolo_vs_hand_<area>.png
  docs/reports/06c_yolo_vs_hand_<area>.md
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geopandas as gpd  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from osgeo import gdal, ogr, osr  # noqa: E402
from scipy import ndimage as nd  # noqa: E402

import config as cfg  # noqa: E402
from peatsh.common import get_logger, write_layer, write_report  # noqa: E402

log = get_logger("06c")
gdal.UseExceptions()
Y = cfg.YOLO
CELL = 25                                  # m
DASH = {"max_h": 3, "min_w": 5, "max_w": 40, "window": 5}
TORF = {"recur_cells": 11, "near_cells": 5}   # 275 m, 125 m windows
NAMES = {0: "–", 1: "Moor", 2: "nasse Wiese", 3: "Heide"}
COLOURS = ["#ffffff", "#8c510a", "#2166ac", "#762a83"]


# ---------------------------------------------------------------------------
def load_map():
    ds = gdal.Open(str(Y["map_tif"]))
    gt = ds.GetGeoTransform()
    a = ds.GetRasterBand(1).ReadAsArray()
    res = gt[1]
    if res != 1:
        sys.exit("The dash filter expects the 1 m GeoTIFF from the WCS export.")
    return a == 0, gt, ds.GetProjection()


def dash_density(ink, n_r, n_c):
    lab, _ = nd.label(ink, structure=np.ones((3, 3)))
    sl = nd.find_objects(lab)
    h = np.array([s[0].stop - s[0].start for s in sl])
    w = np.array([s[1].stop - s[1].start for s in sl])
    r = np.array([(s[0].start + s[0].stop) // 2 for s in sl]) // CELL
    c = np.array([(s[1].start + s[1].stop) // 2 for s in sl]) // CELL
    m = (h <= DASH["max_h"]) & (w >= DASH["min_w"]) & (w <= DASH["max_w"]) & (r < n_r) & (c < n_c)
    g = np.zeros((n_r, n_c))
    np.add.at(g, (r[m], c[m]), 1)
    return nd.uniform_filter(g, DASH["window"], mode="nearest"), int(m.sum())


def count_grid(df, gt, n_r, n_c):
    g = np.zeros((n_r, n_c))
    c = ((df.x - gt[0]) // CELL).astype(int)
    r = ((gt[3] - df.y) // CELL).astype(int)
    ok = (r >= 0) & (r < n_r) & (c >= 0) & (c < n_c)
    np.add.at(g, (r[ok], c[ok]), 1)
    return g


def hand_raster(gt, proj, n_r, n_c):
    """Rasterise peat_1880 on the 25 m grid: 1 Moor, 2 nasse Wiese/nasser Boden, 3 Heide."""
    path = str(cfg.INPUTS["historical_peat"])
    src = ogr.Open(path)
    lyr = src.GetLayerByName(cfg.HISTORICAL["layer"])
    geom = lyr.GetGeometryColumn() or "geometry"
    sql = (f"SELECT {geom}, CASE hist_type WHEN 'Moor' THEN 1 WHEN 'nasse Wiese' THEN 2 "
           f"WHEN 'nasser Boden' THEN 2 WHEN 'Heide' THEN 3 ELSE 0 END AS code "
           f"FROM {cfg.HISTORICAL['layer']}")
    dst = gdal.GetDriverByName("MEM").Create("", n_c, n_r, 1, gdal.GDT_Byte)
    dst.SetGeoTransform((gt[0], CELL, 0, gt[3], 0, -CELL))
    dst.SetProjection(proj)
    gdal.Rasterize(dst, path, SQLStatement=sql, SQLDialect="SQLITE", attribute="code")
    return dst.GetRasterBand(1).ReadAsArray().astype(int)


def classify(tuft_w, dash, torf_moor, t_min, d_min):
    out = np.zeros(tuft_w.shape, int)
    wet = dash >= d_min
    out[wet] = 2
    out[(tuft_w >= t_min) & ~wet] = 3
    out[(tuft_w >= t_min) & wet] = 1
    out[torf_moor] = 1
    return majority(out)


def heath_in_moor(p, recurring, r_cells):
    """Heide patches touching Moor or near recurring Torfstich become Moor."""
    near = nd.binary_dilation(recurring, structure=np.ones((r_cells, r_cells)))
    moor_edge = nd.binary_dilation(p == 1)
    lab, n = nd.label(p == 3)
    out = p.copy()
    for i in range(1, n + 1):
        m = lab == i
        if (m & near).any() or (m & moor_edge).any():
            out[m] = 1
    return out


def majority(a):
    def mode(v):
        return np.bincount(v.astype(int), minlength=4).argmax()
    return nd.generic_filter(a, mode, size=3, mode="nearest").astype(int)


def kappa(ref, pred, k=4):
    cm = np.zeros((k, k))
    np.add.at(cm, (ref.ravel(), pred.ravel()), 1)
    n = cm.sum()
    po = np.trace(cm) / n
    pe = (cm.sum(0) * cm.sum(1)).sum() / n ** 2
    return (po - pe) / (1 - pe), po, cm


# ---------------------------------------------------------------------------
def main() -> None:
    det_path = cfg.DATA_INTERIM / "yolo" / "detections.csv"
    if not det_path.exists():
        sys.exit(f"Missing {det_path} – run 06b_predict.py in the YOLO environment first.")
    det = pd.read_csv(det_path)
    ink, gt, proj = load_map()
    n_r, n_c = ink.shape[0] // CELL, ink.shape[1] // CELL

    dash, n_dash = dash_density(ink, n_r, n_c)
    tuft = count_grid(det[det.cls == "tuft"], gt, n_r, n_c)
    tuft_w = nd.uniform_filter(tuft, 3, mode="constant") * 9            # sum over 3 × 3
    torf = count_grid(det[det.cls == "torfstich"], gt, n_r, n_c)
    k = TORF["recur_cells"]
    recurring = (nd.uniform_filter(torf, k, mode="constant") * k * k >= 2) & (torf > 0)
    torf_moor = nd.binary_dilation(recurring, structure=np.ones((TORF["near_cells"],) * 2))

    hand = hand_raster(gt, proj, n_r, n_c)
    west = np.zeros_like(hand, bool)
    west[:, : n_c // 2] = True

    # tune T, D and the heath-in-moor distance on the west half
    d_grid = np.unique(np.round(np.quantile(dash[dash > 0], np.linspace(0.05, 0.8, 31)), 3))
    best = None
    for t in (1, 2, 3, 4, 5, 6):
        for d in d_grid:
            base = classify(tuft_w, dash, torf_moor, t, d)
            for r_h in (9, 17):
                pred = heath_in_moor(base, recurring, r_h)
                kap = kappa(hand[west], pred[west])[0]
                if best is None or kap > best[0]:
                    best = (kap, t, d, r_h)
    _, t_min, d_min, r_heath = best
    pred = heath_in_moor(classify(tuft_w, dash, torf_moor, t_min, d_min), recurring, r_heath)
    log.info("tuned on west half: tufts ≥ %d per 75 m window, dash density ≥ %.3f, "
             "heath-in-moor distance %d m", t_min, d_min, r_heath // 2 * CELL)

    rows = []
    for name, m in (("west (tuning)", west), ("east (check)", ~west), ("whole block", np.ones_like(west))):
        kap, po, _ = kappa(hand[m], pred[m])
        rows.append({"area": name, "agreement": f"{po:.0%}", "kappa": round(kap, 2)})
    _, _, cm = kappa(hand[~west], pred[~west])
    ha = CELL * CELL / 1e4
    cm_df = pd.DataFrame(cm * ha, index=[f"hand: {NAMES[i]}" for i in range(4)],
                         columns=[f"YOLO: {NAMES[i]}" for i in range(4)]).round(0)
    iou = {NAMES[i]: round(cm[i, i] / (cm[i].sum() + cm[:, i].sum() - cm[i, i]), 2)
           if cm[i].sum() + cm[:, i].sum() else float("nan") for i in (1, 2, 3)}
    area = {NAMES[i]: (round((hand == i).sum() * ha), round((pred == i).sum() * ha)) for i in (1, 2, 3)}

    # outputs: class raster, polygons, detections
    out_tif = cfg.DATA_INTERIM / "yolo" / "yolo_classes.tif"
    drv = gdal.GetDriverByName("GTiff")
    r = drv.Create(str(out_tif), n_c, n_r, 1, gdal.GDT_Byte, options=["COMPRESS=DEFLATE"])
    r.SetGeoTransform((gt[0], CELL, 0, gt[3], 0, -CELL))
    r.SetProjection(proj)
    r.GetRasterBand(1).WriteArray(pred.astype(np.uint8))
    r.GetRasterBand(1).SetNoDataValue(0)
    r.FlushCache()
    mem = ogr.GetDriverByName("MEM" if ogr.GetDriverByName("MEM") else "Memory").CreateDataSource("m")
    srs = osr.SpatialReference()
    srs.ImportFromWkt(proj)
    pl = mem.CreateLayer("p", srs, ogr.wkbPolygon)
    pl.CreateField(ogr.FieldDefn("code", ogr.OFTInteger))
    gdal.Polygonize(r.GetRasterBand(1), r.GetRasterBand(1), pl, 0)
    r = None
    polys = gpd.GeoDataFrame.from_features(
        [{"type": "Feature", "geometry": __import__("json").loads(f.GetGeometryRef().ExportToJson()),
          "properties": {"code": f.GetField("code")}} for f in pl], crs=cfg.TARGET_CRS)
    polys = polys[polys.code > 0].dissolve("code").reset_index()
    polys["hist_type"] = polys.code.map(NAMES)
    polys = polys.explode(index_parts=False).reset_index(drop=True)
    polys["area_ha"] = polys.area / 1e4
    write_layer(polys[["hist_type", "area_ha", "geometry"]], "yolo_1880")
    pts = gpd.GeoDataFrame(det, geometry=gpd.points_from_xy(det.x, det.y), crs=cfg.TARGET_CRS)
    write_layer(pts, "yolo_detections")

    # figure: hand | YOLO | agreement
    ext = [gt[0], gt[0] + n_c * CELL, gt[3] - n_r * CELL, gt[3]]
    cmap = ListedColormap(COLOURS)
    fig, ax = plt.subplots(1, 3, figsize=(15, 5.6), dpi=130)
    for a_, data, title in ((ax[0], hand, "Hand digitising"), (ax[1], pred, "YOLO + rules")):
        a_.imshow(data, cmap=cmap, vmin=0, vmax=3, extent=ext, interpolation="nearest")
        a_.set_title(title, fontsize=10)
    agree = np.where(hand == pred, 1, 2)
    agree[(hand == 0) & (pred == 0)] = 0
    ax[2].imshow(agree, cmap=ListedColormap(["#ffffff", "#bdbdbd", "#e31a1c"]), vmin=0, vmax=2,
                 extent=ext, interpolation="nearest")
    ax[2].set_title("Agreement (grey) / disagreement (red)", fontsize=10)
    for a_ in ax:
        a_.axvline(gt[0] + n_c // 2 * CELL, color="k", lw=0.8, ls="--")
        a_.set_xticks([])
        a_.set_yticks([])
    ax[0].text(gt[0] + 100, gt[3] - 250, "west: tuning", fontsize=8)
    ax[0].text(gt[0] + n_c // 2 * CELL + 100, gt[3] - 250, "east: check", fontsize=8)
    fig.legend(handles=[Patch(color=COLOURS[i], label=NAMES[i]) for i in (1, 2, 3)],
               loc="lower center", ncol=3, fontsize=8, frameon=False)
    fig.text(0.01, 0.01, "1880 map © GeoBasis-DE/LVermGeo SH/CC BY 4.0", fontsize=6, color="#555")
    fig_path = cfg.OUTPUTS / f"06c_yolo_vs_hand_{cfg.aoi_label()}.png"
    fig.savefig(fig_path, bbox_inches="tight")
    plt.close(fig)

    write_report("06c_yolo_vs_hand", "Automated 1880 classes vs. hand digitising", [
        f"- detections used: {int((det.cls == 'tuft').sum())} tufts, "
        f"{int((det.cls == 'torfstich').sum())} Torfstich (from 06b)",
        f"- dash components (flat, {DASH['min_w']}–{DASH['max_w']} m): {n_dash:,}",
        f"- grid {CELL} m, dash window {DASH['window'] * CELL} m, tuft window 75 m",
        f"- tuned on the west half: **tufts ≥ {t_min}** per 75 m window, "
        f"**dash density ≥ {d_min:.3f}**, heath within **{r_heath // 2 * CELL} m** of recurring "
        "Torfstich (or touching Moor) → Moor", "",
        pd.DataFrame(rows).to_markdown(index=False), "",
        "Kappa: agreement beyond chance (0 = chance, 1 = perfect). The east half was "
        "not used for tuning – its value is the honest one.", "",
        "### Confusion matrix, east half (ha)", "", cm_df.to_markdown(), "",
        "### Per class (east half)", "",
        "| class | IoU | area hand ha (block) | area YOLO ha (block) |", "|---|---:|---:|---:|",
        *[f"| {k} | {iou[k]} | {area[k][0]:,} | {area[k][1]:,} |" for k in iou], "",
        f"![comparison](../../outputs/{fig_path.name})", "",
        "Limitations: names ('…moor') are not detected; the YOLO model was trained on "
        "32 tiles of the same block (some overlap with the evaluated area); "
        "Hutung/trockene Wiese are not separated (both count as '–'); "
        "rule 6 turns almost all Heide into Moor, so the small Heide class (29 ha by hand) "
        "is not reproduced.",
    ])
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
