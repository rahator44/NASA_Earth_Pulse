"""
NISAR Surface Change Explorer
NASA Space Apps Challenge Demo Application
Integrated Demo: Human-Readable NISAR Surface Change Explorer
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes import (
    home,
    map as map_route,
    events,
    copilot,
    lab,
    dashboard,
    methods,
    settings,
    demo_api,
    coverage_api,
    location_api,
    situation_api,
    dev_reload,
)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="NISAR Surface Change Explorer",
    description="Interactive Earth-observation demo for visualizing and explaining Earth surface changes using NISAR observations.",
    version="1.0.0-demo",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Mount static assets
static_dir = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Register page routers
app.include_router(home.router)
app.include_router(map_route.router)
app.include_router(events.router)
app.include_router(copilot.router)
app.include_router(lab.router)
app.include_router(dashboard.router)
app.include_router(methods.router)
app.include_router(settings.router)

# Register API routers
app.include_router(demo_api.router)
app.include_router(coverage_api.router)
app.include_router(location_api.router)
app.include_router(situation_api.router)
app.include_router(dev_reload.router)


@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "healthy",
        "app": "NISAR Surface Change Explorer",
        "phase": "Integrated demo with real NISAR showcase and situation interpreter",
        "version": "1.0.0-demo",
    }
