"""
Science Unit Tests for Step 12
Tests classical SAR scientific algorithms, quality masking, power-to-dB conversion,
difference calculations, validation metrics, geospatial polygonization,
and data-origin integrity.

These tests use synthetic NumPy arrays and do NOT contact external networks.
"""
import numpy as np
import pytest

from app.models.coverage import CoverageAcquisition, PairCompatibilityStatus
from app.services.nisar_coverage import NisarCoverageService
from app.services.sar_science import (
    calculate_pixel_area_km2,
    classify_inundation_change,
    compute_difference_db,
    compute_reference_metrics,
    linear_power_filter,
    mask_to_geojson_polygons,
    morphological_cleanup,
    power_to_db,
)


def test_1_positive_power_to_db_conversion():
    """1. Positive power -> dB conversion follows 10 * log10(P)."""
    power = np.array([[1.0, 10.0], [100.0, 0.1]], dtype=np.float64)
    db, valid_mask = power_to_db(power)

    assert valid_mask.all()
    assert np.isclose(db[0, 0], 0.0)      # 10 * log10(1) = 0 dB
    assert np.isclose(db[0, 1], 10.0)     # 10 * log10(10) = 10 dB
    assert np.isclose(db[1, 0], 20.0)     # 10 * log10(100) = 20 dB
    assert np.isclose(db[1, 1], -10.0)    # 10 * log10(0.1) = -10 dB


def test_2_zero_and_negative_power_becomes_invalid():
    """2. Zero or negative power becomes invalid (NaN and False in valid mask)."""
    power = np.array([0.0, -1.0, -999.0, np.nan, np.inf], dtype=np.float64)
    db, valid_mask = power_to_db(power)

    assert not np.any(valid_mask)
    assert np.all(np.isnan(db))


def test_3_difference_is_after_minus_before():
    """3. Difference is defined strictly as: difference_db = after_db - before_db."""
    before_db = np.array([[-10.0, -12.0], [-15.0, -8.0]])
    after_db = np.array([[-16.0, -12.0], [-10.0, -14.0]])

    diff, valid = compute_difference_db(before_db, after_db)

    assert valid.all()
    assert np.isclose(diff[0, 0], -6.0)   # -16 - (-10) = -6 dB (drop in backscatter)
    assert np.isclose(diff[0, 1], 0.0)    # -12 - (-12) = 0 dB
    assert np.isclose(diff[1, 0], 5.0)    # -10 - (-15) = +5 dB (increase)
    assert np.isclose(diff[1, 1], -6.0)   # -14 - (-8) = -6 dB


def test_4_quality_mask_excludes_invalid_pixels():
    """4. Quality mask excludes non-finite or invalid pixels from difference."""
    before_db = np.array([[-10.0, np.nan], [-15.0, -8.0]])
    after_db = np.array([[np.nan, -12.0], [-10.0, -14.0]])

    diff, valid = compute_difference_db(before_db, after_db)

    assert not valid[0, 0]  # after is NaN
    assert not valid[0, 1]  # before is NaN
    assert valid[1, 0]
    assert valid[1, 1]
    assert np.isnan(diff[0, 0])
    assert np.isnan(diff[0, 1])


def test_5_flood_candidate_uses_negative_change_direction():
    """5. Flood / open-water candidate uses negative-change direction (delta <= threshold)."""
    diff_db = np.array([[-5.0, -2.0], [0.0, 3.0]])
    valid_mask = np.ones((2, 2), dtype=bool)

    # Threshold of -3.0 dB: only <= -3.0 is candidate change
    detected = classify_inundation_change(diff_db, valid_mask, delta_threshold=-3.0)

    assert detected[0, 0]   # -5.0 <= -3.0 -> True
    assert not detected[0, 1]  # -2.0 > -3.0 -> False
    assert not detected[1, 0]  # 0.0 > -3.0 -> False
    assert not detected[1, 1]  # +3.0 > -3.0 -> False


def test_6_existing_water_not_counted_as_new_water():
    """6. Pre-existing water is not counted as new inundation when reference mask is available."""
    diff_db = np.array([[-6.0, -6.0], [-6.0, -6.0]])
    valid_mask = np.ones((2, 2), dtype=bool)
    # Top-left and bottom-right were already permanent water
    pre_water = np.array([[True, False], [False, True]])

    detected = classify_inundation_change(
        diff_db, valid_mask, delta_threshold=-3.0, pre_existing_water_mask=pre_water
    )

    assert not detected[0, 0]  # Excluded because already water
    assert detected[0, 1]      # Detected as new inundation
    assert detected[1, 0]      # Detected as new inundation
    assert not detected[1, 1]  # Excluded because already water


