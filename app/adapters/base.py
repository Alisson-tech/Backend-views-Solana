"""
Abstract base class defining the contract every platform adapter must follow.
This ensures the orchestration layer remains platform-agnostic.
"""

from abc import ABC, abstractmethod

from app.schemas.request import PlatformTask
from app.schemas.response import VideoResult


class SocialPlatform(ABC):
    """
    Interface for platform-specific adapters.

    Each adapter must implement `process_batch` to handle a list
    of tasks for its platform and return normalized VideoResult objects.
    """

    @abstractmethod
    async def process_batch(
        self,
        tasks: list[PlatformTask],
        deep_analysis: bool,
    ) -> list[VideoResult]:
        """
        Process a batch of URLs specific to this platform.

        Args:
            tasks: List of platform tasks containing URLs.
            deep_analysis: Whether to fetch comment samples.

        Returns:
            List of normalized VideoResult objects.
        """
        ...
