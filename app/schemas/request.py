"""
Request schemas: contracts for data the AI Agent sends to the microservice.
Uses Pydantic v2 models with strict type hints.
"""

from pydantic import BaseModel, HttpUrl


class PlatformTask(BaseModel):
    """
    A single task targeting one video URL on a specific platform.

    Attributes:
        url: Full video URL.
        platform: Lowercase platform identifier (e.g., "youtube").
        user_handle: The content creator handle that owns this video.
    """

    url: HttpUrl
    platform: str
    user_handle: str


class AnalysisBatchRequest(BaseModel):
    """
    Batch request sent by the AI Agent.

    Attributes:
        job_id: Unique identifier for this analysis job.
        deep_analysis: When True, fetch comment samples per video.
        tasks: List of platform-specific video URL tasks, possibly
               spanning multiple users and platforms.
    """

    job_id: str
    deep_analysis: bool = False
    tasks: list[PlatformTask]
