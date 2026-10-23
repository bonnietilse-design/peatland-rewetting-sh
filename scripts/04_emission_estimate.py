"""
04 – Rough emission estimate
emissions = area × emission factor per land-use class.
Stops if the factors in config.EMISSION_FACTORS have no cited values yet.
Result is an ESTIMATE – labelled as such in every output.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config as cfg  # noqa: E402
from peatsh.common import ef_ready, get_logger, read_layer, write_layer, write_report  # noqa: E402

log = get_logger("04")


def main() -> None:
    if not ef_ready("cropland", "grassland", "rewetted"):
        sys.exit("Emission factors missing in config.py – add cited values first.")
    ef = cfg.EMISSION_FACTORS
    ov = read_layer("overlay_soil_landuse")
    ov["ef_now"] = ov["lu_class"].map(lambda c: ef[c]["mean"])
    ov["em_now_t"] = ov.area_ha * ov.ef_now
    ov["saving_t"] = ov.area_ha * (ov.ef_now - ef["rewetted"]["mean"])
    write_layer(ov, "emissions")

    name = cfg.FIELDS["vg250_gem_name"]
    per_gem = ov.groupby(name)[["area_ha", "em_now_t", "saving_t"]].sum()
    per_gem = per_gem.sort_values("em_now_t", ascending=False)
    per_gem.to_csv(cfg.OUTPUTS / f"04_emissions_per_municipality_{cfg.aoi_label()}.csv")

    write_report("04_emissions", "Emission estimate (ESTIMATE)", [
        "> Area × emission factor. Ignores water level, peat thickness and",
        "> management within a class. Order of magnitude only.", "",
        f"- current emissions: **{ov.em_now_t.sum():,.0f} t CO2-eq/yr**",
        f"- potential saving if all rewetted: {ov.saving_t.sum():,.0f} t CO2-eq/yr", "",
        "Emission factors used:",
        *[f"- {k}: {v['mean']} t CO2-eq/ha/yr – {v['source']}" for k, v in ef.items()], "",
        "### Top 10 municipalities", "", per_gem.head(10).round(0).to_markdown(),
    ])


if __name__ == "__main__":
    main()
