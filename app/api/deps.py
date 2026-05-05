import secrets
from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from app.core.config import settings

# define the header scheme for Swagger UI
api_key_header = APIKeyHeader(
    name="X-API-Key", 
    auto_error=False,
    scheme_name="API Key Authentication",
    description="Your Quittung API Key (set via API_KEY in .env)"
)

async def get_api_key(api_key: str = Security(api_key_header)):
    """
    Dependency that validates the X-API-Key header.
    Returns the key if valid, otherwise raises 403.
    """
    if not settings.API_KEY:
        # If API_KEY is not configured, we don't allow any access
        # This is a safety measure to prevent unintentional open access
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API Key is not configured on the server",
        )

    if api_key and secrets.compare_digest(api_key, settings.API_KEY):
        return api_key
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Could not validate API Key",
    )
