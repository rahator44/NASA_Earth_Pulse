"""
Deterministic Review Priority Calculation Service.
Implements multi-criteria triage scoring for the Situation Dashboard:
ReviewScore = 0.50 * Observation + 0.35 * Exposure + 0.15 * Freshness.

IMPORTANT SCIENTIFIC CONSTRAINTS:
- Observation State is physical truth derived from radar evidence.
- Review Priority is only an operational sorting/triage aid.
- Changing population, infrastructure, or freshness NEVER mutates scientific Observation State.
- Only change_detected, strong_change, and unknown_change are scored.
- no_change and insufficient_data are NEVER scored.
"""
from datetime import datetime, timezone
from typing import Any, Optional, Union

from app.models.enums import ObservationState
from app.models.review_priority import (
    EXPOSURE_WEIGHT_INFRASTRUCTURE,
    EXPOSURE_WEIGHT_POPULATION,
    OBSERVATION_COMPONENT_SCORES,
    REVIEW_WEIGHT_EXPOSURE,
    REVIEW_WEIGHT_FRESHNESS,
    REVIEW_WEIGHT_OBSERVATION,
    SCORED_OBSERVATION_STATES,
    UNSCORED_OBSERVATION_STATES,
    ReviewPriorityResult,
)


def normalize_observation_state_key(state: Union[str, ObservationState]) -> str:
    """Normalize state representation to lowercase underscore string."""
    if isinstance(state, ObservationState):
        return state.value.lower()
    return str(state).strip().lower()


def compute_observation_component(state: Union[str, ObservationState]) -> Optional[float]:
    """
    Computes observation component O:
    - STRONG CHANGE = 1.00
    - CHANGE DETECTED = 0.50
    - UNKNOWN CHANGE = 0.65
    - NO CHANGE = None (not scored)
    - INSUFFICIENT DATA = None (not scored)
    """
    key = normalize_observation_state_key(state)
    return OBSERVATION_COMPONENT_SCORES.get(key, None)


def parse_timestamp(ts: Union[str, datetime, None]) -> Optional[datetime]:
    """Parse string or datetime to timezone-aware UTC datetime."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    try:
        clean_str = str(ts).strip()
        if clean_str.endswith("Z"):
            clean_str = clean_str[:-1] + "+00:00"
        dt = datetime.fromisoformat(clean_str)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def compute_freshness_component(
    observation_time: Union[str, datetime, None],
    reference_time: Union[str, datetime, None],
) -> tuple[float, float]:
    """
    Computes freshness component F from latest relevant observation timestamp:
    Decay schedule:
      0 days old       -> 1.00
      7 days old       -> 0.80
      14 days old      -> 0.60
      30 days old      -> 0.30
      older than 60 d  -> 0.10

    Returns: (freshness_score, age_in_days)
    Both bounded strictly: freshness_score in [0.0, 1.0], age_in_days >= 0.0.
    """
    obs_dt = parse_timestamp(observation_time)
    ref_dt = parse_timestamp(reference_time)

    if not obs_dt or not ref_dt:
        return 0.10, 60.0

    diff_seconds = (ref_dt - obs_dt).total_seconds()
    age_days = max(0.0, diff_seconds / 86400.0)

    if age_days <= 0.0:
        score = 1.00
    elif age_days <= 7.0:
        score = 1.00 - (age_days / 7.0) * 0.20
    elif age_days <= 14.0:
        score = 0.80 - ((age_days - 7.0) / 7.0) * 0.20
    elif age_days <= 30.0:
        score = 0.60 - ((age_days - 14.0) / 16.0) * 0.30
    elif age_days <= 60.0:
        score = 0.30 - ((age_days - 30.0) / 30.0) * 0.20
    else:
        score = 0.10

    clamped_score = max(0.0, min(1.0, round(score, 4)))
    return clamped_score, round(age_days, 1)


def compute_dataset_exposure_scores(
    exposure_records: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    Computes dataset-relative exposure scores across reviewable candidate records.
    Population component: population / max_population in current set.
    Infrastructure component: mean of normalized available infrastructure fields.
    ExposureScore = 0.60 * PopulationScore + 0.40 * InfrastructureScore.
    
    If exposure data is missing: E = 0, marked as missing.
    """
    INFRASTRUCTURE_FIELDS = [
        "road_length_km",
        "rail_length_km",
        "bridge_count",
        "hospital_count",
        "settlement_count",
    ]

    # Find maximums across reviewable records
    max_pop = 0.0
    max_infra: dict[str, float] = {field: 0.0 for field in INFRASTRUCTURE_FIELDS}

    for rec in exposure_records:
        pop = rec.get("estimated_population")
        if pop is not None and isinstance(pop, (int, float)) and pop > max_pop:
            max_pop = float(pop)

        for field in INFRASTRUCTURE_FIELDS:
            val = rec.get(field)
            if val is not None and isinstance(val, (int, float)) and val > max_infra[field]:
                max_infra[field] = float(val)

    results: dict[str, dict[str, Any]] = {}

    for rec in exposure_records:
        aid = rec.get("analysis_id", "")
        raw_pop = rec.get("estimated_population")

        # Population component
        if raw_pop is not None and max_pop > 0.0:
            pop_score = max(0.0, min(1.0, float(raw_pop) / max_pop))
        else:
            pop_score = 0.0

        # Infrastructure component
        norm_infra_values: list[float] = []
        has_any_infra_val = False

        for field in INFRASTRUCTURE_FIELDS:
            val = rec.get(field)
            if val is not None and isinstance(val, (int, float)):
                has_any_infra_val = True
                f_max = max_infra[field]
                if f_max > 0.0:
                    norm_infra_values.append(max(0.0, min(1.0, float(val) / f_max)))
                else:
                    norm_infra_values.append(0.0)

        if norm_infra_values:
            infra_score = sum(norm_infra_values) / len(norm_infra_values)
        else:
            infra_score = 0.0

        is_missing = (raw_pop is None) and not has_any_infra_val

        if is_missing:
            exposure_score = 0.0
        else:
            exposure_score = (
                EXPOSURE_WEIGHT_POPULATION * pop_score
                + EXPOSURE_WEIGHT_INFRASTRUCTURE * infra_score
            )

        clamped_exp = max(0.0, min(1.0, round(exposure_score, 4)))

        results[aid] = {
            "population_component": round(pop_score, 4),
            "infrastructure_component": round(infra_score, 4),
            "exposure_component": clamped_exp,
            "missing_exposure_data": is_missing,
        }

    return results


