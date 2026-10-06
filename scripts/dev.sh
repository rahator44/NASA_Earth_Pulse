#!/usr/bin/env bash
set -e

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run the FastAPI server via uvicorn with scoped autoreload
exec python run.py
