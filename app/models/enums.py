"""
Domain and state enumerations for NISAR Surface Change Explorer.
"""
from enum import Enum


class Domain(str, Enum):
    WILDFIRE = "wildfire"
    FLOOD_WETLAND = "flood_wetland"
    GLACIER = "glacier"
    DEFORMATION = "deformation"
    UNCLASSIFIED = "unclassified"


class ObservationState(str, Enum):
    NO_CHANGE = "no_change"
    CHANGE_DETECTED = "change_detected"
    STRONG_CHANGE = "strong_change"
    UNKNOWN_CHANGE = "unknown_change"
    INSUFFICIENT_DATA = "insufficient_data"


class ProductType(str, Enum):
    GCOV = "GCOV"
    GUNW = "GUNW"
    GOFF = "GOFF"


class ProductMaturity(str, Enum):
    PROVISIONAL = "PROVISIONAL"
    BETA = "BETA"
    UNKNOWN = "UNKNOWN"


class ClassificationStatus(str, Enum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNCLASSIFIED = "unclassified"


class ValidationStatus(str, Enum):
    VALIDATED = "validated"
    CALIBRATED_ONLY = "calibrated_only"
    BETA_DEMO = "beta_demo"
    UNVALIDATED = "unvalidated"


class DataOrigin(str, Enum):
    SYNTHETIC_UI_FIXTURE = "synthetic_ui_fixture"
    PRECOMPUTED_REAL_ANALYSIS = "precomputed_real_analysis"
    LIVE_ANALYSIS = "live_analysis"
    LIVE_METADATA = "live_metadata"
