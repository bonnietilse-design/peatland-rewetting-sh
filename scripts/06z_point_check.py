"""
06z – Point-based check of a trained YOLO model

mAP50 counts a hit only if the predicted box overlaps the labelled box by
≥ 50 %. For counting tufts per grid cell, a detection a few metres off is
just as useful. This script counts a symbol as FOUND if a predicted centre
lies within MATCH_M metres of the labelled centre (one-to-one matching),
for several confidence thresholds.

Run in the YOLO environment (plain Command Prompt, yolo-env activated):
    python scripts\\06z_point_check.py runs\\detect\\runs\\train2\\weights\\best.pt val
(paths relative to data\\interim\\yolo; split = val or test)
Optional third argument: only tiles of one area, e.g.
    python scripts\\06z_point_check.py runs\\detect\\runs\\train5\\weights\\best.pt test fiel
    ... test block      (the hand-digitised block only)
"""
import sys
from pathlib import Path

import numpy as np
from ultralytics import YOLO

TILE_M, TILE_PX = 320, 640           # must match config.YOLO
MATCH_M = 8                          # half a tuft box
CONFS = [0.05, 0.08, 0.10, 0.11, 0.12, 0.13, 0.14, 0.15, 0.17, 0.20, 0.25, 0.35, 0.50]
NAMES = {0: "tuft", 1: "torfstich"}


def read_labels(txt: Path) -> np.ndarray:
    if not txt.exists() or not txt.read_text().strip():
        return np.zeros((0, 3))
    a = np.loadtxt(txt, ndmin=2)
    return a[:, :3]                                  # class, x, y (0-1)


def match(gt: np.ndarray, pr: np.ndarray, tol: float) -> int:
    """Greedy one-to-one matching by distance; returns number of matches."""
    if len(gt) == 0 or len(pr) == 0:
        return 0
    d = np.hypot(gt[:, None, 0] - pr[None, :, 0], gt[:, None, 1] - pr[None, :, 1])
    used_g, used_p, n = set(), set(), 0
    for i, j in zip(*np.unravel_index(np.argsort(d, axis=None), d.shape)):
        if d[i, j] > tol:
            break
        if i in used_g or j in used_p:
            continue
        used_g.add(i)
        used_p.add(j)
        n += 1
    return n


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "data" / "interim" / "yolo"
    weights = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "runs/detect/runs/train2/weights/best.pt"
    if not weights.is_absolute():
        weights = root / weights
    split = sys.argv[2] if len(sys.argv) > 2 else "val"
    img_dir = root / "dataset" / "images" / split
    lab_dir = root / "dataset" / "labels" / split
    imgs = sorted(img_dir.glob("*.png"))
    area = sys.argv[3] if len(sys.argv) > 3 else None
    if area == "block":                               # block tiles have no area prefix
        imgs = [p for p in imgs if not p.stem.split("_")[0].isalpha()]
    elif area:
        imgs = [p for p in imgs if p.stem.startswith(area + "_")]
    if not imgs:
        sys.exit(f"No tiles in {img_dir}" + (f" for area '{area}'" if area else ""))
    model = YOLO(str(weights))
    preds = {p.stem: r for p, r in zip(imgs, model.predict([str(p) for p in imgs], conf=min(CONFS),
                                                            imgsz=TILE_PX, device="cpu", verbose=False))}
    tol = MATCH_M / TILE_M                            # in 0-1 tile units
    print(f"\nmodel: {weights}\nsplit: {split}{' / ' + area if area else ''} ({len(imgs)} tiles), "
          f"match radius {MATCH_M} m\n")
    for cls, name in NAMES.items():
        print(f"{name}:")
        print("  conf   labelled  predicted  found   recall  precision")
        for conf in CONFS:
            n_gt = n_pr = n_ok = 0
            for p in imgs:
                gt = read_labels(lab_dir / f"{p.stem}.txt")
                gt = gt[gt[:, 0] == cls][:, 1:]
                b = preds[p.stem].boxes
                keep = (b.cls.numpy() == cls) & (b.conf.numpy() >= conf)
                pr = b.xywhn.numpy()[keep][:, :2]
                n_gt, n_pr = n_gt + len(gt), n_pr + len(pr)
                n_ok += match(gt, pr, tol)
            rec = n_ok / n_gt if n_gt else float("nan")
            pre = n_ok / n_pr if n_pr else float("nan")
            print(f"  {conf:4.2f}   {n_gt:8d}  {n_pr:9d}  {n_ok:5d}   {rec:6.2f}  {pre:9.2f}")
        print()


if __name__ == "__main__":
    main()
