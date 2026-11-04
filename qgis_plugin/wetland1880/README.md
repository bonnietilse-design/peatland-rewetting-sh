# Wetland 1880 Reader – QGIS plugin

Reads **Moor**, **nasse Wiese** (wet meadow) and **Heide** (heath) from the Prussian survey map 1878–80
(*Preußische Landesaufnahme*) and returns them as polygons. Developed for my portfolio project
[peatland-rewetting-sh](https://github.com/bonnietilse-design/peatland-rewetting-sh).

**How it works**

1. The map is cut into 320 m tiles (enlarged to 640 px).
2. Two small YOLO26 models find **tufts** (first training round) and **peat cuttings / Torfstich** (second round).
3. **Dashes** are found by image analysis and counted **per field** – the fields come from the map's own field lines.
4. The rules of the official 1898 map key turn tufts, dashes and peat cuttings into classes on a 25 m grid:
   tufts + dashes → Moor, recurring peat cuttings → Moor, dashes only → nasse Wiese, tufts only → Heide.

In the Treene–Sorge lowland (Schleswig-Holstein) the result reached **93 % ± 4 %** overall accuracy in a
blind 100-point check. Other landscapes have not been checked – look at the result before using it.

## Installation

1. **QGIS:** *Plugins → Manage and Install Plugins → Install from ZIP* → `wetland1880.zip`.
2. **YOLO environment** (once; QGIS's own Python is not touched):
   ```bat
   python -m venv C:\yolo-env
   C:\yolo-env\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
   C:\yolo-env\Scripts\python -m pip install ultralytics
   ```
3. The tool appears in the **Processing Toolbox → Wetland 1880 Reader → Classify 1878–80 map**.
   The first time, give `C:\yolo-env\Scripts\python.exe` (it is remembered).

## Input

A **1 m raster** of the 1878–80 map, e.g. the WCS *Chronologen* of LVermGeo SH
(`https://dienste.gdi-sh.de/WCS_SH_FD_Chronologen`, coverage `Chronologen_1_1878-1880`,
exported as raw data). Black = ink. It is reprojected to EPSG:25832 automatically. An optional
polygon limits the area. About 5 minutes per 300 km² on a laptop CPU.

## Output

- **1880 classes** – polygons with `hist_type`, `code`, `area_ha`, styled automatically
- **Detected symbols** (optional) – points with `symbol` and `conf`

## Known limitations

- Developed on one landscape (Treene–Sorge lowland). On a test sheet near Fiel (Dithmarschen) the peat
  cuttings were found well, but the dense **dot pairs of dry meadow** were sometimes taken for single
  tufts, which makes small isolated "Heide" squares. If you see these, run again with
  *Advanced → Tufts per 75 m needed for Heide = 2*. Use it only there: in the Treene–Sorge lowland the
  same setting turns about 120 ha of bog heath back from Moor (via the "heath in a moor" rule).
- Moor names on the map are not read; the classes follow the map **symbols** of 1878–80, so a moor that
  was already drained and used as meadow then is not shown as wet.
- Peat-cutting areas become squares around the cuttings, not whole fields.

## Licence and credits

AGPL-3.0, because the models are trained with [Ultralytics YOLO](https://docs.ultralytics.com) (AGPL-3.0).
Map © GeoBasis-DE/LVermGeo SH/CC BY 4.0. Symbol meanings: *Zeichen-Erklärung für die
Messtischblätter 1:25 000* (Kgl. Preuß. Landesaufnahme, 1898). The code was written with AI
assistance; I trained the models, labelled the training data and checked every step.

Bonnie Winter, 2026
