# auth/api_key.py
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from config import settings

# ─── API Key Header ───────────────────────────────────────────────────────────

api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False
)


# ─── Validator ────────────────────────────────────────────────────────────────

async def verify_api_key(
    api_key: str = Security(api_key_header)
) -> str:
    """
    Validate the API key from request header.
    Raises 401 if missing or invalid.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Add 'X-API-Key' header.",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    if api_key not in settings.VALID_API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    return api_key


# ─── Optional validator (for public endpoints) ────────────────────────────────

async def optional_api_key(
    api_key: str = Security(api_key_header)
) -> str | None:
    """
    Optional API key — returns None if not provided.
    Use for public endpoints like /health.
    """
    if not api_key:
        return None
    if api_key not in settings.VALID_API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key."
        )
    return api_key