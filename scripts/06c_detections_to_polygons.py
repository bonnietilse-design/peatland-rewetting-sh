"""
06c – From YOLO detections to 1880 classes, compared with the hand digitising

Runs in the OSGeo4W Shell (needs GDAL, GeoPandas, SciPy):
    python scripts\\06c_detections_to_polygons.py        block: tune + check (default)
    python scripts\\06c_detections_to_polygons.py aoi    whole test area: apply the
        thresholds tuned on the block (rule_parameters.json) – no new tuning

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
     context"): a Heide patch that lies within ~110 m of a recurring Torfstich,
     or touches Moor at least as large as itself, becomes Moor. Bog heath on a drained raised bog has
     tufts but few dashes; on its own it would be read as Heide.
  The thresholds T and D and the Torfstich distance are tuned on the WEST half
  of the block; the result is checked on the EAST half, which the tuning never
  saw. (Rule 6 was added after a first run showed 174 ha "Heide" in the
  Königsmoor – it comes from the digitising rules, not from the check data.
  Two refinements followed the first run on the whole test area, where a heath
  near Friedrichsneuland came out as Moor: tuft base lines no longer count as
  dashes, and heath only joins a moor that is at least as large as itself.
  On the block they leave the check result unchanged.)

Outputs (block; the AOI run adds "_aoi" to every name)
  layers yolo_detections_<area>, yolo_1880_<area> in the project GeoPackage
  data/interim/yolo/rule_parameters.json (block only)
  data/interim/yolo/yolo_classes.tif, outputs/06c_yolo_vs_hand_<area>.png
  docs/reports/06c_yolo_vs_hand_<area>.md
"""
import json
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
from scipy.spatial import cKDTree  # noqa: E402

import config as cfg  # noqa: E402
from peatsh.common import get_logger, write_layer, write_report  # noqa: E402

log = get_logger("06c")
gdal.UseExceptions()
Y = cfg.YOLO
CELL = 25                                  # m
DASH = {"max_h": 3, "min_w": 5, "max_w": 40, "window": 5,
        "tuft_base_m": 10}    # flat marks this close to a detected tuft are its base line, not a dash
TORF = {"recur_cells": 11, "near_cells": 5}   # 275 m, 125 m windows
NAMES = {0: "–", 1: "Moor", 2: "nasse Wiese", 3: "Heide"}
COLOURS = ["#ffffff", "#8c510a", "#2166ac", "#762a83"]


# ---------------------------------------------------------------------------
def open_map(path):
    ds = gdal.Open(str(path))
    gt = ds.GetGeoTransform()
    if gt[1] != 1:
        sys.exit("The dash filter expects the 1 m GeoTIFF from the WCS export.")
    return ds, gt, ds.GetProjection()


