#!/usr/bin/env python3
"""
Launcher for NISAR Surface Change Explorer with optimized auto-reloading.
Restricts watchfiles to the app/ directory to avoid inotify exhaustion on Linux.
Usage: python run.py
"""
from pathlib import Path
import uvicorn

BASE_DIR = Path(__file__).resolve().parent

if __name__ == "__main__":
    print("=" * 65)
    print("  NISAR Surface Change Explorer")
    print("  Server: http://localhost:8000")
    print("  Live Auto-Reload: ENABLED (watching app/ directory)")
    print("=" * 65)
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(BASE_DIR / "app")],
        reload_includes=["*.py", "*.html", "*.css", "*.js", "*.json"],
        reload_excludes=[
            ".venv/*",
            "data/*",
            "docs/*",
            "tests/*",
            "*.pyc",
            "__pycache__/*",
            ".pytest_cache/*",
            "*.h5",
            "*.tif",
            "*.tiff",
            "*.log",
        ],
    )
