"""Decode known NISAR product metadata without classifying surface change.

The filename decoder intentionally translates only documented NISAR naming
fields.  It never maps a filename code to a hazard or physical-change cause.
"""
from typing import Any, Optional, Sequence

from app.models.situation import DecodedNISARMetadata


PRODUCTS = {
    "GCOV": (
        "Geocoded Polarimetric Covariance",
        "Radar Surface Backscatter",
        "Measures how strongly the Earth's surface reflects radar energy. Repeat observations can reveal changes in surface water, vegetation structure, and other land-surface properties.",
    ),
    "GUNW": (
        "Geocoded Unwrapped Interferogram",
        "Ground Movement Evidence",
        "Measures phase differences between repeat radar observations that can reveal relative movement of the ground toward or away from the satellite.",
    ),
    "GOFF": (
        "Geocoded Pixel Offsets",
        "Surface Motion / Glacier Motion Evidence",
        "Measures displacement between repeat radar images and can be used to track large surface motion such as glacier movement.",
    ),
}

POLARIZATIONS = {
    "HH": "Horizontal transmit / horizontal receive polarization.",
    "HV": "Horizontal transmit / vertical receive polarization.",
    "VV": "Vertical transmit / vertical receive polarization.",
    "VH": "Vertical transmit / horizontal receive polarization.",
}

# Official NISAR filename code meanings used by the L2 GCOV naming convention.
PROCESSING_TYPES = {
    "PR": "Production product",
    "UR": "Urgent Response product",
    "OD": "Science On-Demand product",
}
POLARIZATION_MODES = {
    "SH": "HH single-polarization",
    "SV": "VV single-polarization",
    "DH": "HH/HV dual-polarization (H transmit)",
    "DV": "VV/VH dual-polarization (V transmit)",
    "CL": "LH/LV compact polarization (left transmit)",
    "CR": "RH/RV compact polarization (right transmit)",
    "QP": "HH/HV/VV/VH quad-polarization",
    "NA": "band not acquired",
}
SOURCE_CODES = {
    "A": "Acquired observation from a single mode",
    "M": "Mixed source observations / mixed mode",
}
ORBIT_ACCURACY_CODES = {
    "P": "Precise orbit ephemeris / radar pointing",
    "M": "Medium-accuracy orbit ephemeris / radar pointing",
    "N": "Near-real-time orbit ephemeris / radar pointing",
    "F": "Forecast orbit ephemeris / radar pointing",
}
COVERAGE_CODES = {"F": "Full frame coverage", "P": "Partial frame coverage"}
LOCATION_CODES = {"J": "Processed by the JPL Science Data System"}


def _code(value: object) -> str:
    return str(getattr(value, "value", value) or "").strip()


def _decode_bandwidth_mode(code: str) -> Optional[str]:
    if len(code) != 4 or not code.isdigit():
        return None
    primary, secondary = code[:2], code[2:]
    allowed = {"40", "20", "77", "05", "00"}
    if primary not in allowed or secondary not in allowed:
        return None
    primary_text = "not acquired" if primary == "00" else f"{int(primary)} MHz"
    secondary_text = "not acquired" if secondary == "00" else f"{int(secondary)} MHz"
    return f"Primary band {primary_text}; secondary band {secondary_text}."


def _decode_polarization_mode(code: str) -> Optional[str]:
    if len(code) != 4:
        return None
    primary, secondary = code[:2].upper(), code[2:].upper()
    if primary not in POLARIZATION_MODES or secondary not in POLARIZATION_MODES:
        return None
    return f"Primary band: {POLARIZATION_MODES[primary]}; secondary band: {POLARIZATION_MODES[secondary]}."


