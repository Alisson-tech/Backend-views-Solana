"""
Request schemas: contracts for data the AI Agent sends to the microservice.
Uses Pydantic v2 models with strict type hints.
"""

from pydantic import BaseModel, HttpUrl


class VideoTask(BaseModel):
    """
    A single target video URL with its platform.
    """

    url: HttpUrl
    platform: str


class UserTaskGroup(BaseModel):
    """
    A group of video tasks belonging to a specific user.
    """

    user_handle: str
    videos: list[VideoTask]


class AnalysisBatchRequest(BaseModel):
    """
    Batch request sent by the AI Agent.

    Attributes:
        job_id: Unique identifier for this analysis job.
        deep_analysis: When True, fetch comment samples per video.
        tasks: List of task groups, each containing a user handle
               and their associated video URLs and platforms.
    """

    job_id: str
    deep_analysis: bool = False
    tasks: list[UserTaskGroup]
