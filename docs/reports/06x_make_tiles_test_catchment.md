# 06x_make_tiles – Map tiles for YOLO

_Run: 2026-10-26 12:38 · TEST MODE (test_catchment)_

- source: `chronologen_1880_block.tif`, 6000 × 6000 px at 1 m
- tiles: **361** (19 rows × 19 columns), 320 m → 640 px (0.5 m/px)
- images: `data\interim\yolo\tiles` (PNG + world file .pgw)
- index: `data\interim\yolo\tiles.gpkg`, layer `tiles` – set field `use` = `label` for the tiles you label

Map: Preußische Landesaufnahme 1878–80, © GeoBasis-DE/LVermGeo SH/CC BY 4.0
