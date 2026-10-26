# 06_historical – Wet land 1878–80 vs. organic soils today

_Run: 2026-10-26 11:45 · TEST MODE (test_catchment)_

> Compares map *signatures* of 1878–80 with today's *soil* map. The two use different concepts, so differences are not simply gains or losses.

- area checked on the 1880 map (digitised_extent ∩ AOI): **3,600 ha**
- polygons digitised: 48 (2,212 ha before clipping)
- gaps ≤ 30 m closed (roads, ditches): 10.0 ha added
- wet signatures 1880: **2,182 ha** (61% of the extent)
- organic soils today: **2,727 ha** (76%)

| category | ha | meaning |
|---|---:|---|
| kept | 2,007 | wet in 1880, organic soil today |
| lost | 175 | wet in 1880, no organic soil today |
| only_today | 721 | organic today, no wet signature in 1880 (mapping concept – e.g. drained fen used as pasture) |

Within ±25 m of the other layer's boundary (possible position error): lost 55 ha (31% of lost), only_today 96 ha (13% of only_today).

### Per 1880 class

| hist_type   |   total |   kept |   lost |   kept_% |
|:------------|--------:|-------:|-------:|---------:|
| Moor        |  1086   | 1033.9 |   52.1 |     95.2 |
| nasse Wiese |  1067.1 |  971.2 |   95.9 |     91   |
| Heide       |    29   |    1.7 |   27.3 |      5.8 |

Peat evidence per class: Moor = certain, nasser Boden = likely, nasse Wiese = likely, Heide = possible

### 1880 class × today's soil type (kept area, ha)

| hist_type   |   DK_FL_HH |   DK_FL_NH |   DK_MA_NH |   HH |   MF |   NH |
|:------------|-----------:|-----------:|-----------:|-----:|-----:|-----:|
| Moor        |         46 |          8 |          2 |  787 |  119 |   73 |
| nasse Wiese |         13 |         78 |         28 |   51 |  336 |  465 |
| Heide       |          1 |          0 |          0 |    0 |    0 |    0 |

### Organic soil today without a wet signature in 1880 (ha)

| today_type                                       |   area_ha |
|:-------------------------------------------------|----------:|
| NH – Niedermoorboden                             |       423 |
| DK_FL_NH – flach ueberdeckter Niedermoorboden    |        89 |
| MF – Moorfolgeboden                              |        76 |
| HH – Hochmoorboden                               |        61 |
| DK_FL_HH – flach ueberdeckter Hochmoorboden      |        45 |
| DK_MA_NH – maechtig ueberdeckter Niedermoorboden |        27 |

### Notes

- single Torfstich noted (class not changed): 1 polygon(s)
- Moor polygons without a recognised evidence code: 0
- Legend: Zeichen-Erklärung für die Messtischblätter 1:25 000 (1898); map © GeoBasis-DE/LVermGeo SH/CC BY 4.0; soils: Thünen (CC BY 4.0).
- Caveats: hand digitising at ~1:2,500–1:5,000; positional accuracy of the 1880 survey; the 1898 key is ~20 years younger than the sheets; Hutung/trockene Wiese were not digitised although some lie on fen.
