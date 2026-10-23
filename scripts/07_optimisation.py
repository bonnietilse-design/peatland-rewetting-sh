"""
07 – Optimisation instead of ranking (integer programmes, SciPy / HiGHS)

Three ways to reach a CO2 saving target, compared in one report:

A) Parcel ranking   take Feldblöcke by saving per ha until the target is met
B) Parcel optimum   binary programme over Feldblöcke:
                        min Σ cost_i·x_i  s.t.  Σ saving_i·x_i ≥ target
C) Catchment optimum  the same, but the units are whole sub-catchments from
                    step 05. Rewetting raises the water level in the whole
                    hydrological unit, so a field in the middle of a drained
                    catchment can't be rewetted on its own. Choosing a
                    catchment means: all its farmed peat stops emitting
                    (saving), and all its farmland gets wetter (cost) -
                    including farmland on MINERAL soil, which is the
                    collateral damage / land-use conflict.

Solver: scipy.optimize.milp (HiGHS, built into SciPy). PuLP was dropped:
PuLP 4.0 changed its API and its CBC solver is an unsigned .exe that
Windows Smart App Control blocks.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.optimize import Bounds, LinearConstraint, milp  # noqa: E402

import config as cfg  # noqa: E402
from peatsh.common import add_area_ha, get_logger, read_layer, write_layer, write_report  # noqa: E402

log = get_logger("07")


def solve(saving: np.ndarray, cost: np.ndarray, target: float):
    """Binary programme: minimise cost·x subject to saving·x ≥ target."""
    n = len(saving)
    return milp(
        c=cost,
        constraints=LinearConstraint(saving.reshape(1, -1), lb=target, ub=np.inf),
        integrality=np.ones(n),          # all variables integer ...
        bounds=Bounds(0, 1),             # ... between 0 and 1 -> binary
        options={"time_limit": 300, "mip_rel_gap": 1e-4},
    )


def greedy(saving: np.ndarray, area: np.ndarray, target: float) -> np.ndarray:
    """Ranking baseline: take units by saving per ha until target reached."""
    order = np.argsort(-(saving / area))
    picked = np.zeros(len(saving), dtype=bool)
    total = 0.0
    for i in order:
        if total >= target:
            break
        picked[i] = True
        total += saving[i]
    return picked


# --- A + B: parcels -------------------------------------------------------------
def parcel_models(em: gpd.GeoDataFrame, target: float) -> tuple[gpd.GeoDataFrame, str]:
    o = cfg.OPTIMISATION
    pid = cfg.FIELDS["parcel_id"]
    parcels = em.dissolve(by=pid, aggfunc={"area_ha": "sum", "saving_t": "sum"}).reset_index()
    parcels = parcels[parcels.area_ha >= o["min_parcel_ha"]].reset_index(drop=True)
    saving, area = parcels.saving_t.to_numpy(), parcels.area_ha.to_numpy()
    cost = area if o["objective"] == "area" else np.ones(len(parcels))
    res = solve(saving, cost, target)
    if res.x is None:
        sys.exit(f"Parcel model: no solution ({res.message})")
    parcels["selected"] = (res.x > 0.5).astype(int)
    parcels["ranked"] = greedy(saving, area, target).astype(int)
    return parcels, res.message


# --- C: catchments ---------------------------------------------------------------
def catchment_table(em: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Per sub-catchment: saving from its farmed peat, and its farmland."""
    rew = cfg.EMISSION_FACTORS["rewetted"]["mean"]
    basins = read_layer("subbasins")
    if "complete" not in basins:
        basins["complete"] = 1
    b = basins[["basin_id", "geometry"]]

    # farmed peat inside each catchment -> saving
    peat = gpd.overlay(em[["lu_class", "ef_now", "geometry"]], b,
                       how="intersection", keep_geom_type=True)
    peat = add_area_ha(peat)
    peat["saving_t"] = peat.area_ha * (peat.ef_now - rew)
    per_peat = peat.groupby("basin_id").agg(peat_farm_ha=("area_ha", "sum"),
                                            saving_t=("saving_t", "sum"))

    # all farmland (Feldblöcke) inside each catchment -> what gets wetter
    fb = read_layer("feldbloecke")[["geometry"]]
    farm = add_area_ha(gpd.overlay(fb, b, how="intersection", keep_geom_type=True))
    per_farm = farm.groupby("basin_id").agg(farmland_ha=("area_ha", "sum"))

    t = basins.merge(per_peat, on="basin_id", how="left").merge(per_farm, on="basin_id", how="left")
    t[["peat_farm_ha", "saving_t", "farmland_ha"]] = (
        t[["peat_farm_ha", "saving_t", "farmland_ha"]].fillna(0))
    t["non_peat_farm_ha"] = (t.farmland_ha - t.peat_farm_ha).clip(lower=0)
    return t   # ALL catchments; candidates are filtered in main()


