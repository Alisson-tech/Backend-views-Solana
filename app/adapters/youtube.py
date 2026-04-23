"""
YouTube platform adapter.

Implements batch video statistics fetching with YouTube Data API v3,
optimizing quota usage by batching up to 50 video IDs per request
(the maximum allowed by the `videos().list` endpoint).

IMPORTANT — Cross-user batching:
All video IDs from all users are pooled together into a single batch
queue. This means if @UserA sends 30 videos and @UserB sends 40 videos,
they are merged into one batch of 50 + one batch of 20, yielding only
2 API calls instead of the naive 2 + 1 = 3 calls. After the API
responds, each result is re-associated with its original user_handle
via the id_to_user_handle mapping.

Comment sampling (deep_analysis) fires individual `commentThreads().list`
requests concurrently via asyncio.gather.
"""

from __future__ import annotations

import asyncio
import logging
import re
from functools import lru_cache
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.adapters.base import SocialPlatform
from app.core.config import settings
from app.schemas.request import PlatformTask
from app.schemas.response import Metrics, VideoResult

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# YouTube API quota batch limit: the `videos().list` endpoint accepts
# a comma-separated list of up to 50 video IDs in a single request.
# Batching this way converts N individual API calls into ceil(N/50)
# calls, dramatically reducing quota consumption.
# ------------------------------------------------------------------
_YOUTUBE_BATCH_SIZE: int = 50

# Regex pattern for extracting YouTube video IDs from various URL formats
_YT_VIDEO_ID_PATTERN = re.compile(
    r"(?:v=|youtu\.be/|/embed/|/v/|/shorts/)([a-zA-Z0-9_-]{11})"
)


def _extract_video_id(url: str) -> str | None:
    """
    Extract a YouTube video ID from a URL.

    Supports formats:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://www.youtube.com/embed/VIDEO_ID
        - https://www.youtube.com/shorts/VIDEO_ID

    Returns:
        The 11-character video ID, or None if extraction fails.
    """
    match = _YT_VIDEO_ID_PATTERN.search(url)
    if match:
        return match.group(1)

    # Fallback: try query string parsing
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    ids = query_params.get("v")
    return ids[0] if ids else None


def _build_youtube_service() -> Any:
    """
    Build the YouTube Data API v3 service client.

    Uses `google-api-python-client` which is synchronous under the hood;
    actual network calls are wrapped in `asyncio.to_thread` to avoid
    blocking the event loop.
    """
    from googleapiclient.discovery import build

    return build("youtube", "v3", developerKey=settings.YOUTUBE_API_KEY)


