"""
09 – Atlas: one A4 map page per municipality (PyQGIS)

Run INSIDE QGIS, with the project qgis/peatland_sh.qgz open:
  Plugins → Python Console → Show Editor (notepad icon) → open this file → Run.

What it does - fully scripted, so it can be re-run after any analysis change:
  1. builds the atlas coverage layer: every municipality in the AOI with at
     least ATLAS_MIN_PEAT_HA of farmed peat, with key figures per municipality
     (farmed peat, current emissions, saving potential, peat inside the
     catchments chosen by the catchment optimisation of step 07)
  2. loads and styles the map layers (group "Atlas layers" in the layer panel;
     your own layers are not touched)
  3. creates the print layout "Atlas_Gemeinden": main map following each
     municipality, overview map, title, key figures, legend, scale bar,
     north arrow, sources
  4. exports outputs/maps/atlas_gemeinden.pdf (all pages) plus one PNG per page

Re-running replaces the group, the layout and the exports.
"""
import sys
from pathlib import Path

from qgis.core import (QgsCategorizedSymbolRenderer, QgsFillSymbol, QgsLayerTreeGroup,  # type: ignore
                       QgsLayoutExporter, QgsLayoutItemLabel, QgsLayoutItemLegend,
                       QgsLayoutItemMap, QgsLayoutItemPage, QgsLayoutItemPicture,
                       QgsLayoutItemScaleBar, QgsLayoutPoint, QgsLayoutSize,
                       QgsPrintLayout, QgsProject, QgsRasterLayer, QgsRectangle,
                       QgsRendererCategory, QgsRuleBasedRenderer, QgsSingleSymbolRenderer,
                       QgsTextFormat,
                       QgsUnitTypes, QgsVectorLayer)
from qgis.PyQt.QtGui import QColor, QFont  # type: ignore

PROJECT = QgsProject.instance()
if not PROJECT.homePath():
    raise RuntimeError("Save/open the project qgis/peatland_sh.qgz first.")
ROOT = Path(PROJECT.homePath()).parent            # project lives in qgis/
sys.path.insert(0, str(ROOT))

import geopandas as gpd  # noqa: E402

import config as cfg  # noqa: E402

LAYOUT_NAME = "Atlas_Gemeinden"
GROUP_NAME = "Atlas layers"
ATLAS_MIN_PEAT_HA = 50                         # skip municipalities with less farmed peat
OUT_DIR = ROOT / "outputs" / "maps"
ATLAS_GPKG = ROOT / "outputs" / "atlas_layers.gpkg"   # separate file: never locks the main GPKG
LABEL = cfg.aoi_label()
SOURCES = ("Data: organic soils © Thünen-Institut (Wittnebel et al. 2023, CC BY 4.0); "
           "Feldblöcke © Land Schleswig-Holstein 2026 (dl-de/zero-2.0); "
           "DGM1 © GeoBasis-DE/LVermGeo SH (CC BY 4.0); VG250 © GeoBasis-DE/BKG (dl-de/by-2.0); "
           "background © OpenStreetMap contributors. Emission factors: Tiemeyer et al. 2020. "
           "All emission figures are ESTIMATES (area × national emission factors).")


# --- small helpers ----------------------------------------------------------------
def mm():
    try:
        from qgis.core import Qgis  # type: ignore
        return Qgis.LayoutUnit.Millimeters
    except Exception:
        return QgsUnitTypes.LayoutMillimeters


def place(item, x, y, w=None, h=None):
    item.attemptMove(QgsLayoutPoint(x, y, mm()))
    if w is not None:
        item.attemptResize(QgsLayoutSize(w, h, mm()))


def text_label(layout, text, x, y, w, h, size=9, bold=False):
    lab = QgsLayoutItemLabel(layout)
    lab.setText(text)
    font = QFont("Arial")
    font.setBold(bold)
    try:
        fmt = QgsTextFormat()
        fmt.setFont(font)
        fmt.setSize(size)
        lab.setTextFormat(fmt)
    except AttributeError:                      # older QGIS
        font.setPointSizeF(size)
        lab.setFont(font)
    layout.addLayoutItem(lab)
    place(lab, x, y, w, h)
    return lab


def fill(color, outline="0,0,0,0", width="0.1", style="solid"):
    return QgsFillSymbol.createSimple({"color": color, "outline_color": outline,
                                       "outline_width": width, "outline_style": style})


def gpkg_layer(path, layer, name):
    lyr = QgsVectorLayer(f"{path}|layername={layer}", name, "ogr")
    if not lyr.isValid():
        raise RuntimeError(f"Cannot load {layer} from {path} – did the earlier steps run?")
    return lyr


