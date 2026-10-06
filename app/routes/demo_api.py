"""
Lightweight development fixture API endpoints (/api/demo/).
Note: These are synthetic development fixtures for UI testing and prototyping.
"""
from typing import Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.models import (
    AOI,
    Analysis,
    AnalysisEvidence,
    AnalysisLabMetrics,
    AnalysisManifest,
    AreaInspectionRequest,
    AreaInspectionResponse,
    CandidateMatch,
    ChangeRegion,
    Event,
)
from app.services.demo_data import demo_service

router = APIRouter(prefix="/api/demo", tags=["demo-fixtures"])


@router.get("/aois", response_model=list[AOI])
async def list_demo_aois():
    """List all synthetic development Areas of Interest."""
    return demo_service.get_aois()


@router.get("/aois.geojson", response_class=JSONResponse)
async def get_aois_geojson() -> Any:
    """Returns synthetic AOIs formatted as a standard GeoJSON FeatureCollection for MapLibre."""
    features = []
    for aoi in demo_service.get_aois():
        features.append({
            "type": "Feature",
            "id": aoi.id,
            "geometry": aoi.geometry,
            "properties": {
                "id": aoi.id,
                "display_name": aoi.display_name,
                "country": aoi.country,
                "region": aoi.region,
                "is_demo": aoi.is_demo,
                "disclaimer": aoi.disclaimer,
            }
        })
    return JSONResponse(
        content={"type": "FeatureCollection", "features": features},
        media_type="application/geo+json"
    )


@router.get("/aois/{aoi_id}", response_model=AOI)
async def get_demo_aoi(aoi_id: str):
    """Retrieve a single synthetic Area of Interest by ID."""
    aoi = demo_service.get_aoi(aoi_id)
    if not aoi:
        raise HTTPException(status_code=404, detail=f"Synthetic AOI '{aoi_id}' not found")
    return aoi


@router.get("/events", response_model=list[Event])
async def list_demo_events():
    """List all synthetic development change feed events."""
    return demo_service.get_events()


@router.get("/events/{event_id}", response_model=Event)
async def get_demo_event(event_id: str):
    """Retrieve a single synthetic change feed event by ID."""
    event = demo_service.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Synthetic event '{event_id}' not found")
    return event


@router.get("/analyses/{analysis_id}", response_model=Analysis)
async def get_demo_analysis(analysis_id: str):
    """Retrieve a single synthetic analysis record by ID."""
    analysis = demo_service.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Synthetic analysis '{analysis_id}' not found")
    return analysis


@router.get("/analyses/{analysis_id}/evidence", response_model=AnalysisEvidence)
async def get_demo_analysis_evidence(analysis_id: str):
    """Retrieve precomputed visual evidence assets for a given analysis ID."""
    evidence = demo_service.get_evidence_for_analysis(analysis_id)
    if not evidence:
        raise HTTPException(status_code=404, detail=f"Visual evidence for analysis '{analysis_id}' not found")
    return evidence


@router.get("/analyses/{analysis_id}/lab-metrics", response_model=AnalysisLabMetrics)
async def get_demo_analysis_lab_metrics(analysis_id: str):
    """Retrieve exploratory lab metrics and precomputed distributions for an analysis."""
    metrics = demo_service.get_lab_metrics_for_analysis(analysis_id)
    if not metrics:
        raise HTTPException(status_code=404, detail=f"Lab metrics for analysis '{analysis_id}' not found")
    return metrics


@router.get("/analyses/{analysis_id}/regions", response_model=list[ChangeRegion])
async def get_demo_regions_for_analysis(analysis_id: str):
    """Retrieve detected change regions for a given analysis ID."""
    analysis = demo_service.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Synthetic analysis '{analysis_id}' not found")
    return demo_service.get_regions_for_analysis(analysis_id)


@router.get("/regions/{region_id}/candidates", response_model=list[CandidateMatch])
async def get_demo_candidates_for_region(region_id: str):
    """Retrieve candidate domain matches for a specific change region."""
    candidates = demo_service.get_candidates_for_region(region_id)
    return candidates


@router.get("/manifests/{manifest_id}", response_model=AnalysisManifest)
async def get_demo_manifest(manifest_id: str):
    """Retrieve a synthetic analysis manifest provenance record by ID."""
    manifest = demo_service.get_manifest(manifest_id)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Synthetic manifest '{manifest_id}' not found")
    return manifest


@router.get("/change-regions.geojson", response_class=JSONResponse)
async def get_change_regions_geojson() -> Any:
    """
    Returns synthetic change region polygons as a standard GeoJSON FeatureCollection.
    Ready for consumption by MapLibre GL.
    """
    return JSONResponse(
        content=demo_service.get_change_regions_geojson(),
        media_type="application/geo+json"
    )


@router.post("/inspect-area", response_model=AreaInspectionResponse)
async def inspect_area(request: AreaInspectionRequest):
    """
    Inspect a selected point or drawn polygon area against stored synthetic demo analyses.
    
    Returns structured matches containing AOI, Analysis, Event, Candidate Interpretations,
    and Provenance metadata.
    """
    return demo_service.inspect_geometry(
        geometry=request.geometry,
        selection_type=request.selection_type,
        aoi_id=request.aoi_id
    )
