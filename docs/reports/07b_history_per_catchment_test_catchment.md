# 07b_history_per_catchment – The 1878–80 map per sub-catchment

_Run: 2026-10-27 12:33 · TEST MODE (test_catchment)_

- 1880 layer: automated reading of the whole test area (YOLO + rules, step 06 yolo); wet = Moor + nasse Wiese (Heide left out, as in step 06)
- sub-catchments: step 05 (350, 266 complete); candidates and selection: step 07 (248 candidates, 78 chosen, target 75,000 t CO2-eq/yr)

### Chosen catchments vs. the rest

| group | catchments | area ha | wet in 1880 | of it Moor | farmed peat wet in 1880 | Moorfolgeboden (of organic soil today) |
|---|---:|---:|---:|---:|---:|---:|
| chosen in step 07 | 78 | 4,163 | 65% | 29% | 63% | 17% |
| other candidates | 170 | 16,848 | 38% | 15% | 58% | 13% |
| all complete sub-catchments | 266 | 22,045 | 42% | 17% | 60% | 14% |

Shares are area-weighted (sum over the group).

### Sensitivity: prefer land that was wet in 1880

Step 07 is re-run with an extra cost: each ha of farmed peat that was **not** wet in 1880 counts as *w* ha of farmland on mineral soil. The weight is a choice, not a measured value – the table shows how much the selection depends on it.

| weight w | catchments | same as step 07 | saving t/yr | farmland on mineral soil ha | farmed peat wet in 1880 |
|---|---:|---:|---:|---:|---:|
| 0 (step 07) | 78 | – | 75,001 | 44 | 63% |
| 0.25 | 67 | 58 of 78 | 75,001 | 77 | 77% |
| 0.5 | 72 | 55 of 78 | 75,002 | 127 | 82% |
| 1 | 74 | 50 of 78 | 75,002 | 168 | 85% |

Map: `outputs/07b_history_per_catchment_test_catchment.png`; layer `catchments_history` (fields wet1880_ha, moor1880_ha, mf_ha, fpeat_wet1880_ha, selected = step 07, sel_hist = weight 0.5).

Caveats: the 1880 layer is an automated reading (overall accuracy 90 % ± 6 %, report 06v); nasse Wiese is over-mapped by roughly a sixth. 'Wet in 1880' describes map signatures, not measured water levels. Savings are ESTIMATES.