def compact_legend(legend) -> None:
    """Small fonts and symbols - the default legend style is far too big for an
    84 mm column on A4."""
    from qgis.core import QgsLegendStyle  # type: ignore
    sizes = {QgsLegendStyle.Title: (10, True), QgsLegendStyle.Group: (8, True),
             QgsLegendStyle.Subgroup: (8, True), QgsLegendStyle.SymbolLabel: (7.5, False)}
    for style, (size, bold) in sizes.items():
        font = QFont("Arial")
        font.setBold(bold)
        try:                                   # QGIS ≥ 3.30
            fmt = QgsTextFormat()
            fmt.setFont(font)
            fmt.setSize(size)
            legend.rstyle(style).setTextFormat(fmt)
        except AttributeError:
            font.setPointSizeF(size)
            legend.setStyleFont(style, font)
        try:
            legend.rstyle(style).setMargin(QgsLegendStyle.Top, 1.2 if style != QgsLegendStyle.SymbolLabel else 0.6)
        except Exception:
            pass
    legend.setSymbolWidth(6)
    legend.setSymbolHeight(3.5)
    try:
        legend.setBoxSpace(1.5)
    except Exception:
        pass


# --- 1. coverage layer with key figures --------------------------------------------
def build_coverage() -> Path:
    gpkg = cfg.GPKG
    gem = gpd.read_file(gpkg, layer=f"vg250_gem_{LABEL}")
    em = gpd.read_file(gpkg, layer=f"emissions_{LABEL}")
    ags, gen = cfg.FIELDS["vg250_gem_ags"], cfg.FIELDS["vg250_gem_name"]

    stats = em.groupby(ags).agg(farm_peat_ha=("area_ha", "sum"),
                                em_now_t=("em_now_t", "sum"),
                                saving_t=("saving_t", "sum"))
    stats["grass_ha"] = em[em.lu_class == "grassland"].groupby(ags).area_ha.sum()
    stats["crop_ha"] = em[em.lu_class == "cropland"].groupby(ags).area_ha.sum()

    try:   # farmed peat inside the catchments chosen in step 07 (model C)
        cat = gpd.read_file(gpkg, layer=f"optimisation_catchments_{LABEL}")
        chosen = cat[cat.selected == 1][["geometry"]]
        inside = gpd.overlay(em[[ags, "geometry"]], chosen, how="intersection", keep_geom_type=True)
        inside["ha"] = inside.geometry.area / 10_000
        stats["peat_in_chosen_ha"] = inside.groupby(ags).ha.sum()
    except Exception as exc:
        print(f"  (no catchment optimisation layer: {exc})")
        stats["peat_in_chosen_ha"] = 0.0
    stats = stats.fillna(0)

    cov = gem[[ags, gen, "geometry"]].dissolve(by=ags, as_index=False, aggfunc="first")
    cov = cov.merge(stats, on=ags, how="inner")
    cov = cov[cov.farm_peat_ha >= ATLAS_MIN_PEAT_HA].reset_index(drop=True)
    cov["share_chosen"] = (cov.peat_in_chosen_ha / cov.farm_peat_ha * 100).round(0)
    ATLAS_GPKG.parent.mkdir(parents=True, exist_ok=True)
    cov.to_file(ATLAS_GPKG, layer="atlas_gemeinden", driver="GPKG")
    print(f"  coverage: {len(cov)} municipalities with ≥ {ATLAS_MIN_PEAT_HA} ha farmed peat")
    return ATLAS_GPKG


