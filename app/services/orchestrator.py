"""
Service orchestrator responsible for:
  - Grouping incoming tasks by platform.
  - Delegating each group to its corresponding adapter (concurrently).
  - Re-grouping flat VideoResult lists by user_handle for the final output.
  - Running all adapter calls concurrently via asyncio.gather.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from app.adapters.factory import get_adapter
from app.schemas.request import AnalysisBatchRequest, PlatformTask
from app.schemas.response import (
    AnalysisBatchResponse,
    UserSummary,
    VideoResult,
)

logger = logging.getLogger(__name__)


def _group_results_by_user(results: list[VideoResult]) -> list[UserSummary]:
    """
    Group a flat list of VideoResult objects by their user_handle.

    Returns a list of UserSummary, each containing all videos for
    one content creator, the distinct platforms involved, and the
    total count of videos analyzed.
    """
    user_map: dict[str, list[VideoResult]] = defaultdict(list)
    for result in results:
        user_map[result.user_handle].append(result)

    summaries: list[UserSummary] = []
    for handle, videos in user_map.items():
        # Collect unique platforms for this user
        platforms = sorted({v.platform for v in videos})
        summaries.append(
            UserSummary(
                user_handle=handle,
                platforms=platforms,
                total_videos_analyzed=len(videos),
                videos=videos,
            )
        )

    return summaries


async def run_batch_analysis(
    request: AnalysisBatchRequest,
) -> AnalysisBatchResponse:
    """
    Orchestrate a full batch analysis across multiple platforms and users.

    Flow:
        1. Group tasks by their `platform` field.
        2. Resolve each platform to its adapter via the factory.
        3. Fire all adapter `process_batch` calls concurrently via
           asyncio.gather — this ensures @UserA and @UserB videos
           on different platforms are fetched simultaneously.
        4. Flatten results and re-group by user_handle.

    Args:
        request: The batch request from the AI Agent.

    Returns:
        An AnalysisBatchResponse with results grouped by user_handle.
    """
    # Step 1: Group tasks by platform
    grouped: dict[str, list[PlatformTask]] = defaultdict(list)
    for task in request.tasks:
        grouped[task.platform.lower()].append(task)

    # Step 2 & 3: Build coroutines and run concurrently
    coroutines = []
    platform_names: list[str] = []

    for platform, platform_tasks in grouped.items():
        try:
            adapter = get_adapter(platform)
        except ValueError:
            logger.warning("Skipping unsupported platform: %s", platform)
            continue

        coroutines.append(
            adapter.process_batch(platform_tasks, request.deep_analysis)
        )
        platform_names.append(platform)

    # Execute all platform adapters simultaneously
    gathered = await asyncio.gather(*coroutines, return_exceptions=True)

    # Step 4: Flatten and collect results
    all_results: list[VideoResult] = []
    for platform_name, result in zip(platform_names, gathered):
        if isinstance(result, BaseException):
            logger.error(
                "Adapter for '%s' raised an error: %s", platform_name, result
            )
            continue
        all_results.extend(result)

    # Step 5: Re-group by user_handle for the final response
    summary = _group_results_by_user(all_results)

    return AnalysisBatchResponse(
        status="success",
        job_id=request.job_id,
        summary=summary,
    )
