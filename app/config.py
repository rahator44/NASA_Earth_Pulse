"""Application configuration exposed safely to frontend templates."""
import os
import re


_PUBLIC_MAPBOX_TOKEN = re.compile(r"pk\.[A-Za-z0-9._~-]{20,2048}\Z")


def get_mapbox_public_token() -> str:
    """Return a well-formed public Mapbox token; never expose secret tokens."""
    token = os.getenv("MAPBOX_PUBLIC_TOKEN", "").strip()
    return token if _PUBLIC_MAPBOX_TOKEN.fullmatch(token) else ""