class YouTubeAdapter(SocialPlatform):
    """
    Adapter for fetching video metrics from the YouTube Data API v3.

    Key optimizations:
        - Video statistics are fetched in batches of 50 IDs per request,
          which is the maximum the API allows. This reduces quota cost
          from N calls down to ceil(N / 50).
        - IDs from ALL users are pooled into the same batches, maximizing
          quota efficiency. Results are re-associated via id_to_user_handle.
        - Comment sampling requests are fired concurrently via asyncio.gather.
    """

    # ----------------------------------------------------------------
    # Public interface
    # ----------------------------------------------------------------

    async def process_batch(
        self,
        tasks: list[PlatformTask],
        deep_analysis: bool,
    ) -> list[VideoResult]:
        """
        Process a batch of YouTube URLs and return normalized results.

        Steps:
            1. Extract video IDs from ALL task URLs (cross-user).
            2. Build a video_id -> user_handle mapping for re-association.
            3. Chunk IDs into groups of 50 (YouTube batch quota limit).
            4. Fetch statistics for each chunk via `_execute_fetch`.
            5. Re-associate each result with its user_handle.
            6. Optionally fetch comment samples if deep_analysis is True.
        """
        # Step 1 & 2: Extract video IDs and build the user_handle mapping.
        # All IDs are pooled regardless of user — this is critical for
        # quota optimization. For example, 30 videos from @UserA and
        # 40 from @UserB are merged into batches of 50, not split per user.
        id_to_user_handle: dict[str, str] = {}
        for task in tasks:
            vid = _extract_video_id(str(task.url))
            if vid:
                id_to_user_handle[vid] = task.user_handle
            else:
                logger.warning("Could not extract video ID from URL: %s", task.url)

        if not id_to_user_handle:
            return []

        video_ids = list(id_to_user_handle.keys())

        # Step 3 & 4: fetch statistics in batches of 50
        # ------------------------------------------------------------------
        # YouTube batch quota: each `videos().list` call with the `id`
        # parameter accepts up to 50 comma-separated IDs. By batching,
        # we turn potentially hundreds of API calls into just a few.
        # ------------------------------------------------------------------
        all_items: list[dict[str, Any]] = []
        for i in range(0, len(video_ids), _YOUTUBE_BATCH_SIZE):
            chunk = video_ids[i : i + _YOUTUBE_BATCH_SIZE]
            response = await self._execute_fetch(chunk)
            all_items.extend(response.get("items", []))

        # Step 5: Build results and re-associate each video with its user_handle
        results: list[VideoResult] = []
        for item in all_items:
            video_id = item.get("id", "")
            user_handle = id_to_user_handle.get(video_id, "")
            result = self._parse_video_item(item, user_handle=user_handle)
            results.append(result)

        # Step 6: Optionally fetch comments concurrently
        if deep_analysis:
            # Fire comment fetch requests concurrently for all videos
            comment_tasks = [
                self._fetch_comments(r.video_id) for r in results
            ]
            comment_results = await asyncio.gather(
                *comment_tasks, return_exceptions=True
            )
            for result, comments in zip(results, comment_results):
                if isinstance(comments, list):
                    result.comment_sample = comments

        return results

    # ----------------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------------

    async def _execute_fetch(self, video_ids: list[str]) -> dict[str, Any]:
        """
        Execute a single YouTube `videos().list` API call for up to 50 IDs.

        The google-api-python-client is synchronous, so we run it in a
        thread pool to prevent blocking the asyncio event loop.

        Args:
            video_ids: List of up to 50 YouTube video IDs.

        Returns:
            Raw JSON response from the YouTube Data API.
        """
        service = _build_youtube_service()

        # Join IDs into a comma-separated string for the batch request.
        # The `id` parameter accepts up to 50 IDs — this is the key
        # optimization for quota efficiency.
        ids_param = ",".join(video_ids)

        request = service.videos().list(
            part="snippet,statistics",
            id=ids_param,
        )

        # Run synchronous HTTP call in a thread to keep the event loop free
        response: dict[str, Any] = await asyncio.to_thread(request.execute)
        return response

    async def _fetch_comments(
        self, video_id: str, max_results: int = 20
    ) -> list[str]:
        """
        Fetch a sample of comments for a single video.

        Retrieves up to `max_results` top-level comments ordered by
        relevance. The plan targets top 10 + bottom 10 comments;
        this initial implementation fetches the top N by relevance.

        Args:
            video_id: YouTube video ID.
            max_results: Number of comment threads to retrieve.

        Returns:
            List of comment text strings.
        """
        service = _build_youtube_service()

        request = service.commentThreads().list(
            part="snippet",
            videoId=video_id,
            order="relevance",
            maxResults=max_results,
            textFormat="plainText",
        )

        try:
            response: dict[str, Any] = await asyncio.to_thread(request.execute)
        except Exception:
            logger.exception("Failed to fetch comments for video %s", video_id)
            return []

        comments: list[str] = []
        for item in response.get("items", []):
            text = (
                item.get("snippet", {})
                .get("topLevelComment", {})
                .get("snippet", {})
                .get("textDisplay", "")
            )
            if text:
                comments.append(text)

        return comments

    @staticmethod
    def _parse_video_item(
        item: dict[str, Any],
        user_handle: str = "",
    ) -> VideoResult:
        """
        Parse a single YouTube API video item into a normalized VideoResult.

        Args:
            item: A single element from the `items` array of a
                  `videos().list` response.
            user_handle: The content creator handle to associate with
                         this video result.

        Returns:
            A VideoResult with normalized metrics and user_handle.
        """
        stats = item.get("statistics", {})
        snippet = item.get("snippet", {})

        return VideoResult(
            platform="youtube",
            video_id=item.get("id", ""),
            title=snippet.get("title", ""),
            user_handle=user_handle,
            metrics=Metrics(
                views=int(stats.get("viewCount", 0)),
                likes=int(stats.get("likeCount", 0)),
                comments=int(stats.get("commentCount", 0)),
            ),
        )
