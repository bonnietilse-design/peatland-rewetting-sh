"""
06 – Historical wet land 1878–80 vs. today's organic soils

Manual part (QGIS):
  - Wet signatures digitised by hand from the Preußische Landesaufnahme
    1878–80 (WMS Chronologen, LVermGeo SH, CC BY 4.0) into
    data/raw/historical/peat_1880_digitised.gpkg, layer peat_1880,
    field hist_type = Moor | nasser Boden | nasse Wiese | Heide
    (legend: docs/digitising_legend.png, rules: docs/historical_peat_digitising_rules.xlsx).
  - The area that was actually checked: digitised_extent.gpkg.

This script
  1. checks the classes and turns the free-text evidence into codes,
  2. clips everything to digitised_extent ∩ AOI,
  3. closes narrow gaps (roads, ditches) between neighbouring polygons,
  4. compares with today's organic soils (Thünen):
       kept        wet in 1880 and organic soil today
       lost        wet in 1880, no organic soil today
       only_today  organic soil today, no wet signature in 1880 –
                   a difference in mapping concept (e.g. drained fen shown as
                   pasture or dry meadow in 1880), NOT new peat
  5. flags differences within the edge tolerance as possible position error.

    python scripts\\06_historical_loss.py        hand digitising, digitised_extent
    python scripts\\06_historical_loss.py yolo   automated layer yolo_1880_aoi (step 06c aoi),
                                               whole test area; outputs named *_yolo
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geopandas as gpd  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

import config as cfg  # noqa: E402
from peatsh.common import (add_area_ha, get_logger, load_aoi, read_layer,  # noqa: E402
                           write_layer, write_report)

log = get_logger("06")
H = cfg.HISTORICAL
CLASSES = list(H["classes"])          # order = priority for gap filling
SOURCE = "yolo" if "yolo" in sys.argv[1:] else "hand"
SFX = "_yolo" if SOURCE == "yolo" else ""
HEIDE_HA = 0.0


# ---------------------------------------------------------------------------
# 1  read + check
# ---------------------------------------------------------------------------
def read_hist() -> gpd.GeoDataFrame:
    if SOURCE == "yolo":
        try:
            gdf = read_layer("yolo_1880_aoi")
        except Exception:
            sys.exit("Missing layer yolo_1880_aoi – run 06c_detections_to_polygons.py aoi first.")
        # Automated "Heide" = tufts on open ground away from any moor, i.e. mostly
        # heath on the dry geest - no evidence of peat. (Heath inside a moor was
        # already turned into Moor by step 06c.) It is reported, not compared.
        global HEIDE_HA
        HEIDE_HA = gdf.loc[gdf.hist_type == "Heide"].area.sum() / 1e4
        gdf = gdf[gdf.hist_type != "Heide"].copy()
        gdf["evidence_codes"], gdf["single_torfstich"] = "", False
        gdf["geometry"] = gdf.geometry.make_valid()
        return gdf
    path = cfg.INPUTS["historical_peat"]
    if not path.exists():
        sys.exit(f"Missing {path} – digitise the 1880 map first (see docstring).")
    gdf = gpd.read_file(path, layer=H["layer"], fid_as_index=True)   # index = QGIS fid
    # field names typed in QGIS may carry stray spaces ("evidence ")
    gdf = gdf.rename(columns={c: c.strip() for c in gdf.columns if c != gdf.geometry.name})
    if gdf.crs is None or gdf.crs.to_epsg() != 25832:
        gdf = gdf.set_crs(cfg.TARGET_CRS) if gdf.crs is None else gdf.to_crs(cfg.TARGET_CRS)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()

    bad = gdf[~gdf["hist_type"].isin(CLASSES)]
    if len(bad):
        rows = ", ".join(f"fid {i}: {v!r}" for i, v in zip(bad.index, bad["hist_type"]))
        sys.exit(f"Unknown or empty hist_type – fix in QGIS: {rows}\n"
                 f"Allowed: {CLASSES}")
    codes = gdf.apply(evidence_codes, axis=1)
    gdf["evidence_codes"] = codes["evidence_codes"].to_numpy()
    gdf["single_torfstich"] = codes["single_torfstich"].to_numpy()
    gdf["geometry"] = gdf.geometry.make_valid()
    return gdf


def evidence_codes(row: pd.Series) -> pd.Series:
    """Free text in evidence/note -> codes bruch, torfstich, name (+ single flag)."""
    text = " ".join(str(row.get(c) or "") for c in ("evidence", "note")).lower()
    single = bool(re.search(r"\b(one|single|einzeln\w*)\s+torfstich", text))
    codes = []
    if "bruch" in text or ("tuft" in text and "dash" in text):
        codes.append("bruch")
    if "torfstich" in text and not single:
        codes.append("torfstich")
    if re.search(r"\bname\b", text):
        codes.append("name")
    return pd.Series({"evidence_codes": ", ".join(codes), "single_torfstich": single})


# ---------------------------------------------------------------------------
# 2  extent + 3 gap closing
# ---------------------------------------------------------------------------
def study_extent(aoi: gpd.GeoDataFrame):
    if SOURCE == "yolo":                         # the automated layer covers the whole AOI
        return aoi.geometry.iloc[0]
    path = cfg.INPUTS["historical_extent"]
    if not path.exists():
        sys.exit(f"Missing {path} – draw the area you checked on the 1880 map.")
    ext = gpd.read_file(path, layer=H["extent_layer"]).to_crs(cfg.TARGET_CRS)
    return unary_union(ext.geometry.make_valid()).intersection(aoi.geometry.iloc[0])


def close_gaps(by_class: dict, extent) -> tuple[dict, float]:
    """Fill gaps < gap_close_m between polygons; give each piece to a neighbour."""
    d = H["gap_close_m"] / 2
    union = unary_union(list(by_class.values()))
    closed = (union.buffer(d, join_style="mitre", mitre_limit=2.0)
                   .buffer(-d, join_style="mitre", mitre_limit=2.0))
    fill = closed.difference(union).intersection(extent)
    filled = 0.0
    out = dict(by_class)
    for cls in CLASSES:                          # priority order
        if cls not in out or fill.is_empty:
            continue
        part = fill.intersection(out[cls].buffer(d * 1.05))
        if part.is_empty:
            continue
        out[cls] = out[cls].union(part)
        fill = fill.difference(part)
        filled += part.area
    return out, filled / 10_000


def to_gdf(geoms: dict, col: str) -> gpd.GeoDataFrame:
    gdf = gpd.GeoDataFrame({col: list(geoms)}, geometry=list(geoms.values()),
                           crs=cfg.TARGET_CRS)
    gdf = gdf.explode(index_parts=False)
    return add_area_ha(gdf[gdf.geom_type == "Polygon"].reset_index(drop=True))


# ---------------------------------------------------------------------------
# 4  comparison
# ---------------------------------------------------------------------------
def main() -> None:
    aoi = load_aoi()
    extent = study_extent(aoi)
    ext_ha = extent.area / 10_000

    hist = read_hist()
    n_poly = len(hist)
    raw_ha = hist.area.sum() / 10_000
    n_single = int(hist.single_torfstich.sum())
    no_code = (hist[(hist.hist_type == "Moor") & (hist.evidence_codes == "")]
               if SOURCE == "hand" else hist.iloc[0:0])

    # clip to extent, dissolve per class
    hist["geometry"] = hist.geometry.intersection(extent)
    hist = hist[~hist.geometry.is_empty]
    by_class = {c: unary_union(hist.loc[hist.hist_type == c, "geometry"])
                for c in CLASSES if (hist.hist_type == c).any()}
    by_class, gap_ha = close_gaps(by_class, extent)
    hist_cls = to_gdf(by_class, "hist_type")
    hist_cls["peat_1880"] = hist_cls.hist_type.map(H["classes"])
    write_layer(hist_cls, "hist_1880" + SFX)

    # today's organic soils inside the extent
    soil_col, soil_lab = cfg.FIELDS["soil_type"], cfg.FIELDS["soil_type_label"]
    today = read_layer("organic_soils")
    today = today[[soil_col, soil_lab, "geometry"]].copy()
    today["geometry"] = today.geometry.make_valid().intersection(extent)
    today = today[~today.geometry.is_empty]
    today_union = unary_union(today.geometry)
    hist_union = unary_union(hist_cls.geometry)

    kept = gpd.overlay(hist_cls[["hist_type", "geometry"]],
                       today[[soil_col, "geometry"]], how="intersection",
                       keep_geom_type=True)
    kept["category"] = "kept"
    lost = gpd.overlay(hist_cls[["hist_type", "geometry"]],
                       gpd.GeoDataFrame(geometry=[today_union], crs=cfg.TARGET_CRS),
                       how="difference", keep_geom_type=True)
    lost["category"], lost[soil_col] = "lost", None
    only = gpd.overlay(today[[soil_col, "geometry"]],
                       gpd.GeoDataFrame(geometry=[hist_union], crs=cfg.TARGET_CRS),
                       how="difference", keep_geom_type=True)
    only["category"], only["hist_type"] = "only_today", None

    comp = add_area_ha(gpd.GeoDataFrame(
        pd.concat([kept, lost, only], ignore_index=True), crs=cfg.TARGET_CRS))
    comp = comp.rename(columns={soil_col: "today_type"})
    write_layer(comp, "hist_compare" + SFX)

    # 5  edge tolerance: how much of the difference could be position error?
    tol = H["edge_tolerance_m"]
    lost_u = unary_union(lost.geometry) if len(lost) else None
    only_u = unary_union(only.geometry) if len(only) else None
    lost_edge = (lost_u.intersection(today_union.buffer(tol)).area / 1e4) if lost_u else 0
    only_edge = (only_u.intersection(hist_union.buffer(tol)).area / 1e4) if only_u else 0

    # tables
    k_ha, l_ha, o_ha = (comp.loc[comp.category == c, "area_ha"].sum()
                        for c in ("kept", "lost", "only_today"))
    h_ha, t_ha = hist_cls.area_ha.sum(), today_union.area / 1e4

    per_class = (comp[comp.category != "only_today"]
                 .pivot_table(index="hist_type", columns="category",
                              values="area_ha", aggfunc="sum", fill_value=0)
                 .reindex(CLASSES).dropna(how="all").fillna(0))
    for c in ("kept", "lost"):
        if c not in per_class:
            per_class[c] = 0.0
    per_class["total"] = per_class.kept + per_class.lost
    per_class["kept_%"] = 100 * per_class.kept / per_class.total
    per_class = per_class[["total", "kept", "lost", "kept_%"]]

    labels = today.groupby(soil_col)[soil_lab].first()
    cross = (comp[comp.category == "kept"]
             .pivot_table(index="hist_type", columns="today_type", values="area_ha",
                          aggfunc="sum", fill_value=0).reindex(CLASSES).dropna(how="all"))
    only_by = (comp[comp.category == "only_today"].groupby("today_type").area_ha.sum()
               .sort_values(ascending=False))
    cross.to_csv(cfg.OUTPUTS / f"06_hist_x_today{SFX}_{cfg.aoi_label()}.csv")
    per_class.to_csv(cfg.OUTPUTS / f"06_hist_per_class{SFX}_{cfg.aoi_label()}.csv")

    plot_map(comp, extent)

    src_lines = ([f"- source: **hand digitising**, area checked (digitised_extent ∩ AOI): **{ext_ha:,.0f} ha**",
                  f"- polygons digitised: {n_poly} ({raw_ha:,.0f} ha before clipping)"]
                 if SOURCE == "hand" else
                 [f"- source: **automated reading (YOLO + rules, step 06c aoi)**, whole test area: "
                  f"**{ext_ha:,.0f} ha**",
                  "- in the hand-digitised block the automation agrees with the hand digitising on "
                  "~90 % of the area; outside it there is no reference (see report 06c_yolo_aoi)",
                  f"- automated Heide ({HEIDE_HA:,.0f} ha) is left out: heath away from any moor is "
                  "mostly dry geest heath, not evidence of peat"])
    write_report("06_historical" + SFX, "Wet land 1878–80 vs. organic soils today"
                 + (" – automated, whole test area" if SOURCE == "yolo" else ""), [
        "> Compares map *signatures* of 1878–80 with today's *soil* map. The two "
        "use different concepts, so differences are not simply gains or losses.", "",
        *src_lines,
        f"- gaps ≤ {H['gap_close_m']} m closed (roads, ditches): {gap_ha:,.1f} ha added",
        f"- wet signatures 1880: **{h_ha:,.0f} ha** ({h_ha / ext_ha:.0%} of the extent)",
        f"- organic soils today: **{t_ha:,.0f} ha** ({t_ha / ext_ha:.0%})", "",
        "| category | ha | meaning |", "|---|---:|---|",
        f"| kept | {k_ha:,.0f} | wet in 1880, organic soil today |",
        f"| lost | {l_ha:,.0f} | wet in 1880, no organic soil today |",
        f"| only_today | {o_ha:,.0f} | organic today, no wet signature in 1880 "
        "(mapping concept – e.g. drained fen used as pasture) |", "",
        f"Within ±{tol} m of the other layer's boundary (possible position error): "
        f"lost {lost_edge:,.0f} ha ({lost_edge / l_ha:.0%} of lost), "
        f"only_today {only_edge:,.0f} ha ({only_edge / o_ha:.0%} of only_today)."
        if l_ha and o_ha else "", "",
        "### Per 1880 class", "", per_class.round(1).to_markdown(), "",
        "Peat evidence per class: " + ", ".join(f"{k} = {v}" for k, v in H["classes"].items()), "",
        "### 1880 class × today's soil type (kept area, ha)", "",
        cross.round(0).to_markdown(), "",
        "### Organic soil today without a wet signature in 1880 (ha)", "",
        only_by.round(0).rename(index=lambda c: f"{c} – {labels.get(c, '')}").to_markdown(), "",
        "### Notes", "",
        f"- single Torfstich noted (class not changed): {n_single} polygon(s)",
        f"- Moor polygons without a recognised evidence code: {len(no_code)}"
        + (f" (fid {', '.join(map(str, no_code.index))})" if len(no_code) else ""),
        "- Legend: Zeichen-Erklärung für die Messtischblätter 1:25 000 (1898); "
        "map © GeoBasis-DE/LVermGeo SH/CC BY 4.0; soils: Thünen (CC BY 4.0).",
        "- Caveats: hand digitising at ~1:2,500–1:5,000; positional accuracy of the "
        "1880 survey; the 1898 key is ~20 years younger than the sheets; "
        "Hutung/trockene Wiese were not digitised although some lie on fen.",
    ])
    log.info("kept %.0f ha, lost %.0f ha, only_today %.0f ha", k_ha, l_ha, o_ha)


def plot_map(comp: gpd.GeoDataFrame, extent) -> None:
    colours = {"kept": "#1b7837", "lost": "#d6604d", "only_today": "#9ecae1"}
    fig, ax = plt.subplots(figsize=(8, 8), dpi=150)
    for cat, col in colours.items():
        sub = comp[comp.category == cat]
        if len(sub):
            sub.plot(ax=ax, color=col, linewidth=0)
    gpd.GeoSeries([extent], crs=cfg.TARGET_CRS).boundary.plot(ax=ax, color="k", linewidth=1)
    ax.legend(handles=[
        Patch(color=colours["kept"], label="kept – wet 1880, organic soil today"),
        Patch(color=colours["lost"], label="lost – wet 1880, no organic soil today"),
        Patch(color=colours["only_today"], label="only today – mapping-concept difference")],
        loc="lower left", fontsize=7, framealpha=0.95)
    ax.set_title("Wet land 1878–80 vs. organic soils today"
                 + ("\n(1880 layer read automatically – YOLO + rules)" if SOURCE == "yolo" else ""),
                 fontsize=10)
    ax.set_axis_off()
    fig.text(0.01, 0.01, "1880 map © GeoBasis-DE/LVermGeo SH/CC BY 4.0 · soils: Thünen (CC BY 4.0)",
             fontsize=6, color="#555")
    out = cfg.OUTPUTS / f"06_historical{SFX}_{cfg.aoi_label()}.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
