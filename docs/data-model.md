# NISAR Surface Change Explorer — Data Model Architecture

*Step 3: Structured Demo Data Model + Seeded JSON/GeoJSON*

---

## 1. Overview & Data Philosophy

The NISAR Surface Change Explorer models Synthetic Aperture Radar (SAR) observations, spatial disturbance analyses, and scientific provenance.

### Core Architectural Axioms:
1. **Observation State $\neq$ Exposure:**  
   The scientific detection of surface changes (backscatter delta, phase decorrelation) is strictly separated from socioeconomic impact assessments (population, roads, bridges). An area may undergo massive physical disturbance in an uninhabited wilderness, or experience subtle deformation near critical infrastructure.
2. **Unknown Change is a Valid Scientific State:**  
   When radar signals change significantly but do not match known physical signatures (or independent sensor evidence conflicts), the system records `domain = unclassified`, `observation_state = unknown_change`, and `classification_status = unclassified`.
3. **Multiple Competing Candidate Interpretations:**  
   A single detected change region polygon can have multiple `CandidateMatch` hypotheses (e.g., hydrological inundation vs. vegetation canopy scorch) evaluated concurrently without forcing false certainty.
4. **Insufficient Data $\neq$ No Change:**  
   `insufficient_data` indicates that observation quality gates failed (e.g., missing secondary orbit pass, valid pixel fraction below threshold). `no_change` means the observation passed all quality gates and verified surface stability.
5. **Full Auditability & Manifest ID:**  
   Every persisted analysis points to an `AnalysisManifest` containing exact pipeline versions, orbit track/frame geometry, polarizations, thresholding algorithms, and auxiliary sensor buffers.

---

## 2. Entity Relationship Diagram

```text
┌─────────────────┐
│       AOI       │
└────────┬────────┘
         │ 1:N
┌────────▼────────┐        ┌───────────────────────┐
│   Acquisition   │◄───────┤    AnalysisManifest   │
└────────┬────────┘        └───────────▲───────────┘
         │ 1:N                         │ 1:1
┌────────▼─────────────────────────────┴───────────┐
│                     Analysis                     │
└──┬──────────────┬──────────────┬──────────────┬──┘
   │ 1:N          │ 1:1          │ 1:1          │ 1:1
┌──▼──────────┐ ┌─▼────────────┐ ┌▼───────────┐ ┌▼─────────────┐
│ ChangeRegion│ │ExposureResult│ │ Validation │ │    Event     │
└──┬──────────┘ └──────────────┘ └────────────┘ └──────────────┘
   │ 1:N
┌──▼──────────┐
│CandidateMatch
└─────────────┘
```

---

## 3. Model Entities

### Area of Interest (`AOI`)
- **File:** [`app/models/aoi.py`](file:///home/orr/NewVolume/Earth_pulse/app/models/aoi.py)
- **Role:** Geographic boundary definition (GeoJSON Polygon/MultiPolygon) defining observational study domains.

### Acquisition (`Acquisition`)
- **File:** [`app/models/acquisition.py`](file:///home/orr/NewVolume/Earth_pulse/app/models/acquisition.py)
- **Role:** Single radar swath capture metadata, including sensor mode, polarization channels (`HH`, `HV`), track, frame, orbit direction, and product type (`GCOV`, `GUNW`, `GOFF`).

### Analysis (`Analysis`)
- **File:** [`app/models/analysis.py`](file:///home/orr/NewVolume/Earth_pulse/app/models/analysis.py)
- **Role:** Core computation record linking a temporal pair (before/after acquisitions), carrying structured quality metrics (`valid_pixel_fraction`, `quality_gate_passed`), domain classification, and observation state.

### Change Region (`ChangeRegion`)
- **File:** [`app/models/change_region.py`](file:///home/orr/NewVolume/Earth_pulse/app/models/change_region.py)
- **Role:** Discrete spatial polygons representing localized radar anomalies extracted from the analysis. Can be exported as a standard GeoJSON `FeatureCollection`.

### Candidate Match (`CandidateMatch`)
- **File:** [`app/models/candidate_match.py`](file:///home/orr/NewVolume/Earth_pulse/app/models/candidate_match.py)
- **Role:** Hypotheses evaluated against a change region. Contains physical evidence, independent sensor concordance (e.g. thermal infrared, optical indices), and contradicting constraints.

### Exposure Result (`ExposureResult`)
- **File:** [`app/models/exposure.py`](file:///home/orr/NewVolume/Earth_pulse/app/models/exposure.py)
- **Role:** Decoupled socioeconomic indicators: estimated population, highway/road length, bridges, and settlement intersections.

### Validation Result (`ValidationResult`)
- **File:** [`app/models/validation.py`](file:///home/orr/NewVolume/Earth_pulse/app/models/validation.py)
- **Role:** Statistical accuracy benchmarks against external ground truth or reference datasets (IoU, precision, recall, F1, RMSE).

### Analysis Manifest (`AnalysisManifest`)
- **File:** [`app/models/manifest.py`](file:///home/orr/NewVolume/Earth_pulse/app/models/manifest.py)
- **Role:** Complete processing provenance ledger: code version, algorithm pipeline, calibration reference, and algorithm parameters.

### Event (`Event`)
- **File:** [`app/models/event.py`](file:///home/orr/NewVolume/Earth_pulse/app/models/event.py)
- **Role:** Consumer-facing feed record indexing verified analyses for the Home Change Feed and Event Detail views.

---

## 4. Enumerations

| Enum | Values |
| :--- | :--- |
| `Domain` | `wildfire`, `flood_wetland`, `glacier`, `deformation`, `unclassified` |
| `ObservationState` | `no_change`, `change_detected`, `strong_change`, `unknown_change`, `insufficient_data` |
| `ProductType` | `GCOV` (Backscatter), `GUNW` (Interferogram), `GOFF` (Pixel Offset Velocity) |
| `ProductMaturity` | `PROVISIONAL`, `BETA`, `UNKNOWN` |
| `ClassificationStatus` | `resolved`, `ambiguous`, `unclassified` |
| `ValidationStatus` | `validated`, `calibrated_only`, `beta_demo`, `unvalidated` |
| `DataOrigin` | `synthetic_ui_fixture`, `precomputed_real_analysis`, `live_analysis` |

---

## 5. Synthetic Development Fixture Policy

All seeded records in [`app/static/data/demo/`](file:///home/orr/NewVolume/Earth_pulse/app/static/data/demo/) are strictly development fixtures.
Every record contains:
```json
{
  "is_demo": true,
  "data_origin": "synthetic_ui_fixture",
  "disclaimer": "Synthetic development fixture — not an Earth observation result."
}
```
No real disasters or real cities are claimed. These fixtures exist solely to test state rendering, geometry parsing, and UI interaction before connecting real showcase analyses.
