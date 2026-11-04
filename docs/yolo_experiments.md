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
- Whole test area, current → train8: 426 ha Heide → Moor, 193 ha nasse
  Wiese → Moor, 131 ha Moor → nasse Wiese, 254 ha none → Moor.
- First hypothesis (wrong): the heath was cut into pieces that each touched
  more Moor than their own size. A size rule per connected Heide + Moor area
  ("region") left the result unchanged (train8 still 91 %, Heide 435 ha).
- Intermediate layers (`06c ... aoi debug` → `06c_debug_aoi.npz`) showed
  the real cause. Before the heath rule, train8's map still has the area as
  heath (449 ha heath, 66 ha Moor in that connected area). But with train8
  the heath grows a little to the east and south and joins a neighbouring
  heath. Its corner then comes within 100 m of a group of recurring
  Torfstich at x 532,800 / y 6,027,060 (found by both models), and the
  "near recurring Torfstich" rule turns the **whole** 447 ha patch into
  Moor. In the current map the heath stays separate (268 ha) and never
  reaches that zone.
- So the weak point is that the Torfstich part of the heath rule acts on
  whole patches, however large. Tested variant: only heath cells within
  100 m of recurring Torfstich become Moor; the rest of the heath follows the
  Heide/Moor balance of its connected area. Simulated on the saved layers,
  counted on the 100 blind points (unweighted, not the 06v estimator):

| Detections | Rule before (patch) | Test variant (region) |
|---|---|---|
| Current map | 87 / 100 | 88 / 100 (Heide +1) |
| train8 | 76 / 100 | 84 / 100 (Heide 8 → 21, Moor 25 → 20) |

- The variant fixes the large heath but loses 5 Moor points with train8:
  there, heath inside a drained bog needs the whole-patch rule. Neither
  rule works for both cases, so the Heide/Moor decision needs a better
  criterion (e.g. distance to the Torfstich weighted by patch size, or
  tuft and dash density inside the patch).
- Decision: the published map stays with the rule as before
  (`HEATH_RULE = "patch"` in 06c); the variant stays in the script as an
  option for further tests.

### Can each tuft be judged by its own surroundings? (28 Oct)

Idea (from looking at the map): heath tufts stand alone, each on its own
short base line; Bruch tufts sit among horizontal dashes. So count the free
dashes (not base lines) within 20 m of each tuft. Tested on the 1 m map
before changing 06c, in the problem heath and in a Bruch area near
x 529,400 / y 6,014,600 (`docs/crop_heath.png`, `docs/crop_moor.png`: red =
marks the dash filter keeps, blue = tuft centres):

- **The dash filter misses most Bruch dashes.** In dense Bruch the dashes
  are bold, often longer than 40 m, and touch each other or the field lines,
  so they merge into large ink pieces and are dropped. Only 336 "dashes"
  were found in 1.3 km² of Bruch.
- **In heath it picks up the base lines**, often split into two pieces and
  more than 10 m from the tuft centre, so they are not removed as base lines.
- Result: free dashes per tuft were 0–1 in both areas. The per-tuft count
  cannot separate heath from Moor with this dash filter.
- A pixel measure works better: share of horizontal ink (opening with a
  1 × 7 m line) in a 20 m ring around each tuft, base line excluded. Heath
  median 0.009, Bruch median 0.104.
- But at the 50 blind-check points read as Heide or Moor, this measure
  alone gets 42 right (threshold 0.02), against **45** for the published
  map. Several heaths lie next to wet meadow or field lines, and several
  Moor points have only sparse dashes. The context rules of the published
  map do better than the symbols alone.
- The test code was not kept in 06c.

## Round 5 – train9: two tuft classes (28 Oct)

- New class `heath_tuft` (id 2): a tuft alone on its own base line, no
  dashes around. `tuft` (id 0) now means a Bruch tuft (among dashes).
  Labelled by the **symbol**, not the context: heath tufts on a drained bog
  (e.g. next to Torfstich) are heath tufts; the 06c context rules decide
  whether they count as Moor.
- Labels: new field `heath` (0/1) on the tuft points; existing tufts
  re-checked by hand; 5 new Fiel tiles with heath (r08_c13, r08_c14,
  r09_c11, r09_c12, r09_c13). Backup: `labels_backup_1028.gpkg`.
