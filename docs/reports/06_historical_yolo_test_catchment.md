# 06_historical_yolo – Wet land 1878–80 vs. organic soils today – automated, whole test area

_Run: 2026-10-26 16:30 · TEST MODE (test_catchment)_

> Compares map *signatures* of 1878–80 with today's *soil* map. The two use different concepts, so differences are not simply gains or losses.

- source: **automated reading (YOLO + rules, step 06c aoi)**, whole test area: **30,358 ha**
- in the hand-digitised block the automation agrees with the hand digitising on ~90 % of the area; outside it there is no reference (see report 06c_yolo_aoi)
- automated Heide (761 ha) is left out: heath away from any moor is mostly dry geest heath, not evidence of peat
- gaps ≤ 30 m closed (roads, ditches): 84.2 ha added
- wet signatures 1880: **11,385 ha** (38% of the extent)
- organic soils today: **15,952 ha** (53%)

| category | ha | meaning |
|---|---:|---|
| kept | 10,020 | wet in 1880, organic soil today |
| lost | 1,365 | wet in 1880, no organic soil today |
| only_today | 5,932 | organic today, no wet signature in 1880 (mapping concept – e.g. drained fen used as pasture) |

Within ±25 m of the other layer's boundary (possible position error): lost 301 ha (22% of lost), only_today 1,380 ha (23% of only_today).

### Per 1880 class

| hist_type   |   total |   kept |   lost |   kept_% |
|:------------|--------:|-------:|-------:|---------:|
| Moor        |  4435.3 | 4043.5 |  391.9 |     91.2 |
| nasse Wiese |  6949.6 | 5976.7 |  972.9 |     86   |

Peat evidence per class: Moor = certain, nasser Boden = likely, nasse Wiese = likely, Heide = possible

### 1880 class × today's soil type (kept area, ha)

| hist_type   |   DK_FL_HH |   DK_FL_NH |   DK_MA_NH |   HH |   MF |   NH |
|:------------|-----------:|-----------:|-----------:|-----:|-----:|-----:|
| Moor        |        175 |         37 |         27 | 3349 |  107 |  347 |
| nasse Wiese |        114 |       1054 |        656 |  518 | 1191 | 2443 |

### Organic soil today without a wet signature in 1880 (ha)

| today_type                                       |   area_ha |
|:-------------------------------------------------|----------:|
| NH – Niedermoorboden                             |      2549 |
| MF – Moorfolgeboden                              |       973 |
| DK_FL_NH – flach ueberdeckter Niedermoorboden    |       862 |
| DK_MA_NH – maechtig ueberdeckter Niedermoorboden |       727 |
| HH – Hochmoorboden                               |       606 |
| DK_FL_HH – flach ueberdeckter Hochmoorboden      |       216 |

### Notes

- single Torfstich noted (class not changed): 0 polygon(s)
- Moor polygons without a recognised evidence code: 0
- Legend: Zeichen-Erklärung für die Messtischblätter 1:25 000 (1898); map © GeoBasis-DE/LVermGeo SH/CC BY 4.0; soils: Thünen (CC BY 4.0).
- Caveats: hand digitising at ~1:2,500–1:5,000; positional accuracy of the 1880 survey; the 1898 key is ~20 years younger than the sheets; Hutung/trockene Wiese were not digitised although some lie on fen.
