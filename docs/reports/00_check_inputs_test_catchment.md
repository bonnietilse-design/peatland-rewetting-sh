# 00_check_inputs – Input check

_Run: 2026-10-23 10:28 · TEST MODE (test_catchment)_

## organic_soils
- file: `thuenen_kulisse_orgboeden_v1.shp`
- features: 303,672
- CRS: EPSG:25832
- geometry: Polygon

| field | dtype | examples |
|---|---|---|
| BL | str | mv, ni, hb, by, be |
| GENESE | str | NH, HH, XH |
| DECKE | str | DK0, DK2s, DK3s, DK2x, DK1b |
| TORFMAECHT | str | TM4, TM5, TM3, TM1, TM2 |
| ABMOORIGKE | str | AB0, ABb, ABx, ABs |
| TIEFUMBRUC | str | TR0 |
| MUDDE | str | MD0, MDx, MDh, MDk |
| UNTERLAGER | str | LGs, LGx, LGf, LGu, LGl |
| MASSSTAB | str | 1:25.000, 1:50.000, 1:1.000 und 1:25.000, 1:5.000, 1:5.000 bis 1:10.000 und 1:100.000 |
| AREA_HA | float64 | 0.1297716292, 41.1298748168, 0.2463857568, 0.4337892735, 1.8699389961 |
| AREA_HA_R | float64 | 0.13, 41.13, 0.25, 0.43, 1.87 |
| AREA_HA_WG | float64 | 0.1297257178, 41.1612814543, 0.246578245, 0.434049451, 1.8672278265 |
| AREA_HA_01 | float64 | 0.13, 41.16, 0.25, 0.43, 1.87 |
| KAT_KURZ | str | NH, HH, MF, DK_MA_NH, DK_FL_NH |
| KAT_LANG | str | Niedermoorboden, Hochmoorboden, Moorfolgeboden, maechtig ueberdeckter Niedermoorboden, flach ueberdeckter Niedermoorboden |

## feldbloecke
- file: `FB_20260101.gpkg`
- features: 194,503
- CRS: EPSG:4647  ⚠ differs from EPSG:25832
- geometry: Polygon

| field | dtype | examples |
|---|---|---|
| FLIK | str | DESHLIL080100006, DESHLIL080100002, DESHLIL080110000, DESHLIL080100004, DESHLIL080100017 |
| FACHGUELTI | str | 01.01.2026 |
| HBN | str | Dauergrünland, Ackerland |
| FLAECHE | str | 1,3181, 0,1685, 0,2203, 2,6420, 0,6807 |

## vg250_land
- file: `VG250_LAN.shp`
- features: 34
- CRS: EPSG:25832
- geometry: MultiPolygon, Polygon

| field | dtype | examples |
|---|---|---|
| OBJID | str | DEBKGVG200000CJN, DEBKGVG200000CJO, DEBKGVG200000CJP, DEBKGVG200000CJQ, DEBKGVG200000CJR |
| BEGINN | datetime64[ms] | 2025-04-12 00:00:00, 2025-01-04 00:00:00, 2026-06-11 00:00:00, 2023-10-04 00:00:00, 2025-01-16 00:00:00 |
| ADE | int32 | 2 |
| GF | int32 | 4, 3, 2, 1 |
| BSG | int32 | 1, 9 |
| LKZ | str | SH, HH, NI, HB, NW |
| ARS | str | 01, 02, 03, 04, 05 |
| AGS | str | 01, 02, 03, 04, 05 |
| SDV_ARS | str | 010020000000, 020000000000, 032410001001, 040110000000, 051110000000 |
| GEN | str | Schleswig-Holstein, Hamburg, Niedersachsen, Bremen, Nordrhein-Westfalen |
| BEZ | str | Land, Freie und Hansestadt, Freie Hansestadt, Freistaat |
| IBZ | int32 | 20, 22, 23, 21 |
| BEM | str | -- |
| NBD | str | ja, nein |
| SN_L | str | 01, 02, 03, 04, 05 |
| SN_R | str | 0 |
| SN_K | str | 00 |
| SN_V1 | str | 00 |
| SN_V2 | str | 00 |
| SN_G | str | 000 |
| FK_S3 | str | 0 |
| NUTS | str | DEF, DE6, DE9, DE5, DEA |
| ARS_0 | str | 010000000000, 020000000000, 030000000000, 040000000000, 050000000000 |
| AGS_0 | str | 01000000, 02000000, 03000000, 04000000, 05000000 |
| WSK | datetime64[ms] | 2012-02-01 00:00:00, 1974-01-01 00:00:00, 2015-01-01 00:00:00, 2010-01-01 00:00:00, 2009-11-01 00:00:00 |
| DLM_ID | str | DEBKGDL200000029, DEBKGDL20000E6GD, DEBKGDL20000E6EW, DEBKGDL20000E0SF, DEBKGDL20000E6GR |

