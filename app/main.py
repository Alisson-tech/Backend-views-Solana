"""
FastAPI application entrypoint.
Initializes the app and registers all routers.
"""

import logging

from fastapi import FastAPI

from app.api.endpoints import router as analysis_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

app = FastAPI(
    title="Social Media Metrics Microservice",
    description=(
        "High-performance bridge between an AI Agent and social media APIs. "
        "Processes batches of heterogeneous video URLs concurrently and "
        "returns unified, normalized metrics."
    ),
    version="0.1.0",
)

app.include_router(analysis_router)


@app.get("/health", tags=["infra"])
async def health_check() -> dict[str, str]:
    """Simple liveness probe."""
    return {"status": "ok"}
