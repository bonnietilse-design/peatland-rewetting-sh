# Data sources

| Dataset | Provider | Licence | Attribution | Folder |
|---|---|---|---|---|
| Aktualisierte Kulisse organischer Böden in Deutschland (Wittnebel, Frank, Tiemeyer 2023), DOI 10.3220/DATA20230510130443-0 | Thünen-Institut | CC BY 4.0 | Wittnebel M, Frank S, Tiemeyer B (2023), Thünen Working Paper 212 | `data/raw/thuenen_organic_soils/` |
| Feldblöcke Schleswig-Holstein, reference date 1.1.2026 (FB_20260101.gpkg) | Land SH | dl-de/zero-2.0 (TODO: confirm for 2026) | – | `data/raw/feldbloecke/` |
| DGM1 (1 m terrain model) | LVermGeo SH, OpenGBD portal | CC BY 4.0 | © GeoBasis-DE/LVermGeo SH/CC-BY 4.0 | `data/raw/dgm1/` |
| Preußische Landesaufnahme mit Chronologen bis 1950 (WCS/WMS) | LVermGeo SH | CC BY 4.0 (NOT the all-editions version – private use only) | © GeoBasis-DE/LVermGeo SH/CC-BY 4.0 | `data/raw/historical/` |
| VG250 administrative boundaries | BKG | dl-de/by-2.0 | © GeoBasis-DE / BKG (year) | `data/raw/vg250/` |
| Protected areas (FFH, NSG) | LfU SH | TODO – check | TODO | `data/raw/protected/` |

## Emission factors

| Class | Value [t CO2-eq/ha/yr] | SD | Source (table/page) |
|---|---|---|---|
| Cropland on organic soil | 40.4 | 6.9* | Tiemeyer et al. 2020, Ecol. Indic. 109:105838, Table 5 (p. 9) |
| Grassland on organic soil | 31.7 | 9.0* | same |
| Rewetted organic soil | 5.5 | 3.5* | same |

Values are implied national emission factors (total GHG: CO2 incl. DOC, CH4 from soil and ditches, N2O; GWP IPCC AR4), valid for the whole land-use category including its undrained share.

\* SD is not given in the paper. It is approximated from the 95 % range of the CO2-onsite EF in Table 2 (p. 7): SD = (upper − lower) / 3.92 × 44/12. Those ranges are skewed, so the normal distribution in the Monte Carlo is a simplification.

These are national averages. The regional water table in the test area may differ from the German mean (e.g. existing wet-grassland schemes), which this estimate does not capture.

Tiemeyer B, Freibauer A, Borraz EA, et al. (2020): A new methodology for organic soils in national greenhouse gas inventories: Data synthesis, derivation and application. Ecological Indicators 109: 105838. https://doi.org/10.1016/j.ecolind.2019.105838
