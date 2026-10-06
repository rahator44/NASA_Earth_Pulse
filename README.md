# NISAR Surface Change Explorer

**NASA Space Apps Challenge Demo Application**  
*Step 4: Home / Change Feed*

---

## Purpose
The **NISAR Surface Change Explorer** is an interactive Earth-observation demonstration designed to visualize and explain surface changes using radar observations from the NASA-ISRO Synthetic Aperture Radar (NISAR) mission.

In future iterations, the platform will enable users to:
- Explore global radar coverage, swath tracks, and localized anomaly polygons.
- Inspect precomputed surface change analyses (wetland inundation, wildfire vegetation burn, glacier motion, ground deformation).
- Conduct dual-polarization and interferometric phase comparisons in the Scientist Image Lab.
- Monitor exposure indicators on a Situation Dashboard.
- Consult an AI Earth Copilot for grounded, plain-language scientific explanations.

> **Current State:**  
> **Step 4: Home / Change Feed.**  
> Server-side integration of validated Event records from `DemoDataService` into the editorial Home Feed. Includes Hero, Featured Observations, All Observations with reactive Alpine.js filtering, coverage CTA, and dataset empty-state handling. Every synthetic event is prominently labeled `DEMO FIXTURE`.

---

## Synthetic Data Policy & Transparency

All seeded records in `app/static/data/demo/` are development fixtures intended exclusively for testing rendering, filtering, state handling, geometry, and API contracts.

- Every synthetic record contains `is_demo = true`, `data_origin = "synthetic_ui_fixture"`, and an explicit disclaimer:
  > *"Synthetic development fixture — not an Earth observation result."*
- Every synthetic event card in the feed visibly displays the **DEMO FIXTURE** badge and the visible disclaimer caption.
- When real showcase events (`data_origin = "precomputed_real_analysis"`) are introduced in subsequent steps, the synthetic badge will disappear automatically based on the data field.
- Fictional names (`Synthetic AOI Alpha`, `Beta`, `Gamma`, `Delta`) and neutral coordinates are used.
- Cause attributions remain scientifically cautious: e.g., raw `wildfire` domains are presented as **Vegetation Disturbance** rather than claiming verified wildfire without independent confirmation.

---

## Technical Architecture (Python-First)

- **Language:** Python 3.11+ (verified on Python 3.14)
- **Web Framework:** FastAPI + Uvicorn
- **Data Validation:** Pydantic v2
- **Template Engine:** Jinja2
- **Presentation Helper:** `app/utils/presentation.py`
- **Interactivity:** Alpine.js (reactive state & domain filtering) + HTMX
- **Styling:** Tailwind CSS + NASA-inspired dark theme CSS variables
- **Geospatial Engine:** MapLibre GL JS with shared OpenStreetMap streets and optional Mapbox satellite basemaps
- **Icons:** Lucide Icons

---

## Project Structure

