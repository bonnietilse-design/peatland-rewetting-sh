# YOLO experiment log – 1880 map symbols (tufts, Torfstich)

Working log of the training rounds for detecting map symbols on the
Preußische Landesaufnahme 1878–1880 (WCS `Chronologen_1_1878-1880`, GDI-SH).
It records what I tried, what I measured and what I concluded, including the
dead ends. All training and inference ran locally on my own computer (CPU,
Ultralytics YOLO in a separate Python environment). I used an AI assistant
(Claude) to help write the scripts, plan the experiments and interpret results;
all labelling was done manually by me in QGIS.

Classes: `0 tuft` (grass-tuft symbol: Moor, nasse Wiese, Heide), `1 torfstich`
(peat-cutting symbol). Tiles: 320 m × 320 m, 640 × 640 px (0.5 m/px).

## How models are compared

- **06z point check** (`scripts/06z_point_check.py <weights> test <area>`):
  predicted box centres are matched to labelled box centres within 8 m on the
  held-out test tiles of each map sheet. Reported per confidence threshold:
  recall, precision. I summarise with F1 = 2·R·P/(R+P).
- **06v blind accuracy check**: 100 stratified random points, interpreted
  blind, area-weighted accuracy following Olofsson et al. (2014); `compare`
  mode uses the Stehman (2014) estimator when strata ≠ map classes.
- Validation mAP from training is **not** used to choose models: the val set
  is small and mAP rewards box overlap, while I only need symbol positions.

Test tiles per sheet (never used in training):

| Sheet | Test tiles | Labelled tufts | Torfstich |
|---|---|---|---|
| Sorge block | 4 | 53 | 4 |
| Fiel | 2 (r00_c10, r09_c10) | 8 | 0 |
| Dosenmoor | 2 (r06_c09, r12_c02) | 26 | 0 |

## Round 1 – train2 (baseline)

- Training data: Sorge block only, tiles from my QGIS export (0.5 m).
- Became the tuft model of the final 1880 map.
- Sorge test, conf 0.20: R 0.75 / P 0.59. Fiel test, conf 0.20: 6/8 found, P 0.55.

## Round 2 – train3 (augmentation), train4 (fine-tune)

- train3: more labels, rotation augmentation `degrees=30`.
- Tuft confidences became unstable between runs/sheets; in the AOI map the
  round-2 tufts produced false Moor. I first suspected Torfstich – that was
  wrong; the cause was the round-2 tufts.
- Torfstich detection, however, improved clearly.
- train4: fine-tune of train3, no gain.

## Hybrid model + rule tuning (06c)

- **Hybrid**: round-1 tufts + round-2 Torfstich. This is the current map.
- Torfstich rule tuned: min chains (2, 3, 4) × near cells (3, 5) → 2 / 5.
- Dash density per field ("pasture rows"): field lines = ink > 80 m on a 5 m
  grid, fields 0.2–40 ha, fallback to window value. Tie rule (within
  0.01 κ prefer "field") was fixed **before** the blind check.
- Final parameters: t_min 1, d_min 0.311, r_heath 9, torf_min 2,
  torf_near 5, dash_mode field.
- **Blind check (AOI): 93 % ± 4 %** (87/100 points; window method 88).
  Moor UA/PA 0.89/0.93, nasse Wiese 0.86/0.86, Heide 0.89/0.78.
- AOI areas: Moor 4,608 ha, nasse Wiese 7,166 ha, Heide 841 ha.

## QGIS plugin test on Fiel (transfer to another sheet)

- Torfstich good; but many dot pairs read as tufts.
- False-tuft confidences 0.21–0.25 overlapped real ones 0.21–0.26 → a
  threshold cannot separate them. Conclusion: needs training data from other
  sheets.

## Round 3 – train5 (Fiel labels)

- Added 10 labelled Fiel tiles.
- Confidences collapsed to a narrow low band.
- Fiel test: conf 0.10 → 8/8 found, 15 false; 0.15 → 1/8.
- Sorge test: 0.10 → R 0.87 / P 0.35; 0.15 → R 0.58 / P 0.86.
- Not clearly better than round 1.

## Native resolution tiles – and a silent data problem

- The WCS native resolution is ≈ 0.78 m. My earlier tiles came from a QGIS
  export that was resampled before thresholding. New variant
  (`tile_variant: "native"`): download at native resolution, bilinear resample
  to 0.5 m, then threshold. Same tile ids and use flags.
- **Problem:** QGIS raster export of the large WCS areas silently wrote
  all-zero files. The first train7/train8 attempts were therefore trained on
  blank tiles (zero detections on block/Fiel, but plausible on Dosenmoor,
  which had a valid file). Runs deleted.
- **Fix:** `06w_download_wcs.py` downloads via the GDAL WCS driver and checks
  the result is not empty; `06x_make_tiles.py` now refuses empty sources.
- Added Dosenmoor: 14 labelled tiles (126 tufts, 4 Torfstich) + 2 test tiles.
- Dataset (06y): train 58 tiles (17 empty), 618 tufts, 66 Torfstich;
  val 4 tiles; test 8 tiles (87 tufts, 4 Torfstich).

## Round 4 – train7 (yolo26n, native tiles, three sheets)

`yolo detect train data=dataset/data.yaml model=yolo26n.pt imgsz=640 epochs=300 patience=80 batch=8 device=cpu workers=2 scale=0.2`

- Early stop, best epoch 64, 0.67 h on CPU.
- Confidences again in a narrow band (max ≈ 0.20), so I refined the 06z
  threshold grid (0.08, 0.11–0.14, 0.17 added).

**Like-for-like comparison on the same native test tiles** (best F1 per sheet):

