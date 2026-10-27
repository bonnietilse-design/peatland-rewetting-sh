# 06c_yolo_aoi – 1880 classes for the whole test area (YOLO + rules)

_Run: 2026-10-27 12:30 · TEST MODE (test_catchment)_

- detections: 11,943 tufts, 1,129 Torfstich (06b aoi)
- dash components: 177,867
- thresholds from the block (not re-tuned): tufts ≥ 1 per 75 m window, dash density ≥ 0.280, heath-in-moor distance 100 m, recurring Torfstich ≥ 3 chains per 275 m → Moor within 62 m
- AOI: 30,358 ha

| class       |   ha (whole AOI) | share of AOI   |
|:------------|-----------------:|:---------------|
| Moor        |             4500 | 15%            |
| nasse Wiese |             6831 | 23%            |
| Heide       |              822 | 3%             |

Consistency check inside the hand-digitised block (same thresholds, AOI tiling): agreement **87%**, κ = **0.81**.

![map](../../outputs/06c_yolo_aoi_test_catchment.png)

Outside the block there is no reference: check the spot-check images (outputs/yolo_spotcheck) and a few areas in QGIS before relying on the result there.
