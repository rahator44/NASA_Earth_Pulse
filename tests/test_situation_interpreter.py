"""Focused tests for deterministic NISAR situation explanations."""
from fastapi.testclient import TestClient

from app.main import app
from app.models.enums import Domain, ObservationState, ProductType
from app.models.situation import DecodedNISARMetadata
from app.services.demo_data import demo_service
from app.services.nisar_decoder import decode_nisar_metadata
from app.services.situation_interpreter import build_coverage_only_situation, build_situation_record


client = TestClient(app)


def real_components():
    analysis = demo_service.get_analysis("real_flood_001")
    event = demo_service.get_event("real_flood_001")
    return {
        "analysis": analysis,
        "event": event,
        "aoi": demo_service.get_aoi(analysis.aoi_id),
        "before": demo_service.get_acquisition(analysis.before_acquisition_id),
        "after": demo_service.get_acquisition(analysis.after_acquisition_id),
        "manifest": demo_service.get_manifest(analysis.manifest_id),
        "candidates": demo_service.get_candidates_for_analysis(analysis.id),
        "validation": demo_service.get_validation_for_analysis(analysis.id),
        "evidence": demo_service.get_evidence_for_analysis(analysis.id),
        "regions": demo_service.get_regions_for_analysis(analysis.id),
    }


def test_decoder_translates_products_orbits_and_polarizations():
    expected = {
        "GCOV": "Radar Surface Backscatter",
        "GUNW": "Ground Movement Evidence",
        "GOFF": "Surface Motion / Glacier Motion Evidence",
    }
    for code, public in expected.items():
        assert decode_nisar_metadata(product_code=code).product_name_public == public
    assert decode_nisar_metadata(orbit_direction="ASCENDING").orbit_direction_public == "Northbound satellite pass"
    assert decode_nisar_metadata(orbit_direction="DESCENDING").orbit_direction_public == "Southbound satellite pass"
    decoded = decode_nisar_metadata(polarizations=["HH", "HV", "VV", "VH"])
    assert decoded.polarization_explanations == [
        "Horizontal transmit / horizontal receive polarization.",
        "Horizontal transmit / vertical receive polarization.",
        "Vertical transmit / vertical receive polarization.",
        "Vertical transmit / horizontal receive polarization.",
    ]
    provisional = decode_nisar_metadata(product_code="NISAR_L2_PR_GCOV", maturity="PROVISIONAL")
    beta = decode_nisar_metadata(product_code="GOFF", maturity="BETA")
    assert provisional.processing_level == "Level-2 geocoded science product"
    assert provisional.maturity_label == "Provisional calibrated public product"
    assert beta.maturity_label == "Earlier lower-maturity data product"
    assert decode_nisar_metadata(track=11, frame=9, crid="P05023", processing_version="v1").track_explanation == "Repeat satellite ground path"


def test_unknown_metadata_does_not_invent_meaning():
    decoded = decode_nisar_metadata(product_code="L9", maturity="FUTURE")
    assert decoded.product_name_public == "Technical metadata available; interpretation not defined."
    assert decoded.maturity_label == "Technical metadata available; interpretation not defined."


def test_coverage_only_situation_has_no_physical_interpretation():
    situation = build_coverage_only_situation(DecodedNISARMetadata(product_code="GCOV"), acquisition_count=2)
    assert situation.headline == "NISAR observations are available for this area."
    assert situation.what_changed == "No processed surface-change analysis exists yet."
    assert not situation.interpretations


def test_no_change_and_insufficient_states_are_neutral_and_explain_quality():
    analysis = demo_service.get_analysis("analysis_synth_004")
    no_change = demo_service.get_situation_for_analysis(analysis.id)
    assert no_change.headline == "No significant surface change detected"
    assert "configured analysis criteria" in no_change.what_changed
    insufficient = demo_service.get_situation_for_analysis("analysis_synth_003")
    assert insufficient.headline == "Not enough usable data to determine surface change."
    assert insufficient.data_quality["status"] == "Insufficient"
    assert insufficient.data_quality["failure_reason"]


def test_unknown_change_says_cause_not_identified():
    situation = demo_service.get_situation_for_analysis("analysis_synth_002")
    assert situation.headline == "Unusual radar change detected. Cause not identified."