| Sheet | train7 | Round 1 (train2) |
|---|---|---|
| Sorge block | 0.64 @ 0.12 (R .70 / P .59) | **0.68** @ 0.25 (R .66 / P .71) |
| Fiel | **0.84** @ 0.13 (8/8, 3 false) | 0.57 @ 0.20 (6/8, 7 false) |
| Dosenmoor | **0.69** @ 0.14 (R .73 / P .66) | 0.53 @ 0.20 (R .54 / P .52) |
| All 87 tufts, one threshold | **0.66** @ 0.12–0.13 | 0.60 @ 0.20 |

- Torfstich (Sorge test, 4): train7 4/4 with no false detections from 0.25.
- Interpretation: round 1 is slightly better on its own sheet but transfers
  poorly; train7 is much better on the new sheets. For a state-wide map,
  transfer matters more. Test sets are small (8 tufts on Fiel), so one or
  two symbols move F1 by ~0.1 – a trend, not a precise number.
- Proposed thresholds for train7: tuft 0.12–0.13, Torfstich 0.25.

## Round 4b – train8 (yolo26s, same data)

Same command with `model=yolo26s.pt`, `name=train8`. Early stop, best epoch
33, 113 epochs in 1.2 h on CPU.

Best tuft F1 per sheet, all three models on the same native test tiles:

| Sheet | train8 (yolo26s) | train7 (yolo26n) | Round 1 (train2) |
|---|---|---|---|
| Sorge block | **0.72** @ 0.17 (R .83 / P .64) | 0.64 @ 0.12 | 0.68 @ 0.25 |
| Fiel | **0.94** @ 0.17 (8/8, 1 false) | 0.84 @ 0.13 | 0.57 @ 0.20 |
| Dosenmoor | **0.72** @ 0.17 (R .88 / P .61) | 0.69 @ 0.14 | 0.53 @ 0.20 |
| All 87 tufts, one threshold | **0.74** @ 0.17 (R .86 / P .65) | 0.66 @ 0.12–0.13 | 0.60 @ 0.20 |

- train8 is best on every sheet, including the Sorge sheet that round 1 was
  trained on. One threshold (0.17) is best on all three sheets, which makes
  it easy to apply state-wide.
- Recall drops sharply between 0.17 and 0.20, so the threshold must not be
  set higher than ~0.17.
- Torfstich: train8 finds 4/4 but with extra false detections (5 at 0.17,
  2 at 0.50); train7 had none from 0.25. Only 4 test symbols, so weak
  evidence, but it points to a hybrid again: train8 tufts + train7 Torfstich.

### train8 on the whole test area (28 Oct)

train8 alone, thresholds 0.17/0.50 (tuft/Torfstich), 06c re-tuned on the block.

- Block: tuning chose the same parameters as before; east half 91 %,
  κ 0.87 – identical to the current map.
- AOI (06b): 12,795 tufts, 828 Torfstich (current map: 11,943 / 1,129).

| | Current map (round 1 + round 2 hybrid) | train8 |
|---|---|---|
| Moor (ha) | 4,608 | 5,212 |
| nasse Wiese (ha) | 7,166 | 7,113 |
| Heide (ha) | 841 | 431 |
| Blind check, overall | **93 % ± 4 %** | 91 % ± 4 % |
| Moor UA / PA | 0.89 / 0.93 | 0.80 / 0.93 |
| nasse Wiese UA / PA | 0.86 / 0.86 | 0.86 / 0.86 |
| Heide UA / PA | 0.89 / 0.78 | 0.80 / **0.26** |

- The difference overall is within the uncertainty, but the pattern is
  clear: about 400 ha of Heide become Moor. Better symbol detection did not
  give a better map, because the Heide/Moor split depends on the rules
  (dash density, heath-in-moor), not only on finding tufts.
- Decision: the current map (hybrid) stays the published result. train8 is
  kept as the candidate model for other sheets; the Heide → Moor shift has
  to be understood before it is used state-wide.
- Results saved in `data/interim/yolo/train8_aoi/`.

### Why heath became Moor with train8 (analysis, 28 Oct)

- Blind-check points read as Heide: current map 20 of 23 correct, train8
  8 of 23; 14 became Moor. 11 of those 14 lie in **one heath** (≈ 268 ha,
  EPSG:25832 x 529,200–532,600, y 6,026,050–6,028,550).
- The symbols there are almost unchanged: 979 tufts (current) vs 983
  (train8); tuft box centres differ by a median of 1.6 m, no systematic
  shift. The one extra Torfstich (conf 0.53) at the heath's south edge is a
  single detection, so it is not "recurring" and does not trigger the rule.
- In train8's map the heath is part of one 510 ha Moor patch, which also
  took in 155 ha of further heath and 66 ha of unclassified land.
- Mechanism: the "heath in a moor" rule turns a heath patch into Moor if it
  touches Moor at least as large as itself. In the current map the heath is
  one 268 ha patch next to tiny Moor bits (< 2 ha), so it stays heath. Small
  changes in where tufts + dashes reach the Moor threshold (dash density is
  measured per field, so one field can switch at once) can cut a heath into
  smaller patches, each touching more Moor than its own size – and then all
  of them flip. The rule is sensitive to fragmentation, not to the symbols.
- Whole test area, current → train8: 426 ha Heide → Moor, 193 ha nasse
  Wiese → Moor, 131 ha Moor → nasse Wiese, 254 ha none → Moor.

## Next steps

1. Make the heath rule robust to fragmentation, e.g. treat small Moor
   islands (< ~5 ha) inside a heath as part of that heath when comparing
   sizes; re-run 06c for the current detections and for train8 and check
   both with 06v compare.
2. If that is fixed: update plugin models; label further sheets (Himmelmoor,
   Jardelunder Moor, Eiderstedt) for the state-wide run.
