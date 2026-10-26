# 06c_yolo_aoi – 1880 classes for the whole test area (YOLO + rules)

_Run: 2026-10-26 16:27 · TEST MODE (test_catchment)_

- detections: 11,943 tufts, 771 Torfstich (06b aoi)
- dash components: 177,867
- thresholds from the block (not re-tuned): tufts ≥ 1 per 75 m window, dash density ≥ 0.280, heath-in-moor distance 100 m
- AOI: 30,358 ha

| class       |   ha (whole AOI) | share of AOI   |
|:------------|-----------------:|:---------------|
| Moor        |             4388 | 14%            |
| nasse Wiese |             6916 | 23%            |
| Heide       |              761 | 3%             |

Consistency check inside the hand-digitised block (same thresholds, AOI tiling): agreement **87%**, κ = **0.81**.

![map](../../outputs/06c_yolo_aoi_test_catchment.png)

Outside the block there is no reference: check the spot-check images (outputs/yolo_spotcheck) and a few areas in QGIS before relying on the result there.
