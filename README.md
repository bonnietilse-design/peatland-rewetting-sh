# Peatland rewetting in Schleswig-Holstein

Where are the peat soils in Schleswig-Holstein, how are they used, how much do they emit – and where would rewetting make the most sense?

A QGIS / open-source portfolio project by **Bonnie Winter** (GIS-Akademie Hamburg, 2026).

> **Status:** work in progress. All emission figures are **estimates** (area × emission factor) and are labelled as such.

## Context

According to the Land Schleswig-Holstein (Moor-Klimaschutz, Jan 2024), carbon-rich soils cover about 152,800 ha (≈10 % of the state), more than 81 % of them are used for agriculture, and they cause about 17 % of the state's greenhouse gas emissions.

## Methods (new skills compared with my earlier projects)

| Step | Script | Method | Tools |
|---|---|---|---|
| 00 | `00_check_inputs.py` | Inventory of inputs: CRS, fields, example values | GeoPandas |
| 01 | `01_prepare_dgm1.py` | DGM1 completeness check, XYZ → GeoTIFF, survey years | GDAL |
| 02 | `02_prepare_inputs.py` | Reproject, repair, clip to AOI → one GeoPackage | GeoPandas |
| 03 | `03_overlay_soils_landuse.py` | Organic soils × arable/grassland, per municipality | GeoPandas |
| 04 | `04_emission_estimate.py` | Area × emission factor (Thünen) | pandas |
| 05 | `05_hydrology.py` | Flow direction, accumulation, streams, sub-catchments | GRASS r.watershed via qgis_process |
| 06 | `06_historical_loss.py` | Preußische Landesaufnahme 1878–80 vs. today | QGIS georeferencer, GeoPandas |
| 07 | `07_optimisation.py` | Minimum area / parcels for a CO2 target | SciPy milp / HiGHS (integer programming) |
| 08 | `08_monte_carlo.py` | Uncertainty from emission factors | numpy |
| 09 | `09_export_maps_pyqgis.py` | Atlas map series | PyQGIS |

Each step writes a short report to `docs/reports/`.

## Repository structure

```
config.py            all paths, fields, parameters, emission factors
peatsh/common.py     shared helpers (AOI, clipping, GeoPackage I/O, reports)
scripts/             numbered steps 00–09
qgis/                QGIS project, Graphical Modeler models, styles (.qml)
data/raw/            downloads – not in git
data/interim/        intermediate rasters – not in git
data/processed/      peatland_sh.gpkg – not in git
outputs/             maps, figures, CSV tables
docs/reports/        one markdown report per step
```

## How to run

```bash
conda env create -f environment.yml
conda activate peatland-sh
# 1. download data into data/raw/ (see DATA_SOURCES.md)
# 2. draw or derive the test catchment → data/raw/aoi/test_aoi.gpkg
python scripts/00_check_inputs.py      # then fill FIELDS in config.py
python scripts/02_prepare_inputs.py
python scripts/03_overlay_soils_landuse.py
# ...
```

`TEST_MODE = True` in `config.py` runs everything on one catchment; set it to `False` for the whole state.

## Limitations

- Emission factors are class averages; water level, peat thickness and management within a class are ignored.
- The DEM does not show ditches, drains or pumping stations, which control water in fen landscapes.
- Historical peat extent comes from map signatures, not soil survey – different concepts, plus georeferencing error.

## Data and licences

See [DATA_SOURCES.md](DATA_SOURCES.md). Code: MIT (or your choice). Code was written with AI assistance; every step was run and checked by me.