## vg250_gem
- file: `VG250_GEM.shp`
- features: 11,094
- CRS: EPSG:25832
- geometry: Polygon, MultiPolygon

| field | dtype | examples |
|---|---|---|
| OBJID | str | DEBKGVG200000008, DEBKGVG200000009, DEBKGVG20000000A, DEBKGVG20000000B, DEBKGVG20000000C |
| BEGINN | datetime64[ms] | 2022-12-20 00:00:00, 2025-01-04 00:00:00, 2026-06-11 00:00:00, 2025-04-12 00:00:00, 2023-10-04 00:00:00 |
| ADE | int32 | 6 |
| GF | int32 | 4 |
| BSG | int32 | 1 |
| LKZ | str | SH |
| ARS | str | 010010000000, 010020000000, 010030000000, 010040000000, 010510011011 |
| AGS | str | 01001000, 01002000, 01003000, 01004000, 01051011 |
| SDV_ARS | str | 010010000000, 010020000000, 010030000000, 010040000000, 010510011011 |
| GEN | str | Flensburg, Kiel, Lübeck, Neumünster, Brunsbüttel |
| BEZ | str | Stadt, Gemeinde |
| IBZ | int32 | 60, 61, 64, 63, 62 |
| BEM | str | kreisfrei, --, gemeinschaftsangehörig |
| NBD | str | ja |
| SN_L | str | 01 |
| SN_R | str | 0 |
| SN_K | str | 01, 02, 03, 04, 51 |
| SN_V1 | str | 00, 51, 01, 53, 54 |
| SN_V2 | str | 00, 11, 44, 63, 66 |
| SN_G | str | 000, 011, 044, 003, 010 |
| FK_S3 | str | R |
| NUTS | str | DEF01, DEF02, DEF03, DEF04, DEF05 |
| ARS_0 | str | 010010000000, 010020000000, 010030000000, 010040000000, 010510011011 |
| AGS_0 | str | 01001000, 01002000, 01003000, 01004000, 01051011 |
| WSK | datetime64[ms] | 2008-01-01 00:00:00, 2006-01-01 00:00:00, 2006-02-01 00:00:00, 1970-04-26 00:00:00, 2009-01-01 00:00:00 |
| DLM_ID | str | DEBKGDL20000E5MA, DEBKGDL20000004J, DEBKGDL20000DYMA, DEBKGDL20000E4SA, DEBKGDL20000E2IK |

## historical_peat
- **missing** – expected at `D:\PORTFOLIO\Peatlands\peatland-rewetting-sh\peatland-rewetting-sh\data\raw\historical\peat_1880_digitised.gpkg`

## protected_areas
- **missing** – expected at `D:\PORTFOLIO\Peatlands\peatland-rewetting-sh\peatland-rewetting-sh\data\raw\protected\TODO_filename.gpkg`

## dgm1
- GeoTIFF tiles found: 0

