"""
06b – Run the trained YOLO model on every tile of the block

Runs in the YOLO environment (plain Command Prompt, yolo-env activated):
    python scripts\\06b_predict.py
    python scripts\\06b_predict.py data\\interim\\yolo\\runs\\detect\\runs\\train2\\weights\\best.pt 0.20

Reads   data/interim/yolo/tiles/*.png + .wld world files (step 06x)
Writes  data/interim/yolo/detections.csv – one row per detection, in map
        coordinates (EPSG:25832): cls, x, y, w_m, h_m, conf, tile_id

Duplicates (several boxes on the same symbol, common at low confidence
thresholds) are merged: detections of the same class whose centres lie
closer than MERGE_M[cls] are reduced to the one with the highest confidence.
Tiles are processed one by one, so symbols on a tile edge can appear in two
neighbouring tiles; the merge also removes those.
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from ultralytics import YOLO  # noqa: E402

import config as cfg  # noqa: E402

Y = cfg.YOLO
NAMES = dict(enumerate(Y["classes"]))
MERGE_M = {"tuft": 8.0, "torfstich": 20.0}
DEFAULT_WEIGHTS = cfg.DATA_INTERIM / "yolo" / "runs" / "detect" / "runs" / "train2" / "weights" / "best.pt"


def world_file(png: Path):
    """Six-line world file: pixel size x, rot, rot, -pixel size y, x of centre of top-left px, y."""
    for ext in (".wld", ".pgw"):                       # GDAL writes .wld
        wf = png.with_suffix(ext)
        if wf.exists():
            break
    else:
        sys.exit(f"No world file (.wld/.pgw) next to {png}")
    v = [float(s) for s in wf.read_text().split()]
    return v[0], v[3], v[4], v[5]                      # dx, dy (negative), x0c, y0c


def merge(rows: list[dict]) -> list[dict]:
    out = []
    for name in NAMES.values():
        r = sorted((d for d in rows if d["cls"] == name), key=lambda d: -d["conf"])
        if not r:
            continue
        xy = np.array([[d["x"], d["y"]] for d in r])
        taken = np.zeros(len(r), bool)
        for i in range(len(r)):
            if taken[i]:
                continue
            out.append(r[i])
            near = np.hypot(*(xy - xy[i]).T) < MERGE_M[name]
            taken |= near
    return out


def main() -> None:
    weights = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_WEIGHTS
    if not weights.is_absolute():
        weights = ROOT / weights
    conf = float(sys.argv[2]) if len(sys.argv) > 2 else 0.20
    tiles = sorted(Y["tile_dir"].glob("*.png"))
    if not tiles:
        sys.exit(f"No tiles in {Y['tile_dir']} – run 06x first.")
    model = YOLO(str(weights))
    rows = []
    for i, png in enumerate(tiles, 1):
        dx, dy, x0c, y0c = world_file(png)
        res = model.predict(str(png), conf=conf, imgsz=Y["tile_px"], device="cpu", verbose=False)[0]
        b = res.boxes
        for (cx, cy, w, h), c, k in zip(b.xywh.numpy(), b.conf.numpy(), b.cls.numpy().astype(int)):
            rows.append({"cls": NAMES[k],
                         "x": x0c + cx * dx - dx / 2,     # world file refers to pixel centres
                         "y": y0c + cy * dy - dy / 2,
                         "w_m": w * dx, "h_m": h * -dy,
                         "conf": float(c), "tile_id": png.stem})
        if i % 50 == 0 or i == len(tiles):
            print(f"{i}/{len(tiles)} tiles, {len(rows)} raw detections")
    merged = merge(rows)
    out = cfg.DATA_INTERIM / "yolo" / "detections.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["cls", "x", "y", "w_m", "h_m", "conf", "tile_id"])
        w.writeheader()
        for d in merged:
            w.writerow({k: (round(v, 2) if isinstance(v, float) else v) for k, v in d.items()})
    n = {name: sum(d["cls"] == name for d in merged) for name in NAMES.values()}
    print(f"\nmodel {weights.name}, conf ≥ {conf}: {len(rows)} raw → {len(merged)} after merging")
    print(", ".join(f"{k}: {v}" for k, v in n.items()))
    print(f"written: {out}")


if __name__ == "__main__":
    main()