def assign_priority_band(review_score: float) -> str:
    """Assigns priority band based on transparent thresholds."""
    if review_score >= 0.65:
        return "HIGH"
    if review_score >= 0.35:
        return "MEDIUM"
    return "LOW"


def calculate_review_priority_for_analysis(
    analysis_id: str,
    observation_state: Union[str, ObservationState],
    exposure_dict: Optional[dict[str, Any]],
    dataset_exposure_metrics: Optional[dict[str, Any]],
    observation_time: Union[str, datetime, None],
    dataset_latest_time: Union[str, datetime, None],
    event_id: Optional[str] = None,
) -> Optional[ReviewPriorityResult]:
    """
    Calculates deterministic Review Priority result for a single analysis.
    Returns None if state is no_change, insufficient_data, or not in scored set.
    """
    state_key = normalize_observation_state_key(observation_state)
    if state_key not in SCORED_OBSERVATION_STATES:
        return None

    obs_comp = compute_observation_component(state_key)
    if obs_comp is None:
        return None

    # Exposure components
    if dataset_exposure_metrics:
        pop_comp = dataset_exposure_metrics.get("population_component", 0.0)
        infra_comp = dataset_exposure_metrics.get("infrastructure_component", 0.0)
        exp_comp = dataset_exposure_metrics.get("exposure_component", 0.0)
        missing_exp = dataset_exposure_metrics.get("missing_exposure_data", False)
    else:
        pop_comp = 0.0
        infra_comp = 0.0
        exp_comp = 0.0
        missing_exp = True

    # Freshness component
    fresh_comp, age_days = compute_freshness_component(
        observation_time=observation_time,
        reference_time=dataset_latest_time,
    )

    # Weighted contributions
    obs_weighted = round(REVIEW_WEIGHT_OBSERVATION * obs_comp, 4)
    exp_weighted = round(REVIEW_WEIGHT_EXPOSURE * exp_comp, 4)
    fresh_weighted = round(REVIEW_WEIGHT_FRESHNESS * fresh_comp, 4)

    total_score = round(obs_weighted + exp_weighted + fresh_weighted, 2)
    # Ensure total_score is bounded in [0.0, 1.0]
    total_score = max(0.0, min(1.0, total_score))

    band = assign_priority_band(total_score)

    calc_notes = (
        f"ReviewScore ({total_score:.2f}) = "
        f"0.50 × Obs ({obs_comp:.2f}) + "
        f"0.35 × Exp ({exp_comp:.2f}) + "
        f"0.15 × Fresh ({fresh_comp:.2f})"
    )

    return ReviewPriorityResult(
        analysis_id=analysis_id,
        event_id=event_id,
        observation_state=state_key,
        observation_component=obs_comp,
        population_component=pop_comp,
        infrastructure_component=infra_comp,
        exposure_component=exp_comp,
        freshness_component=fresh_comp,
        observation_weighted=obs_weighted,
        exposure_weighted=exp_weighted,
        freshness_weighted=fresh_weighted,
        review_score=total_score,
        priority_band=band,
        freshness_age_days=age_days,
        calculation_notes=calc_notes,
        missing_exposure_data=missing_exp,
    )