def test_real_water_situation_uses_recorded_area_and_cautious_language():
    situation = demo_service.get_situation_for_analysis("real_flood_001")
    assert situation.human_label == "REAL NISAR ANALYSIS"
    assert "0.837 km²" in situation.what_changed
    assert "Possible surface-water expansion" == situation.interpretations[0].public_label
    assert "Flood confirmed" not in situation.recommended_public_wording
    assert situation.direct_evidence and situation.context
    assert situation.technical_metadata.processing_version is None
    assert situation.technical_metadata.analysis_pipeline_version == "v1.0.0-real-nisar"
    assert situation.technical_metadata.dataset_path == "science/LSAR/GCOV/grids/frequencyA/HHHH"


def test_water_direction_uses_stored_signed_backscatter_difference():
    parts = real_components()
    parts["analysis"] = parts["analysis"].model_copy(update={"measurements": {"mean_backscatter_difference_db": -1.8}})
    expansion = build_situation_record(**parts)
    assert expansion.interpretations[0].code == "surface_water_expansion"
    parts["analysis"] = parts["analysis"].model_copy(update={"measurements": {"mean_backscatter_difference_db": 1.8}})
    recession = build_situation_record(**parts)
    assert recession.interpretations[0].code == "surface_water_recession"


def test_vegetation_without_firms_does_not_attribute_fire():
    parts = real_components()
    parts["analysis"] = parts["analysis"].model_copy(update={"domain": Domain.WILDFIRE})
    situation = build_situation_record(**parts)
    assert situation.interpretations[0].code == "vegetation_disturbance"
    assert "consistent with fire" not in situation.interpretations[0].public_label.lower()
    assert "prove that fire caused" in situation.what_we_cannot_say[0]


def test_firms_support_allows_cautious_fire_consistency_wording():
    parts = real_components()
    parts["analysis"] = parts["analysis"].model_copy(update={"domain": Domain.WILDFIRE})
    parts["manifest"] = parts["manifest"].model_copy(update={
        "matching_firms_detection_count": 2,
        "firms_time_buffer_hours": 24,
        "firms_spatial_buffer_m": 1000,
        "nearest_firms_distance_m": 240,
    })
    situation = build_situation_record(**parts)
    assert "consistent with fire activity" in situation.interpretations[0].public_label
    assert any(item.evidence_type == "active_fire_point_detections" for item in situation.supporting_evidence)
    assert any("do not define a burn perimeter" in text for text in situation.what_we_cannot_say)


def test_distant_firms_detection_does_not_corroborate_fire():
    parts = real_components()
    parts["analysis"] = parts["analysis"].model_copy(update={"domain": Domain.WILDFIRE})
    parts["manifest"] = parts["manifest"].model_copy(update={
        "matching_firms_detection_count": 1,
        "firms_time_buffer_hours": 24,
        "firms_spatial_buffer_m": 1000,
        "nearest_firms_distance_m": 1800,
    })
    situation = build_situation_record(**parts)
    assert situation.interpretations[0].code == "vegetation_disturbance"
    assert "consistent with fire" not in situation.interpretations[0].public_label.lower()


def test_gunw_interpretation_does_not_claim_subsidence():
    parts = real_components()
    parts["analysis"] = parts["analysis"].model_copy(update={
        "domain": Domain.DEFORMATION,
        "observation_state": ObservationState.CHANGE_DETECTED,
        "measurements": {"los_displacement_mm": 12.0},
    })
    parts["before"] = parts["before"].model_copy(update={"id": "NISAR_L2_GUNW_BEFORE", "product_type": ProductType.GUNW})
    parts["after"] = parts["after"].model_copy(update={"id": "NISAR_L2_GUNW_AFTER", "product_type": ProductType.GUNW})
    situation = build_situation_record(**parts)
    assert situation.interpretations[0].code == "ground_displacement"
    assert "subsidence" not in situation.interpretations[0].public_label.lower()
    assert "Line-of-sight displacement is not the same as vertical subsidence." in situation.what_we_cannot_say


def test_goff_interpretation_does_not_infer_hazard():
    parts = real_components()
    parts["analysis"] = parts["analysis"].model_copy(update={
        "domain": Domain.GLACIER,
        "observation_state": ObservationState.CHANGE_DETECTED,
        "measurements": {"velocity_m_per_day": 3.5},
    })
    parts["before"] = parts["before"].model_copy(update={"id": "NISAR_L2_GOFF_BEFORE", "product_type": ProductType.GOFF})
    parts["after"] = parts["after"].model_copy(update={"id": "NISAR_L2_GOFF_AFTER", "product_type": ProductType.GOFF})
    situation = build_situation_record(**parts)
    assert situation.interpretations[0].code == "glacier_displacement"
    assert "hazard" in situation.what_we_cannot_say[0].lower()


