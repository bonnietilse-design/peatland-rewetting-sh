# 06y_labels_to_yolo – YOLO dataset from QGIS labels

_Run: 2026-10-26 13:33 · TEST MODE (test_catchment)_

- labelled tiles: **32** (320 m → 640 px)
- objects: 399 tufts (boxes 16 m), 23 Torfstich chains
- tuft points outside the labelled tiles (ignored): 1

Split (edge-neighbouring tiles kept together, stratified by content, seed 42):

| split   |   tiles |   empty |   tufts |   torfstich |
|:--------|--------:|--------:|--------:|------------:|
| train   |      24 |       7 |     288 |          17 |
| val     |       4 |       1 |      58 |           2 |
| test    |       4 |       1 |      53 |           4 |

| split | tiles |
|---|---|
| train | r01_c03, r03_c02, r03_c05, r05_c06, r05_c11, r05_c18, r06_c09, r06_c16, r07_c03, r07_c09, r07_c14, r08_c05, r08_c10, r08_c14, r08_c17, r10_c01, r14_c02, r14_c08, r14_c12, r15_c06, r15_c09, r16_c08, r16_c10, r18_c00 |
| val | r06_c00, r11_c05, r15_c14, r17_c07 |
| test | r03_c08, r06_c13, r07_c12, r09_c18 |

Dataset: `data\interim\yolo\dataset` – check the boxes in QGIS: `boxes.gpkg` over the tile PNGs.

Map: Preußische Landesaufnahme 1878–80, © GeoBasis-DE/LVermGeo SH/CC BY 4.0
