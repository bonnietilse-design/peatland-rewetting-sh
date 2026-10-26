"""
Central configuration for the peatland rewetting project (Schleswig-Holstein).

Every script imports from here. Change paths, test mode, field names and
emission factors in THIS file only - never hard-code them in the scripts.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
DATA_RAW = ROOT / "data" / "raw"            # downloads, never edited
DATA_INTERIM = ROOT / "data" / "interim"    # reprojected / clipped
DATA_PROCESSED = ROOT / "data" / "processed"  # analysis results
OUTPUTS = ROOT / "outputs"                  # maps, figures, tables
REPORTS = ROOT / "docs" / "reports"         # one short report per step

# One GeoPackage collects all vector results of the project
GPKG = DATA_PROCESSED / "peatland_sh.gpkg"

# ---------------------------------------------------------------------------
# Coordinate reference system
# ---------------------------------------------------------------------------
TARGET_CRS = "EPSG:25832"  # ETRS89 / UTM 32N - same as LVermGeo SH data

# ---------------------------------------------------------------------------
# Study area / test mode
# ---------------------------------------------------------------------------
# TEST_MODE = True  -> everything is clipped to TEST_AOI (one catchment)
# TEST_MODE = False -> whole state (VG250, Land Schleswig-Holstein)
TEST_MODE = True
TEST_AOI_NAME = "test_catchment"  # used in file names and reports
TEST_AOI = DATA_RAW / "aoi" / "test_aoi.gpkg"  # polygon you draw / derive

# ---------------------------------------------------------------------------
# Raw input files  (adjust names after downloading)
# ---------------------------------------------------------------------------
INPUTS = {
    # Thünen "Aktualisierte Kulisse organischer Böden" (Wittnebel et al. 2023)
    # DOI 10.3220/DATA20230510130443-0, CC BY 4.0
    "organic_soils": (DATA_RAW / "thuenen_organic_soils" / "Thuenen_Kulisse_OrgBoeden_v1"
                      / "Thuenen_Kulisse_OrgBoeden_v1" / "thuenen_kulisse_orgboeden_v1.shp"),
    # Feldblöcke SH, reference date 1.1.2026, licence: check metadata (dl-de/zero-2.0?)
    "feldbloecke": DATA_RAW / "feldbloecke" / "Feldbloecke_2026_GPKG" / "FB_20260101.gpkg",
    # VG250 (BKG), dl-de/by-2.0 - state and municipality boundaries
    "vg250_land": DATA_RAW / "vg250" / "VG250_LAN.shp",
    "vg250_gem": DATA_RAW / "vg250" / "VG250_GEM.shp",
    # Historical bog/fen extent digitised from the Preußische Landesaufnahme
    "historical_peat": DATA_RAW / "historical" / "peat_1880_digitised.gpkg",
    # Area that was actually checked on the 1880 map (step 06 compares only here)
    "historical_extent": DATA_RAW / "historical" / "digitised_extent.gpkg",
    # Protected areas (FFH, NSG) - LfU SH, check licence before publishing
    "protected_areas": DATA_RAW / "protected" / "TODO_filename.gpkg",
}

# Folder with DGM1 GeoTIFF tiles (OpenGBD SH, CC BY 4.0)
DGM1_DIR = DATA_RAW / "dgm1"   # put the downloaded Mehrfachdownload_*.zip here
# 1 m GeoTIFFs converted from the XYZ text tiles by step 01
DGM1_TIF_DIR = DATA_INTERIM / "dgm1_tif"
DGM1_TILE_KM = 1               # tile size; names: dgm1_32_<E km>_<N km>_1_sh_<year>.xyz
# Official bulk-download index ("Massendownload - GeoJSON" on the DGM1 page of
# the OpenGBD portal): one feature per tile with a direct download link.
DGM1_INDEX = DGM1_DIR / "DGM1_SH__Massendownload.geojson"
# Which tiles step 01 downloads:
#   "focus" - 7×7 km window over Meggerdorf/Bergenhusen (49 tiles, ~170 MB)
#   "aoi"   - every tile intersecting the AOI (354 tiles in the test AOI)
DGM1_SCOPE = "aoi"
DGM1_FOCUS_KM = {"e": (519, 525), "n": (6019, 6025)}   # inclusive ranges
DGM1_PAUSE_S = 1.0             # polite pause between downloads

# ---------------------------------------------------------------------------
# Attribute fields  (fill in after running 00_check_inputs.py)
# ---------------------------------------------------------------------------
FIELDS = {
    # VG250: state key "01" = Schleswig-Holstein; GF == 4 -> land area only
    "vg250_state_key": "SN_L",
    "vg250_state_value": "01",
    "vg250_gf": "GF",
    "vg250_gem_name": "GEN",
    "vg250_gem_ags": "AGS",
    # Thünen organic soils: KAT_KURZ = short category code (NH, HH, MF,
    # DK_MA_NH ...); KAT_LANG = full German name, use it for map labels.
    # GENESE = NH (fen) / HH (bog) / XH (other organic soil).
    "soil_type": "KAT_KURZ",
    "soil_type_label": "KAT_LANG",
    "soil_genesis": "GENESE",
    # Feldblöcke 2026: HBN = main land use, FLIK = field block ID.
    # FLAECHE is text with a decimal comma - don't use it, area is recomputed.
    "landuse": "HBN",
    "parcel_id": "FLIK",
}

# Map raw land-use codes from Feldblöcke (HBN) to analysis classes.
# Values not listed here are excluded; script 03 reports how many.
LANDUSE_CLASSES = {
    "Ackerland": "cropland",
    "Dauergrünland": "grassland",
}

# ---------------------------------------------------------------------------
# Emission factors  [t CO2-eq / ha / yr]
# ---------------------------------------------------------------------------
# Source: Tiemeyer et al. (2020), Ecological Indicators 109:105838, and/or the
# current National Inventory Report (LULUCF chapter). Fill in WITH the table/
# page reference. Leave None until you have a cited value - scripts will then
# skip the emission step instead of using made-up numbers.
#
# mean = implied national emission factor (IEF), Tiemeyer et al. 2020,
#        Table 5, p. 9: total GHG incl. CO2, CH4 (soil + ditches), N2O, DOC;
#        GWP from IPCC AR4. Valid for the whole land-use category incl. its
#        undrained share -> can be multiplied directly with area.
# Variability for the Monte Carlo (step 08) - derived from the paper's numbers:
#   - CO2 is ~90 % of the total GHG and carries most of the spread.
#   - Table 2 (p. 7) gives the CO2-onsite EF with 2.5–97.5 % percentiles, e.g.
#     grassland 8.3 [1.4–11.0] t C/ha/yr -> skewed: -6.9 / +2.7 t C.
#   - IMPORTANT (p. 5 and p. 7): these percentiles are taken over all grid
#     points, i.e. they describe how much single HECTARES differ (mainly
#     water table), NOT how uncertain the average over a large area is.
#   - Step 08 therefore draws a skewed two-piece normal in CO2-C space,
#     fitted so its MEAN equals the CO2 part of the IEF (Table 5,
#     CO2-Corganic) and its 2.5/97.5 % quantiles match Table 2; CH4, N2O and DOC stay fixed.
#   - min / max below = IEF with the CO2 part moved to the Table 2 percentiles
#     (for information; "sd" = older symmetric approximation, kept for the
#     "normal" comparison run).
# The paper found no emission difference between "true peat" and soils with
# lower organic carbon at German agricultural sites (sect. 4.1.1, p. 9), so the
# same factor is applied to all KAT_KURZ classes incl. MF and covered peat.
_SRC = "Tiemeyer et al. 2020, Ecol. Indic. 109:105838"
_C_TO_CO2 = 44 / 12

# Paper values per class:
#   ief      = Table 5 total GHG IEF [t CO2-eq/ha/yr]
#   co2c_ief = Table 5 CO2-Corganic [t C/ha/yr]
#   co2c_t2  = Table 2 CO2-onsite German EF (mean, lower 2.5 %, upper 97.5 %) [t C]
_PAPER = {
    "cropland":  {"ief": 40.4, "co2c_ief": 9.5,  "co2c_t2": (9.2, 3.8, 11.2)},
    "grassland": {"ief": 31.7, "co2c_ief": 8.0,  "co2c_t2": (8.3, 1.4, 11.0)},
    "rewetted":  {"ief": 5.5,  "co2c_ief": -0.4, "co2c_t2": (-0.4, -2.4, 1.3)},
}


def _triangle(p: dict) -> tuple[float, float]:
    """min / max in t CO2-eq: shift only the CO2 part by the Table 2 offsets."""
    mean, lo, hi = p["co2c_t2"]
    return (round(p["ief"] + (lo - mean) * _C_TO_CO2, 1),
            round(p["ief"] + (hi - mean) * _C_TO_CO2, 1))


EMISSION_FACTORS = {}
for _k, _p in _PAPER.items():
    _lo, _hi = _triangle(_p)
    _m, _l, _h = _p["co2c_t2"]
    EMISSION_FACTORS[_k] = {
        "mean": _p["ief"], "min": _lo, "max": _hi,
        "sd": round((_h - _l) / 3.92 * _C_TO_CO2, 1),
        # two-piece normal in t C: CO2 part of IEF, lower / upper sd
        "co2c": _p["co2c_ief"],
        "sd_c_low": round((_m - _l) / 1.96, 3),
        "sd_c_high": round((_h - _m) / 1.96, 3),
        "source": f"{_SRC}, Table 5; range from Table 2 CO2 {_m} [{_l} to {_h}] t C",
    }
# Result: cropland 40.4 [20.6–47.7], grassland 31.7 [6.4–41.6],
#         rewetted 5.5 [-1.8–11.7]  t CO2-eq/ha/yr

# ---------------------------------------------------------------------------
# Hydrology (WhiteboxTools)
# ---------------------------------------------------------------------------
HYDRO = {  # step 05, GRASS r.watershed run through qgis_process
    "resample_m": 5,              # 1 m is huge; 5 m is a sensible working res
    # how 25 one-metre cells become one 5 m cell: "min" keeps ditch bottoms
    # (1–3 m wide) so the drainage network survives; "average" smooths them away
    "resample_alg": "min",
    "basin_threshold_ha": 50,     # min. sub-catchment size (-> cells at resample_m)
    "single_flow": True,          # True = D8 (one downslope neighbour, -s flag)
    "memory_mb": 4000,            # RAM r.watershed may use
    # qgis_process command; None = search the usual names in the OSGeo4W shell
    "qgis_process": None,
}

# ---------------------------------------------------------------------------
# Optimisation (SciPy milp / HiGHS)
# ---------------------------------------------------------------------------
OPTIMISATION = {  # step 07, solved with scipy.optimize.milp
    # t CO2-eq / yr to reach. Test AOI: ~1/4 of the 293,000 t potential
    # saving from step 04. Adjust when switching AOI / TEST_MODE.
    "target_savings_t": 75_000,
    "min_parcel_ha": 1.0,         # ignore slivers from the overlay
    "objective": "area",          # parcel model: "area" or "parcels"
    # Catchment model (needs step 05): only whole sub-catchments can be chosen,
    # because raising the water level affects the whole hydrological unit.
    #   "non_peat_farmland" - wet as little farmland on MINERAL soil as possible
    #                         (collateral damage / land-use conflict)
    #   "affected_farmland" - wet as little farmland in total as possible
    #   "count"             - as few sub-catchments as possible
    "catchment_objective": "non_peat_farmland",
    "only_complete_catchments": True,   # skip catchments cut by the AOI edge
}

# ---------------------------------------------------------------------------
# Monte Carlo
# ---------------------------------------------------------------------------
MONTE_CARLO = {
    "n_runs": 10_000,
    "seed": 42,
    # "skewed": two-piece normal from Table 2 percentiles, mean = IEF (default)
    # "normal": symmetric mean ± sd (first version, for comparison)
    "distribution": "skewed",
    # Step 08 always reports two bounding scenarios:
    #   whole_area - one draw for the entire AOI per run (all fields share the
    #                same deviation; = "this region as a whole is wetter/drier
    #                than the German average") -> widest range
    #   per_parcel - independent draw per Feldblock (deviations cancel out)
    #                -> narrowest range
    # The truth lies in between: neighbouring fields share drainage systems.
}

# ---------------------------------------------------------------------------
# Historical comparison (step 06)
# ---------------------------------------------------------------------------
# Classes digitised from the 1878-80 map (legend: Zeichen-Erklärung 1898,
# see docs/digitising_legend.png) and what they say about peat.
HISTORICAL = {
    "layer": "peat_1880",
    "extent_layer": "digitised_extent",
    "classes": {                       # hist_type -> peat evidence in 1880
        "Moor": "certain",             # Sumpf, Bruch, Moor (+ Torfstich)
        "nasser Boden": "likely",
        "nasse Wiese": "likely",
        "Heide": "possible",           # lowland heath next to moor only
    },
    # Roads and ditches were mostly left out while digitising. Gaps between
    # neighbouring 1880 polygons up to this width are closed (buffer out and
    # back in) and given to the neighbouring class with the highest priority
    # (order of "classes" above).
    "gap_close_m": 30,                 # 15 m closed only 0.1 ha (roads + ditches wider)
    # Positional tolerance for the comparison: hand digitising + 1880 survey
    # + soil-map generalisation. Differences within this distance of the other
    # layer's boundary are reported as "edge" (could be position error).
    "edge_tolerance_m": 25,
}


def aoi_label() -> str:
    """Short label for file names: test AOI name or 'sh' for the whole state."""
    return TEST_AOI_NAME if TEST_MODE else "sh"
