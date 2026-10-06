"""Shared, cautious human wording for SituationRecord generation."""
from typing import Any


STATE_WORDING = {
    "no_change": (
        "No significant surface change detected",
        "Usable repeat observations were analyzed and no significant surface change was found under the configured analysis criteria.",
    ),
    "change_detected": ("Surface change detected", "A processed repeat-observation analysis identified surface change under its configured criteria."),
    "strong_change": ("Strong surface change detected", "A processed analysis measured a strong surface-change signal; this does not describe hazard severity."),
    "unknown_change": ("Unusual radar change detected. Cause not identified.", "Radar change is present, but the available evidence does not identify its physical cause."),
    "insufficient_data": ("Not enough usable data to determine surface change.", "Available observations do not support a reliable conclusion."),
}

LIMITATIONS = {
    "water": "Radar change alone does not establish the cause of the surface-water change.",
    "vegetation": "Radar disturbance alone does not prove that fire caused the change.",
    "gunw": "Line-of-sight displacement is not the same as vertical subsidence.",
    "goff": "Motion change alone does not establish hazard severity.",
    "unknown": "The physical cause has not been determined.",
    "insufficient": "Available observations do not support a reliable conclusion.",
}


def enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def format_measurement(value: Any, unit: str = "") -> str:
    if isinstance(value, float):
        formatted = f"{value:.3f}" if abs(value) < 1 else f"{value:.2f}"
    else:
        formatted = str(value)
    return f"{formatted} {unit}".strip()


def public_quality(valid_fraction: float, quality_gate_passed: bool, reason: str | None, coherence: Any = None, coherence_threshold: Any = None) -> dict[str, Any]:
    pct = max(0.0, min(1.0, valid_fraction)) * 100
    if not quality_gate_passed:
        status = "Insufficient"
        explanation = "Too much of the selected area lacked usable radar data for a reliable change analysis."
    elif valid_fraction >= 0.8:
        status = "Good"
        explanation = "Most of the selected area contained usable radar data."
    else:
        status = "Limited"
        explanation = "Some of the selected area lacked usable radar data; interpret results cautiously."
    result = {
        "status": status,
        "valid_pixel_fraction": valid_fraction,
        "valid_pixel_percent": round(pct, 1),
        "explanation": explanation,
    }
    if reason:
        result["failure_reason" if not quality_gate_passed else "notes"] = reason
    if coherence is not None:
        result["coherence"] = coherence
        if coherence_threshold is None:
            result["coherence_explanation"] = "A coherence value is stored, but no interpretation threshold is recorded."
        else:
            result["coherence_threshold"] = coherence_threshold
            result["coherence_explanation"] = (
                "Stored coherence meets the analysis configuration's minimum for surface-motion interpretation."
                if coherence >= coherence_threshold
                else "Stored coherence is below the analysis configuration's minimum for surface-motion interpretation."
            )
    return result
