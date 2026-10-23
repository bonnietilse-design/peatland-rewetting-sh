"""
03 – Overlay organic soils × agricultural land use
Intersects the Thünen organic soils with the Feldblöcke and summarises
hectares by soil type × land-use class, overall and per municipality.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geopandas as gpd  # noqa: E402

import config as cfg  # noqa: E402
from peatsh.common import (add_area_ha, get_logger, read_layer,  # noqa: E402
                           write_layer, write_report)

log = get_logger("03")


def main() -> None:
    f = cfg.FIELDS
    if "TODO" in (f["soil_type"], f["landuse"], f["parcel_id"]) or not cfg.LANDUSE_CLASSES:
        sys.exit("Fill in FIELDS and LANDUSE_CLASSES in config.py (see report 00).")

    soils = read_layer("organic_soils")[[f["soil_type"], f["soil_genesis"], "geometry"]]
    fb = read_layer("feldbloecke")[[f["parcel_id"], f["landuse"], "geometry"]]
    fb["lu_class"] = fb[f["landuse"]].map(cfg.LANDUSE_CLASSES)
    unmapped_counts = fb.loc[fb["lu_class"].isna(), f["landuse"]].value_counts()
    unmapped = int(unmapped_counts.sum())
    fb = fb.dropna(subset=["lu_class"])

    ov = gpd.overlay(fb, soils, how="intersection", keep_geom_type=True)
    ov = add_area_ha(ov)
    ov = ov[ov.area_ha >= cfg.OPTIMISATION["min_parcel_ha"] / 100]  # drop slivers

    gem = read_layer("vg250_gem")[[f["vg250_gem_ags"], f["vg250_gem_name"], "geometry"]]
    ov = gpd.overlay(ov, gem, how="intersection", keep_geom_type=True)
    ov = add_area_ha(ov)
    write_layer(ov, "overlay_soil_landuse")

    pivot = ov.pivot_table(index=f["soil_type"], columns="lu_class",
                           values="area_ha", aggfunc="sum", fill_value=0)
    per_gem = ov.groupby([f["vg250_gem_name"], "lu_class"]).area_ha.sum().unstack(fill_value=0)
    per_gem["total"] = per_gem.sum(axis=1)
    per_gem = per_gem.sort_values("total", ascending=False)
    pivot["total"] = pivot.sum(axis=1)
    cfg.OUTPUTS.mkdir(exist_ok=True)
    per_gem.to_csv(cfg.OUTPUTS / f"03_ha_per_municipality_{cfg.aoi_label()}.csv")

    log.info("overlay: %d pieces, %.0f ha", len(ov), ov.area_ha.sum())
    write_report("03_overlay", "Organic soils × land use", [
        f"- agricultural organic soil area: **{ov.area_ha.sum():,.0f} ha**",
        f"- Feldblöcke with unmapped land-use code (excluded): {unmapped}",
        *[f"  - {k}: {v}" for k, v in unmapped_counts.items()], "",
        "### Hectares by soil type × land use", "", pivot.round(0).to_markdown(), "",
        "### Top 10 municipalities", "", per_gem.head(10).round(0).to_markdown(),
    ])


if __name__ == "__main__":
    main()
