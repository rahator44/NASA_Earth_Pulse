"""
Review Priority Data Models and Configuration Constants.
Provides typed data structures for multi-criteria triage scoring:
ReviewScore = 0.50 * Observation + 0.35 * Exposure + 0.15 * Freshness.
"""
from typing import Optional
from pydantic import BaseModel, Field

# Core Review Priority Weights
REVIEW_WEIGHT_OBSERVATION: float = 0.50
REVIEW_WEIGHT_EXPOSURE: float = 0.35
REVIEW_WEIGHT_FRESHNESS: float = 0.15

# Exposure Component Sub-Weights
EXPOSURE_WEIGHT_POPULATION: float = 0.60
EXPOSURE_WEIGHT_INFRASTRUCTURE: float = 0.40

# Observation Component Baseline Scores
OBSERVATION_COMPONENT_SCORES: dict[str, float] = {
    "strong_change": 1.00,
    "change_detected": 0.50,
    "unknown_change": 0.65,
}

# Observation states that are eligible for Review Priority scoring
SCORED_OBSERVATION_STATES: set[str] = {
    "strong_change",
    "change_detected",
    "unknown_change",
}

# Unscored observation states (routed to dedicated non-triage sections)
UNSCORED_OBSERVATION_STATES: set[str] = {
    "no_change",
    "insufficient_data",
}


class ReviewPriorityResult(BaseModel):
    """
    Derived UI triage presentation model.
    Not stored as scientific analysis truth; calculated dynamically for review triage.
    """
    analysis_id: str
    event_id: Optional[str] = None
    observation_state: str

    # Normalized component values (0.0 to 1.0)
    observation_component: float = Field(ge=0.0, le=1.0)
    population_component: float = Field(ge=0.0, le=1.0, default=0.0)
    infrastructure_component: float = Field(ge=0.0, le=1.0, default=0.0)
    exposure_component: float = Field(ge=0.0, le=1.0, default=0.0)
    freshness_component: float = Field(ge=0.0, le=1.0, default=0.1)

    # Weighted contributions to total ReviewScore
    observation_weighted: float = Field(ge=0.0, le=REVIEW_WEIGHT_OBSERVATION)
    exposure_weighted: float = Field(ge=0.0, le=REVIEW_WEIGHT_EXPOSURE)
    freshness_weighted: float = Field(ge=0.0, le=REVIEW_WEIGHT_FRESHNESS)

    # Final combined score & priority band
    review_score: float = Field(ge=0.0, le=1.0)
    priority_band: str = "MEDIUM"  # "LOW", "MEDIUM", "HIGH"

    # Contextual metadata
    freshness_age_days: float = 0.0
    calculation_notes: str = ""
    missing_exposure_data: bool = False
