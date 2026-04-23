"""
Unit tests for YouTube adapter and orchestrator with user-grouped batching.

All YouTube API interactions are mocked — the test suite NEVER hits the
real YouTube API, preserving quota and enabling offline execution.
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.adapters.youtube import YouTubeAdapter
from app.schemas.request import AnalysisBatchRequest, PlatformTask
from app.services.orchestrator import run_batch_analysis


# =====================================================================
# YouTube Adapter Tests
# =====================================================================


@pytest.mark.asyncio
async def test_youtube_adapter_parses_statistics_correctly() -> None:
    """Verify that a mocked videos().list response is correctly normalized."""
    tasks = [
        PlatformTask(
            url="https://youtube.com/watch?v=mock1",
            platform="youtube",
            user_handle="@CorteMestre",
        ),
    ]
    adapter = YouTubeAdapter()

    mock_response: dict = {
        "items": [
            {
                "id": "mock1",
                "snippet": {"title": "Mocked Analytics Video"},
                "statistics": {
                    "viewCount": "1000",
                    "likeCount": "50",
                    "commentCount": "5",
                },
            }
        ]
    }

    with patch.object(
        adapter, "_execute_fetch", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = mock_response
        results = await adapter.process_batch(tasks, deep_analysis=False)

    assert len(results) == 1
    assert results[0].video_id == "mock1"
    assert results[0].title == "Mocked Analytics Video"
    assert results[0].user_handle == "@CorteMestre"
    assert results[0].metrics.views == 1000
    assert results[0].metrics.likes == 50
    assert results[0].metrics.comments == 5
    assert results[0].platform == "youtube"
    assert results[0].comment_sample == []


@pytest.mark.asyncio
async def test_youtube_adapter_handles_missing_video() -> None:
    """When the API returns no items, the adapter should return an empty list."""
    tasks = [
        PlatformTask(
            url="https://youtube.com/watch?v=gone123",
            platform="youtube",
            user_handle="@UserGone",
        ),
    ]
    adapter = YouTubeAdapter()

    mock_response: dict = {"items": []}

    with patch.object(
        adapter, "_execute_fetch", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = mock_response
        results = await adapter.process_batch(tasks, deep_analysis=False)

    assert results == []


@pytest.mark.asyncio
async def test_youtube_adapter_batches_cross_user_correctly() -> None:
    """
    Verify cross-user batching: 75 videos from mixed users should
    result in exactly 2 _execute_fetch calls (50 + 25), NOT split per user.
    """
    tasks = []
    # 40 videos from @UserA
    for i in range(40):
        tasks.append(
            PlatformTask(
                url=f"https://youtube.com/watch?v=vidA{i:03d}___",
                platform="youtube",
                user_handle="@UserA",
            )
        )
    # 35 videos from @UserB
    for i in range(35):
        tasks.append(
            PlatformTask(
                url=f"https://youtube.com/watch?v=vidB{i:03d}___",
                platform="youtube",
                user_handle="@UserB",
            )
        )

    adapter = YouTubeAdapter()
    mock_response: dict = {"items": []}

    with patch.object(
        adapter, "_execute_fetch", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = mock_response
        await adapter.process_batch(tasks, deep_analysis=False)

    # 75 total videos / 50 per batch = 2 API calls (cross-user pooling)
    assert mock_fetch.call_count == 2


@pytest.mark.asyncio
async def test_youtube_adapter_reassociates_user_handles() -> None:
    """
    After a cross-user batch fetch, each video result must carry
    the correct user_handle from the original task.
    """
    tasks = [
        PlatformTask(
            url="https://youtube.com/watch?v=vidUserA01",
            platform="youtube",
            user_handle="@UserA",
        ),
        PlatformTask(
            url="https://youtube.com/watch?v=vidUserB01",
            platform="youtube",
            user_handle="@UserB",
        ),
    ]
    adapter = YouTubeAdapter()

    mock_response: dict = {
        "items": [
            {
                "id": "vidUserA01",
                "snippet": {"title": "UserA Video"},
                "statistics": {"viewCount": "100", "likeCount": "10", "commentCount": "1"},
            },
            {
                "id": "vidUserB01",
                "snippet": {"title": "UserB Video"},
                "statistics": {"viewCount": "200", "likeCount": "20", "commentCount": "2"},
            },
        ]
    }

    with patch.object(
        adapter, "_execute_fetch", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = mock_response
        results = await adapter.process_batch(tasks, deep_analysis=False)

    assert len(results) == 2

    result_a = next(r for r in results if r.video_id == "vidUserA01")
    result_b = next(r for r in results if r.video_id == "vidUserB01")

    assert result_a.user_handle == "@UserA"
    assert result_a.metrics.views == 100

    assert result_b.user_handle == "@UserB"
    assert result_b.metrics.views == 200


@pytest.mark.asyncio
async def test_youtube_adapter_deep_analysis_fetches_comments() -> None:
    """When deep_analysis=True, comments should be fetched and attached."""
    tasks = [
        PlatformTask(
            url="https://youtube.com/watch?v=cmtVid01",
            platform="youtube",
            user_handle="@Commenter",
        ),
    ]
    adapter = YouTubeAdapter()

    mock_video_response: dict = {
        "items": [
            {
                "id": "cmtVid01",
                "snippet": {"title": "Video with Comments"},
                "statistics": {
                    "viewCount": "500",
                    "likeCount": "10",
                    "commentCount": "3",
                },
            }
        ]
    }

    mock_comments = ["Great video!", "Very helpful", "Thanks!"]

    with (
        patch.object(
            adapter, "_execute_fetch", new_callable=AsyncMock
        ) as mock_fetch,
        patch.object(
            adapter, "_fetch_comments", new_callable=AsyncMock
        ) as mock_comments_fetch,
    ):
        mock_fetch.return_value = mock_video_response
        mock_comments_fetch.return_value = mock_comments
        results = await adapter.process_batch(tasks, deep_analysis=True)

    assert len(results) == 1
    assert results[0].comment_sample == ["Great video!", "Very helpful", "Thanks!"]


# =====================================================================
# Orchestrator Tests — User Grouping
# =====================================================================


@pytest.mark.asyncio
async def test_orchestrator_groups_results_by_user() -> None:
    """
    End-to-end test: send tasks for two users, verify the response
    is grouped by user_handle with correct aggregation.
    """
    request = AnalysisBatchRequest(
        job_id="job-multi-user",
        deep_analysis=False,
        tasks=[
            PlatformTask(
                url="https://youtube.com/watch?v=userA_vid1",
                platform="youtube",
                user_handle="@UserA",
            ),
            PlatformTask(
                url="https://youtube.com/watch?v=userA_vid2",
                platform="youtube",
                user_handle="@UserA",
            ),
            PlatformTask(
                url="https://youtube.com/watch?v=userB_vid1",
                platform="youtube",
                user_handle="@UserB",
            ),
        ],
    )

    mock_response: dict = {
        "items": [
            {
                "id": "userA_vid1",
                "snippet": {"title": "A1"},
                "statistics": {"viewCount": "100", "likeCount": "10", "commentCount": "1"},
            },
            {
                "id": "userA_vid2",
                "snippet": {"title": "A2"},
                "statistics": {"viewCount": "200", "likeCount": "20", "commentCount": "2"},
            },
            {
                "id": "userB_vid1",
                "snippet": {"title": "B1"},
                "statistics": {"viewCount": "300", "likeCount": "30", "commentCount": "3"},
            },
        ]
    }

    with patch(
        "app.adapters.youtube.YouTubeAdapter._execute_fetch",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        response = await run_batch_analysis(request)

    assert response.status == "success"
    assert response.job_id == "job-multi-user"
    assert len(response.summary) == 2

    # Find each user summary
    user_a = next(s for s in response.summary if s.user_handle == "@UserA")
    user_b = next(s for s in response.summary if s.user_handle == "@UserB")

    assert user_a.total_videos_analyzed == 2
    assert user_a.platforms == ["youtube"]
    assert len(user_a.videos) == 2

    assert user_b.total_videos_analyzed == 1
    assert user_b.platforms == ["youtube"]
    assert len(user_b.videos) == 1
    assert user_b.videos[0].metrics.views == 300
