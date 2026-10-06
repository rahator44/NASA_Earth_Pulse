"""
Data models for real NISAR metadata discovery through ASF search.
Metadata only — no raw raster downloads or scientific processing.
"""
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class CoverageSearchStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    NO_RESULTS = "NO_RESULTS"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INVALID_REQUEST = "INVALID_REQUEST"
    SEARCH_AREA_TOO_LARGE = "SEARCH_AREA_TOO_LARGE"


class PairCompatibilityStatus(str, Enum):
    COMPATIBLE = "COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    INSUFFICIENT_METADATA = "INSUFFICIENT_METADATA"


class CoverageAcquisition(BaseModel):
    """Normalized metadata for a single NISAR product granule from ASF."""
    id: str = Field(..., description="Granule scene name or file identifier")
    product_type: str = Field(..., description="Product level: GCOV, GUNW, or GOFF")
    acquisition_datetime: Optional[str] = Field(default=None, description="Primary acquisition timestamp ISO")
    start_time: Optional[str] = Field(default=None, description="Observation start time")
    stop_time: Optional[str] = Field(default=None, description="Observation end time")
    track: Optional[int] = Field(default=None, description="Relative orbit / path number")
    frame: Optional[int] = Field(default=None, description="Frame number")
    orbit_direction: Optional[str] = Field(default=None, description="ASCENDING or DESCENDING")
    polarizations: list[str] = Field(default_factory=list, description="Available radar polarizations")
    beam_mode: Optional[str] = Field(default=None, description="Radar beam / observation mode")
    frequency: Optional[str] = Field(default=None, description="Radar frequency band (e.g. L-SAR)")
    bandwidth: Optional[str] = Field(default=None, description="Range bandwidth")
    data_maturity: str = Field("UNKNOWN", description="PROVISIONAL or BETA product maturity")
    processing_version: Optional[str] = Field(default=None, description="PGE processing software version")
    crid: Optional[str] = Field(default=None, description="Composite Release ID")
    geometry: Optional[dict[str, Any]] = Field(default=None, description="GeoJSON footprint polygon")
    metadata_url: Optional[str] = Field(default=None, description="Source catalog or context URL")
    download_url: Optional[str] = Field(default=None, description="Reference data access URL (not downloaded)")
    source: str = "NASA NISAR / ASF DAAC"
    data_origin: str = "live_metadata"


class MaturityProductSummary(BaseModel):
    """Collection of acquisitions for a specific product maturity (PROVISIONAL or BETA)."""
    count: int = 0
    latest_date: Optional[str] = None
    acquisitions: list[CoverageAcquisition] = Field(default_factory=list)


class CoverageProductSummary(BaseModel):
    """Separated counts and records for a single product type (GCOV, GUNW, or GOFF)."""
    provisional: MaturityProductSummary = Field(default_factory=MaturityProductSummary)
    beta: MaturityProductSummary = Field(default_factory=MaturityProductSummary)
    total_count: int = 0


class ModuleAvailability(BaseModel):
    """
    DATA AVAILABILITY only — NOT physical change detection.
    Indicates whether required input products exist in the archive.
    """
    vegetation_disturbance: str = "PRODUCT NOT FOUND"
    flood_wetland: str = "PRODUCT NOT FOUND"
    glacier: str = "PRODUCT NOT FOUND"
    deformation: str = "PRODUCT NOT FOUND"


class NinePointChecks(BaseModel):
    """Explicit nine-point compatibility verification for GCOV comparison pairs."""
    same_track: Optional[bool] = None
    same_frame: Optional[bool] = None
    same_direction: Optional[bool] = None
    compatible_mode: Optional[bool] = None
    compatible_polarization: Optional[bool] = None
    compatible_frequency: Optional[bool] = None
    compatible_bandwidth: Optional[bool] = None
    same_maturity: Optional[bool] = None
    compatible_processing_version: Optional[bool] = None
    details: dict[str, str] = Field(default_factory=dict)


class CompatiblePairCandidate(BaseModel):
    """Candidate comparison pair of GCOV acquisitions evaluated under the nine-point criteria."""
    before_id: str
    after_id: str
    before_date: Optional[str] = None
    after_date: Optional[str] = None
    temporal_baseline_days: Optional[int] = None
    compatibility_status: PairCompatibilityStatus = PairCompatibilityStatus.INSUFFICIENT_METADATA
    checks: NinePointChecks
    comparison_policy: str = "nearest_previous"
    notes: Optional[str] = None


class CoverageSearchRequest(BaseModel):
    """User request payload for querying NISAR metadata over a geographic area."""
    geometry: dict[str, Any] = Field(..., description="GeoJSON Point, Polygon, or Rectangle")
    requested_products: list[str] = Field(default=["GCOV", "GUNW", "GOFF"], description="Product levels to query")
    maturity: Optional[str] = Field(default=None, description="Optional maturity filter ('PROVISIONAL' or 'BETA')")
    date_range: Optional[dict[str, str]] = Field(default=None, description="Optional start/end ISO date strings")


class CoverageSearchResponse(BaseModel):
    """Complete structured response for live NISAR archive coverage discovery."""
    search_status: CoverageSearchStatus
    searched_at: str
    geometry_summary: Optional[str] = None
    date_range_summary: Optional[str] = None
    source: str = "NASA NISAR / ASF DAAC"
    products: dict[str, CoverageProductSummary] = Field(default_factory=dict)
    module_availability: ModuleAvailability = Field(default_factory=ModuleAvailability)
    gcov_pair_candidates: list[CompatiblePairCandidate] = Field(default_factory=list)
    results_truncated: bool = False
    warnings: list[str] = Field(default_factory=list)
    footprints_geojson: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
