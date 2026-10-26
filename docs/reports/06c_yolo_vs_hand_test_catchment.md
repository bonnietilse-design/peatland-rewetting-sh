# 06c_yolo_vs_hand – Automated 1880 classes vs. hand digitising

_Run: 2026-10-26 14:48 · TEST MODE (test_catchment)_

- detections used: 2203 tufts, 109 Torfstich (from 06b)
- dash components (flat, 5–40 m): 24,521
- grid 25 m, dash window 125 m, tuft window 75 m
- tuned on the west half: **tufts ≥ 1** per 75 m window, **dash density ≥ 0.280**, heath within **100 m** of recurring Torfstich (or touching Moor) → Moor

| area          | agreement   |   kappa |
|:--------------|:------------|--------:|
| west (tuning) | 84%         |    0.74 |
| east (check)  | 90%         |    0.85 |
| whole block   | 87%         |    0.8  |

Kappa: agreement beyond chance (0 = chance, 1 = perfect). The east half was not used for tuning – its value is the honest one.

### Confusion matrix, east half (ha)

|                   |   YOLO: – |   YOLO: Moor |   YOLO: nasse Wiese |   YOLO: Heide |
|:------------------|----------:|-------------:|--------------------:|--------------:|
| hand: –           |       537 |           12 |                  78 |             2 |
| hand: Moor        |        16 |          709 |                  21 |             0 |
| hand: nasse Wiese |        19 |            3 |                 376 |             0 |
| hand: Heide       |         2 |           26 |                   0 |             0 |

### Per class (east half)

| class | IoU | area hand ha (block) | area YOLO ha (block) |
|---|---:|---:|---:|
| Moor | 0.9 | 1,084 | 923 |
| nasse Wiese | 0.76 | 1,060 | 1,248 |
| Heide | 0.0 | 29 | 5 |

![comparison](../../outputs/06c_yolo_vs_hand_test_catchment.png)

Limitations: names ('…moor') are not detected; the YOLO model was trained on 32 tiles of the same block (some overlap with the evaluated area); Hutung/trockene Wiese are not separated (both count as '–'); rule 6 turns almost all Heide into Moor, so the small Heide class (29 ha by hand) is not reproduced.
