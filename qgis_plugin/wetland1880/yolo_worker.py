"""Runs in a Python environment with Ultralytics installed (not in QGIS).

    python yolo_worker.py <tile_dir> <out.csv> <weights>:<class>:<conf> [...]

Each model spec takes ONE class from ONE model, e.g.
    tufts_round1.pt:tuft:0.20  torfstich_round2.pt:torfstich:0.20
The tiles are PNGs with GDAL world files (.wld). Detections are written in map
coordinates; duplicates of the same class closer than MERGE_M are merged.
Progress is printed as "PROGRESS <0-100>" for the QGIS plugin.
"""
import csv
import sys
from pathlib import Path

import numpy as np
from ultralytics import YOLO

MERGE_M = {"tuft": 8.0, "torfstich": 20.0}


def world_file(png):
    for ext in (".wld", ".pgw"):
        wf = png.with_suffix(ext)
        if wf.exists():
            v = [float(s) for s in wf.read_text().split()]
            return v[0], v[3], v[4], v[5]
    raise SystemExit(f"No world file next to {png}")


def merge(rows):
    out = []
    for name, dist in MERGE_M.items():
        r = sorted((d for d in rows if d["cls"] == name), key=lambda d: -d["conf"])
        if not r:
            continue
        xy = np.array([[d["x"], d["y"]] for d in r])
        taken = np.zeros(len(r), bool)
        for i in range(len(r)):
            if taken[i]:
                continue
            out.append(r[i])
            taken |= np.hypot(*(xy - xy[i]).T) < dist
    return out


def main():
    tile_dir, out_csv, specs = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
    tiles = sorted(tile_dir.glob("*.png"))
    jobs = []
    for spec in specs:
        path, cls, conf = spec.rsplit(":", 2)
        jobs.append((YOLO(path), cls, float(conf)))
    rows, total, done = [], len(tiles) * len(jobs), 0
    for model, cls, conf in jobs:
        names = model.names
        for png in tiles:
            dx, dy, x0c, y0c = world_file(png)
            res = model.predict(str(png), conf=conf, imgsz=640, device="cpu", verbose=False)[0]
            b = res.boxes
            for (cx, cy, w, h), c, k in zip(b.xywh.numpy(), b.conf.numpy(), b.cls.numpy().astype(int)):
                if names[k] != cls:
                    continue
                rows.append({"cls": cls, "x": x0c + cx * dx - dx / 2, "y": y0c + cy * dy - dy / 2,
                             "w_m": w * dx, "h_m": h * -dy, "conf": float(c)})
            done += 1
            if done % 20 == 0 or done == total:
                print(f"PROGRESS {100 * done / total:.0f}", flush=True)
    merged = merge(rows)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["cls", "x", "y", "w_m", "h_m", "conf"])
        w.writeheader()
        w.writerows(merged)
    print(f"DONE {len(merged)}", flush=True)


if __name__ == "__main__":
    main()
