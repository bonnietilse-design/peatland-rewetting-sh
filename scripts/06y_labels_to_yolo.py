"""
06y – Turn the QGIS labels into a YOLO training dataset

Inputs (see config.YOLO):
  tiles.gpkg   layer tiles      – tiles with use = 'label' are fully labelled
  labels.gpkg  layer tufts      – one point per tuft
               layer torfstich  – one rectangle per Torfstich chain
  tiles/       640 × 640 px PNGs from step 06x

Output: data/interim/yolo/dataset/
  images/{train,val,test}/<tile_id>.png
  labels/{train,val,test}/<tile_id>.txt   one line per object:
          class x_centre y_centre width height   (0–1, relative to the tile)
  data.yaml                                for `yolo detect train data=...`
  boxes.gpkg                               the YOLO boxes as polygons, to check in QGIS

Split: tiles that share an edge stay together (no near-duplicate pieces in
both training and test), and each split gets tiles with Torfstich, with tufts
only and without symbols (stratified, fixed seed).

Second round: tiles of the whole test area (tiles_aoi.gpkg, use = 'label')
are added to TRAINING only, with the prefix "aoi_". The block tiles keep
exactly the split of round 1, so val/test stay the same and the two models
can be compared fairly. Pick extra tiles away from the blind check points of
step 06v, or that check is no longer independent.

Run in the OSGeo4W Shell:  python scripts\\06y_labels_to_yolo.py
"""
import random
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402
from shapely.geometry import box  # noqa: E402

import config as cfg  # noqa: E402
from peatsh.common import get_logger, write_report  # noqa: E402

log = get_logger("06y")
Y = cfg.YOLO
CLS = {name: i for i, name in enumerate(Y["classes"])}


def labelled(index_path: Path) -> gpd.GeoDataFrame:
    if not index_path.exists():
        return gpd.GeoDataFrame()
    t = gpd.read_file(index_path, layer="tiles")
    return t[t["use"].fillna("").str.strip().str.lower().isin(["label", "done"])].copy()


def read_inputs():
    tiles = labelled(Y["tile_index"])
    if tiles.empty:
        sys.exit("No tiles with use = 'label' in tiles.gpkg – save the edits in QGIS first.")
    tiles["name"], tiles["src_dir"], tiles["extra"] = tiles.tile_id, str(Y["tile_dir"]), 0
    extra = labelled(cfg.YOLO_AREAS["aoi"]["tile_index"])
    if len(extra):
        extra["name"] = "aoi_" + extra.tile_id
        extra["src_dir"], extra["extra"] = str(cfg.YOLO_AREAS["aoi"]["tile_dir"]), 1
        cols = [c for c in tiles.columns if c in extra.columns]
        tiles = gpd.GeoDataFrame(pd.concat([tiles[cols], extra[cols]], ignore_index=True),
                                 crs=tiles.crs)
    tufts = gpd.read_file(Y["labels"], layer="tufts").to_crs(cfg.TARGET_CRS)
    torf = gpd.read_file(Y["labels"], layer="torfstich").to_crs(cfg.TARGET_CRS)
    tufts = tufts[tufts.geometry.notna() & ~tufts.geometry.is_empty]
    torf = torf[torf.geometry.notna() & ~torf.geometry.is_empty]
    return tiles.reset_index(drop=True), tufts, torf


def object_boxes(tufts, torf) -> gpd.GeoDataFrame:
    """All objects as axis-aligned boxes in map coordinates."""
    h = Y["tuft_box_m"] / 2
    rows = [{"cls": "tuft", "geometry": box(p.x - h, p.y - h, p.x + h, p.y + h)}
            for p in tufts.geometry]
    rows += [{"cls": "torfstich", "geometry": box(*g.bounds)} for g in torf.geometry]
    return gpd.GeoDataFrame(rows, crs=cfg.TARGET_CRS)


def yolo_lines(tile_geom, objs: gpd.GeoDataFrame) -> tuple[list[str], list[dict]]:
    tx0, ty0, tx1, ty1 = tile_geom.bounds
    size = tx1 - tx0
    lines, kept = [], []
    for o in objs[objs.intersects(tile_geom)].itertuples():
        inter = o.geometry.intersection(tile_geom)
        if inter.is_empty:
            continue
        if o.cls == "tuft":
            c = o.geometry.centroid                 # tuft counts if its point is inside
            if not tile_geom.contains(c):
                continue
        elif inter.area / o.geometry.area < Y["min_inside"]:
            continue
        x0, y0, x1, y1 = inter.bounds               # clip box to the tile
        xc, yc = ((x0 + x1) / 2 - tx0) / size, (ty1 - (y0 + y1) / 2) / size
        w, h = (x1 - x0) / size, (y1 - y0) / size
        lines.append(f"{CLS[o.cls]} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}")
        kept.append({"cls": o.cls, "geometry": box(x0, y0, x1, y1)})
    return lines, kept


