# Code Review Changes — Explainability Fix Pass

This pass prioritizes **explanation before classification**. The public UI should tell a user what NISAR measured, why the application suggests an interpretation, what other explanations remain possible, and where the conclusion stops.

## Scientific wording fixes
- Replaced the real showcase field `inundated_area_km2` with measurement-first fields:
  - `candidate_radar_change_area_km2`
  - `retained_mapped_region_area_km2`
  - `removed_small_component_area_km2`
  - `change_criterion_db`
- The real record now explains the difference between **0.837 km² candidate radar-change pixels** and **0.527 km² retained mapped regions**; **0.310 km²** was removed by minimum-region filtering.
- OPERA DSWx-HLS is now explicitly **context only** in this build. It is no longer presented as corroboration or validation because the stored DSWx raster was not reprojected and spatially compared with the NISAR mask.
- Migrated the synthetic water fixture from the ambiguous `backscatter_reduction_mean_db` key to the canonical signed `mean_backscatter_difference_db = after - before`. Negative values now consistently mean radar backscatter decreased.
- Real validation wording is now: **calibration/context only — not independently validated**.

## Explainability engine
- Added `app/services/interpretation_rules.py` with transparent deterministic rule IDs such as `GCOV_BACKSCATTER_DECREASE_01`.
- These are explicitly application rules, **not NASA hazard codes**.
- `SituationInterpretation` now carries:
  - `rule_id`
  - `public_reason`
  - `evidence_ids`
  - `alternative_explanations`
- Public Event Detail and Area Inspector now show:
  - what changed
  - what NISAR measured
  - why the interpretation is plausible
  - other plausible explanations
  - supporting/context evidence
  - data quality
  - what cannot be concluded
- Rule IDs and internal reasoning remain Scientist Mode details.

## Geometry and map fixes
- Replaced connected-component bounding rectangles with true raster component outlines using `rasterio.features.shapes`.
- Regenerated the stored real showcase GeoJSON from the existing candidate mask so mapped regions now follow the detected pixel geometry.
- Removed fake polygon properties such as generic `confidence` and noncanonical `observation_state` from the science polygonizer.
- Map legends no longer imply every resolved change is flood/wetland.
- Dashboard and Event Detail mini-maps now show a visible fallback message if MapLibre/basemap configuration fails instead of silently leaving an empty map.

## Dashboard consistency
- Removed hard-coded unknown-change hypotheses from the Dashboard.
- Dashboard candidate interpretations now come directly from each deterministic `SituationRecord`.
- Validation summaries now distinguish independent validation from calibration/context-only records.

## Real showcase provenance cleanup
- The old Earthdata-authentication failure reports were moved to `docs/history/failed-showcase-attempt-2026-10-05/` and clearly marked historical.
- `configs/flood_showcase.json` now reflects the successfully processed frozen demo AOI and current limitations.
- The active manifest now records that DSWx spatial comparison was **not performed** and that reference metrics are **not independently validated**.

## Verification
- `pytest`: **225 passed**
- Python compilation: passed
- JavaScript syntax (`node --check` on all app JS files): passed
- Browser automation: intentionally not performed per project instruction.
