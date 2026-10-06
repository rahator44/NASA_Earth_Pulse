"""
Demo Data Service for NISAR Surface Change Explorer.
Loads and validates synthetic development fixtures against Pydantic models.
Provides server-side spatial query and area inspection capabilities.
"""
import json
from pathlib import Path
from typing import Any, Optional
from pydantic import ValidationError
from shapely.geometry import Point, Polygon, shape

from app.models import (
    AnalysisLabMetrics,
    AOI,
    Acquisition,
    Analysis,
    AnalysisManifest,
    CandidateMatch,
    ChangeRegion,
    AnalysisEvidence,
    Event,
    ExposureResult,
    ObservationState,
    ValidationResult,
    DataOrigin,
)
from app.services.showcase_data import load_real_flood_showcase
from app.services.situation_interpreter import build_situation_record
from app.models.inspection import (
    AreaInspectionResponse,
    InspectionCandidate,
    InspectionExposure,
    InspectionMatch,
)
from app.utils.presentation import (
    format_date_range,
    format_domain_label,
    format_observation_state,
    format_validation_status,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "static" / "data" / "demo"


class FixtureValidationError(Exception):
    """Raised when a development fixture file fails validation."""
    pass


class DemoDataService:
    def __init__(self, fixtures_dir: Path = FIXTURES_DIR):
        self.fixtures_dir = fixtures_dir
        self.aois: dict[str, AOI] = {}
        self.acquisitions: dict[str, Acquisition] = {}
        self.manifests: dict[str, AnalysisManifest] = {}
        self.analyses: dict[str, Analysis] = {}
        self.change_regions: dict[str, ChangeRegion] = {}
        self.candidate_matches: dict[str, CandidateMatch] = {}
        self.exposure_results: dict[str, ExposureResult] = {}
        self.validation_results: dict[str, ValidationResult] = {}
        self.events: dict[str, Event] = {}
        self.evidence: dict[str, AnalysisEvidence] = {}
        self.lab_metrics: dict[str, AnalysisLabMetrics] = {}
        self.raw_geojson: dict[str, Any] = {}
        
        self.load_and_validate_all()

    def _read_json_file(self, filename: str) -> Any:
        file_path = self.fixtures_dir / filename
        if not file_path.exists():
            raise FixtureValidationError(f"Required fixture file not found: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise FixtureValidationError(f"Invalid JSON in fixture file '{filename}': {e}") from e

    def load_and_validate_all(self):
        """Loads all JSON/GeoJSON fixtures, validating each record against its Pydantic model."""
        # 1. AOIs
        raw_aois = self._read_json_file("aois.json")
        for item in raw_aois:
            record_id = item.get("id", "UNKNOWN")
            try:
                aoi = AOI.model_validate(item)
                self.aois[aoi.id] = aoi
            except ValidationError as e:
                raise FixtureValidationError(f"Validation failed in 'aois.json' for record '{record_id}': {e}") from e

        # 2. Acquisitions
        raw_acquisitions = self._read_json_file("acquisitions.json")
        for item in raw_acquisitions:
            record_id = item.get("id", "UNKNOWN")
            try:
                acq = Acquisition.model_validate(item)
                self.acquisitions[acq.id] = acq
            except ValidationError as e:
                raise FixtureValidationError(f"Validation failed in 'acquisitions.json' for record '{record_id}': {e}") from e

        # 3. Manifests
        raw_manifests = self._read_json_file("manifests.json")
        for item in raw_manifests:
            record_id = item.get("manifest_id", "UNKNOWN")
            try:
                manifest = AnalysisManifest.model_validate(item)
                self.manifests[manifest.manifest_id] = manifest
            except ValidationError as e:
                raise FixtureValidationError(f"Validation failed in 'manifests.json' for record '{record_id}': {e}") from e

        # 4. Analyses
        raw_analyses = self._read_json_file("analyses.json")
        for item in raw_analyses:
            record_id = item.get("id", "UNKNOWN")
            try:
                analysis = Analysis.model_validate(item)
                self.analyses[analysis.id] = analysis
            except ValidationError as e:
                raise FixtureValidationError(f"Validation failed in 'analyses.json' for record '{record_id}': {e}") from e

        # 5. Change Regions GeoJSON
        raw_geojson = self._read_json_file("change_regions.geojson")
        if raw_geojson.get("type") != "FeatureCollection":
            raise FixtureValidationError("change_regions.geojson root must be a 'FeatureCollection'")
        self.raw_geojson = raw_geojson
        for feature in raw_geojson.get("features", []):
            props = feature.get("properties", {})
            region_id = props.get("region_id", feature.get("id", "UNKNOWN"))
            region_payload = {
                "id": region_id,
                "analysis_id": props.get("analysis_id"),
                "geometry": feature.get("geometry"),
                "area_km2": props.get("area_km2"),
                "classification_status": props.get("classification_status"),
                "final_classification": props.get("final_classification"),
                "context_tags": props.get("context_tags", []),
                "is_demo": props.get("is_demo", True),
                "data_origin": props.get("data_origin", "synthetic_ui_fixture"),
                "disclaimer": props.get("disclaimer", "Synthetic development fixture — not an Earth observation result."),
            }
            try:
                region = ChangeRegion.model_validate(region_payload)
                self.change_regions[region.id] = region
            except ValidationError as e:
                raise FixtureValidationError(f"Validation failed in 'change_regions.geojson' for region '{region_id}': {e}") from e

        # 6. Candidate Matches
        raw_candidates = self._read_json_file("candidate_matches.json")
        for item in raw_candidates:
            record_id = item.get("id", "UNKNOWN")
            try:
                candidate = CandidateMatch.model_validate(item)
                self.candidate_matches[candidate.id] = candidate
            except ValidationError as e:
                raise FixtureValidationError(f"Validation failed in 'candidate_matches.json' for candidate '{record_id}': {e}") from e

        # 7. Exposure
        raw_exposure = self._read_json_file("exposure.json")
        for item in raw_exposure:
            record_id = item.get("id", "UNKNOWN")
            try:
                exposure = ExposureResult.model_validate(item)
                self.exposure_results[exposure.analysis_id] = exposure
            except ValidationError as e:
                raise FixtureValidationError(f"Validation failed in 'exposure.json' for record '{record_id}': {e}") from e

        # 8. Validation Results
        raw_validation = self._read_json_file("validation.json")
        for item in raw_validation:
            record_id = item.get("id", "UNKNOWN")
            try:
                val = ValidationResult.model_validate(item)
                self.validation_results[val.analysis_id] = val
            except ValidationError as e:
                raise FixtureValidationError(f"Validation failed in 'validation.json' for record '{record_id}': {e}") from e

        # 9. Events
        raw_events = self._read_json_file("events.json")
        for item in raw_events:
            record_id = item.get("id", "UNKNOWN")
            try:
                event = Event.model_validate(item)
                self.events[event.id] = event
            except ValidationError as e:
                raise FixtureValidationError(f"Validation failed in 'events.json' for event '{record_id}': {e}") from e

        # 10. Evidence
        raw_evidence = self._read_json_file("evidence.json")
        for item in raw_evidence:
            record_id = item.get("analysis_id", "UNKNOWN")
            try:
                evidence = AnalysisEvidence.model_validate(item)
                self.evidence[evidence.analysis_id] = evidence
            except ValidationError as e:
                raise FixtureValidationError(f"Validation failed in 'evidence.json' for analysis '{record_id}': {e}") from e

        # 11. Lab Metrics
        raw_lab_metrics = self._read_json_file("lab_metrics.json")
        for item in raw_lab_metrics:
            record_id = item.get("analysis_id", "UNKNOWN")
            try:
                metrics = AnalysisLabMetrics.model_validate(item)
                self.lab_metrics[metrics.analysis_id] = metrics
            except ValidationError as e:
                raise FixtureValidationError(f"Validation failed in 'lab_metrics.json' for analysis '{record_id}': {e}") from e

        # 12. Precomputed Real NISAR Showcase
        try:
            pkg = load_real_flood_showcase()
            self.aois[pkg.aoi.id] = pkg.aoi
            for acq in pkg.acquisitions:
                self.acquisitions[acq.id] = acq
            self.manifests[pkg.manifest.manifest_id] = pkg.manifest
            self.analyses[pkg.analysis.id] = pkg.analysis
            # Put real event at beginning so it is featured first
            self.events = {pkg.event.id: pkg.event, **self.events}
            self.evidence[pkg.evidence.analysis_id] = pkg.evidence
            self.lab_metrics[pkg.lab_metrics.analysis_id] = pkg.lab_metrics
            self.validation_results[pkg.validation.analysis_id] = pkg.validation
            for cand in pkg.candidates:
                self.candidate_matches[cand.id] = cand
            for cr in pkg.change_regions:
                self.change_regions[cr.id] = cr
            if "features" in self.raw_geojson:
                self.raw_geojson["features"].extend(pkg.raw_geojson.get("features", []))
        except Exception as e:
            print(f"Warning: Failed to load real showcase: {e}")

    # Query APIs
    def get_aois(self) -> list[AOI]:
        return list(self.aois.values())

    def get_aoi(self, aoi_id: str) -> Optional[AOI]:
        return self.aois.get(aoi_id)

    def get_acquisitions(self) -> list[Acquisition]:
        return list(self.acquisitions.values())

    def get_acquisition(self, acquisition_id: str) -> Optional[Acquisition]:
        return self.acquisitions.get(acquisition_id)

    def get_analyses(self) -> list[Analysis]:
        return list(self.analyses.values())

    def get_analysis(self, analysis_id: str) -> Optional[Analysis]:
        return self.analyses.get(analysis_id)

    def get_analyses_for_aoi(self, aoi_id: str) -> list[Analysis]:
        return [a for a in self.analyses.values() if a.aoi_id == aoi_id]

    def get_events(self) -> list[Event]:
        return list(self.events.values())

    def get_event(self, event_id: str) -> Optional[Event]:
        return self.events.get(event_id)

    def get_events_for_analysis(self, analysis_id: str) -> list[Event]:
        return [e for e in self.events.values() if e.analysis_id == analysis_id]

    def get_regions_for_analysis(self, analysis_id: str) -> list[ChangeRegion]:
        return [r for r in self.change_regions.values() if r.analysis_id == analysis_id]

    def get_candidates_for_region(self, region_id: str) -> list[CandidateMatch]:
        return [c for c in self.candidate_matches.values() if c.region_id == region_id]

    def get_candidates_for_analysis(self, analysis_id: str) -> list[CandidateMatch]:
        return [c for c in self.candidate_matches.values() if c.analysis_id == analysis_id]

    def get_manifest(self, manifest_id: str) -> Optional[AnalysisManifest]:
        return self.manifests.get(manifest_id)

    def get_exposure_for_analysis(self, analysis_id: str) -> Optional[ExposureResult]:
        return self.exposure_results.get(analysis_id)

    def get_validation_for_analysis(self, analysis_id: str) -> Optional[ValidationResult]:
        return self.validation_results.get(analysis_id)

    def get_change_regions_geojson(self) -> dict[str, Any]:
        return self.raw_geojson

    def get_evidence_for_analysis(self, analysis_id: str) -> Optional[AnalysisEvidence]:
        return self.evidence.get(analysis_id)

    def get_lab_metrics_for_analysis(self, analysis_id: str) -> Optional[AnalysisLabMetrics]:
        return self.lab_metrics.get(analysis_id)

    def get_situation_for_analysis(self, analysis_id: str):
        analysis = self.get_analysis(analysis_id)
        if not analysis:
            return None
        events = self.get_events_for_analysis(analysis_id)
        event = events[0] if events else None
        before = self.get_acquisition(analysis.before_acquisition_id) if analysis.before_acquisition_id else None
        after = self.get_acquisition(analysis.after_acquisition_id) if analysis.after_acquisition_id else None
        return build_situation_record(
            analysis,
            event=event,
            aoi=self.get_aoi(analysis.aoi_id),
            before=before,
            after=after,
            manifest=self.get_manifest(analysis.manifest_id),
            candidates=self.get_candidates_for_analysis(analysis_id),
            validation=self.get_validation_for_analysis(analysis_id),
            evidence=self.get_evidence_for_analysis(analysis_id),
            regions=self.get_regions_for_analysis(analysis_id),
        )

    # Area Inspection Query
    def inspect_geometry(
        self,
        geometry: Optional[dict[str, Any]] = None,
        selection_type: str = "point",
        aoi_id: Optional[str] = None
    ) -> AreaInspectionResponse:
        """
        Performs server-side spatial intersection between selected geometry (or AOI ID)
        and stored synthetic development fixtures.
        
        CRITICAL SCIENTIFIC RULES:
        - Point intersection: AOI contains or intersects point.
        - Polygon/Rectangle intersection: AOI intersects selected polygon.
        - Case A: Stored analysis found -> return stored observation state.
        - Case B: Stored analysis is insufficient_data -> return INSUFFICIENT DATA.
        - Case C: No stored analysis -> has_processed_analysis=False (NOT No Change!).
        """
        matched_aois_dict: dict[str, AOI] = {}
        coords_str: Optional[str] = None

        # 1. Direct AOI Lookup (via dropdown search or query param)
        if aoi_id and aoi_id in self.aois:
            target_aoi = self.aois[aoi_id]
            matched_aois_dict[target_aoi.id] = target_aoi
            try:
                aoi_geom = shape(target_aoi.geometry)
                centroid = aoi_geom.centroid
                lat, lon = centroid.y, centroid.x
                coords_str = f"{abs(lat):.4f}° {'N' if lat >= 0 else 'S'}, {abs(lon):.4f}° {'E' if lon >= 0 else 'W'}"
            except Exception:
                coords_str = target_aoi.display_name

        # 2. Geometric Spatial Intersection via Shapely
        elif geometry:
            try:
                user_shape = shape(geometry)
            except Exception:
                return AreaInspectionResponse(
                    selection_type=selection_type,
                    has_processed_analysis=False,
                    notice="Invalid GeoJSON geometry provided.",
                )

            # Format coordinates for presentation
            if user_shape.geom_type == "Point":
                lat, lon = user_shape.y, user_shape.x
                coords_str = f"{abs(lat):.4f}° {'N' if lat >= 0 else 'S'}, {abs(lon):.4f}° {'E' if lon >= 0 else 'W'}"
            else:
                minx, miny, maxx, maxy = user_shape.bounds
                lat_c = (miny + maxy) / 2.0
                lon_c = (minx + maxx) / 2.0
                coords_str = f"{abs(lat_c):.4f}° {'N' if lat_c >= 0 else 'S'}, {abs(lon_c):.4f}° {'E' if lon_c >= 0 else 'W'}"

            # Intersect with all synthetic AOIs
            for aoi in self.aois.values():
                try:
                    aoi_geom = shape(aoi.geometry)
                    if aoi_geom.intersects(user_shape):
                        matched_aois_dict[aoi.id] = aoi
                except Exception:
                    continue

            # Also check direct intersection with change region polygons
            for r in self.change_regions.values():
                if r.geometry:
                    try:
                        r_geom = shape(r.geometry)
                        if r_geom.intersects(user_shape):
                            analysis = self.analyses.get(r.analysis_id)
                            if analysis and analysis.aoi_id in self.aois:
                                matched_aois_dict[analysis.aoi_id] = self.aois[analysis.aoi_id]
                    except Exception:
                        continue

        # If no AOIs intersected, return Case C (NO STORED ANALYSIS)
        if not matched_aois_dict:
            return AreaInspectionResponse(
                selection_type=selection_type,
                coordinates_display=coords_str,
                has_processed_analysis=False,
                matched_aoi_ids=[],
                matched_count=0,
                matched_aois=[],
                analyses=[],
                events=[],
                change_regions=[],
                matches=[],
                is_demo=True,
                disclaimer="Synthetic development fixtures — not an Earth observation result.",
                notice="No processed surface-change analysis is available for this selection in the current demo."
            )

        # 3. Compile Enriched Matches for Matched AOIs
        matches: list[InspectionMatch] = []
        matched_aois_payload: list[dict[str, Any]] = []
        analyses_payload: list[dict[str, Any]] = []
        events_payload: list[dict[str, Any]] = []
        change_regions_payload: list[dict[str, Any]] = []

        for aoi in matched_aois_dict.values():
            matched_aois_payload.append({
                "id": aoi.id,
                "display_name": aoi.display_name,
                "country": aoi.country,
                "region": aoi.region
            })

            aoi_analyses = self.get_analyses_for_aoi(aoi.id)
            for analysis in aoi_analyses:
                analyses_payload.append(analysis.model_dump())

                # Associated events
                ev_list = self.get_events_for_analysis(analysis.id)
                ev = ev_list[0] if ev_list else None
                if ev:
                    events_payload.append(ev.model_dump())

                # Associated change regions
                regions = self.get_regions_for_analysis(analysis.id)
                for r in regions:
                    change_regions_payload.append(r.model_dump())

                # Candidate domain matches
                candidates_raw = self.get_candidates_for_analysis(analysis.id)
                candidate_items: list[InspectionCandidate] = []
                for c in candidates_raw:
                    candidate_items.append(InspectionCandidate(
                        id=c.id,
                        candidate_domain=c.candidate_domain.value,
                        candidate_domain_label=format_domain_label(c.candidate_domain),
                        candidate_score=c.candidate_score,
                        supported=c.supported,
                        notes=c.notes,
                        has_physical_evidence=bool(c.physical_evidence),
                        has_independent_evidence=bool(c.independent_evidence and any(c.independent_evidence.values())),
                        is_demo=c.is_demo,
                        disclaimer=c.disclaimer
                    ))

                # Exposure context
                exp_raw = self.get_exposure_for_analysis(analysis.id)
                exp_item: Optional[InspectionExposure] = None
                if exp_raw and analysis.observation_state != ObservationState.INSUFFICIENT_DATA:
                    exp_item = InspectionExposure(
                        estimated_population=exp_raw.estimated_population,
                        population_is_estimate=exp_raw.population_is_estimate,
                        road_length_km=exp_raw.road_length_km,
                        settlement_count=exp_raw.settlement_count,
                        is_demo=exp_raw.is_demo,
                        notes=exp_raw.notes,
                        disclaimer=exp_raw.disclaimer
                    )
                elif exp_raw and analysis.observation_state == ObservationState.INSUFFICIENT_DATA:
                    exp_item = InspectionExposure(
                        is_demo=exp_raw.is_demo,
                        notes=exp_raw.notes or "Exposure calculation withheld due to insufficient primary SAR observations.",
                        disclaimer=exp_raw.disclaimer
                    )

                # Formatted presentation strings
                domain_label = format_domain_label(analysis.domain)
                state_label, state_badge_class = format_observation_state(analysis.observation_state)
                val_status = ev.validation_status if ev else "unvalidated"
                val_label, val_badge_class = format_validation_status(val_status)
                date_display = format_date_range(ev.comparison_start if ev else None, ev.comparison_end if ev else None)

                # Primary measurement handling (withheld for insufficient_data)
                meas_label = ev.primary_measurement_label if ev else None
                meas_val = ev.primary_measurement_value if ev else None
                if analysis.observation_state == ObservationState.INSUFFICIENT_DATA:
                    meas_label = None
                    meas_val = None

                is_analysis_demo = (
                    analysis.data_origin == DataOrigin.SYNTHETIC_UI_FIXTURE or
                    getattr(analysis, "is_demo", False)
                )
                match_obj = InspectionMatch(
                    aoi_id=aoi.id,
                    aoi_display_name=aoi.display_name,
                    aoi_country=aoi.country,
                    aoi_region=aoi.region,
                    analysis_id=analysis.id,
                    domain_raw=analysis.domain.value,
                    domain_label=domain_label,
                    observation_state_raw=analysis.observation_state.value,
                    observation_state_label=state_label,
                    observation_state_badge_class=state_badge_class,
                    event_id=ev.id if ev else None,
                    event_title=ev.title if ev else f"{aoi.display_name} Analysis",
                    event_description=ev.short_description if ev else None,
                    comparison_start=ev.comparison_start if ev else None,
                    comparison_end=ev.comparison_end if ev else None,
                    date_range_display="2026-06-28 → 2026-07-10" if not is_analysis_demo and ev and "2026-06-28" in str(ev.comparison_start) else date_display,
                    primary_measurement_label=meas_label,
                    primary_measurement_value=meas_val,
                    product_maturity_label=ev.product_maturity.value if ev else "PROVISIONAL",
                    validation_status_label=val_label,
                    validation_status_badge_class=val_badge_class,
                    quality_notes=analysis.quality.notes,
                    quality_gate_passed=analysis.quality.quality_gate_passed,
                    manifest_id=analysis.manifest_id,
                    candidates=candidate_items,
                    exposure=exp_item,
                    is_demo=is_analysis_demo,
                    data_origin=analysis.data_origin.value if hasattr(analysis.data_origin, "value") else str(analysis.data_origin),
                    disclaimer="" if not is_analysis_demo else "Synthetic development fixture — not an Earth observation result.",
                    situation=self.get_situation_for_analysis(analysis.id),
                )
                matches.append(match_obj)

        has_analysis = len(matches) > 0

        has_real_analysis = any(not m.is_demo for m in matches)
        return AreaInspectionResponse(
            selection_type=selection_type,
            coordinates_display=coords_str,
            has_processed_analysis=has_analysis,
            matched_aoi_ids=list(matched_aois_dict.keys()),
            matched_count=len(matched_aois_dict),
            matched_aois=matched_aois_payload,
            analyses=analyses_payload,
            events=events_payload,
            change_regions=change_regions_payload,
            matches=matches,
            is_demo=not has_real_analysis,
            data_origin="precomputed_real_analysis" if has_real_analysis else "synthetic_ui_fixture",
            disclaimer="" if has_real_analysis else "Synthetic development fixtures — not an Earth observation result.",
            notice=None if has_analysis else "No processed surface-change analysis is available for this selection in the current demo."
        )


# Global singleton instance for service access
demo_service = DemoDataService()
