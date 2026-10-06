"""Single-query OSM Nominatim search with coordinate parsing and local caching."""
import asyncio
import re
import time
from typing import Any

import httpx


COORDINATE_QUERY = re.compile(
    r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*,\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*$"
)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "NISAR-Surface-Change-Explorer-SpaceApps/1.0"
UNAVAILABLE_MESSAGE = (
    "Place search is temporarily unavailable. You can still enter coordinates "
    "or select an area directly on the map."
)


class InvalidCoordinates(ValueError):
    pass


class LocationSearchService:
    def __init__(self) -> None:
        self._cache: dict[str, list[dict[str, Any]]] = {}
        self._request_lock = asyncio.Lock()
        self._last_request_at = 0.0

    async def search(self, query: str) -> list[dict[str, Any]]:
        normalized = " ".join(query.strip().split()).casefold()
        if not normalized:
            raise ValueError("Enter a place name or latitude, longitude.")

        coordinate_match = COORDINATE_QUERY.fullmatch(query)
        if coordinate_match:
            lat, lon = map(float, coordinate_match.groups())
            if not -90 <= lat <= 90:
                raise InvalidCoordinates("Latitude must be between -90 and 90.")
            if not -180 <= lon <= 180:
                raise InvalidCoordinates("Longitude must be between -180 and 180.")
            return [{
                "name": query.strip(), "lat": lat, "lon": lon, "source": "coordinates"
            }]

        if normalized in self._cache:
            return [dict(item) for item in self._cache[normalized]]

        async with self._request_lock:
            if normalized in self._cache:
                return [dict(item) for item in self._cache[normalized]]
            delay = 1.0 - (time.monotonic() - self._last_request_at)
            if delay > 0:
                await asyncio.sleep(delay)
            self._last_request_at = time.monotonic()
            results = (await self._request_nominatim(query.strip()))[:5]
            self._cache[normalized] = results
            return [dict(item) for item in results]

    async def _request_nominatim(self, query: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        ) as client:
            response = await client.get(
                NOMINATIM_URL,
                params={"q": query, "format": "jsonv2", "limit": 5},
            )
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, list):
            raise ValueError("Unexpected place-search response")
        normalized_results = []
        for item in payload[:5]:
            if not isinstance(item, dict):
                continue
            try:
                lat, lon = float(item["lat"]), float(item["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue
            normalized_results.append({
                "name": str(item.get("display_name") or f"{lat:.5f}, {lon:.5f}"),
                "lat": lat,
                "lon": lon,
                "source": "nominatim",
            })
        return normalized_results


location_search_service = LocationSearchService()
