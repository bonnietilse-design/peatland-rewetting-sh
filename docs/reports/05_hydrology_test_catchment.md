# 05_hydrology – Sub-catchments from DGM1 (GRASS r.watershed)

_Run: 2026-10-23 13:53 · TEST MODE (test_catchment)_

- DGM1 tiles: 355, working resolution 5 m (min of the 1 m cells)
- algorithm: grass:r.watershed, single (D8) flow direction
- min. sub-catchment size: 50 ha (20,000 cells)
- sub-catchments: 367 (of which 72 small pieces)
- touching the AOI/DEM edge (field `complete` = 0, incomplete – water from outside missing): 80
- complete sub-catchments ≥ 50 % organic soil: **196** (14,741 ha, 12,119 ha of it peat)

The AOI is a hand-drawn test polygon, not a real catchment: the Treene,
Sorge and Eider drain much larger areas. Interpret only complete
sub-catchments.

Rasters (accumulation, drainage direction, streams, basins) are in
`data/interim/hydro/test_catchment/` – load them in QGIS to check.

Limitations: the DEM does not show pipe drains, culverts or pumping
stations, which control water in fen landscapes; drainage there is
largely artificial. Compare the streams with the official water-body
network before interpreting. Tiles from different survey years can
create small steps at tile edges (see report 01).
