"""
07b – The 1878–80 map per sub-catchment: were the chosen catchments wet in 1880?

Links the historical comparison (step 06, automated YOLO layer for the whole
test area) to the rewetting question (step 07):

  1. per sub-catchment (step 05): how much was wet in 1880 (Moor + nasse
     Wiese), how much was Moor, how much of today's organic soil is
     Moorfolgeboden (MF – peat largely gone), and how much of the farmed peat
     was already wet in 1880
  2. compare the sub-catchments chosen in step 07 with the other candidates
  3. sensitivity: re-run the step-07 catchment model with a penalty for
     farmed peat that was NOT wet in 1880 (weights in HISTORY_WEIGHTS), and
     see how much the choice changes

Run in the OSGeo4W Shell after steps 05, 06 yolo and 07:
    python scripts\\07b_history_per_catchment.py

Writes  layer catchments_history (project GeoPackage) – every sub-catchment
        with its 1880 figures and the selections; CSV and PNG in outputs/;
        report docs/reports/07b_history_per_catchment_<aoi>.md
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import geopandas as gpd  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

import config as cfg  # noqa: E402
from peatsh.common import add_area_ha, get_logger, read_layer, write_layer, write_report  # noqa: E402

log = get_logger("07b")
# ha of farmed peat that was NOT wet in 1880 counted as this many ha of
# "conflict" (like farmland on mineral soil). 0 = step 07 as it is.
HISTORY_WEIGHTS = (0.25, 0.5, 1.0)
HIST_LAYER = "hist_compare_yolo"     # step 06 yolo: kept / lost / only_today


def load_step07():
    """Import 07_optimisation.py (file name starts with a digit) for solve()."""
    spec = importlib.util.spec_from_file_location("opt07", ROOT / "scripts" / "07_optimisation.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def per_basin(parts: gpd.GeoDataFrame, basins: gpd.GeoDataFrame, by: str) -> pd.DataFrame:
    """Area (ha) of `parts` per basin_id, split by column `by`."""
    x = add_area_ha(gpd.overlay(parts, basins[["basin_id", "geometry"]],
                                how="intersection", keep_geom_type=True))
    return x.pivot_table(index="basin_id", columns=by, values="area_ha",
                         aggfunc="sum", fill_value=0)


def share(a: float, b: float) -> str:
    return f"{a / b:.0%}" if b else "–"


def main() -> None:
    basins = read_layer("subbasins")
    try:
        comp = read_layer(HIST_LAYER)
    except Exception:
        sys.exit(f"Layer {HIST_LAYER} missing – run  python scripts\\06_historical_loss.py yolo  first.")
    try:
        opt = read_layer("optimisation_catchments")
    except Exception:
        sys.exit("Layer optimisation_catchments missing – run step 07 first.")
    em = read_layer("emissions")
    rew = cfg.EMISSION_FACTORS["rewetted"]["mean"]

    # 1  1880 and today per sub-catchment ---------------------------------------
    log.info("1880 comparison per sub-catchment ...")
    comp = comp[["category", "hist_type", "today_type", "geometry"]].copy()
    comp["hist_type"] = comp.hist_type.fillna("")
    comp["today_type"] = comp.today_type.fillna("")
    comp["key"] = np.select(
        [comp.category.isin(["kept", "lost"]) & (comp.hist_type == "Moor"),
         comp.category.isin(["kept", "lost"])],
        ["wet_moor", "wet_other"], "not_wet")
    wet = per_basin(comp[comp.key != "not_wet"][["key", "geometry"]], basins, "key")
    org = comp[comp.category.isin(["kept", "only_today"])].copy()
    org["mf"] = np.where(org.today_type == "MF", "mf", "other_org")
    mf = per_basin(org[["mf", "geometry"]], basins, "mf")

    # farmed peat (step 04) and the part of it that was wet in 1880
    log.info("farmed peat wet in 1880 ...")
    wet_union = unary_union(comp.loc[comp.key != "not_wet", "geometry"])
    fp = em[["ef_now", "geometry"]].copy()
    fp["w1880"] = "no"
    fp_wet = fp.copy()
    fp_wet["geometry"] = fp_wet.geometry.intersection(wet_union)
    fp_wet = fp_wet[~fp_wet.geometry.is_empty]
    fp_wet["w1880"] = "yes"
    fpw = per_basin(fp_wet[["w1880", "geometry"]], basins, "w1880")

    t = basins[["basin_id", "area_ha", "peat_ha", "complete", "geometry"]].copy()
    t = t.merge(wet, on="basin_id", how="left").merge(mf, on="basin_id", how="left")
    t = t.merge(fpw, on="basin_id", how="left")
    for c in ("wet_moor", "wet_other", "mf", "other_org", "yes"):
        if c not in t:
            t[c] = 0.0
    t = t.fillna({"wet_moor": 0, "wet_other": 0, "mf": 0, "other_org": 0, "yes": 0})
    t["wet1880_ha"] = t.wet_moor + t.wet_other
    t["moor1880_ha"] = t.wet_moor
    t["mf_ha"] = t.mf
    t["fpeat_wet1880_ha"] = t.yes
    t["wet1880_share"] = t.wet1880_ha / t.area_ha
    t = t.drop(columns=["wet_moor", "wet_other", "mf", "other_org", "yes"])

    o = opt[["basin_id", "peat_farm_ha", "saving_t", "farmland_ha", "non_peat_farm_ha", "selected"]]
    t = t.merge(o, on="basin_id", how="left")
    t["candidate"] = t.selected.notna().astype(int)
    t["selected"] = t.selected.fillna(0).astype(int)
    for c in ("peat_farm_ha", "saving_t", "farmland_ha", "non_peat_farm_ha"):
        t[c] = t[c].fillna(0)
    t["fpeat_wet1880_ha"] = np.minimum(t.fpeat_wet1880_ha, t.peat_farm_ha)

    # 2  chosen vs. other candidates ---------------------------------------------
    def summary(name: str, g: pd.DataFrame) -> str:
        return (f"| {name} | {len(g)} | {g.area_ha.sum():,.0f} | "
                f"{share(g.wet1880_ha.sum(), g.area_ha.sum())} | "
                f"{share(g.moor1880_ha.sum(), g.area_ha.sum())} | "
                f"{share(g.fpeat_wet1880_ha.sum(), g.peat_farm_ha.sum())} | "
                f"{share(g.mf_ha.sum(), g.peat_ha.sum())} |")

    cand = t[t.candidate == 1]
    chosen, others = cand[cand.selected == 1], cand[cand.selected == 0]
    complete = t[t.complete == 1]

    # 3  sensitivity: penalise farmed peat that was not wet in 1880 ---------------
    log.info("sensitivity runs ...")
    m07 = load_step07()
    target = cfg.OPTIMISATION["target_savings_t"]
    cc = cand.reset_index(drop=True)
    base_cost = cc.non_peat_farm_ha.to_numpy() + 1e-3 * cc.farmland_ha.to_numpy()
    not_wet = (cc.peat_farm_ha - cc.fpeat_wet1880_ha).clip(lower=0).to_numpy()
    base_ids = set(cc.loc[cc.selected == 1, "basin_id"])
    rows = [f"| 0 (step 07) | {len(base_ids)} | – | {chosen.saving_t.sum():,.0f} | "
            f"{chosen.non_peat_farm_ha.sum():,.0f} | "
            f"{share(chosen.fpeat_wet1880_ha.sum(), chosen.peat_farm_ha.sum())} |"]
    t["sel_hist"] = 0
    for w in HISTORY_WEIGHTS:
        res = m07.solve(cc.saving_t.to_numpy(), base_cost + w * not_wet, target)
        if res.x is None:
            rows.append(f"| {w:g} | no solution | | | | |")
            continue
        pick = cc[res.x > 0.5]
        ids = set(pick.basin_id)
        same = len(ids & base_ids)
        rows.append(f"| {w:g} | {len(ids)} | {same} of {len(base_ids)} | {pick.saving_t.sum():,.0f} | "
                    f"{pick.non_peat_farm_ha.sum():,.0f} | "
                    f"{share(pick.fpeat_wet1880_ha.sum(), pick.peat_farm_ha.sum())} |")
        if w == 0.5:
            t.loc[t.basin_id.isin(ids), "sel_hist"] = 1

    # outputs ----------------------------------------------------------------------
    write_layer(t, "catchments_history")
    t.drop(columns="geometry").round(3).to_csv(
        cfg.OUTPUTS / f"07b_history_per_catchment_{cfg.aoi_label()}.csv", index=False)
    plot(t)

    write_report("07b_history_per_catchment",
                 "The 1878–80 map per sub-catchment", [
        "- 1880 layer: automated reading of the whole test area (YOLO + rules, step 06 yolo); "
        "wet = Moor + nasse Wiese (Heide left out, as in step 06)",
        f"- sub-catchments: step 05 ({len(t)}, {len(complete)} complete); "
        f"candidates and selection: step 07 ({len(cand)} candidates, {len(chosen)} chosen, "
        f"target {target:,} t CO2-eq/yr)", "",
        "### Chosen catchments vs. the rest", "",
        "| group | catchments | area ha | wet in 1880 | of it Moor | farmed peat wet in 1880 "
        "| Moorfolgeboden (of organic soil today) |",
        "|---|---:|---:|---:|---:|---:|---:|",
        summary("chosen in step 07", chosen),
        summary("other candidates", others),
        summary("all complete sub-catchments", complete), "",
        "Shares are area-weighted (sum over the group).", "",
        "### Sensitivity: prefer land that was wet in 1880", "",
        "Step 07 is re-run with an extra cost: each ha of farmed peat that was **not** wet "
        "in 1880 counts as *w* ha of farmland on mineral soil. The weight is a choice, not a "
        "measured value – the table shows how much the selection depends on it.", "",
        "| weight w | catchments | same as step 07 | saving t/yr | farmland on mineral soil ha "
        "| farmed peat wet in 1880 |",
        "|---|---:|---:|---:|---:|---:|",
        *rows, "",
        f"Map: `outputs/07b_history_per_catchment_{cfg.aoi_label()}.png`; "
        "layer `catchments_history` (fields wet1880_ha, moor1880_ha, mf_ha, fpeat_wet1880_ha, "
        "selected = step 07, sel_hist = weight 0.5).", "",
        "Caveats: the 1880 layer is an automated reading (overall accuracy 90 % ± 6 %, "
        "report 06v); nasse Wiese is over-mapped by roughly a sixth. 'Wet in 1880' "
        "describes map signatures, not measured water levels. Savings are ESTIMATES.",
    ])
    log.info("done: %d chosen catchments, %s of their area wet in 1880", len(chosen),
             share(chosen.wet1880_ha.sum(), chosen.area_ha.sum()))


def plot(t: gpd.GeoDataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 8), dpi=150)
    t.plot(ax=ax, column="wet1880_share", cmap="Blues", vmin=0, vmax=1,
           edgecolor="#bbbbbb", linewidth=0.2, legend=True,
           legend_kwds={"label": "share of sub-catchment wet in 1880", "shrink": 0.6})
    t[t.selected == 1].boundary.plot(ax=ax, color="#d6604d", linewidth=1.0)
    t[(t.sel_hist == 1) & (t.selected == 0)].boundary.plot(ax=ax, color="#1b7837", linewidth=1.0,
                                                           linestyle="--")
    ax.legend(handles=[Patch(facecolor="none", edgecolor="#d6604d", label="chosen in step 07"),
                       Patch(facecolor="none", edgecolor="#1b7837", linestyle="--",
                             label="added when 1880 wetness counts (w = 0.5)")],
              loc="lower left", fontsize=7, framealpha=0.95)
    ax.set_title("Sub-catchments: wet in 1878–80 and chosen for rewetting", fontsize=10)
    ax.set_axis_off()
    fig.text(0.01, 0.01, "1880 map © GeoBasis-DE/LVermGeo SH/CC BY 4.0 · DGM1 © GeoBasis-DE/LVermGeo SH/"
             "CC BY 4.0 · soils: Thünen (CC BY 4.0)", fontsize=6, color="#555")
    fig.savefig(cfg.OUTPUTS / f"07b_history_per_catchment_{cfg.aoi_label()}.png", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
