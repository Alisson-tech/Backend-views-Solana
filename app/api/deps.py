"""
API dependencies for security and shared utilities.
Provides the API Key validation dependency used to protect routes.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.core.config import settings

api_key_header = APIKeyHeader(name="X-API-Key")


async def get_api_key(api_key: str = Depends(api_key_header)) -> str:
    """
    Validate the API key provided in the X-API-Key header.
    Raises HTTP 401 if the key is missing or invalid.
    """
    if api_key != settings.APP_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )
    return api_key