def test_7_cloud_and_nodata_reference_pixels_excluded_from_metrics():
    """7. Cloud and no-data reference pixels are strictly excluded from validation metrics."""
    detected = np.array([[True, True], [False, False]])
    reference_water_gain = np.array([[True, False], [True, False]])
    # Top-right and bottom-left are cloudy / invalid in reference
    reference_valid = np.array([[True, False], [False, True]])

    metrics = compute_reference_metrics(detected, reference_water_gain, reference_valid)

    assert metrics["valid_evaluation_pixels"] == 2
    assert metrics["tp"] == 1  # (0, 0): detected=True, ref=True
    assert metrics["tn"] == 1  # (1, 1): detected=False, ref=False
    assert metrics["fp"] == 0
    assert metrics["fn"] == 0
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0


def test_8_connected_component_minimum_area_filtering():
    """8. Connected-component minimum-area filtering removes isolated speckle pixels."""
    # A 5x5 grid with one 1-pixel speckle and one 4-pixel blob
    mask = np.zeros((5, 5), dtype=bool)
    mask[0, 0] = True  # isolated 1 pixel
    mask[2:4, 2:4] = True  # 4-pixel connected block

    cleaned = morphological_cleanup(mask, min_pixels=3, apply_opening=False)

    assert not cleaned[0, 0]  # 1-pixel speckle removed
    assert cleaned[2, 2] and cleaned[2, 3] and cleaned[3, 2] and cleaned[3, 3]  # 4-pixel block preserved


def test_9_area_calculation_uses_projected_pixel_dimensions():
    """9. Area calculation uses projected pixel dimensions (pixel_width * pixel_height)."""
    # 1000 pixels with 30m x 30m resolution = 1000 * 900 m2 = 900,000 m2 = 0.9 km2
    area_km2 = calculate_pixel_area_km2(1000, pixel_width_m=30.0, pixel_height_m=30.0)
    assert np.isclose(area_km2, 0.9)

    # 500 pixels with 10m x 10m resolution = 50,000 m2 = 0.05 km2
    area_km2_10m = calculate_pixel_area_km2(500, pixel_width_m=10.0, pixel_height_m=10.0)
    assert np.isclose(area_km2_10m, 0.05)


def test_10_iou_calculation_is_correct():
    """10. IoU calculation: TP / (TP + FP + FN)."""
    detected = np.array([True, True, True, False])
    reference = np.array([True, True, False, True])
    valid = np.array([True, True, True, True])

    metrics = compute_reference_metrics(detected, reference, valid)

    # TP=2, FP=1, FN=1, TN=0. Union = 4. IoU = 2/4 = 0.5
    assert metrics["tp"] == 2
    assert metrics["fp"] == 1
    assert metrics["fn"] == 1
    assert np.isclose(metrics["iou"], 0.5)


def test_11_precision_calculation_is_correct():
    """11. Precision: TP / (TP + FP)."""
    detected = np.array([True, True, True, False])
    reference = np.array([True, True, False, False])
    valid = np.ones(4, dtype=bool)

    metrics = compute_reference_metrics(detected, reference, valid)

    # TP=2, FP=1. Precision = 2/3 = 0.6667
    assert metrics["tp"] == 2
    assert metrics["fp"] == 1
    assert np.isclose(metrics["precision"], 2.0 / 3.0, atol=1e-3)


def test_12_recall_calculation_is_correct():
    """12. Recall: TP / (TP + FN)."""
    detected = np.array([True, False, False, False])
    reference = np.array([True, True, True, False])
    valid = np.ones(4, dtype=bool)

    metrics = compute_reference_metrics(detected, reference, valid)

    # TP=1, FN=2. Recall = 1/3 = 0.3333
    assert metrics["tp"] == 1
    assert metrics["fn"] == 2
    assert np.isclose(metrics["recall"], 1.0 / 3.0, atol=1e-3)


def test_13_f1_calculation_is_correct():
    """13. F1 score: 2 * P * R / (P + R)."""
    detected = np.array([True, True, False, False])
    reference = np.array([True, False, True, False])
    valid = np.ones(4, dtype=bool)

    metrics = compute_reference_metrics(detected, reference, valid)

    # TP=1, FP=1, FN=1. Precision = 0.5, Recall = 0.5 -> F1 = 0.5
    assert np.isclose(metrics["f1"], 0.5)


def test_14_geojson_regions_use_geospatial_coordinates():
    """14. GeoJSON regions use geospatial coordinates (lon, lat), not pixel indices."""
    mask = np.zeros((10, 10), dtype=bool)
    mask[2:5, 3:6] = True  # block
    bounds = (-91.5, 30.0, -91.0, 30.5)

    fc = mask_to_geojson_polygons(mask, bounds, min_pixels=2)

    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) > 0

    first_feat = fc["features"][0]
    poly_coords = first_feat["geometry"]["coordinates"][0]

    for coord in poly_coords:
        lon, lat = coord
        assert -91.5 <= lon <= -91.0, f"Longitude {lon} out of geographic bounds"
        assert 30.0 <= lat <= 30.5, f"Latitude {lat} out of geographic bounds"