```text
Earth_pulse/
├── .gitignore
├── README.md
├── requirements.txt
├── run.py
├── docs/
│   ├── data-model.md               # Data model architecture and documentation
│   └── schemas/                    # Generated JSON Schemas
│       ├── analysis.schema.json
│       ├── event.schema.json
│       └── manifest.schema.json
├── scripts/
│   └── dev.sh
├── tests/
│   ├── __init__.py
│   ├── test_routes.py              # Pytest suite for page routes and design tokens
│   ├── test_demo_data.py           # Pytest suite for fixture loading and data integrity
│   └── test_home_feed.py           # Pytest suite for Home Feed presentation & filtering
└── app/
    ├── __init__.py
    ├── main.py                     # FastAPI application entry & router assembly
    ├── templates_config.py         # Shared Jinja2Templates instance
    ├── models/                     # Standardized Pydantic Data Models
    │   ├── __init__.py
    │   ├── enums.py                # Domain, ObservationState, ProductType, etc.
    │   ├── aoi.py                  # Area of Interest model
    │   ├── acquisition.py          # NISAR radar acquisition model
    │   ├── analysis.py             # Analysis & AnalysisQuality models
    │   ├── change_region.py        # Detected polygon model
    │   ├── candidate_match.py      # Competing hypothesis match model
    │   ├── exposure.py             # Socioeconomic exposure model
    │   ├── validation.py           # Validation & benchmark metrics model
    │   ├── manifest.py             # Complete provenance & manifest model
    │   └── event.py                # Change feed event model
    ├── services/
    │   ├── __init__.py
    │   └── demo_data.py            # Fixture loading and validation service
    ├── utils/
    │   ├── __init__.py
    │   └── presentation.py         # Presentation view models & safe domain formatters
    ├── routes/
    │   ├── __init__.py
    │   ├── home.py                 # Route: / (Home / Change Feed)
    │   ├── map.py                  # Route: /map
    │   ├── events.py               # Route: /event/{event_id}
    │   ├── copilot.py              # Route: /copilot
    │   ├── lab.py                  # Route: /lab/{analysis_id}
    │   ├── dashboard.py            # Route: /dashboard
    │   ├── methods.py              # Route: /methods
    │   ├── settings.py             # Route: /settings
    │   └── demo_api.py             # API Routes: /api/demo/*
    ├── templates/
    │   ├── base.html
    │   ├── components/
    │   │   ├── header.html
    │   │   ├── mobile_nav.html
    │   │   ├── page_header.html
    │   │   ├── section_header.html
    │   │   ├── event_card.html     # Dedicated data-driven event card component
    │   │   ├── media_card.html     # Generic editorial media card primitive
    │   │   ├── empty_state.html
    │   │   ├── metadata_row.html
    │   │   ├── skeleton_card.html
    │   │   └── placeholder_panel.html
    │   └── pages/
    │       ├── home.html           # Data-driven Home / Change Feed
    │       ├── map.html
    │       ├── event_detail.html
    │       ├── copilot.html
    │       ├── lab.html
    │       ├── dashboard.html
    │       ├── methods.html
    │       └── settings.html
    └── static/
        ├── css/
        │   └── app.css
        ├── js/
        │   ├── app.js
        │   ├── navigation.js
        │   └── map.js
        └── data/
            └── demo/               # Synthetic development JSON & GeoJSON fixtures
                ├── aois.json
                ├── acquisitions.json
                ├── analyses.json
                ├── change_regions.geojson
                ├── candidate_matches.json
                ├── exposure.json
                ├── validation.json
                ├── manifests.json
                └── events.json
```

---

## Setup & Running the Application

### 1. Setup Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run Application
```bash
python run.py
```

### 3. Run Tests
```bash
pytest -v
```

App URL: **`http://localhost:8000`**  
OpenAPI Documentation: **`http://localhost:8000/api/docs`**

> **Note on NASA Credentials:**  
> Teammates **do not** need a `~/.netrc` file or a NASA Earthdata account to run the web application, inspect the real NISAR Lake Henderson showcase, search the live NASA metadata archive, or run the test suite. All required processed products and mock fixtures are committed in the repository.  
> NASA Earthdata credentials are only required if you choose to re-run the offline raw granule streaming script (`scripts/real_flood/run_showcase.py`), which can be provided via `.env` (see `.env.example`).


---

## Home Feed Functionality (Step 4)

- **Hero / Intro:** Clean editorial presentation of the NISAR exploration mission with direct CTAs to `/map` and `/methods`.
- **Featured Observations:** Highlights analyses flagged `featured = true`.
- **Observation Filtering:** Alpine.js client-side filters for observation states (`All`, `Change Detected`, `Strong Change`, `Unknown Change`, `No Change`, `Insufficient Data`) and domains (`Flood / Wetland`, `Vegetation Disturbance`, `Glacier Change`, `Ground Deformation`, `Unclassified Change`).
- **Transparency Badging:** Prominent `DEMO FIXTURE` badge and visible disclaimer on synthetic data.
- **Empty State:** Clean fallback state rendering when no analyses are returned.
