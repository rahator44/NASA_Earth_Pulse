# NISAR Metadata Coverage & Acquisition Discovery

## 1. Overview
The NISAR Surface Change Explorer connects interactive map selections to real metadata discovery through the **Alaska Satellite Facility (ASF) DAAC** via `asf_search`.

This integration discovers what NISAR observation products exist for a selected location or Area of Interest (AOI), normalizes their metadata into typed models, evaluates candidate comparison pairs, and indicates data availability for domain analysis modules.

> [!IMPORTANT]
> **Metadata Only Scope**: This capability queries catalog metadata only. It does **not** download raw radar products (which require Earthdata authentication and large disk transfers), and does **not** perform radar image differencing or machine learning. Physical surface change is never inferred from metadata availability.

---

## 2. Core Concepts & Scientific Distinctions
Three concepts are strictly separated:
1. **Stored Analysis**: A precomputed demonstration analysis fixture in the application (`/api/demo/inspect-area`).
2. **NISAR Coverage**: One or more NISAR products (GCOV, GUNW, GOFF) indexed in the ASF archive over the selected geometry.
3. **No Coverage Found**: The metadata query executed successfully, but zero acquisitions matched the criteria.

Neither **Coverage Found** nor **No Coverage Found** equates to:
- `NO CHANGE` (an observation state requiring verified SAR backscatter stability)
- `INSUFFICIENT DATA` (an observation state where primary SAR inputs failed quality gates)

---

## 3. Products Queried
The coverage service queries three primary NISAR product levels independently:

| Product | Name | Primary Radar Mode | Applications |
| :--- | :--- | :--- | :--- |
| **GCOV** | Geocoded Polarimetric Backscatter | L-band / Dual-pol & Quad-pol | Wetland inundation, flood extent, forest/canopy disturbance |
| **GUNW** | Geocoded Unwrapped Interferogram | Repeat-pass interferometric SAR | Ground deformation, fault slip, volcanic subsidence |
| **GOFF** | Geocoded Pixel Offsets | Speckle / cross-correlation offsets | Glacier ice velocity, large displacement tracking |

---

## 4. Product Maturity Handling
NISAR data products are indexed under specific maturity stages:
- **`PROVISIONAL`**: Validated and calibrated public product releases suitable for scientific comparison.
- **`BETA`**: Early post-launch / engineering releases prior to finalized radiometric calibration.

### Rules
1. The service queries `PROVISIONAL` and `BETA` independently.
2. Counts, latest acquisition dates, and granule lists remain separated.
3. Automated comparison pairing **never** links a `BETA` acquisition with a `PROVISIONAL` acquisition.

---

## 5. Search Parameters & Limits
- **Search Start Date**: Configurable default `2026-06-17` (`NISAR_PROVISIONAL_START_DATE`).
- **Search End Date**: Current UTC date / time.
- **Result Limits**: Capped at `50` records per product/maturity combination (`MAX_SEARCH_RESULTS_PER_PRODUCT`). If exceeded, `results_truncated = true` is flagged.
- **Maximum AOI Size**: Bounding box span cannot exceed `5.0°` in latitude or longitude (~550 km). Queries exceeding this limit return `SEARCH_AREA_TOO_LARGE` (HTTP 400).
- **Cache TTL**: In-process thread-safe cache with a `900-second` (15-minute) TTL keyed by geometry WKT, products, maturity, and date range.
- **Search Timeout**: `15 seconds` bounded execution via `ThreadPoolExecutor` to avoid blocking web workers.

---

## 6. Status Definitions
| Status | Meaning |
| :--- | :--- |
| **`AVAILABLE`** | Search completed successfully; products were found. |
| **`NO_RESULTS`** | Search completed successfully; zero matching products in archive. |
| **`SERVICE_UNAVAILABLE`** | Network failure, DNS issue, or ASF API timeout occurred. |
| **`INVALID_REQUEST`** | Malformed GeoJSON or unrepairable geometry. |
| **`SEARCH_AREA_TOO_LARGE`** | Selected bounding box exceeds `5.0°` span limit. |

---

## 7. GCOV Nine-Point Compatibility Engine
For GCOV backscatter products, candidate before/after acquisition pairs are generated using a **nearest-earlier** comparison policy. Pairs are evaluated against nine criteria:

1. **Same Relative Track** (`pathNumber`)
2. **Same Frame** (`frameNumber`)
3. **Same Flight / Orbit Direction** (`flightDirection`: ASCENDING / DESCENDING)
4. **Compatible Beam Mode** (`beamModeType`)
5. **Compatible Polarization** (common polarization channel present)
6. **Compatible Frequency** (radar band / sensor)
7. **Compatible Bandwidth** (`rangeBandwidth`)
8. **Same Maturity Level** (PROVISIONAL ↔ PROVISIONAL only)
9. **Compatible Processing Software Version** (`crid` or `pgeVersion`)

### Status Values
- **`COMPATIBLE`**: All required metadata is present and all nine criteria match.
- **`INCOMPATIBLE`**: At least one physical or radar parameter conflicts.
- **`INSUFFICIENT_METADATA`**: Catalog records are missing one or more required fields. Missing metadata **never** produces a false `COMPATIBLE` claim.

---

## 8. Why GUNW & GOFF Are Excluded from GCOV Pair Matching
- **GUNW** products are already generated from an interferometric pair (reference and secondary acquisitions) during standard level-2 processing.
- **GOFF** products already represent cross-correlation offset measurements derived from an acquisition pair.
- Treating GUNW or GOFF as single uncoupled images for pair differencing is physically invalid. Therefore, the nine-point differencing engine applies exclusively to GCOV backscatter products.

---

## 9. API Reference
- **`POST /api/coverage/search`**
  - **Request**: `{ "geometry": GeoJSON, "requested_products": ["GCOV", "GUNW", "GOFF"], "maturity": "PROVISIONAL"|"BETA"|null }`
  - **Response**: `CoverageSearchResponse` (product counts, latest dates, module availability, granule records, pair candidates).
- **`GET /api/coverage/status`**
  - **Response**: Service configuration, `asf_search` version, cache statistics.