def test_glacier_speed_direction_uses_two_stored_measurements():
    parts = real_components()
    parts["analysis"] = parts["analysis"].model_copy(update={
        "domain": Domain.GLACIER,
        "observation_state": ObservationState.CHANGE_DETECTED,
        "measurements": {"before_velocity_m_per_day": 2.0, "after_velocity_m_per_day": 3.0},
    })
    parts["before"] = parts["before"].model_copy(update={"id": "NISAR_L2_GOFF_BEFORE", "product_type": ProductType.GOFF})
    parts["after"] = parts["after"].model_copy(update={"id": "NISAR_L2_GOFF_AFTER", "product_type": ProductType.GOFF})
    situation = build_situation_record(**parts)
    assert situation.interpretations[0].code == "glacier_acceleration"
    assert "increased glacier velocity" in situation.interpretations[0].description


def test_situation_api_and_event_detail_use_same_record():
    api = client.get("/api/analyses/real_flood_001/situation")
    event = client.get("/event/real_flood_001")
    assert api.status_code == 200
    assert api.json()["manifest_id"] == "manifest_real_flood_001"
    assert "HUMAN INTERPRETATION" in event.text
    assert "Possible surface-water expansion" in event.text
    assert client.get("/api/analyses/missing/situation").status_code == 404


def test_area_inspector_serializes_human_situation_and_copilot_uses_it():
    inspection = client.post("/api/demo/inspect-area", json={"aoi_id": "aoi_real_001"})
    assert inspection.status_code == 200
    match = next(item for item in inspection.json()["matches"] if item["analysis_id"] == "real_flood_001")
    assert match["situation"]["headline"] == "Surface-water change detected"
    assert "WHAT NISAR OBSERVED" in client.get("/static/js/area_inspector.js").text
    copilot = client.get("/copilot?event=real_flood_001")
    assert copilot.status_code == 200
    assert "What did NISAR measure?" in copilot.text
    assert "const situation = context.situation" in copilot.text
    assert "What can&#39;t you conclude?" in copilot.text


def test_interpretation_keeps_support_context_and_contradiction_separate():
    parts = real_components()
    situation = build_situation_record(**parts)
    assert all(item.support_level == "direct_measurement" for item in situation.direct_evidence)
    assert all(item.support_level == "contextual" for item in situation.context)
    assert isinstance(situation.supporting_evidence, list)
    assert isinstance(situation.contradicting_evidence, list)


def test_synthetic_situation_is_labeled_as_demo_interpretation():
    situation = demo_service.get_situation_for_analysis("analysis_synth_001")
    assert situation.human_label == "DEMO INTERPRETATION"
    assert "Synthetic development fixture — not an Earth observation result." in situation.summary


def test_gcov_granule_filename_codes_are_decoded_without_hazard_inference():
    granule = "NISAR_L2_PR_GCOV_024_033_A_017_4005_DHDH_A_20260628T112725_20260628T112800_P05023_N_F_J_001"
    decoded = decode_nisar_metadata(product_code=granule, maturity="PROVISIONAL")
    assert decoded.product_code == "GCOV"
    assert decoded.processing_type_code == "PR"
    assert decoded.processing_type_label == "Production product"
    assert decoded.cycle == 24
    assert decoded.track == 33
    assert decoded.frame == 17
    assert decoded.orbit_direction_public == "Northbound satellite pass"
    assert decoded.bandwidth_mode_code == "4005"
    assert "40 MHz" in decoded.bandwidth_mode_explanation
    assert "5 MHz" in decoded.bandwidth_mode_explanation
    assert decoded.polarization_mode_code == "DHDH"
    assert "HH/HV dual-polarization" in decoded.polarization_mode_explanation
    assert decoded.source_explanation == "Acquired observation from a single mode"
    assert decoded.orbit_accuracy_explanation == "Near-real-time orbit ephemeris / radar pointing"
    assert decoded.coverage_explanation == "Full frame coverage"
    assert decoded.processing_location_explanation == "Processed by the JPL Science Data System"
    assert decoded.product_counter == "001"
    # Filename codes describe product configuration, not a hazard label.
    assert "flood" not in (decoded.product_explanation or "").lower()


def test_real_event_public_explanation_decodes_nisar_codes():
    response = client.get("/event/real_flood_001")
    assert response.status_code == 200
    assert "HOW TO READ THE NISAR DATA" in response.text
    assert "Radar Surface Backscatter" in response.text
    assert "Northbound satellite pass" in response.text
    assert "Provisional calibrated public product" in response.text
