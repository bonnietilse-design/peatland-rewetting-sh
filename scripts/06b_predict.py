"""
06b – Run the trained YOLO model on every tile of an area

Runs in the YOLO environment (plain Command Prompt, yolo-env activated):
    python scripts\\06b_predict.py                 block (default), best.pt of train2, conf 0.20
    python scripts\\06b_predict.py aoi             whole test area
    python scripts\\06b_predict.py aoi <weights> 0.20
    python scripts\\06b_predict.py aoi spot        only the spot-check images (≈ 1 min)

Reads   the tiles of the area (step 06x) + .wld world files
Writes  detections.csv / detections_aoi.csv – one row per detection, in map
        coordinates (EPSG:25832): cls, x, y, w_m, h_m, conf, tile_id
        For the AOI also outputs/yolo_spotcheck/: 12 random tiles OUTSIDE the
        hand-digitised block with the detections drawn – check these before
        trusting the model there.

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


BLOCK = (524000, 6020000, 530000, 6026000)          # hand-digitised extent
N_SPOT = 12


def main() -> None:
    area, A = cfg.yolo_area(sys.argv)
    spot_only = "spot" in sys.argv[1:]
    args = [a for a in sys.argv[1:] if a not in cfg.YOLO_AREAS and a != "spot"]
    weights = Path(args[0]) if args else DEFAULT_WEIGHTS
    if not weights.is_absolute():
        weights = ROOT / weights
    conf = float(args[1]) if len(args) > 1 else 0.20
    tiles = sorted(A["tile_dir"].glob("*.png"))
    if not tiles:
        sys.exit(f"No tiles in {A['tile_dir']} – run 06x {area} first.")
    spot = set()
    if area == "aoi":
        import random
        from PIL import Image
        outside = []
        for png in tiles:
            dx, dy, x0c, y0c = world_file(png)
            cx, cy = x0c + 320 * dx, y0c + 320 * dy
            if not (BLOCK[0] <= cx <= BLOCK[2] and BLOCK[1] <= cy <= BLOCK[3]):
                outside.append(png)
        rnd = random.Random(1)
        rnd.shuffle(outside)
        spot = set()
        for png in outside:                      # skip near-empty tiles (< 8 % ink)
            if (np.asarray(Image.open(png).convert("L")) < 128).mean() >= 0.08:
                spot.add(png)
            if len(spot) == N_SPOT:
                break
        spot_dir = cfg.OUTPUTS / "yolo_spotcheck"
        spot_dir.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(weights))
    if spot_only:
        if not spot:
            sys.exit("Spot checks are only made for the aoi area.")
        tiles = sorted(spot)
    rows = []
    for i, png in enumerate(tiles, 1):
        dx, dy, x0c, y0c = world_file(png)
        res = model.predict(str(png), conf=conf, imgsz=Y["tile_px"], device="cpu", verbose=False)[0]
        if png in spot:
            Image.fromarray(res.plot(line_width=1, font_size=8)[:, :, ::-1]).save(spot_dir / f"{png.stem}.jpg")
        b = res.boxes
        for (cx, cy, w, h), c, k in zip(b.xywh.numpy(), b.conf.numpy(), b.cls.numpy().astype(int)):
            rows.append({"cls": NAMES[k],
                         "x": x0c + cx * dx - dx / 2,     # world file refers to pixel centres
                         "y": y0c + cy * dy - dy / 2,
                         "w_m": w * dx, "h_m": h * -dy,
                         "conf": float(c), "tile_id": png.stem})
        if i % 250 == 0 or i == len(tiles):
            print(f"{i}/{len(tiles)} tiles, {len(rows)} raw detections")
    if spot_only:
        print(f"{len(spot)} spot-check images written to {spot_dir}")
        return
    merged = merge(rows)
    out = A["detections"]
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["cls", "x", "y", "w_m", "h_m", "conf", "tile_id"])
        w.writeheader()
        for d in merged:
            w.writerow({k: (round(v, 2) if isinstance(v, float) else v) for k, v in d.items()})
    n = {name: sum(d["cls"] == name for d in merged) for name in NAMES.values()}
    print(f"\nmodel {weights.name}, conf ≥ {conf}: {len(rows)} raw → {len(merged)} after merging")
    print(", ".join(f"{k}: {v}" for k, v in n.items()))
    print(f"written: {out}")
    if spot:
        print(f"spot-check images ({len(spot)} tiles outside the block): {spot_dir}")


if __name__ == "__main__":
    main()
