"""Transparent, deterministic interpretation rules for public explanations.

These are application rules, not NASA hazard codes. They document why a stored
measurement can support a cautious physical interpretation and where that
interpretation stops.
"""
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class InterpretationRule:
    rule_id: str
    public_reason: str
    alternative_explanations: tuple[str, ...]
    limitation: str


RULES = {
    "GCOV_BACKSCATTER_DECREASE_01": InterpretationRule(
        rule_id="GCOV_BACKSCATTER_DECREASE_01",
        public_reason=(
            "The after-minus-before radar backscatter difference is negative across coherent, "
            "quality-screened regions. Smooth open water often returns less radar energy, so "
            "this pattern can be consistent with increased open water."
        ),
        alternative_explanations=(
            "Wet soil or changing surface moisture",
            "Vegetation structure or moisture change",
            "Other surface-property changes that alter radar backscatter",
        ),
        limitation="Radar backscatter change alone does not prove flooding or establish the cause.",
    ),
    "GCOV_BACKSCATTER_INCREASE_01": InterpretationRule(
        rule_id="GCOV_BACKSCATTER_INCREASE_01",
        public_reason=(
            "The after-minus-before radar backscatter difference is positive across coherent, "
            "quality-screened regions. In a water-focused analysis this can be consistent with "
            "less open water, but other surface changes can also increase radar return."
        ),
        alternative_explanations=(
            "Vegetation or roughness change",
            "Wet soil or changing surface moisture",
            "Other surface-property changes that alter radar backscatter",
        ),
        limitation="Radar backscatter change alone does not prove surface-water recession.",
    ),
    "WATER_CONTEXT_DSWX_01": InterpretationRule(
        rule_id="WATER_CONTEXT_DSWX_01",
        public_reason=(
            "An OPERA DSWx-HLS water observation is available near the analysis period, but this "
            "build has not spatially compared that layer with the NISAR change mask."
        ),
        alternative_explanations=(),
        limitation="The DSWx-HLS layer is contextual evidence here, not independent validation.",
    ),
    "GCOV_VEGETATION_DISTURBANCE_01": InterpretationRule(
        rule_id="GCOV_VEGETATION_DISTURBANCE_01",
        public_reason=(
            "A quality-screened repeat-pass GCOV analysis found a coherent radar-backscatter change over "
            "vegetated surfaces. Radar can respond to changes in canopy structure, moisture, and roughness."
        ),
        alternative_explanations=(
            "Harvesting or vegetation removal",
            "Storm or wind damage",
            "Vegetation moisture change",
            "Other land-surface disturbance",
        ),
        limitation="Radar disturbance alone does not identify the physical cause.",
    ),
    "FIRMS_FIRE_SUPPORT_01": InterpretationRule(
        rule_id="FIRMS_FIRE_SUPPORT_01",
        public_reason=(
            "The stored vegetation disturbance overlaps the configured spatial and temporal window for NASA FIRMS "
            "active-fire point detections, so fire activity is a supported context for the disturbance."
        ),
        alternative_explanations=(
            "Fire-related vegetation disturbance",
            "A separate vegetation disturbance occurring near active-fire detections",
        ),
        limitation="FIRMS detections are points at observation time and do not define a burn perimeter or prove causation.",
    ),
    "GUNW_LOS_DISPLACEMENT_01": InterpretationRule(
        rule_id="GUNW_LOS_DISPLACEMENT_01",
        public_reason=(
            "A processed GUNW record stores line-of-sight displacement from repeat radar phase "
            "measurements, indicating relative motion toward or away from the satellite."
        ),
        alternative_explanations=("Subsidence", "Uplift", "Tectonic or other surface motion"),
        limitation="Line-of-sight displacement is not the same as vertical subsidence.",
    ),
    "GOFF_MOTION_01": InterpretationRule(
        rule_id="GOFF_MOTION_01",
        public_reason=(
            "A processed GOFF record stores repeat-image pixel-offset motion measurements."
        ),
        alternative_explanations=(),
        limitation="Motion change alone does not establish hazard severity.",
    ),
    "UNKNOWN_CHANGE_01": InterpretationRule(
        rule_id="UNKNOWN_CHANGE_01",
        public_reason=(
            "The quality-screened analysis found a coherent radar change, but the available "
            "evidence does not support one physical cause strongly enough to resolve it."
        ),
        alternative_explanations=(),
        limitation="The physical cause has not been determined.",
    ),
}


def rule(rule_id: str) -> InterpretationRule:
    return RULES[rule_id]


def evidence_ids(items: Iterable[object]) -> list[str]:
    """Build stable, human-auditable IDs for explanation evidence."""
    out: list[str] = []
    for index, item in enumerate(items, start=1):
        name = getattr(item, "measurement_name", None) or getattr(item, "evidence_type", None) or "evidence"
        safe = "_".join(str(name).lower().replace("/", " ").replace("-", " ").split())
        out.append(f"evidence_{index}_{safe}")
    return out