def _parse_gcov_granule_id(raw: str) -> dict[str, Any]:
    """Parse documented GCOV filename fields when a full standard granule ID is supplied."""
    if not raw or "GCOV" not in raw.upper():
        return {}
    filename = raw.rsplit("/", 1)[-1].split(".", 1)[0]
    tokens = filename.split("_")
    # NISAR_L2_PR_GCOV_CYL_REL_P_FRM_MODE_POLE_S_START_END_CRID_A_C_LOC_CTR
    if len(tokens) < 18 or tokens[0] != "NISAR" or tokens[3] != "GCOV":
        return {}
    try:
        cycle = int(tokens[4])
        track = int(tokens[5])
        frame = int(tokens[7])
    except (TypeError, ValueError):
        cycle = track = frame = None
    direction_code = tokens[6]
    return {
        "processing_level": "Level-2 geocoded science product" if tokens[1] == "L2" else None,
        "processing_type_code": tokens[2],
        "processing_type_label": PROCESSING_TYPES.get(tokens[2]),
        "cycle": cycle,
        "track": track,
        "frame": frame,
        "orbit_direction": "ASCENDING" if direction_code == "A" else "DESCENDING" if direction_code == "D" else None,
        "bandwidth_mode_code": tokens[8],
        "bandwidth_mode_explanation": _decode_bandwidth_mode(tokens[8]),
        "polarization_mode_code": tokens[9],
        "polarization_mode_explanation": _decode_polarization_mode(tokens[9]),
        "source_code": tokens[10],
        "source_explanation": SOURCE_CODES.get(tokens[10]),
        "crid": tokens[13],
        "orbit_accuracy_code": tokens[14],
        "orbit_accuracy_explanation": ORBIT_ACCURACY_CODES.get(tokens[14]),
        "coverage_code": tokens[15],
        "coverage_explanation": COVERAGE_CODES.get(tokens[15]),
        "processing_location_code": tokens[16],
        "processing_location_explanation": LOCATION_CODES.get(tokens[16]),
        "product_counter": tokens[17],
    }