# --- 2. layers and styles ------------------------------------------------------------
def load_layers(cov_path: Path) -> dict:
    root = PROJECT.layerTreeRoot()
    old = root.findGroup(GROUP_NAME)
    if old:
        for lyr_node in old.findLayers():
            PROJECT.removeMapLayer(lyr_node.layerId())
        root.removeChildNode(old)
    group: QgsLayerTreeGroup = root.insertGroup(0, GROUP_NAME)

    gpkg = str(cfg.GPKG)
    L = {
        "cov": gpkg_layer(cov_path, "atlas_gemeinden", "Municipalities (atlas)"),
        "catch": gpkg_layer(gpkg, f"optimisation_catchments_{LABEL}", "Sub-catchments"),
        "peat": gpkg_layer(gpkg, f"emissions_{LABEL}", "Farmed peat"),
        "aoi": gpkg_layer(gpkg, f"aoi_{LABEL}", "Test area"),
    }
    osm = QgsRasterLayer("type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png"
                         "&zmax=19&zmin=0", "OpenStreetMap (grey)", "wms")
    if osm.isValid():
        osm.renderer().setOpacity(0.55)
        try:
            from qgis.core import QgsHueSaturationFilter  # type: ignore
            osm.hueSaturationFilter().setGrayscaleMode(QgsHueSaturationFilter.GrayscaleLuminosity)
        except Exception:
            pass
        L["osm"] = osm

    # chosen catchments: blue; others: thin grey outline
    L["catch"].setRenderer(QgsCategorizedSymbolRenderer("selected", [
        QgsRendererCategory(1, fill("0,114,178,70", "0,114,178,255", "0.6"),
                            "Catchment chosen for rewetting"),
        QgsRendererCategory(0, fill("0,0,0,0", "120,120,120,180", "0.2"),
                            "Other sub-catchment"),
    ]))
    # farmed peat by land use
    L["peat"].setRenderer(QgsCategorizedSymbolRenderer("lu_class", [
        QgsRendererCategory("grassland", fill("153,112,60,150"), "Grassland on peat"),
        QgsRendererCategory("cropland", fill("230,159,0,200"), "Cropland on peat"),
    ]))
    L["aoi"].setRenderer(QgsSingleSymbolRenderer(fill("0,0,0,0", "200,0,0,255", "0.5", "dash")))
    # current atlas municipality: thick outline; others: faint
    rules = QgsRuleBasedRenderer.Rule(None)
    # Rule(symbol, maxScale, minScale, filter, label) - positional for older bindings
    cur = QgsRuleBasedRenderer.Rule(fill("0,0,0,0", "20,20,20,255", "0.9"),
                                    0, 0, "@atlas_featureid = $id", "Municipality")
    oth = QgsRuleBasedRenderer.Rule(fill("255,255,255,90", "90,90,90,160", "0.25"),
                                    0, 0, "ELSE", "Neighbouring municipality")
    rules.appendChild(cur)
    rules.appendChild(oth)
    L["cov"].setRenderer(QgsRuleBasedRenderer(rules))

    for key in ("cov", "aoi", "catch", "peat", "osm"):   # top → bottom
        if key in L:
            PROJECT.addMapLayer(L[key], False)
            group.addLayer(L[key])
    return L