def split_tiles(tiles: pd.DataFrame) -> dict:
    """Edge-neighbour groups, stratified by content, assigned to train/val/test."""
    rc = {t: (r, c) for t, r, c in zip(tiles.tile_id, tiles.row, tiles.col)}
    parent = {t: t for t in rc}

    def find(t):
        while parent[t] != t:
            parent[t] = parent[parent[t]]
            t = parent[t]
        return t
    for a, (ra, ca) in rc.items():
        for b, (rb, cb) in rc.items():
            if abs(ra - rb) + abs(ca - cb) == 1:
                parent[find(a)] = find(b)
    groups = {}
    for t in rc:
        groups.setdefault(find(t), []).append(t)

    content = dict(zip(tiles.tile_id, tiles.content))
    rank = {"torfstich": 0, "tufts": 1, "empty": 2}
    strata = {}
    for g in groups.values():
        key = min((content[t] for t in g), key=rank.get)   # group with any Torfstich → torfstich
        strata.setdefault(key, []).append(sorted(g))

    rnd = random.Random(Y["seed"])
    out = {}
    for key, gs in strata.items():
        gs.sort()
        rnd.shuffle(gs)
        n = sum(len(g) for g in gs)
        want = {s: Y["split"][s] * n for s in ("test", "val")}
        have = {"test": 0, "val": 0}
        for g in gs:
            target = next((s for s in ("test", "val")
                           if have[s] < max(1, round(want[s])) and len(gs) >= 3), "train")
            for t in g:
                out[t] = target
            if target != "train":
                have[target] += len(g)
    return out


def main() -> None:
    tiles, tufts, torf = read_inputs()
    objs = object_boxes(tufts, torf)

    ds = Y["dataset_dir"]
    if ds.exists():
        shutil.rmtree(ds)
    lines_per_tile, kept_all = {}, []
    for t in tiles.itertuples():
        lines, kept = yolo_lines(t.geometry, objs)
        lines_per_tile[t.name] = lines
        for k in kept:
            k["tile_id"] = t.name
        kept_all += kept
    tiles["n_tuft"] = [sum(l.startswith(f"{CLS['tuft']} ") for l in lines_per_tile[t])
                       for t in tiles.name]
    tiles["n_torfstich"] = [sum(l.startswith(f"{CLS['torfstich']} ") for l in lines_per_tile[t])
                            for t in tiles.name]
    tiles["content"] = ["torfstich" if b else "tufts" if a else "empty"
                        for a, b in zip(tiles.n_tuft, tiles.n_torfstich)]
    block = tiles[tiles.extra == 0]
    split = split_tiles(block)                       # same as round 1
    tiles["split"] = [split.get(t, "train") if e == 0 else "train"
                      for t, e in zip(tiles.tile_id, tiles.extra)]

    for t in tiles.itertuples():
        src = Path(t.src_dir) / f"{t.tile_id}.png"
        if not src.exists():
            sys.exit(f"Missing tile image {src} – run 06x first.")
        img_dir = ds / "images" / t.split
        lab_dir = ds / "labels" / t.split
        img_dir.mkdir(parents=True, exist_ok=True)
        lab_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, img_dir / f"{t.name}.png")
        lines = lines_per_tile[t.name]
        (lab_dir / f"{t.name}.txt").write_text("\n".join(lines) + ("\n" if lines else ""),
                                               encoding="utf-8")

    yaml = [f"path: {ds.as_posix()}", "train: images/train", "val: images/val",
            "test: images/test", "names:"] + [f"  {i}: {n}" for i, n in enumerate(Y["classes"])]
    (ds / "data.yaml").write_text("\n".join(yaml) + "\n", encoding="utf-8")

    check = gpd.GeoDataFrame(kept_all, crs=cfg.TARGET_CRS)
    if len(check):
        check["split"] = check.tile_id.map(dict(zip(tiles.name, tiles.split)))
        check.to_file(ds / "boxes.gpkg", layer="yolo_boxes", driver="GPKG")
    tiles.drop(columns="geometry").to_csv(ds / "tiles_split.csv", index=False)

    s = (tiles.groupby("split")
         .agg(tiles=("tile_id", "size"), empty=("content", lambda c: (c == "empty").sum()),
              tufts=("n_tuft", "sum"), torfstich=("n_torfstich", "sum"))
         .reindex(["train", "val", "test"]).fillna(0).astype(int))
    outside = len(tufts) - int(tiles.n_tuft.sum())
    write_report("06y_labels_to_yolo", "YOLO dataset from QGIS labels", [
        f"- labelled tiles: **{len(tiles)}** ({Y['tile_m']} m → {Y['tile_px']} px), "
        f"of which {int(tiles.extra.sum())} from the whole test area (training only)",
        f"- objects: {int(tiles.n_tuft.sum())} tufts (boxes {Y['tuft_box_m']} m), "
        f"{int(tiles.n_torfstich.sum())} Torfstich chains",
        f"- tuft points outside the labelled tiles (ignored): {outside}", "",
        "Split (edge-neighbouring tiles kept together, stratified by content, seed "
        f"{Y['seed']}):", "", s.to_markdown(), "",
        "| split | tiles |", "|---|---|",
        *[f"| {k} | {', '.join(sorted(tiles.name[tiles.split == k]))} |"
          for k in ("train", "val", "test")], "",
        f"Dataset: `{ds.relative_to(cfg.ROOT)}` – check the boxes in QGIS: "
        "`boxes.gpkg` over the tile PNGs.",
        "",
        "Map: Preußische Landesaufnahme 1878–80, © GeoBasis-DE/LVermGeo SH/CC BY 4.0",
    ])
    log.info("dataset written: %s", ds)
    print(s.to_string())


if __name__ == "__main__":
    main()
