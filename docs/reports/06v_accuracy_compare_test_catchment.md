# 06v_accuracy_compare – Blind accuracy check: new map vs. the map the sample came from

_Run: 2026-10-27 12:31 · TEST MODE (test_catchment)_

- 100 reference points (the same as in report 06v), outside the hand-digitised block
- sample drawn from `yolo_classes_aoi.tif` (strata); new map: `yolo_classes_aoi.tif`
- **overall accuracy: old map 90% ± 6% → new map 91% ± 6%** (area-weighted, 95 % CI)

Points right/wrong in old (rows) and new map (columns):

| row_0     |   new right |   new wrong |
|:----------|------------:|------------:|
| old right |          85 |           1 |
| old wrong |           3 |          11 |

### Old map

|             |   user's acc. |   producer's acc. |   mapped ha |   estimated ha |   ± 95 % ha |
|:------------|--------------:|------------------:|------------:|---------------:|------------:|
| none        |          0.96 |              0.93 |       16862 |          17381 |        1605 |
| Moor        |          0.92 |              0.86 |        3478 |           3714 |         726 |
| nasse Wiese |          0.72 |              0.86 |        5665 |           4754 |        1668 |
| Heide       |          0.84 |              0.69 |         752 |            910 |         393 |

### New map

|             |   user's acc. |   producer's acc. |   mapped ha |   estimated ha |   ± 95 % ha |
|:------------|--------------:|------------------:|------------:|---------------:|------------:|
| none        |          0.96 |              0.93 |       16764 |          17381 |        1605 |
| Moor        |          0.9  |              0.93 |        3600 |           3714 |         726 |
| nasse Wiese |          0.78 |              0.86 |        5581 |           4754 |        1668 |
| Heide       |          0.89 |              0.81 |         813 |            910 |         393 |

The new map is evaluated with the strata of the old one (Stehman 2014): each point keeps the weight of the stratum it was drawn from. The confidence intervals overlap strongly when both maps are similar – look at the points that changed (table above).