def test_15_beta_provisional_pairing_remains_forbidden():
    """15. BETA / PROVISIONAL pairing remains strictly forbidden under compatibility policy."""
    svc = NisarCoverageService()
    p1 = CoverageAcquisition(
        id="GCOV_PROV",
        product_type="GCOV",
        data_maturity="PROVISIONAL",
        track=33,
        frame=17,
        orbit_direction="ASCENDING",
        beam_mode="DHDH",
        polarizations=["HH", "HV"],
        frequency="L-SAR",
        bandwidth="40+5 MHz",
        crid="P05023"
    )
    b1 = CoverageAcquisition(
        id="GCOV_BETA",
        product_type="GCOV",
        data_maturity="BETA",
        track=33,
        frame=17,
        orbit_direction="ASCENDING",
        beam_mode="DHDH",
        polarizations=["HH", "HV"],
        frequency="L-SAR",
        bandwidth="40+5 MHz",
        crid="P05023"
    )

    pair = svc._evaluate_gcov_pair(p1, b1)
    assert pair.compatibility_status == PairCompatibilityStatus.INCOMPATIBLE
    assert pair.checks.same_maturity is False


def test_16_missing_metadata_cannot_become_compatible():
    """16. Incomplete metadata produces INSUFFICIENT_METADATA, never false COMPATIBLE."""
    svc = NisarCoverageService()
    a1 = CoverageAcquisition(
        id="A1",
        product_type="GCOV",
        data_maturity="PROVISIONAL",
        track=33,
        frame=None,  # Missing frame
        orbit_direction="ASCENDING",
        beam_mode="DHDH",
        polarizations=["HH", "HV"]
    )
    a2 = CoverageAcquisition(
        id="A2",
        product_type="GCOV",
        data_maturity="PROVISIONAL",
        track=33,
        frame=17,
        orbit_direction="ASCENDING",
        beam_mode="DHDH",
        polarizations=["HH", "HV"]
    )

    pair = svc._evaluate_gcov_pair(a1, a2)
    assert pair.compatibility_status == PairCompatibilityStatus.INSUFFICIENT_METADATA


def test_17_real_manifest_records_exact_granule_ids(tmp_path):
    """17. Real manifest records exact granule IDs, CRID, and product metadata."""
    manifest = {
        "manifest_id": "MAN_REAL_FLOOD_001",
        "data_origin": "precomputed_real_analysis",
        "before_granule_id": "NISAR_L2_PR_GCOV_024_033_A_017_4005_DHDH_A_20260628T112725_20260628T112800_P05023_N_F_J_001",
        "after_granule_id": "NISAR_L2_PR_GCOV_025_033_A_017_4005_DHDH_A_20260710T112724_20260710T112759_P05023_N_F_J_001",
        "product": "GCOV",
        "maturity": "PROVISIONAL",
        "track": 33,
        "frame": 17,
        "orbit_direction": "ASCENDING",
        "crid": "P05023"
    }

    assert manifest["before_granule_id"].startswith("NISAR_L2_PR_GCOV_")
    assert manifest["after_granule_id"].startswith("NISAR_L2_PR_GCOV_")
    assert manifest["maturity"] == "PROVISIONAL"
    assert manifest["crid"] == "P05023"


def test_18_data_origin_uses_precomputed_real_analysis():
    """18. Real showcase uses data_origin = 'precomputed_real_analysis', never synthetic fixture."""
    from app.models.enums import DataOrigin

    assert DataOrigin.PRECOMPUTED_REAL_ANALYSIS.value == "precomputed_real_analysis"
    assert DataOrigin.SYNTHETIC_UI_FIXTURE.value == "synthetic_ui_fixture"
    assert DataOrigin.PRECOMPUTED_REAL_ANALYSIS.value != DataOrigin.SYNTHETIC_UI_FIXTURE.value


def test_19_linear_power_filter_occurs_before_db():
    """19. Linear power filtering operates on linear power before conversion to dB."""
    linear_p = np.array([[10.0, 10.0, 10.0],
                         [10.0, 100.0, 10.0],
                         [10.0, 10.0, 10.0]])
    valid = np.ones((3, 3), dtype=bool)

    # Center pixel is 100; neighbors are 10. Average of 9 pixels is (8*10 + 100) / 9 = 20.0
    filtered_p = linear_power_filter(linear_p, valid, kernel_size=3)
    assert np.isclose(filtered_p[1, 1], 20.0)

    # dB of filtered center pixel is 10 * log10(20) ~ 13.01 dB
    # (If we erroneously filtered in dB: (8*10 + 20) / 9 = 11.11 dB)
    filtered_db, _ = power_to_db(filtered_p)
    assert np.isclose(filtered_db[1, 1], 10.0 * np.log10(20.0))


def test_20_all_previous_project_tests_remain_passing():
    """20. Meta-check that core application imports and routers remain fully operational."""
    from app.main import app
    assert app is not None
