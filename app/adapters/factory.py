"""
Factory pattern for dynamically instantiating the correct platform adapter
based on the platform identifier from the request payload.
"""

from app.adapters.base import SocialPlatform
from app.adapters.youtube import YouTubeAdapter

# Registry mapping platform identifiers to their adapter classes.
# Extend this dictionary when adding new platforms.
_ADAPTER_REGISTRY: dict[str, type[SocialPlatform]] = {
    "youtube": YouTubeAdapter,
    # "instagram": InstagramAdapter,
    # "tiktok": TikTokAdapter,
}


def get_adapter(platform: str) -> SocialPlatform:
    """
    Return an adapter instance for the given platform.

    Args:
        platform: Lowercase platform identifier (e.g., "youtube").

    Returns:
        An instance of the corresponding SocialPlatform adapter.

    Raises:
        ValueError: If the platform is not supported.
    """
    adapter_cls = _ADAPTER_REGISTRY.get(platform.lower())
    if adapter_cls is None:
        supported = ", ".join(sorted(_ADAPTER_REGISTRY.keys()))
        raise ValueError(
            f"Unsupported platform '{platform}'. Supported: {supported}"
        )
    return adapter_cls()
