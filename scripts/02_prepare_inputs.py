"""
02 – Prepare inputs
Reproject to EPSG:25832, repair geometries, clip to the AOI and store
everything in the project GeoPackage. Also writes the AOI itself.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config as cfg  # noqa: E402
from peatsh.common import (add_area_ha, clip_to_aoi, ensure_dirs,  # noqa: E402
                           get_logger, load_aoi, read_vector, write_layer,
                           write_report)

log = get_logger("02")
LAYERS = ["organic_soils", "feldbloecke", "vg250_gem", "protected_areas"]


def main() -> None:
    ensure_dirs()
    aoi = add_area_ha(load_aoi())
    write_layer(aoi, "aoi")
    lines = [f"- AOI area: {aoi.area_ha.sum():,.0f} ha", "",
             "| layer | features | area ha |", "|---|---|---|"]
    for name in LAYERS:
        path = cfg.INPUTS[name]
        if not path.exists():
            log.warning("skip %s – missing", name)
            lines.append(f"| {name} | missing | – |")
            continue
        gdf = add_area_ha(clip_to_aoi(read_vector(path, mask=aoi), aoi))
        write_layer(gdf, name)
        log.info("%s: %d features", name, len(gdf))
        lines.append(f"| {name} | {len(gdf):,} | {gdf.area_ha.sum():,.0f} |")
    write_report("02_prepare_inputs", "Reproject and clip", lines)


if __name__ == "__main__":
    main()
