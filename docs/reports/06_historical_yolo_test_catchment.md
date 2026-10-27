# 06_historical_yolo – Wet land 1878–80 vs. organic soils today – automated, whole test area

_Run: 2026-10-27 12:32 · TEST MODE (test_catchment)_

> Compares map *signatures* of 1878–80 with today's *soil* map. The two use different concepts, so differences are not simply gains or losses.

- source: **automated reading (YOLO + rules, step 06c aoi)**, whole test area: **30,358 ha**
- in the hand-digitised block the automation agrees with the hand digitising on ~90 % of the area; outside it there is no reference (see report 06c_yolo_aoi)
- automated Heide (822 ha) is left out: heath away from any moor is mostly dry geest heath, not evidence of peat
- gaps ≤ 30 m closed (roads, ditches): 80.9 ha added
- wet signatures 1880: **11,409 ha** (38% of the extent)
- organic soils today: **15,952 ha** (53%)

| category | ha | meaning |
|---|---:|---|
| kept | 10,150 | wet in 1880, organic soil today |
| lost | 1,259 | wet in 1880, no organic soil today |
| only_today | 5,802 | organic today, no wet signature in 1880 (mapping concept – e.g. drained fen used as pasture) |

Within ±25 m of the other layer's boundary (possible position error): lost 306 ha (24% of lost), only_today 1,328 ha (23% of only_today).

### Per 1880 class

| hist_type   |   total |   kept |   lost |   kept_% |
|:------------|--------:|-------:|-------:|---------:|
| Moor        |  4544.8 | 4254.7 |  290.1 |     93.6 |
| nasse Wiese |  6864.3 | 5895   |  969.3 |     85.9 |

Peat evidence per class: Moor = certain, nasser Boden = likely, nasse Wiese = likely, Heide = possible

### 1880 class × today's soil type (kept area, ha)

| hist_type   |   DK_FL_HH |   DK_FL_NH |   DK_MA_NH |   HH |   MF |   NH |
|:------------|-----------:|-----------:|-----------:|-----:|-----:|-----:|
| Moor        |        178 |         41 |         26 | 3468 |  117 |  423 |
| nasse Wiese |        111 |       1051 |        655 |  474 | 1188 | 2416 |

### Organic soil today without a wet signature in 1880 (ha)

| today_type                                       |   area_ha |
|:-------------------------------------------------|----------:|
| NH – Niedermoorboden                             |      2500 |
| MF – Moorfolgeboden                              |       966 |
| DK_FL_NH – flach ueberdeckter Niedermoorboden    |       860 |
| DK_MA_NH – maechtig ueberdeckter Niedermoorboden |       729 |
| HH – Hochmoorboden                               |       531 |
| DK_FL_HH – flach ueberdeckter Hochmoorboden      |       216 |

### Notes

- single Torfstich noted (class not changed): 0 polygon(s)
- Moor polygons without a recognised evidence code: 0
- Legend: Zeichen-Erklärung für die Messtischblätter 1:25 000 (1898); map © GeoBasis-DE/LVermGeo SH/CC BY 4.0; soils: Thünen (CC BY 4.0).
- Caveats: hand digitising at ~1:2,500–1:5,000; positional accuracy of the 1880 survey; the 1898 key is ~20 years younger than the sheets; Hutung/trockene Wiese were not digitised although some lie on fen.