def catchment_model(t: gpd.GeoDataFrame, target: float) -> tuple[gpd.GeoDataFrame, str]:
    obj = cfg.OPTIMISATION["catchment_objective"]
    if obj == "non_peat_farmland":
        # tiny tie-break on total farmland, so catchments without mineral-soil
        # farmland are not picked beyond what the target needs
        cost = t.non_peat_farm_ha.to_numpy() + 1e-3 * t.farmland_ha.to_numpy()
    elif obj == "affected_farmland":
        cost = t.farmland_ha.to_numpy()
    else:
        cost = np.ones(len(t))
    res = solve(t.saving_t.to_numpy(), cost, target)
    if res.x is None:
        sys.exit(f"Catchment model: no solution ({res.message}). Lower the target "
                 f"or set only_complete_catchments = False.")
    t["selected"] = (res.x > 0.5).astype(int)
    return t, res.message


def main() -> None:
    o = cfg.OPTIMISATION
    target = o["target_savings_t"]
    em = read_layer("emissions")
    if em.saving_t.sum() < target:
        sys.exit(f"Target {target:,} t unreachable (max {em.saving_t.sum():,.0f} t).")

    log.info("parcel models ...")
    parcels, msg_p = parcel_models(em, target)
    write_layer(parcels, "optimisation")
    sel, rnk = parcels[parcels.selected == 1], parcels[parcels.ranked == 1]

    # how much mineral-soil farmland would the parcel solutions wet in reality?
    # (all farmland in every catchment that contains a selected parcel)
    lines_c, t = [], None
    try:
        log.info("catchment model ...")
        allb = catchment_table(em)
        cand = allb[allb.saving_t > 0]
        if o["only_complete_catchments"]:
            cand = cand[cand.complete == 1]
        t, msg_c = catchment_model(cand.reset_index(drop=True), target)
        write_layer(t, "optimisation_catchments")
        cs = t[t.selected == 1]

        def implied(chosen: gpd.GeoDataFrame) -> tuple[int, float, float]:
            """Catchments (complete or not) containing a chosen parcel.
            Each parcel is assigned by a point inside it, so a parcel that just
            touches a catchment boundary doesn't count for both catchments."""
            pts = chosen[["geometry"]].copy()
            pts["geometry"] = pts.geometry.representative_point()
            hit = gpd.sjoin(allb[["basin_id", "farmland_ha", "non_peat_farm_ha", "geometry"]],
                            pts, predicate="contains", how="inner")
            hit = hit.drop_duplicates("basin_id")
            return len(hit), hit.farmland_ha.sum(), hit.non_peat_farm_ha.sum()

        n_s, f_s, m_s = implied(sel)
        n_r, f_r, m_r = implied(rnk)
        lines_c = [
            "### C) Catchment optimum", "",
            f"- solver: {msg_c}",
            f"- objective: minimise **{o['catchment_objective']}**; "
            f"only complete catchments: {o['only_complete_catchments']}",
            f"- candidate sub-catchments with farmed peat: {len(t)}", "",
            "### Comparison", "",
            "| approach | units | farmed peat rewetted ha | saving t/yr | "
            "catchments touched | all farmland wetted ha | of it on mineral soil ha |",
            "|---|---|---|---|---|---|---|",
            f"| A) parcel ranking | {len(rnk):,} parcels | {rnk.area_ha.sum():,.0f} | "
            f"{rnk.saving_t.sum():,.0f} | {n_r} | {f_r:,.0f}* | {m_r:,.0f}* |",
            f"| B) parcel optimum | {len(sel):,} parcels | {sel.area_ha.sum():,.0f} | "
            f"{sel.saving_t.sum():,.0f} | {n_s} | {f_s:,.0f}* | {m_s:,.0f}* |",
            f"| C) catchment optimum | {len(cs)} catchments | {cs.peat_farm_ha.sum():,.0f} | "
            f"{cs.saving_t.sum():,.0f} | {len(cs)} | {cs.farmland_ha.sum():,.0f} | "
            f"{cs.non_peat_farm_ha.sum():,.0f} |", "",
            "\\* if the water level is raised in every catchment that contains a",
            "selected parcel - which is what rewetting physically does. The parcel",
            "models ignore this and look cheaper than they are; their savings",
            "would also be higher, since all peat in those catchments gets wet.", "",
            "Reading: the parcel models scatter their picks over many catchments.",
            "The catchment model concentrates rewetting in few hydrological units",
            "that are mostly peat, so far less farmland on mineral soil gets wet.",
        ]
    except Exception as exc:   # no step-05 layer yet, or overlay problem
        log.warning("catchment model skipped: %s", exc)
        lines_c = ["### C) Catchment optimum", "",
                   f"- skipped: {exc} (run step 05 first)"]

    write_report("07_optimisation", "Parcels vs. catchments for a CO2 target", [
        f"- target: **{target:,} t CO2-eq/yr**; solver SciPy milp (HiGHS)", "",
        "### A) Parcel ranking / B) parcel optimum", "",
        f"- parcel model: {msg_p}; objective minimise {o['objective']}",
        f"- candidate parcels (≥ {o['min_parcel_ha']} ha on organic soil): {len(parcels):,}",
        f"- B selects {len(sel):,} parcels / {sel.area_ha.sum():,.0f} ha; "
        f"A selects {len(rnk):,} / {rnk.area_ha.sum():,.0f} ha", "",
        *lines_c, "",
        "All savings are ESTIMATES (area × national emission factors).",
    ])
    log.info("done")


if __name__ == "__main__":
    main()
