"""
SAR Scientific Processing Utilities
Classical, explainable radiometric differencing, quality masking,
thresholding, morphological filtering, and spatial evaluation metrics.

NO machine learning or deep learning is used.
All operations adhere strictly to radar physics:
- Linear power filtering occurs BEFORE dB conversion.
- dB conversion: 10 * log10(power) for strictly positive power.
- Difference: after_db - before_db.
- Open-water expansion: negative backscatter difference (delta_threshold <= 0).
- Permanent water excluded from new change detection.
- Independent validation metrics computed ONLY over valid reference pixels.
"""
from typing import Any, Optional, Tuple, Dict
import numpy as np
import scipy.ndimage as ndi
from rasterio.features import shapes as raster_shapes
from rasterio.transform import from_bounds


def linear_power_filter(
    power_array: np.ndarray,
    valid_mask: np.ndarray,
    kernel_size: int = 3
) -> np.ndarray:
    """
    Applies spatial filtering in LINEAR POWER domain before dB conversion.
    Filters only over valid positive pixels; does not bleed invalid values.
    """
    if kernel_size <= 1:
        return power_array.copy()

    # Zero-out invalid pixels for weighted mean
    clean_power = np.where(valid_mask & (power_array > 0), power_array, 0.0)
    weights = np.where(valid_mask & (power_array > 0), 1.0, 0.0)

    kernel = np.ones((kernel_size, kernel_size), dtype=np.float64)
    sum_power = ndi.convolve(clean_power, kernel, mode="constant", cval=0.0)
    sum_weights = ndi.convolve(weights, kernel, mode="constant", cval=0.0)

    filtered = np.zeros_like(power_array, dtype=np.float64)
    valid_filtered = sum_weights > 0
    filtered[valid_filtered] = sum_power[valid_filtered] / sum_weights[valid_filtered]
    filtered[~valid_filtered] = np.nan
    return filtered


