# 07_optimisation – Parcels vs. catchments for a CO2 target

_Run: 2026-10-27 10:26 · TEST MODE (test_catchment)_

- target: **75,000 t CO2-eq/yr**; solver SciPy milp (HiGHS)

### A) Parcel ranking / B) parcel optimum

- parcel model: Optimization terminated successfully. (HiGHS Status 7: Optimal); objective minimise area
- candidate parcels (≥ 1.0 ha on organic soil): 3,411
- B selects 808 parcels / 2,789 ha; A selects 914 / 2,791 ha

### C) Catchment optimum

- solver: Optimization terminated successfully. (HiGHS Status 7: Optimal)
- objective: minimise **non_peat_farmland**; only complete catchments: True
- candidate sub-catchments with farmed peat: 248

### Comparison

| approach | units | farmed peat rewetted ha | saving t/yr | catchments touched | all farmland wetted ha | of it on mineral soil ha |
|---|---|---|---|---|---|---|
| A) parcel ranking | 914 parcels | 2,791 | 75,037 | 220 | 17,194* | 7,164* |
| B) parcel optimum | 808 parcels | 2,789 | 75,001 | 121 | 9,368* | 4,512* |
| C) catchment optimum | 78 catchments | 2,857 | 75,001 | 78 | 2,901 | 44 |

\* if the water level is raised in every catchment that contains a
selected parcel - which is what rewetting physically does. The parcel
models ignore this and look cheaper than they are; their savings
would also be higher, since all peat in those catchments gets wet.

Reading: the parcel models scatter their picks over many catchments.
The catchment model concentrates rewetting in few hydrological units
that are mostly peat, so far less farmland on mineral soil gets wet.

All savings are ESTIMATES (area × national emission factors).
