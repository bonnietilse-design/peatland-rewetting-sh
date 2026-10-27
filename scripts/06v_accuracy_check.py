"""
06v – Blind accuracy check of the automated 1880 map outside the hand-digitised block

Step 1 – draw the sample (OSGeo4W Shell):
    python scripts\\06v_accuracy_check.py make
  Draws N_PER_CLASS random points per predicted class (Moor, nasse Wiese, Heide,
  none) inside the test area but OUTSIDE the hand-digitised block, from
  data/interim/yolo/yolo_classes_aoi.tif (step 06c aoi).
  Writes data/raw/historical/check_points.gpkg, layer check_points, with an empty
  field "ref" – the prediction is NOT stored in that layer, so the check is blind.
  The predictions go to data/interim/yolo/check_points_pred.csv.

Step 2 – in QGIS: for every point, look at the 1878–80 map (Chronologen) at the
  point and enter what the map shows there in "ref":
      Moor | nasse Wiese | Heide | none
  (same legend and rules as the hand digitising; judge the 25 m around the point;
  hide the yolo_1880 layers while doing this)

Step 3 – evaluate:
    python scripts\\06v_accuracy_check.py eval
  ...
Step 4 (optional) – evaluate a NEW map (e.g. a retrained model) with the same
  points and your same reference readings:
    python scripts\\06v_accuracy_check.py compare data\\interim\\yolo\\round1\\yolo_classes_aoi.tif
  The argument is the map the sample was DRAWN from (it defines the strata and
  their weights); the new map is the current yolo_classes_aoi.tif. Estimator
  for strata that differ from the map classes: Stehman S.V. (2014), Int. J.
  Remote Sensing 35: 4923–4939.
  Confusion matrix, overall accuracy, user's and producer's accuracy per class,
  all weighted by the mapped area of each class (Olofsson et al. 2014,
  stratified estimator), plus area estimates with 95 % confidence intervals.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from osgeo import gdal, ogr  # noqa: E402

import config as cfg  # noqa: E402
from peatsh.common import get_logger, write_report  # noqa: E402

log = get_logger("06v")
gdal.UseExceptions()
N_PER_CLASS = 25
SEED = 7
CLASSES = {0: "none", 1: "Moor", 2: "nasse Wiese", 3: "Heide"}
RASTER = cfg.DATA_INTERIM / "yolo" / "yolo_classes_aoi.tif"
POINTS = cfg.DATA_RAW / "historical" / "check_points.gpkg"
PRED = cfg.DATA_INTERIM / "yolo" / "check_points_pred.csv"


def burn(path, gt, shape, proj):
    dst = gdal.GetDriverByName("MEM").Create("", shape[1], shape[0], 1, gdal.GDT_Byte)
    dst.SetGeoTransform(gt)
    dst.SetProjection(proj)
    src = ogr.Open(str(path))              # keep a reference, or the layer dies with it
    gdal.RasterizeLayer(dst, [1], src.GetLayer(0), burn_values=[1])
    return dst.GetRasterBand(1).ReadAsArray().astype(bool)


def load():
    if not RASTER.exists():
        sys.exit(f"Missing {RASTER} – run 06c_detections_to_polygons.py aoi first.")
    ds = gdal.Open(str(RASTER))
    gt, proj = ds.GetGeoTransform(), ds.GetProjection()
    cls = ds.GetRasterBand(1).ReadAsArray().astype(int)
    aoi = burn(cfg.TEST_AOI, gt, cls.shape, proj)
    block = burn(cfg.INPUTS["historical_extent"], gt, cls.shape, proj)
    return cls, gt, aoi & ~block


def make() -> None:
    if POINTS.exists():
        sys.exit(f"{POINTS} exists already – delete it first if you really want a new sample "
                 "(your entries in 'ref' would be lost).")
    cls, gt, valid = load()
    rnd = np.random.default_rng(SEED)
    rows = []
    for code, name in CLASSES.items():
        rr, cc = np.nonzero(valid & (cls == code))
        if len(rr) == 0:
            continue
        pick = rnd.choice(len(rr), size=min(N_PER_CLASS, len(rr)), replace=False)
        for i in pick:
            # random position inside the 25 m cell
            x = gt[0] + (cc[i] + rnd.uniform(0.2, 0.8)) * gt[1]
            y = gt[3] + (rr[i] + rnd.uniform(0.2, 0.8)) * gt[5]
            rows.append({"pred": name, "x": x, "y": y})
    df = pd.DataFrame(rows).sample(frac=1, random_state=SEED).reset_index(drop=True)
    df.insert(0, "point_id", np.arange(1, len(df) + 1))
    df.to_csv(PRED, index=False)
    pts = gpd.GeoDataFrame({"point_id": df.point_id, "ref": [None] * len(df), "note": [None] * len(df)},
                           geometry=gpd.points_from_xy(df.x, df.y), crs=cfg.TARGET_CRS)
    pts.to_file(POINTS, layer="check_points", driver="GPKG")
    log.info("%d points written to %s (prediction kept separately in %s)", len(pts), POINTS, PRED)
    print(df.pred.value_counts().to_string())


def evaluate() -> None:
    pts = gpd.read_file(POINTS, layer="check_points")
    pred = pd.read_csv(PRED)
    df = pred.merge(pts[["point_id", "ref"]], on="point_id")
    df["ref"] = df.ref.fillna("").str.strip()
    alias = {"": None, "-": "none", "–": "none", "keine": "none", "nasse wiese": "nasse Wiese",
             "moor": "Moor", "heide": "Heide", "none": "none"}
    df["ref"] = df.ref.map(lambda v: alias.get(v.lower(), v) if isinstance(v, str) else v)
    todo = df[df.ref.isna()]
    bad = df[~df.ref.isna() & ~df.ref.isin(CLASSES.values())]
    if len(bad):
        sys.exit(f"Unknown ref values: {sorted(bad.ref.unique())} – use {list(CLASSES.values())}")
    df = df[~df.ref.isna()]
    if len(todo):
        log.warning("%d points without ref are skipped", len(todo))

    # mapped area per class outside the block (weights)
    cls, gt, valid = load()
    cell_ha = abs(gt[1] * gt[5]) / 1e4
    names = list(CLASSES.values())
    area = pd.Series({n: (valid & (cls == c)).sum() * cell_ha for c, n in CLASSES.items()})
    w = area / area.sum()

    cm = pd.crosstab(df.pred, df.ref).reindex(index=names, columns=names, fill_value=0)
    n_i = cm.sum(axis=1)
    p = cm.div(n_i.replace(0, np.nan), axis=0).mul(w, axis=0).fillna(0)     # estimated area shares
    oa = np.trace(p.values)
    ua = pd.Series({k: cm.loc[k, k] / n_i[k] if n_i[k] else np.nan for k in names})
    pa = pd.Series({k: p.loc[k, k] / p[k].sum() if p[k].sum() else np.nan for k in names})
    # standard errors (Olofsson et al. 2014, eq. 5 and 10)
    se_oa = np.sqrt(sum(w[k] ** 2 * ua[k] * (1 - ua[k]) / (n_i[k] - 1)
                        for k in names if n_i[k] > 1 and not np.isnan(ua[k])))
    area_est = p.sum(axis=0) * area.sum()
    se_area = pd.Series({j: area.sum() * np.sqrt(sum(
        w[i] ** 2 * (cm.loc[i, j] / n_i[i]) * (1 - cm.loc[i, j] / n_i[i]) / (n_i[i] - 1)
        for i in names if n_i[i] > 1)) for j in names})

    tab = pd.DataFrame({"mapped ha": area.round(0), "sample": n_i,
                        "user's acc.": ua.round(2), "producer's acc.": pa.round(2),
                        "estimated ha": area_est.round(0),
                        "± 95 % ha": (1.96 * se_area).round(0)})
    write_report("06v_accuracy_check", "Blind accuracy check outside the hand-digitised block", [
        f"- {len(df)} checked points ({len(todo)} left empty), stratified by predicted class, "
        f"outside the hand-digitised block; reference read by me from the 1878–80 map without "
        "seeing the prediction",
        f"- **overall accuracy {oa:.0%} ± {1.96 * se_oa:.0%}** (area-weighted, 95 % CI)", "",
        "### Confusion matrix (sample counts; rows = automated map, columns = my reading)", "",
        cm.to_markdown(), "",
        "### Per class (area-weighted)", "", tab.to_markdown(), "",
        "User's accuracy: of the area mapped as a class, the share that really is that class. "
        "Producer's accuracy: of the real area of a class, the share the map finds. "
        "Estimated ha: area of each class corrected for the map errors.", "",
        "Method: Olofsson P. et al. (2014): Good practices for estimating area and assessing "
        "accuracy of land change. Remote Sensing of Environment 148: 42–57.",
    ])
    print(cm.to_string())
    print(f"\noverall accuracy {oa:.0%} ± {1.96 * se_oa:.0%}")
    print(tab.to_string())


def compare(strata_path: Path) -> None:
    """Accuracy of the CURRENT map, using the sample drawn from an older map."""
    if not strata_path.is_absolute():
        strata_path = cfg.ROOT / strata_path
    if not strata_path.exists():
        sys.exit(f"Missing {strata_path} – the map the check points were drawn from.")
    pts = gpd.read_file(POINTS, layer="check_points")
    pred = pd.read_csv(PRED)                       # pred = stratum (old map class)
    df = pred.merge(pts[["point_id", "ref"]], on="point_id")
    alias = {"": None, "-": "none", "–": "none", "keine": "none", "nasse wiese": "nasse Wiese",
             "moor": "Moor", "heide": "Heide", "none": "none"}
    df["ref"] = df.ref.fillna("").astype(str).str.strip().map(lambda v: alias.get(v.lower(), v))
    df = df[df.ref.notna()].copy()
    names = list(CLASSES.values())

    # new map value at each point
    ds = gdal.Open(str(RASTER))
    gt = ds.GetGeoTransform()
    new = ds.GetRasterBand(1).ReadAsArray().astype(int)
    ds = None
    col = ((df.x - gt[0]) / gt[1]).astype(int)
    row = ((df.y - gt[3]) / gt[5]).astype(int)
    df["new"] = [CLASSES.get(int(new[r, c]), "none") for r, c in zip(row, col)]

    # strata weights = area of each OLD map class outside the block
    sds = gdal.Open(str(strata_path))
    sgt, sproj = sds.GetGeoTransform(), sds.GetProjection()
    old = sds.GetRasterBand(1).ReadAsArray().astype(int)
    sds = None
    aoi = burn(cfg.TEST_AOI, sgt, old.shape, sproj)
    block = burn(cfg.INPUTS["historical_extent"], sgt, old.shape, sproj)
    valid = aoi & ~block
    cell_ha = abs(sgt[1] * sgt[5]) / 1e4
    area_h = pd.Series({n: (valid & (old == c)).sum() * cell_ha for c, n in CLASSES.items()})
    W = area_h / area_h.sum()
    n_h = df.groupby("pred").size().reindex(names, fill_value=0)

    def est(ind: pd.Series) -> tuple[float, float]:
        """Stratified mean of an indicator and its standard error."""
        m, v = 0.0, 0.0
        for h in names:
            y = ind[df.pred == h]
            if len(y) == 0:
                continue
            m += W[h] * y.mean()
            if len(y) > 1:
                v += W[h] ** 2 * y.var(ddof=1) / len(y)
        return m, float(np.sqrt(v))

    new_area = pd.Series({n: (valid & (new == c)).sum() * cell_ha for c, n in CLASSES.items()}) \
        if new.shape == old.shape else None

    def summary(map_col: str) -> tuple[float, float, pd.DataFrame]:
        oa, se = est((df[map_col] == df.ref).astype(float))
        rows = {}
        for k in names:
            p_map, _ = est((df[map_col] == k).astype(float))
            p_ref, se_ref = est((df.ref == k).astype(float))
            p_ok, _ = est(((df[map_col] == k) & (df.ref == k)).astype(float))
            rows[k] = {"user's acc.": round(p_ok / p_map, 2) if p_map else np.nan,
                       "producer's acc.": round(p_ok / p_ref, 2) if p_ref else np.nan,
                       "mapped ha": round(area_h[k] if map_col == "pred" else
                                          new_area[k] if new_area is not None else p_map * area_h.sum()),
                       "estimated ha": round(p_ref * area_h.sum()),
                       "± 95 % ha": round(1.96 * se_ref * area_h.sum())}
        return oa, se, pd.DataFrame(rows).T

    oa_old, se_old, t_old = summary("pred")
    oa_new, se_new, t_new = summary("new")
    paired = pd.crosstab(df.pred == df.ref, df.new == df.ref).reindex(
        index=[True, False], columns=[True, False], fill_value=0)
    write_report("06v_accuracy_compare", "Blind accuracy check: new map vs. the map the sample came from", [
        f"- {len(df)} reference points (the same as in report 06v), outside the hand-digitised block",
        f"- sample drawn from `{strata_path.name}` (strata); new map: `{RASTER.name}`",
        f"- **overall accuracy: old map {oa_old:.0%} ± {1.96 * se_old:.0%} → new map "
        f"{oa_new:.0%} ± {1.96 * se_new:.0%}** (area-weighted, 95 % CI)", "",
        "Points right/wrong in old (rows) and new map (columns):", "",
        paired.rename(index={True: "old right", False: "old wrong"},
                      columns={True: "new right", False: "new wrong"}).to_markdown(), "",
        "### Old map", "", t_old.to_markdown(), "",
        "### New map", "", t_new.to_markdown(), "",
        "The new map is evaluated with the strata of the old one (Stehman 2014): each point "
        "keeps the weight of the stratum it was drawn from. The confidence intervals overlap "
        "strongly when both maps are similar – look at the points that changed (table above).",
    ])
    print(f"overall accuracy old {oa_old:.0%} ± {1.96 * se_old:.0%}  →  new {oa_new:.0%} ± {1.96 * se_new:.0%}")
    print(paired.to_string())
    print("\nnew map:\n" + t_new.to_string())


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "make":
        make()
    elif mode == "eval":
        evaluate()
    elif mode == "compare" and len(sys.argv) > 2:
        compare(Path(sys.argv[2]))
    else:
        sys.exit("Use:  python scripts\\06v_accuracy_check.py make  |  ... eval  |  "
                 "... compare <tif the sample was drawn from>")