def power_to_db(power_array: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Converts strictly positive linear power to decibels:
    dB = 10 * log10(power)
    
    Zero, negative, NaN, and Inf values are marked invalid.
    Returns (db_array, valid_mask).
    """
    valid_mask = np.isfinite(power_array) & (power_array > 0.0)
    db_array = np.full(power_array.shape, np.nan, dtype=np.float64)
    db_array[valid_mask] = 10.0 * np.log10(power_array[valid_mask])
    return db_array, valid_mask


def compute_difference_db(before_db: np.ndarray, after_db: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculates change in backscatter:
    difference_db = after_db - before_db

    Returns (difference_db, common_valid_mask).
    """
    common_valid = np.isfinite(before_db) & np.isfinite(after_db)
    diff = np.full(before_db.shape, np.nan, dtype=np.float64)
    diff[common_valid] = after_db[common_valid] - before_db[common_valid]
    return diff, common_valid


def classify_inundation_change(
    difference_db: np.ndarray,
    valid_mask: np.ndarray,
    delta_threshold: float = -3.0,
    after_db: Optional[np.ndarray] = None,
    post_water_threshold: Optional[float] = None,
    pre_existing_water_mask: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Classifies candidate open-water inundation / surface-water expansion.
    
    Rule:
    - difference_db <= delta_threshold (negative backscatter change)
    - optional: after_db <= post_water_threshold (specular reflection gate)
    - pre-existing water is EXCLUDED from new change
    """
    candidate = valid_mask & (difference_db <= delta_threshold)

    if after_db is not None and post_water_threshold is not None:
        candidate = candidate & (after_db <= post_water_threshold)

    if pre_existing_water_mask is not None:
        # Exclude pixels that were already permanent/pre-existing water
        candidate = candidate & (~pre_existing_water_mask)

    return candidate


def morphological_cleanup(
    binary_mask: np.ndarray,
    min_pixels: int = 5,
    apply_opening: bool = True
) -> np.ndarray:
    """
    Performs classical morphological cleanup:
    1. Binary opening (removes 1-pixel speckle noise)
    2. Connected-component labeling and minimum-area filtering
    """
    cleaned = binary_mask.copy()

    if apply_opening:
        structure = ndi.generate_binary_structure(2, 1)  # 4-connectivity
        cleaned = ndi.binary_opening(cleaned, structure=structure)

    if min_pixels > 1:
        labeled, num_features = ndi.label(cleaned)
        if num_features > 0:
            component_sizes = np.bincount(labeled.ravel())
            too_small = component_sizes < min_pixels
            too_small_mask = too_small[labeled]
            cleaned[too_small_mask] = False

    return cleaned


def calculate_pixel_area_km2(
    pixel_count: int,
    pixel_width_m: float = 30.0,
    pixel_height_m: float = 30.0
) -> float:
    """
    Computes real geographic area in km² using projected pixel dimensions.
    """
    area_m2 = pixel_count * abs(pixel_width_m * pixel_height_m)
    return float(area_m2 / 1e6)


def compute_reference_metrics(
    detected_mask: np.ndarray,
    reference_water_gain_mask: np.ndarray,
    reference_valid_mask: np.ndarray,
    pixel_width_m: float = 30.0,
    pixel_height_m: float = 30.0
) -> Dict[str, Any]:
    """
    Computes spatial verification metrics strictly over VALID reference pixels.
    Cloud, shadow, and no-data reference pixels are strictly excluded.
    
    Returns TP, FP, FN, TN, IoU, Precision, Recall, F1, and Area Error.
    """
    eval_mask = reference_valid_mask & np.isfinite(detected_mask)
    if not np.any(eval_mask):
        return {
            "valid_evaluation_pixels": 0,
            "tp": 0, "fp": 0, "fn": 0, "tn": 0,
            "iou": None, "precision": None, "recall": None, "f1": None,
            "area_error_km2": None
        }

    det = detected_mask[eval_mask].astype(bool)
    ref = reference_water_gain_mask[eval_mask].astype(bool)

    tp = int(np.sum(det & ref))
    fp = int(np.sum(det & ~ref))
    fn = int(np.sum(~det & ref))
    tn = int(np.sum(~det & ~ref))

    union = tp + fp + fn
    iou = float(tp / union) if union > 0 else 1.0 if (tp == 0 and fp == 0 and fn == 0) else 0.0
    precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    f1 = float(2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    detected_area = calculate_pixel_area_km2(int(np.sum(det)), pixel_width_m, pixel_height_m)
    reference_area = calculate_pixel_area_km2(int(np.sum(ref)), pixel_width_m, pixel_height_m)
    area_error = float(detected_area - reference_area)

    return {
        "valid_evaluation_pixels": int(np.sum(eval_mask)),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "iou": round(iou, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "detected_eval_area_km2": round(detected_area, 4),
        "reference_eval_area_km2": round(reference_area, 4),
        "area_error_km2": round(area_error, 4)
    }


def compute_histogram_stats(diff_array: np.ndarray, valid_mask: np.ndarray, num_bins: int = 30) -> Dict[str, Any]:
    """
    Computes empirical backscatter difference histogram from real numeric arrays.
    """
    valid_data = diff_array[valid_mask & np.isfinite(diff_array)]
    if len(valid_data) == 0:
        return {
            "bins": [],
            "counts": [],
            "minimum": None,
            "maximum": None,
            "mean": None,
            "median": None,
            "std": None
        }

    # Constrain to 1st - 99th percentile for robust visual histogram
    p1, p99 = float(np.percentile(valid_data, 1)), float(np.percentile(valid_data, 99))
    counts, bin_edges = np.histogram(valid_data, bins=num_bins, range=(p1, p99))
    
    bin_centers = [round(float((bin_edges[i] + bin_edges[i+1]) / 2.0), 2) for i in range(len(counts))]
    
    return {
        "bins": bin_centers,
        "counts": [int(c) for c in counts],
        "minimum": round(float(np.min(valid_data)), 2),
        "maximum": round(float(np.max(valid_data)), 2),
        "mean": round(float(np.mean(valid_data)), 2),
        "median": round(float(np.median(valid_data)), 2),
        "std": round(float(np.std(valid_data)), 2),
        "sample_count": int(len(valid_data))
    }


def mask_to_geojson_polygons(
    binary_mask: np.ndarray,
    bounds: Tuple[float, float, float, float],
    min_pixels: int = 5
) -> Dict[str, Any]:
    """
    Convert a binary mask to GeoJSON using each connected component's actual
    raster outline, not a bounding rectangle.

    ``bounds`` is (min_lon, min_lat, max_lon, max_lat). This helper is intended
    for small demo/reference rasters already expressed in EPSG:4326.
    """
    min_lon, min_lat, max_lon, max_lat = bounds
    height, width = binary_mask.shape
    d_lon = (max_lon - min_lon) / width
    d_lat = (max_lat - min_lat) / height
    transform = from_bounds(min_lon, min_lat, max_lon, max_lat, width, height)

    labeled, num_features = ndi.label(binary_mask.astype(bool))
    features = []

    for label_id in range(1, num_features + 1):
        component_mask = labeled == label_id
        pixel_count = int(np.sum(component_mask))
        if pixel_count < min_pixels:
            continue

        component_u8 = component_mask.astype(np.uint8)
        geoms = [
            geom for geom, value in raster_shapes(
                component_u8, mask=component_mask, transform=transform, connectivity=4
            ) if int(value) == 1
        ]
        if not geoms:
            continue

        area_km2 = round(
            calculate_pixel_area_km2(
                pixel_count, abs(d_lon) * 111320.0, abs(d_lat) * 111320.0
            ),
            4,
        )
        for geom_index, geom in enumerate(geoms, start=1):
            feature_id = f"change_region_{label_id:03d}" + (f"_{geom_index}" if len(geoms) > 1 else "")
            features.append({
                "type": "Feature",
                "id": feature_id,
                "geometry": geom,
                "properties": {
                    "region_id": feature_id.upper(),
                    "pixel_count": pixel_count,
                    "area_km2": area_km2,
                },
            })

    return {"type": "FeatureCollection", "features": features}
