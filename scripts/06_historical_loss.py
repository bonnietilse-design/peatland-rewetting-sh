"""
06 – Historical peatland loss (Preußische Landesaufnahme 1878–80 vs. today)

Manual part (QGIS, documented in docs/reports/06_digitising_notes.md):
  1. Layer → Add WCS/WMS: "Preußische Landesaufnahme mit Chronologen bis 1950"
     (LVermGeo SH, CC BY 4.0).
  2. Digitise bog/fen signatures ("Moor", "Bruch", marsh hatching) into
     data/raw/historical/peat_1880_digitised.gpkg with a field `hist_type`.
  3. Note scale and positional uncertainty.

This script then compares the digitised extent with today's organic soils.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geopandas as gpd  # noqa: E402

import config as cfg  # noqa: E402
from peatsh.common import (add_area_ha, clip_to_aoi, get_logger, load_aoi,  # noqa: E402
                           read_layer, read_vector, write_layer, write_report)

log = get_logger("06")


def main() -> None:
    aoi = load_aoi()
    hist = add_area_ha(clip_to_aoi(read_vector(cfg.INPUTS["historical_peat"]), aoi))
    today = read_layer("organic_soils")[["geometry"]].dissolve()

    lost = add_area_ha(gpd.overlay(hist, today, how="difference"))
    kept = add_area_ha(gpd.overlay(hist, today, how="intersection"))
    write_layer(lost, "hist_peat_lost")
    write_layer(kept, "hist_peat_still_organic")

    h, k = hist.area_ha.sum(), kept.area_ha.sum()
    write_report("06_historical", "Peatland 1880 vs. today", [
        f"- digitised peatland ~1880: {h:,.0f} ha",
        f"- still mapped as organic soil today: {k:,.0f} ha ({k / h:.0%})",
        f"- no longer organic soil: {h - k:,.0f} ha", "",
        "Caveats: different mapping concepts (map signature vs. soil survey),",
        "georeferencing error of the historical map, digitising scale.",
    ])


if __name__ == "__main__":
    main()
