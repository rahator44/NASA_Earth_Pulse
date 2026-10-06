"""
NISAR Coverage API Endpoints (/api/coverage/).
Performs real metadata discovery and acquisition coverage queries against the ASF DAAC.
Metadata only — no raw file downloads or scientific processing.
"""
from typing import Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.models.coverage import (
    CoverageSearchRequest,
    CoverageSearchResponse,
    CoverageSearchStatus,
)
from app.services.nisar_coverage import coverage_service

router = APIRouter(prefix="/api/coverage", tags=["coverage"])


@router.post("/search", response_model=CoverageSearchResponse)
def search_coverage(request: CoverageSearchRequest):
    """
    Search the live NASA/ASF NISAR metadata catalog over a selected Area of Interest.
    
    Returns categorized acquisition summaries for GCOV, GUNW, and GOFF,
    identifies GCOV comparison pair candidates, and indicates module availability.
    """
    response = coverage_service.search_coverage(request)

    # Return HTTP 400 for invalid request geometry or excessive area size
    if response.search_status == CoverageSearchStatus.INVALID_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=response.error_message or "Invalid search geometry provided."
        )
    elif response.search_status == CoverageSearchStatus.SEARCH_AREA_TOO_LARGE:
        raise HTTPException(
            status_code=400,
            detail=response.error_message or "Search area exceeds allowable size limit."
        )

    return response


@router.get("/status")
async def get_coverage_service_status() -> dict[str, Any]:
    """
    Lightweight health and configuration check for the NISAR metadata discovery service.
    Does not invoke external network requests.
    """
    return coverage_service.get_status()