# --- 3. layout ---------------------------------------------------------------------------
def build_layout(L: dict) -> QgsPrintLayout:
    mgr = PROJECT.layoutManager()
    old = mgr.layoutByName(LAYOUT_NAME)
    if old:
        mgr.removeLayout(old)
    layout = QgsPrintLayout(PROJECT)
    layout.initializeDefaults()
    layout.setName(LAYOUT_NAME)
    layout.pageCollection().page(0).setPageSize("A4", QgsLayoutItemPage.Landscape)
    mgr.addLayout(layout)

    stack = [L[k] for k in ("cov", "aoi", "catch", "peat", "osm") if k in L]

    # main map (left) - follows the atlas feature
    main = QgsLayoutItemMap(layout)
    layout.addLayoutItem(main)
    place(main, 8, 8, 190, 180)          # bottom strip (y 191–205) holds the sources
    main.setCrs(L["cov"].crs())
    main.setLayers(stack)
    main.setKeepLayerSet(True)
    main.setFrameEnabled(True)
    # zoomToExtent keeps the frame size; setExtent would resize the frame
    # to the extent's shape
    main.zoomToExtent(L["aoi"].extent())
    main.setAtlasDriven(True)
    main.setAtlasScalingMode(QgsLayoutItemMap.Auto)
    main.setAtlasMargin(0.08)

    # overview map (top right): whole test area; the current municipality is
    # already outlined in black there, so no extra extent frame is drawn
    ov = QgsLayoutItemMap(layout)
    layout.addLayoutItem(ov)
    place(ov, 205, 8, 84, 62)
    ov.setCrs(L["cov"].crs())
    ov.setLayers([L["cov"], L["aoi"]] + ([L["osm"]] if "osm" in L else []))
    ov.setKeepLayerSet(True)
    ov.setFrameEnabled(True)
    e = L["aoi"].extent()
    ov.zoomToExtent(QgsRectangle(e.xMinimum() - 1000, e.yMinimum() - 1000,
                                 e.xMaximum() + 1000, e.yMaximum() + 1000))

    # title + key figures (expressions are evaluated per atlas page)
    text_label(layout, '[% "GEN" %]', 205, 74, 84, 10, size=16, bold=True)
    text_label(layout, "Peatland rewetting – Eider-Treene-Sorge test area", 205, 84, 84, 6, size=8)
    def num(field):   # English thousands separator, e.g. 29,809
        return f"[% format_number(\"{field}\", 0, 'en') %]"

    def chosen_line():
        """Municipalities get a page for their farmed peat, not for the
        optimisation result - so say it plainly when nothing was chosen."""
        target = f"{cfg.OPTIMISATION['target_savings_t']:,}"
        return (
            "[% CASE WHEN \"peat_in_chosen_ha\" < 0.5 "
            f"THEN 'No catchment chosen at the {target} t target' "
            "ELSE 'Farmed peat in chosen catchments: ' "
            "|| format_number(\"peat_in_chosen_ha\", 0, 'en') || ' ha (' "
            "|| format_number(\"share_chosen\", 0, 'en') || ' %)' END %]"
        )

    figures = (
        f"Farmed peat: {num('farm_peat_ha')} ha\n"
        f"   grassland {num('grass_ha')} ha · cropland {num('crop_ha')} ha\n"
        f"Current emissions: ≈ {num('em_now_t')} t CO2-eq/yr\n"
        f"Saving if all rewetted: ≈ {num('saving_t')} t CO2-eq/yr\n"
        + chosen_line()
    )
    text_label(layout, figures, 205, 92, 84, 20, size=8.5)

    # legend
    legend = QgsLayoutItemLegend(layout)
    legend.setTitle("Legend")
    legend.setLinkedMap(main)
    layout.addLayoutItem(legend)
    legend.setAutoUpdateModel(False)
    lroot = legend.model().rootGroup()
    lroot.removeAllChildren()
    for key in ("catch", "peat", "cov", "aoi"):
        lroot.addLayer(L[key])
    compact_legend(legend)
    place(legend, 205, 112)           # directly under the key figures
    legend.adjustBoxSize()

    # scale bar + north arrow
    try:
        sb = QgsLayoutItemScaleBar(layout)
        sb.setStyle("Single Box")
        sb.setLinkedMap(main)
        try:
            from qgis.core import Qgis  # type: ignore
            sb.setUnits(Qgis.DistanceUnit.Kilometers)
        except Exception:
            sb.setUnits(QgsUnitTypes.DistanceKilometers)
        sb.setUnitLabel("km")
        sb.setNumberOfSegments(2)
        sb.setNumberOfSegmentsLeft(0)
        sb.setUnitsPerSegment(1.0)
        try:   # let QGIS pick a round segment length that fits 25–50 mm
            from qgis.core import QgsScaleBarSettings  # type: ignore
            sb.setSegmentSizeMode(QgsScaleBarSettings.SegmentSizeFitWidth)
            sb.setMinimumBarWidth(25)
            sb.setMaximumBarWidth(50)
        except Exception:
            pass
        layout.addLayoutItem(sb)
        place(sb, 12, 176)
    except Exception as exc:
        print(f"  (scale bar skipped: {exc})")
    try:
        arrow = QgsLayoutItemPicture(layout)
        arrow.setPicturePath(":/images/north_arrows/layout_default_north_arrow.svg")
        arrow.setLinkedMap(main)
        layout.addLayoutItem(arrow)
        place(arrow, 186, 12, 9, 12)
    except Exception as exc:
        print(f"  (north arrow skipped: {exc})")

    # sources / disclaimer
    text_label(layout, SOURCES, 8, 191, 281, 14, size=6.5)

    # atlas settings
    atlas = layout.atlas()
    atlas.setCoverageLayer(L["cov"])
    atlas.setHideCoverage(False)
    atlas.setEnabled(True)
    atlas.setPageNameExpression('"GEN"')
    atlas.setFilenameExpression("'gemeinde_' || \"AGS\" || '_' || replace(\"GEN\", ' ', '_')")
    atlas.setSortFeatures(True)
    atlas.setSortExpression('"em_now_t"')
    atlas.setSortAscending(False)            # biggest emitters first
    return layout


# --- 4. export ---------------------------------------------------------------------------
def export(layout: QgsPrintLayout) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf = OUT_DIR / "atlas_gemeinden.pdf"
    settings = QgsLayoutExporter.PdfExportSettings()
    settings.dpi = 150                 # background tiles at 150 dpi: sharp, much smaller file
    settings.simplifyGeometries = True
    res, err = QgsLayoutExporter.exportToPdf(layout.atlas(), str(pdf), settings)
    print(f"  PDF: {pdf}" if res == QgsLayoutExporter.Success else f"  PDF failed: {err}")

    img = QgsLayoutExporter.ImageExportSettings()
    img.dpi = 150
    atlas = layout.atlas()
    atlas.beginRender()
    n = 0
    while atlas.next():
        QgsLayoutExporter(layout).exportToImage(
            str(OUT_DIR / f"{atlas.currentFilename()}.png"), img)
        n += 1
    atlas.endRender()
    print(f"  PNG: {n} pages in {OUT_DIR}")


def run():
    print("09 – atlas")
    cov = build_coverage()
    L = load_layers(cov)
    layout = build_layout(L)
    export(layout)
    print(f"Done. Open Project → Layouts → {LAYOUT_NAME} to edit the layout by hand.")


run()
