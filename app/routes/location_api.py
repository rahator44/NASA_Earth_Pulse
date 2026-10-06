"""Place and coordinate search API, separate from NISAR archive discovery."""
from fastapi import APIRouter, HTTPException, Query

from app.services.location_search import (
    InvalidCoordinates,
    UNAVAILABLE_MESSAGE,
    location_search_service,
)

router = APIRouter(prefix="/api/locations", tags=["location-search"])


@router.get("/search")
async def search_location(q: str = Query(..., min_length=1, max_length=200)):
    try:
        results = await location_search_service.search(q)
    except InvalidCoordinates as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(status_code=503, detail=UNAVAILABLE_MESSAGE) from None
    return {"results": results}
