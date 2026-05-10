"""
Response schemas: contracts for data the microservice returns to the AI Agent.
Uses Pydantic v2 models with strict type hints.

The final output is grouped by user_handle so the AI Agent can easily
compare and count metrics per content creator.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Metrics(BaseModel):
    """Normalized engagement metrics for a single video."""

    views: int
    likes: int
    comments: int


class VideoResult(BaseModel):
    """
    Result for a single analyzed video, normalized across platforms.

    Attributes:
        platform: Source platform (e.g., "youtube", "instagram").
        video_id: Platform-specific video identifier.
        title: Video title.
        user_handle: Content creator handle this video belongs to.
        youtube_channel: The visual channel name if available (e.g., from YouTube).
        youtube_channel_id: The unique channel ID if available (e.g., from YouTube).
        metrics: Engagement metrics.
        comment_sample: Sample comments when deep_analysis is enabled.
        normalized_at: Timestamp when the data was normalized.
    """

    platform: str
    video_id: str
    title: str = ""
    user_handle: str = ""
    youtube_channel: str | None = None
    youtube_channel_id: str | None = None
    metrics: Metrics
    comment_sample: list[str] = Field(default_factory=list)
    normalized_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )


class UserSummary(BaseModel):
    """
    Aggregated results for a single content creator.

    Groups all analyzed videos under one user_handle, listing
    the platforms involved and the total count of videos analyzed.
    """

    user_handle: str
    platforms: list[str]
    total_videos_analyzed: int
    videos: list[VideoResult]


class AnalysisBatchResponse(BaseModel):
    """
    Top-level response returned to the AI Agent.
    Results are grouped by user_handle in the `summary` field.
    """

    status: str
    job_id: str
    summary: list[UserSummary]