- Dataset (06y): train 63 tiles, 676 tufts of which 118 heath, 66
  Torfstich; val 4 tiles (no heath); test 8 tiles, 87 tufts of which 25
  heath.
- Code: 06y writes the class from `heath`; 06b merges heath and Bruch boxes
  on the same symbol; 06z also reports "all tufts" (class ignored); 06c takes
  Heide/Moor from the tuft classes when a 3-class model is used (Moor where
  ≥ half of the tufts in the 75 m window are Bruch tufts), otherwise from the
  dash density as before.
- Training: yolo26s, same settings as train8; best epoch 58, 138 epochs,
  1.7 h on CPU.
- 06z, all tufts (class ignored), best F1: block 0.57, Fiel 0.78,
  Dosenmoor 0.56, all 87 tufts 0.52 (train8: 0.72 / 0.94 / 0.72 / 0.74).
  Splitting the class costs detection: confidences are spread over two
  classes and stay low (heath ≤ 0.15).
- Heath class: Fiel 7/8 found with 2 false (conf 0.11); block 10/17 with
  P 0.56 (0.13); on Dosenmoor ~7 of 26 Bruch tufts called heath, and heath
  predicted although the test tiles have none.
- Map (thresholds 0.12/0.50/0.12; 06c re-tuned, Heide/Moor from the
  classes): block east half 90 %, κ 0.85. Whole test area Moor 4,988 ha,
  nasse Wiese 6,521 ha, Heide 670 ha.

| Blind check (06v compare) | Published map | train8 | train9 (2 tuft classes) |
|---|---|---|---|
| Overall | 93 % ± 4 % | 91 % ± 4 % | **93 % ± 4 %** |
| Moor UA / PA | 0.89 / 0.93 | 0.80 / 0.93 | 0.91 / 0.90 |
| nasse Wiese UA / PA | 0.86 / 0.86 | 0.86 / 0.86 | 0.90 / 0.86 |
| Heide UA / PA | 0.89 / 0.78 | 0.80 / 0.26 | 1.00 / 0.62 |

- The tuft classes fix train8's heath collapse (Heide PA 0.26 → 0.62)
  without any dash-density rule for Heide/Moor, and reach the same overall
  accuracy as the published map – with only 118 heath examples. Every area
  mapped as Heide is heath, but a third of the heath is still missed.
- Decision: the published map stays (equal accuracy, nothing gained yet).
  The two-class approach is the one to continue: more heath tiles should
  raise both heath recall and overall tuft detection. Outputs saved in
  `data/interim/yolo/train9_aoi/`.
- Heath is still rare (118 vs 558 Bruch tufts in training). A heath-rich
  sheet (candidates: Lürschauer Heide ~x 532,000 / y 6,045,000; Segeberger
  Heide ~x 585,400 / y 5,976,500) is planned for the next round.

## Round 6 – train10: more heath labels (30 Oct)

- yolo26s, ≈ 209 heath tufts (train9: 118), new heath sheet Lürschau added.
- 06z at conf 0.15 (test tiles): all tufts F1 0.67 on the three original
  sheets; heath class: block 13/17 found (P 0.65), Fiel 8/8 (P 0.62),
  Dosenmoor 5 false heath, Lürschau 8/17 (P 0.44).
- Map (thresholds 0.15/0.50/0.15): far fewer heath tufts than train9 –
  block 79 (227), whole test area 1,553 (2,470). Block east half 91 %,
  κ 0.87. Whole test area Moor 5,442 ha, nasse Wiese 7,072 ha, Heide 226 ha.

| Blind check (06v compare) | Published map | train9 | train10 |
|---|---|---|---|
| Overall | **93 % ± 4 %** | 93 % ± 4 % | 90 % ± 4 % |
| Moor UA / PA | 0.89 / 0.93 | 0.91 / 0.90 | 0.80 / 0.90 |
| nasse Wiese UA / PA | 0.86 / 0.86 | 0.90 / 0.86 | 0.86 / 0.86 |
| Heide UA / PA | 0.89 / 0.78 | 1.00 / 0.62 | 0.67 / 0.07 |

- The heath collapse is back (Heide PA 0.07): heath is mapped as Moor
  (Moor UA 0.91 → 0.80). The test-tile scores looked fine, but across the
  test area the model calls most heath tufts Bruch tufts. More heath labels
  alone did not help; the higher threshold (0.15 instead of 0.12) may add
  to it.
