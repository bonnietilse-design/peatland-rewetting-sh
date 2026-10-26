# 06v_accuracy_check – Blind accuracy check outside the hand-digitised block

_Run: 2026-10-26 17:18 · TEST MODE (test_catchment)_

- 100 checked points (0 left empty), stratified by predicted class, outside the hand-digitised block; reference read by me from the 1878–80 map without seeing the prediction
- **overall accuracy 90% ± 6%** (area-weighted, 95 % CI)

### Confusion matrix (sample counts; rows = automated map, columns = my reading)

| pred        |   none |   Moor |   nasse Wiese |   Heide |
|:------------|-------:|-------:|--------------:|--------:|
| none        |     24 |      0 |             1 |       0 |
| Moor        |      0 |     23 |             0 |       2 |
| nasse Wiese |      5 |      2 |            18 |       0 |
| Heide       |      2 |      2 |             0 |      21 |

### Per class (area-weighted)

|             |   mapped ha |   sample |   user's acc. |   producer's acc. |   estimated ha |   ± 95 % ha |
|:------------|------------:|---------:|--------------:|------------------:|---------------:|------------:|
| none        |       16862 |       25 |          0.96 |              0.93 |          17381 |        1605 |
| Moor        |        3478 |       25 |          0.92 |              0.86 |           3714 |         726 |
| nasse Wiese |        5665 |       25 |          0.72 |              0.86 |           4754 |        1668 |
| Heide       |         752 |       25 |          0.84 |              0.69 |            910 |         393 |

User's accuracy: of the area mapped as a class, the share that really is that class. Producer's accuracy: of the real area of a class, the share the map finds. Estimated ha: area of each class corrected for the map errors.

Method: Olofsson P. et al. (2014): Good practices for estimating area and assessing accuracy of land change. Remote Sensing of Environment 148: 42–57.
