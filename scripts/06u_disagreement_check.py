"""
06u – Blind check of two maps where they DISAGREE (decides between published and a new model)

Both maps agree on most of the area; there they are equally right or wrong.
Only the cells where they differ can show which map is better, so the sample
is drawn there (outside the hand-digitised block, inside the test area).

Step 1 – draw the sample (OSGeo4W Shell):
    python scripts\\06u_disagreement_check.py make <map A tif> <map B tif> [n]
  e.g. map A = data\\interim\\yolo\\final_v1\\yolo_classes_aoi.tif (published),
       map B = data\\interim\\yolo\\train13_aoi\\yolo_classes_aoi.tif, n = 40 (default).
  Writes data/raw/historical/check_points_new.gpkg (layer check_points, empty
  "ref"); both predictions go to data/interim/yolo/check_points_new_pred.csv
  (don't open it before step 2 – the check is blind).

Step 2 – in QGIS: enter in "ref" what the 1878–80 map shows at each point:
      Moor | nasse Wiese | Heide | none
  (same rules as 06v; judge the 25 m around the point; hide the yolo layers)

Step 3 – evaluate:
    python scripts\\06u_disagreement_check.py eval
  Points right for A and for B, and the estimated difference in overall
  accuracy (B − A, percentage points of the checked area) with a 95 % interval.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from osgeo import gdal, ogr  # noqa: E402

import config as cfg  # noqa: E402
from peatsh.common import get_logger  # noqa: E402

log = get_logger("06u")
gdal.UseExceptions()
SEED = 11
CLASSES = {0: "none", 1: "Moor", 2: "nasse Wiese", 3: "Heide"}
POINTS = cfg.DATA_RAW / "historical" / "check_points_new.gpkg"
PRED = cfg.DATA_INTERIM / "yolo" / "check_points_new_pred.csv"


def burn(path, gt, shape, proj):
    dst = gdal.GetDriverByName("MEM").Create("", shape[1], shape[0], 1, gdal.GDT_Byte)
    dst.SetGeoTransform(gt)
    dst.SetProjection(proj)
    src = ogr.Open(str(path))
    gdal.RasterizeLayer(dst, [1], src.GetLayer(0), burn_values=[1])
    return dst.GetRasterBand(1).ReadAsArray().astype(bool)


def read(path):
    ds = gdal.Open(str(path))
    return ds.GetRasterBand(1).ReadAsArray().astype(int), ds.GetGeoTransform(), ds.GetProjection()


def make(a_path: Path, b_path: Path, n: int) -> None:
    if POINTS.exists():
        sys.exit(f"{POINTS} exists already – delete it first if you really want a new sample.")
    a, gt, proj = read(a_path)
    b, gt_b, _ = read(b_path)
    if a.shape != b.shape or gt != gt_b:
        sys.exit("The two maps are not on the same grid.")
    valid = burn(cfg.TEST_AOI, gt, a.shape, proj) & ~burn(cfg.INPUTS["historical_extent"], gt, a.shape, proj)
    diff = valid & (a != b)
    rr, cc = np.nonzero(diff)
    cell_ha = abs(gt[1] * gt[5]) / 1e4
    log.info("checked area %.0f ha, maps disagree on %.0f ha (%.1f %%)",
             valid.sum() * cell_ha, diff.sum() * cell_ha, 100 * diff.sum() / valid.sum())
    rnd = np.random.default_rng(SEED)
    pick = rnd.choice(len(rr), size=min(n, len(rr)), replace=False)
    rows = []
    for k, i in enumerate(pick, 1):
        x = gt[0] + (cc[i] + rnd.uniform(0.2, 0.8)) * gt[1]
        y = gt[3] + (rr[i] + rnd.uniform(0.2, 0.8)) * gt[5]
        rows.append({"point_id": k, "pred_a": CLASSES[a[rr[i], cc[i]]],
                     "pred_b": CLASSES[b[rr[i], cc[i]]], "x": x, "y": y})
    df = pd.DataFrame(rows)
    meta = pd.DataFrame([{"point_id": 0, "pred_a": str(a_path), "pred_b": str(b_path),
                          "x": diff.sum() * cell_ha, "y": valid.sum() * cell_ha}])
    pd.concat([meta, df]).to_csv(PRED, index=False)
    pts = gpd.GeoDataFrame({"point_id": df.point_id, "ref": [None] * len(df), "note": [None] * len(df)},
                           geometry=gpd.points_from_xy(df.x, df.y), crs=cfg.TARGET_CRS)
    pts.to_file(POINTS, layer="check_points", driver="GPKG")
    log.info("%d points written to %s", len(pts), POINTS)
    print(pd.crosstab(df.pred_a, df.pred_b).to_string())


def evaluate() -> None:
    raw = pd.read_csv(PRED)
    meta, pred = raw[raw.point_id == 0].iloc[0], raw[raw.point_id > 0]
    diff_ha, valid_ha = float(meta.x), float(meta.y)
    ref = gpd.read_file(POINTS, layer="check_points")[["point_id", "ref"]]
    df = pred.merge(ref, on="point_id")
    canon = {v.lower(): v for v in CLASSES.values()}          # accept "None", "moor", ...
    df["ref"] = df["ref"].fillna("").str.strip().str.lower().map(canon).fillna("")
    todo = df[~df.ref.isin(CLASSES.values())]
    if len(todo):
        log.warning("%d points without a valid 'ref' are left out: %s", len(todo), list(todo.point_id))
    df = df[df.ref.isin(CLASSES.values())]
    a_ok, b_ok = df.pred_a == df.ref, df.pred_b == df.ref
    d = b_ok.astype(int) - a_ok.astype(int)       # +1 B right, −1 A right, 0 neither
    n = len(df)
    share = diff_ha / valid_ha
    gain = 100 * share * d.mean()
    ci = 100 * share * 1.96 * d.std(ddof=1) / np.sqrt(n) if n > 1 else float("nan")
    print(f"map A: {meta.pred_a}\nmap B: {meta.pred_b}")
    print(f"maps disagree on {diff_ha:.0f} of {valid_ha:.0f} ha ({100 * share:.1f} %); {n} points checked")
    print(f"A right: {a_ok.sum()}   B right: {b_ok.sum()}   neither: {(~a_ok & ~b_ok).sum()}")
    print(f"overall accuracy B − A: {gain:+.1f} percentage points (95 %: {gain - ci:+.1f} to {gain + ci:+.1f})")
    print("\nby reference class (A right / B right):")
    print(df.assign(A=a_ok, B=b_ok).groupby("ref")[["A", "B"]].sum().to_string())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "make":
        if len(sys.argv) < 4:
            sys.exit("usage: 06u_disagreement_check.py make <map A tif> <map B tif> [n]")
        make(Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else 40)
    elif len(sys.argv) > 1 and sys.argv[1] == "eval":
        evaluate()
    else:
        sys.exit(__doc__)