- Threshold test (heath 0.08 instead of 0.15, same model): heath tufts in the
  test area 1,553 → 2,379 (train9: 2,470), but Heide only 249 ha; blind check
  90 % ± 4 %, Heide UA / PA 0.75 / 0.10, Moor UA 0.77. So it is not the
  threshold: train10 finds about as many heath tufts as train9, but not in
  the places that make a field Heide (Bruch tufts nearby turn it into Moor).
- Analysis of the 23 blind-check points that are heath (tufts within 150 m):
  train9 called 196 of 210 tufts heath, train10 only 109 of 203 (94 Bruch).
  Map at these points: published 20 Heide, train9 15, train10 2 (16 Moor).
- Across the test area, of train9's 2,470 heath tufts train10 calls 1,074
  Bruch tufts and misses 419; Bruch tufts stay Bruch (only 86 flip to heath).
  The flipped tufts are not borderline: train10 is more confident in "Bruch"
  (median conf 0.23) than train9 was in "heath" (0.15). So train10 learned a
  narrower heath symbol, probably shaped by the Lürschau labels, and reads the
  test-area heath as Bruch. Swapped tufts for checking in QGIS:
  `data/interim/yolo/train10_aoi/t9heath_vs_t10.csv` (x, y in the project CRS, TARGET_CRS).
- Correction: a first look in QGIS suggested the detections lie off the
  symbols – that was the wrong background layer. On the tiles themselves the
  points sit on the tufts, and AOI and block detections are a median 3–4 m
  from my hand labels with no systematic shift.
- Visual check of the 16 heath check points that train10 maps as Moor
  (`outputs/heath_points_t10_moor.png`): two separate problems.
  1. YOLO: at points 9, 26, 57, 58, 66, 81 the tufts are heath (checked by
     me: small, fine tufts on open ground, no dashes), but train10 calls
     them Bruch. Where train9's "heath" tufts flipped in real Moor (dashes,
     Torfstich, "Moor" lettering), train10 is right. Missed tufts are real tufts.
  2. 06c: at points 37, 50, 94, 96 nearly all tufts are detected as heath,
     yet the map says Moor. HEATH_RULE "region" (new switch: `06c ... region`)
     barely helps: 90 % ± 4 %, Heide 251 ha, UA / PA 0.75 / 0.10. So the
     heath is lost before the heath-in-moor rule; not yet explained
     (next: `06c ... aoi debug` if it remains after retraining).
- Next round: label the small heath tuft on test-area tiles at least two
  tiles (640 m) away from every check point, so the blind check stays blind.
  Candidates: `outputs/heath_label_candidates.png` (heath-like: r30_c54,
  r29_c54, r27_c51, maybe r19_c57).
- Decision: the published map stays. Outputs saved in
  `data/interim/yolo/train10_aoi/`.

## train11 (30 Oct): + 68 heath tufts on test-area tiles

- yolo26s, same settings; 06y: 77 train tiles / 277 heath tufts (val still 0 heath).
- 06z at conf 0.15: heath class block 9/17 (P 0.41, train10 13/17), Fiel 8/8
  (P 0.73), Lürschau 9/17 (P 0.56), Dosenmoor 10 false heath (train10 5).
- 06b (0.15/0.50/0.15): test area 2,939 heath tufts (train10 1,553, train9 2,470).
- Debug (`06c ... aoi debug`, `train11_aoi/06c_debug_aoi.npz`) at the heath check
  points: points 26, 37, 50, 51, 58, 81, 94, 96 are **Heide in the base
  classification** (only heath tufts within 150 m). The "patch" heath-in-moor rule
  then flips the whole heath patch to Moor because a few cells lie within 100 m
  of recurring Torfstich: a 278 ha heath by 57 cells, a 192 ha heath by 27 cells.
  This explains the unexplained loss at 37/50/94/96 seen with train10.

| Blind check (06v compare) | Published map | train11 patch | train11 region |
|---|---|---|---|
| Overall | **93 % ± 4 %** | 91 % ± 4 % | **93 % ± 4 %** |
| Moor UA / PA | 0.89 / 0.93 | 0.84 / 0.94 | 0.94 / 0.94 |
| nasse Wiese UA / PA | 0.86 / 0.86 | 0.86 / 0.86 | 0.86 / 0.86 |
| Heide UA / PA | 0.89 / 0.78 | 0.89 / 0.26 | 0.96 / 0.77 |
| Moor / nW / Heide ha | 4,608 / 7,166 / 841 | 5,328 / 7,075 / 358 | 4,814 / 7,075 / 873 |