def dash_density(ds, n_r, n_c, gt, tufts, chunk=2500, margin=60):
    """Count dash components per 25 m cell, reading the map in overlapping chunks
    (the whole test area is ~700 million pixels). A component is counted in the
    chunk that contains its centre. Flat marks within DASH["tuft_base_m"] of a
    detected tuft are tuft base lines and are not counted - otherwise heath
    (tufts on open ground) looks like Bruch (tufts + dashes)."""
    tree = cKDTree(np.c_[tufts.x - gt[0], gt[3] - tufts.y]) if len(tufts) else None
    band = ds.GetRasterBand(1)
    W, H = ds.RasterXSize, ds.RasterYSize
    g = np.zeros((n_r, n_c))
    total = 0
    for y0 in range(0, H, chunk):
        for x0 in range(0, W, chunk):
            xa, ya = max(0, x0 - margin), max(0, y0 - margin)
            xb, yb = min(W, x0 + chunk + margin), min(H, y0 + chunk + margin)
            ink = band.ReadAsArray(xa, ya, xb - xa, yb - ya) == 0
            lab, n = nd.label(ink, structure=np.ones((3, 3)))
            if n == 0:
                continue
            sl = nd.find_objects(lab)
            h = np.array([s[0].stop - s[0].start for s in sl])
            w = np.array([s[1].stop - s[1].start for s in sl])
            cy = np.array([(s[0].start + s[0].stop) // 2 for s in sl]) + ya
            cx = np.array([(s[1].start + s[1].stop) // 2 for s in sl]) + xa
            core = (cx >= x0) & (cx < x0 + chunk) & (cy >= y0) & (cy < y0 + chunk)
            m = core & (h <= DASH["max_h"]) & (w >= DASH["min_w"]) & (w <= DASH["max_w"])
            if tree is not None and m.any():
                dist, _ = tree.query(np.c_[cx[m], cy[m]])
                m[np.flatnonzero(m)[dist <= DASH["tuft_base_m"]]] = False
            r, c = cy[m] // CELL, cx[m] // CELL
            ok = (r < n_r) & (c < n_c)
            np.add.at(g, (r[ok], c[ok]), 1)
            total += int(ok.sum())
    return nd.uniform_filter(g, DASH["window"], mode="nearest"), total


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


def mask_raster(path, gt, proj, n_r, n_c):
    """1 inside the polygons of a vector file (AOI, digitised extent), else 0."""
    dst = gdal.GetDriverByName("MEM").Create("", n_c, n_r, 1, gdal.GDT_Byte)
    dst.SetGeoTransform((gt[0], CELL, 0, gt[3], 0, -CELL))
    dst.SetProjection(proj)
    src = ogr.Open(str(path))
    gdal.RasterizeLayer(dst, [1], src.GetLayer(0), burn_values=[1])
    return dst.GetRasterBand(1).ReadAsArray().astype(bool)


def classify(tuft_w, dash, torf_moor, t_min, d_min):
    out = np.zeros(tuft_w.shape, int)
    wet = dash >= d_min
    out[wet] = 2
    out[(tuft_w >= t_min) & ~wet] = 3
    out[(tuft_w >= t_min) & wet] = 1
    out[torf_moor] = 1
    return majority(out)


def heath_in_moor(p, recurring, r_cells):
    """Heath inside a moor becomes Moor: a Heide patch near recurring Torfstich,
    or touching Moor that is at least as large as the heath patch itself.
    (A large heath with a few moor-like cells at its edge stays heath.)"""
    near = nd.binary_dilation(recurring, structure=np.ones((r_cells, r_cells)))
    hl, hn = nd.label(p == 3)
    ml, _ = nd.label(p == 1)
    out = p.copy()
    if hn == 0:
        return out
    m_size = np.bincount(ml.ravel())
    h_size = np.bincount(hl.ravel())
    touch = nd.grey_dilation(ml, size=3)            # Moor label next to each cell
    near_hit = set(np.unique(hl[near & (hl > 0)]))
    for i in range(1, hn + 1):
        cells = hl == i
        if i in near_hit:
            out[cells] = 1
            continue
        t = np.unique(touch[cells])
        t = t[t > 0]
        if len(t) and m_size[t].sum() >= h_size[i]:
            out[cells] = 1
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


def save_outputs(pred, det, gt, proj, n_r, n_c, suffix):
    """Class raster, polygons and detection points."""
    out_tif = cfg.DATA_INTERIM / "yolo" / f"yolo_classes{suffix}.tif"
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
        [{"type": "Feature", "geometry": json.loads(f.GetGeometryRef().ExportToJson()),
          "properties": {"code": f.GetField("code")}} for f in pl], crs=cfg.TARGET_CRS)
    polys = polys[polys.code > 0].dissolve("code").reset_index()
    polys["hist_type"] = polys.code.map(NAMES)
    polys = polys.explode(index_parts=False).reset_index(drop=True)
    polys["area_ha"] = polys.area / 1e4
    write_layer(polys[["hist_type", "area_ha", "geometry"]], f"yolo_1880{suffix}")
    pts = gpd.GeoDataFrame(det, geometry=gpd.points_from_xy(det.x, det.y), crs=cfg.TARGET_CRS)
    write_layer(pts, f"yolo_detections{suffix}")


def apply_aoi(det, dash, n_dash, tuft_w, recurring, torf_moor, gt, proj, n_r, n_c, A):
    """Whole test area: fixed thresholds from the block, no tuning."""
    if not cfg.YOLO_RULES.exists():
        sys.exit(f"Missing {cfg.YOLO_RULES} – run 06c on the block first (it tunes the thresholds).")
    P = json.loads(cfg.YOLO_RULES.read_text(encoding="utf-8"))
    pred = heath_in_moor(classify(tuft_w, dash, torf_moor, P["t_min"], P["d_min"]),
                         recurring, P["r_heath"])
    aoi = mask_raster(cfg.TEST_AOI, gt, proj, n_r, n_c)
    pred[~aoi] = 0
    save_outputs(pred, det, gt, proj, n_r, n_c, A["suffix"])

    # consistency check: the AOI run inside the hand-digitised block
    block = mask_raster(cfg.INPUTS["historical_extent"], gt, proj, n_r, n_c) & aoi
    hand = hand_raster(gt, proj, n_r, n_c)
    kap, po, _ = kappa(hand[block], pred[block])
    ha = CELL * CELL / 1e4
    tab = pd.DataFrame({"class": [NAMES[i] for i in (1, 2, 3)],
                        "ha (whole AOI)": [round((pred[aoi] == i).sum() * ha) for i in (1, 2, 3)],
                        "share of AOI": [f"{(pred[aoi] == i).mean():.0%}" for i in (1, 2, 3)]})

    ext = [gt[0], gt[0] + n_c * CELL, gt[3] - n_r * CELL, gt[3]]
    fig, ax = plt.subplots(figsize=(8.5, 8.5), dpi=140)
    show = np.where(aoi, pred, np.nan)
    ax.imshow(show, cmap=ListedColormap(COLOURS), vmin=0, vmax=3, extent=ext, interpolation="nearest")
    ax.contour(np.flipud(aoi.astype(float)), levels=[0.5], colors="k", linewidths=0.8,
               extent=ext, origin="lower")
    ax.contour(np.flipud(block.astype(float)), levels=[0.5], colors="#d62728", linewidths=1.2,
               extent=ext, origin="lower")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Wet signatures 1878–80, read automatically (YOLO + rules)\n"
                 "red: hand-digitised block used for training and tuning", fontsize=10)
    ax.legend(handles=[Patch(color=COLOURS[i], label=NAMES[i]) for i in (1, 2, 3)],
              loc="lower left", fontsize=8, framealpha=0.95)
    fig.text(0.01, 0.01, "1880 map © GeoBasis-DE/LVermGeo SH/CC BY 4.0", fontsize=6, color="#555")
    fig_path = cfg.OUTPUTS / f"06c_yolo{A['suffix']}_{cfg.aoi_label()}.png"
    fig.savefig(fig_path, bbox_inches="tight")
    plt.close(fig)

    write_report("06c_yolo" + A["suffix"], "1880 classes for the whole test area (YOLO + rules)", [
        f"- detections: {int((det.cls == 'tuft').sum()):,} tufts, "
        f"{int((det.cls == 'torfstich').sum()):,} Torfstich (06b aoi)",
        f"- dash components: {n_dash:,}",
        f"- thresholds from the block (not re-tuned): tufts ≥ {P['t_min']} per 75 m window, "
        f"dash density ≥ {P['d_min']:.3f}, heath-in-moor distance {P['r_heath'] // 2 * CELL} m",
        f"- AOI: {aoi.sum() * ha:,.0f} ha", "",
        tab.to_markdown(index=False), "",
        f"Consistency check inside the hand-digitised block (same thresholds, AOI tiling): "
        f"agreement **{po:.0%}**, κ = **{kap:.2f}**.", "",
        f"![map](../../outputs/{fig_path.name})", "",
        "Outside the block there is no reference: check the spot-check images "
        "(outputs/yolo_spotcheck) and a few areas in QGIS before relying on the result there.",
    ])
    print(tab.to_string(index=False))
    print(f"inside the block: agreement {po:.0%}, kappa {kap:.2f}")


# ---------------------------------------------------------------------------
def main() -> None:
    area, A = cfg.yolo_area(sys.argv)
    det_path = A["detections"]
    if not det_path.exists():
        sys.exit(f"Missing {det_path} – run 06b_predict.py {area} in the YOLO environment first.")
    det = pd.read_csv(det_path)
    ds, gt, proj = open_map(A["map_tif"])
    n_r, n_c = ds.RasterYSize // CELL, ds.RasterXSize // CELL

    dash, n_dash = dash_density(ds, n_r, n_c, gt, det[det.cls == "tuft"])
    ds = None
    tuft = count_grid(det[det.cls == "tuft"], gt, n_r, n_c)
    tuft_w = nd.uniform_filter(tuft, 3, mode="constant") * 9            # sum over 3 × 3
    torf = count_grid(det[det.cls == "torfstich"], gt, n_r, n_c)
    k = TORF["recur_cells"]
    recurring = (nd.uniform_filter(torf, k, mode="constant") * k * k >= 2) & (torf > 0)
    torf_moor = nd.binary_dilation(recurring, structure=np.ones((TORF["near_cells"],) * 2))

    if area == "aoi":
        apply_aoi(det, dash, n_dash, tuft_w, recurring, torf_moor, gt, proj, n_r, n_c, A)
        return

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
    cfg.YOLO_RULES.write_text(json.dumps({"t_min": int(t_min), "d_min": float(d_min),
                                          "r_heath": int(r_heath), "tuned_on": "west half of the block"},
                                         indent=2), encoding="utf-8")

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

    save_outputs(pred, det, gt, proj, n_r, n_c, A["suffix"])

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
        "Torfstich (or joined to a larger Moor) → Moor", "",
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
        "the small Heide class (29 ha by hand) is hardly reproduced.",
    ])
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