def decode_nisar_metadata(
    *,
    product_code: Optional[object] = None,
    maturity: Optional[object] = None,
    orbit_direction: Optional[str] = None,
    track: Optional[int] = None,
    frame: Optional[int] = None,
    mode: Optional[str] = None,
    frequency: Optional[str] = None,
    bandwidth: Optional[str] = None,
    polarizations: Optional[Sequence[str]] = None,
    acquisition_dates: Optional[Sequence[str]] = None,
    processing_version: Optional[str] = None,
    analysis_pipeline_version: Optional[str] = None,
    code_version: Optional[str] = None,
    crid: Optional[str] = None,
    comparison_policy: Optional[str] = None,
    dataset_path: Optional[str] = None,
    quality_parameters: Optional[dict[str, Any]] = None,
    detection_parameters: Optional[dict[str, Any]] = None,
    source: Optional[str] = None,
    before_granule_id: Optional[str] = None,
    after_granule_id: Optional[str] = None,
) -> DecodedNISARMetadata:
    raw_product = _code(product_code)
    raw_product_upper = raw_product.upper()
    pieces = raw_product_upper.replace("-", "_").split("_")
    product = next((piece for piece in pieces if piece in PRODUCTS), raw_product_upper)
    product_info = PRODUCTS.get(product)
    filename_fields = _parse_gcov_granule_id(raw_product)

    raw_maturity = _code(maturity).upper()
    if raw_maturity in {"PR", "PROVISIONAL"}:
        maturity_code = "PROVISIONAL"
        maturity_label = "Provisional calibrated public product"
        maturity_explanation = "This calibrated product is publicly available provisionally; it may receive later revisions."
    elif raw_maturity == "BETA":
        maturity_code = "BETA"
        maturity_label = "Earlier lower-maturity data product"
        maturity_explanation = "BETA identifies an earlier, lower-maturity product release."
    elif raw_maturity:
        maturity_code = raw_maturity
        maturity_label = "Technical metadata available; interpretation not defined."
        maturity_explanation = "Technical metadata available; interpretation not defined."
    else:
        maturity_code = None
        maturity_label = None
        maturity_explanation = None

    raw_orbit = (orbit_direction or filename_fields.get("orbit_direction") or "").strip().upper()
    if raw_orbit == "ASCENDING":
        orbit_public = "Northbound satellite pass"
    elif raw_orbit == "DESCENDING":
        orbit_public = "Southbound satellite pass"
    elif raw_orbit:
        orbit_public = "Technical metadata available; interpretation not defined."
    else:
        orbit_public = None

    polarizations_clean = [str(item).strip().upper() for item in (polarizations or []) if str(item).strip()]
    pol_explanations = [POLARIZATIONS.get(value, "Technical metadata available; interpretation not defined.") for value in polarizations_clean]
    dates = [str(value) for value in (acquisition_dates or []) if value]

    return DecodedNISARMetadata(
        product_code=product or None,
        product_name_technical=product_info[0] if product_info else ("Technical metadata available; interpretation not defined." if raw_product else None),
        product_name_public=product_info[1] if product_info else ("Technical metadata available; interpretation not defined." if raw_product else None),
        product_explanation=product_info[2] if product_info else ("Technical metadata available; interpretation not defined." if raw_product else None),
        processing_level=filename_fields.get("processing_level") or ("Level-2 geocoded science product" if "L2" in pieces or raw_product_upper == "L2" else None),
        processing_type_code=filename_fields.get("processing_type_code"),
        processing_type_label=filename_fields.get("processing_type_label"),
        cycle=filename_fields.get("cycle"),
        bandwidth_mode_code=filename_fields.get("bandwidth_mode_code"),
        bandwidth_mode_explanation=filename_fields.get("bandwidth_mode_explanation"),
        polarization_mode_code=filename_fields.get("polarization_mode_code"),
        polarization_mode_explanation=filename_fields.get("polarization_mode_explanation"),
        source_code=filename_fields.get("source_code"),
        source_explanation=filename_fields.get("source_explanation"),
        orbit_accuracy_code=filename_fields.get("orbit_accuracy_code"),
        orbit_accuracy_explanation=filename_fields.get("orbit_accuracy_explanation"),
        coverage_code=filename_fields.get("coverage_code"),
        coverage_explanation=filename_fields.get("coverage_explanation"),
        processing_location_code=filename_fields.get("processing_location_code"),
        processing_location_explanation=filename_fields.get("processing_location_explanation"),
        product_counter=filename_fields.get("product_counter"),
        maturity_code=maturity_code,
        maturity_label=maturity_label,
        maturity_explanation=maturity_explanation,
        orbit_direction=raw_orbit.lower() if raw_orbit else None,
        orbit_direction_public=orbit_public,
        track=track if track is not None else filename_fields.get("track"),
        track_explanation="Repeat satellite ground path" if (track is not None or filename_fields.get("track") is not None) else None,
        frame=frame if frame is not None else filename_fields.get("frame"),
        frame_explanation="Geographic segment along the satellite path" if (frame is not None or filename_fields.get("frame") is not None) else None,
        mode=mode,
        frequency=frequency,
        bandwidth=bandwidth,
        polarizations=polarizations_clean,
        polarization_explanations=pol_explanations,
        acquisition_dates=dates,
        processing_version=processing_version,
        processing_version_explanation=("Software version used to generate the science product." if processing_version else None),
        analysis_pipeline_version=analysis_pipeline_version,
        code_version=code_version,
        crid=crid or filename_fields.get("crid"),
        crid_explanation=("Processing/release configuration identifier." if (crid or filename_fields.get("crid")) else None),
        comparison_policy=comparison_policy,
        dataset_path=dataset_path,
        quality_parameters=quality_parameters or {},
        detection_parameters=detection_parameters or {},
        source=source,
        before_granule_id=before_granule_id,
        after_granule_id=after_granule_id,
    )