- train11 + region ties the published map (85 vs 87 of 100 points right
  unweighted; 9 points better, 10 worse) with higher Moor and Heide UA. First
  two-class model to match the published map. Published map kept for now.
- With train10, region did not help because the heath tufts were already
  called Bruch; with train11 the tufts are there, and region stops the flip.

## train12 (2-3 Nov): val split with heath tufts
- 06y: use='val' allowed outside the block (r50_c74, r39_c71 in tiles_aoi; r10_c09 in
  tiles_fiel). Train 74 tiles / 234 heath, val 7 / 43 heath, test 10 / 42 heath.
- yolo26s, same settings as train11. Early stop at epoch 154, best epoch 74.
  Val: tuft mAP50 0.51, torfstich 0.99, heath_tuft 0.31 (R 0.16).
- 06z test, conf 0.15, 4 sheets pooled (train11 -> train12):
  all tufts F1 0.61 -> 0.63, heath_tuft F1 0.51 -> 0.59 (R 0.71, P 0.50).
  Block heath 12/17 (P 0.57), Lürschau heath 11/17, Dosenmoor still 10 false heath.
- 06b (0.15/0.5/0.15): AOI 11,621 Bruch, 2,034 heath (train11: 2,939), 772 Torfstich.
- Map, rule "region": 92 % ± 4 %, 84/100 points right (published 86 in the same
  compare), Moor UA/PA 0.94/0.94, Heide 0.95/0.62. Moor 4,886 / nW 7,023 / Heide 719 ha.
  Block κ 0.81 (east 0.85). Not better – published map kept; outputs in `train12_aoi\`.
- Conclusion: better heath on the test tiles does not carry over to the AOI; the
  model finds fewer heath tufts there than train11. Retrains on the same labels
  trade Bruch against heath – more heath labels from other sheets are needed.

## train13 (3 Nov): + Segeberger Heide labels
- Segeberg sheet: extent moved onto the heath west of the town (575000-580000 /
  5973000-5978000). 11 tiles fully labelled (9 label, val r10_c03 + r13_c00).
  06y: train 83 tiles / 419 heath, val 9 / 66 heath, test 10 / 42 heath.
- Training stopped at epoch 155, best epoch 75. Val heath_tuft R 0.31 (train12 0.16).
- 06z test, 4 sheets pooled: heath scores lower, best heath conf ≈ 0.11. At 0.15:
  Bruch F1 0.62 (train12 0.58), heath F1 0.44 (0.59), all tufts 0.60 (0.63); at 0.11 heath
  F1 0.54. Lürschau heath worse (2/17 at 0.15), Dosenmoor false heath 10 → 4.
- 06b with 0.15/0.5/0.11. Map, rule "region": 93 % ± 4 %, 86/100 old points (published 86),
  Moor UA/PA 0.94/0.90, **Heide 0.96/0.83** (best so far). Moor 4,689 / nW 7,122 / Heide 892 ha.
  Outputs in `train13_aoi\`.
- New blind check `06u_disagreement_check.py`: 40 new points only where the published map and
  train13 differ (1,041 ha, 3.9 % of the checked area). Published right 16, train13 right 14,
  neither 10 → B − A −0.2 percentage points (95 %: −1.3 to +0.9). **Tie – published map kept.**
- Pattern in the 40 points: 13 are Heide on the old map; train13 maps 10 of them as none
  (6 where the published map has Heide). Train13 wins on Moor that the published map leaves as
  none (5 points). Both maps miss heath; neither is clearly better.

## Next steps

1. Heide/Moor needs a better reading of the dashes, not a new rule on top of
   the current dash filter. Options:
   - two tuft classes in YOLO (heath tuft / Bruch tuft), labelled by hand;
     the network sees the surroundings of each box and can learn the dashes
   - a separate detector or segmentation for Bruch dashes
   Test both detection sets with `06c ... aoi debug` and 06v compare.
2. If that is fixed: update plugin models; label further sheets (Himmelmoor,
   Jardelunder Moor, Eiderstedt) for the state-wide run.
