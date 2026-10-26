# YOLO plan – detecting map symbols on the Preußische Landesaufnahme

Goal: train a small object-detection model (YOLO) that finds the **tufts** (Bruch/Heide) and **Torfstich** rectangles on the 1878–80 map, then turn the detections into Moor / Wiese polygons using the rules in `historical_peat_digitising_rules.xlsx`. The hand-digitised layer stays the reference; the model is a test of whether this can be automated.

Everything runs **locally on my own computer** – no cloud training, no upload of map tiles.

| | |
|---|---|
| Tool | Ultralytics YOLO (licence **AGPL-3.0** – fine for a public portfolio repo; code that uses it must stay open source) |
| Hardware | CPU only (`device=cpu`) |
| Environment | separate venv `D:\PORTFOLIO\yolo-env` (QGIS's Python stays untouched) |
| Map data | © GeoBasis-DE/LVermGeo SH/CC BY 4.0 |

---

## Step 0 – Environment ✅ done

Open a **plain Command Prompt** (not the OSGeo4W Shell, not the ArcGIS Pro prompt):

```
D:\PORTFOLIO\yolo-env\Scripts\activate
```

Checked: torch 2.14.1+cpu, ultralytics 8.4.184.

## Step 1 – Get the map as a GeoTIFF

Download the test-area extent of `Chronologen_1_1878-1880` from the **WCS** (download service, not the WMS screenshot) at about **1 m per pixel**. Save it to `data/raw/historical/chronologen_1880_aoi.tif`.
(WCS URL still to be copied from "zur Ressource" in the metadata.)

## Step 2 – Cut tiles – `scripts/06x_make_tiles.py`

- 640 × 640 px tiles, each written as a georeferenced GeoTIFF/PNG + world file
- a tile index layer (`tiles`) with tile id and bounds, so every detection can go back to map coordinates

## Step 3 – Label symbols in QGIS

- Point layer `symbol_labels` (field `class` = `tuft`): one click per tuft – the script turns each point into a fixed-size box
- Polygon layer `torfstich_boxes`: one rectangle around each whole Torfstich chain ("Add Rectangle from Extent") – chains vary in length, so a point isn't enough
- Illustrated examples: `docs/labelling_guide.png`
- Pick **30–50 tiles** spread over the test area (moor, meadow, geest, villages)
- In each chosen tile, label **every** symbol – a missed symbol teaches the model "this is background"
- Include some **empty tiles** (geest, arable) so the model also learns what *not* to detect
- Dashes are not labelled – they are lines, handled by a filter in step 7

## Step 4 – Convert labels – `scripts/06y_labels_to_yolo.py`

- map coordinates → YOLO text files (class, x, y, w, h relative to the tile)
- **spatial split** 70 / 15 / 15 (train / val / test) by area, not random tiles, so neighbouring tiles don't leak into the test set
- writes `data.yaml`

## Step 5 – Train

```
yolo detect train data=data.yaml model=yolo26n.pt imgsz=640 epochs=100 batch=8 device=cpu
```

`yolo26n` is the nano version of YOLO26 – the newest Ultralytics model, faster on CPUs and with a label assignment aimed at small objects (tufts are only 10–20 px). Expect a few hours.

If `yolo26n.pt` doesn't download with my Ultralytics version, use `yolo11n.pt` instead. Optional extra: train both and compare them in step 8.

## Step 6 – Evaluate on the test tiles

```
yolo detect val model=runs\detect\train\weights\best.pt data=data.yaml split=test
```

Report precision, recall and mAP50 per class in `docs/reports/`.

## Step 7 – Predict and build polygons – `scripts/06b_detections_to_polygons.py`

```
yolo detect predict model=runs\detect\train\weights\best.pt source=tiles save_txt=True save_conf=True
```

Then in the script:

1. pixel boxes → map points (via the tile index)
2. count tufts / Torfstich per 25 m grid cell
3. dashes from a morphology filter (horizontal line opening) on the raster
4. apply the legend rules: recurring Bruch signature or Torfstich → `Moor`; only dashes → `Wiese`; heath tufts only with moor context
5. dissolve cells into polygons with `hist_type` and `evidence`
6. names ("…moor") are still added by hand

## Step 8 – Compare

Compare three versions of the 1880 peat extent by area and overlap (IoU):

- hand-digitised reference (`peat_1880_digitised.gpkg`)
- rule-based baseline – `scripts/06a_detect_signatures.py` (template matching, no training)
- YOLO result (yolo26n; optionally yolo11n for comparison)

Write up honestly where each one fails (faded print, lettering over symbols, sheet edges).

---

## Notes

- The **legend** used for symbol meanings is the Messtischblatt legend of 1933 (Wikimedia Commons). The official 1882 key (Musterblätter, TIB) was not accessible.
- Model weights and tiles are large → they go in `.gitignore`; only the scripts, `data.yaml` and the evaluation report go on GitHub.
- Step 06 (historical loss) will use the class names **Moor / Wiese** and add a third category: *only today = mapping-concept difference, not gain*.
