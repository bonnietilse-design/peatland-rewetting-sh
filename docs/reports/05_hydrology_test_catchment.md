# 05_hydrology – Sub-catchments from DGM1 (GRASS r.watershed)

_Run: 2026-10-27 10:24 · TEST MODE (test_catchment)_

- DGM1 tiles: 355, working resolution 5 m (min of the 1 m cells)
- algorithm: grass:r.watershed, single (D8) flow direction
- min. sub-catchment size: 50 ha (20,000 cells)
- sub-catchments: 350 (of which 61 small pieces)
- touching the AOI/DEM edge (field `complete` = 0, incomplete – water from outside missing): 84
- complete sub-catchments ≥ 50 % organic soil: **178** (14,002 ha, 11,651 ha of it peat)

### Stream burning
- water-body network: `water_network.gpkg`, 1,885 km of lines inside the DEM, burned 3 m deep
- official water bodies within 10 m of a modelled stream: 7% without burning → **12%** with burning
  (modelled streams only start above the sub-catchment threshold, so
  small ditches stay below 100 % – what matters is the change)
- sub-catchments reaching into the AOI: 367 without burning → 350 with burning
- compare `stream_min.tif` and `stream_min_burn.tif` in QGIS with the water-body network

The AOI is a hand-drawn test polygon, not a real catchment: the Treene,
Sorge and Eider drain much larger areas. Interpret only complete
sub-catchments.

Rasters (accumulation, drainage direction, streams, basins) are in
`data/interim/hydro/test_catchment/` – load them in QGIS to check.

Limitations: the DEM does not show pipe drains, culverts or pumping
stations, which control water in fen landscapes; drainage there is
largely artificial. Burning the official water-body network corrects the main ditches and culverted streams, but not pipe drains or pumps. Tiles from different survey years can
create small steps at tile edges (see report 01).
