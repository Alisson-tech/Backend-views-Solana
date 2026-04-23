"""
API route definitions.
Exposes POST /api/v1/analyze for the AI Agent.
"""

from fastapi import APIRouter, HTTPException

from app.schemas.request import AnalysisBatchRequest
from app.schemas.response import AnalysisBatchResponse
from app.services.orchestrator import run_batch_analysis

router = APIRouter(prefix="/api/v1", tags=["analysis"])


@router.post("/analyze", response_model=AnalysisBatchResponse)
async def analyze_batch(request: AnalysisBatchRequest) -> AnalysisBatchResponse:
    """
    Receive a batch of video URLs from the AI Agent,
    analyze them concurrently, and return normalized results.
    """
    if not request.tasks:
        raise HTTPException(status_code=400, detail="No tasks provided.")

    response = await run_batch_analysis(request)
    return response
