"""
Authentication middleware (placeholder for Phase 2)

Current implementation: Optional header-based client identification
Future: API keys, JWT tokens, OAuth, etc.
"""

from fastapi import Header, HTTPException, Request
from typing import Optional, Annotated
import os


class AuthConfig:
    """Authentication configuration"""

    @staticmethod
    def is_enabled() -> bool:
        """Check if auth is enabled"""
        return os.getenv("AUTH_ENABLED", "false").lower() == "true"

    @staticmethod
    def require_client_id() -> bool:
        """Check if client_id is required"""
        return os.getenv("AUTH_REQUIRE_CLIENT_ID", "false").lower() == "true"

    @staticmethod
    def get_valid_api_keys() -> set:
        """Get valid API keys from environment"""
        keys = os.getenv("AUTH_API_KEYS", "")
        if not keys:
            return set()
        return set(key.strip() for key in keys.split(","))


async def get_current_user(
    x_client_id: Annotated[Optional[str], Header()] = None,
    x_api_key: Annotated[Optional[str], Header()] = None,
) -> dict:
    """
    Get current user/client info from headers.

    Phase 1 (placeholder):
    - Optional X-Client-ID header for multi-tenancy
    - Optional X-API-Key header for future auth
    - No actual validation (just logging/tracking)

    Phase 2 (future):
    - Validate API keys against database
    - Check permissions/roles
    - Rate limiting per client
    - JWT token support

    Headers:
        X-Client-ID: Optional client identifier
        X-API-Key: Optional API key (not validated yet)

    Returns:
        User/client info dict
    """

    # Phase 1: Just capture headers for tracking
    user_info = {
        "client_id": x_client_id or "anonymous",
        "api_key_provided": bool(x_api_key),
        "authenticated": False,  # Phase 1: always False
        "role": "user",  # Phase 2: get from database
    }

    # If auth is enabled (Phase 2 ready)
    if AuthConfig.is_enabled():
        # Require client_id
        if AuthConfig.require_client_id() and not x_client_id:
            raise HTTPException(
                status_code=401,
                detail="X-Client-ID header required. Set AUTH_ENABLED=false to disable."
            )

        # Validate API key if provided
        valid_keys = AuthConfig.get_valid_api_keys()
        if valid_keys:
            if not x_api_key:
                raise HTTPException(
                    status_code=401,
                    detail="X-API-Key header required"
                )
            if x_api_key not in valid_keys:
                raise HTTPException(
                    status_code=403,
                    detail="Invalid API key"
                )
            user_info["authenticated"] = True

    return user_info


async def verify_job_ownership(
    job_id: str,
    job: dict,
    current_user: dict
) -> None:
    """
    Verify user has access to job (placeholder for Phase 2).

    Phase 1: No enforcement (all jobs visible to all users)
    Phase 2: Check job.client_id == current_user.client_id

    Raises:
        HTTPException: If user doesn't own the job (Phase 2)
    """

    # Phase 1: No enforcement, just log intent
    if AuthConfig.is_enabled() and AuthConfig.require_client_id():
        job_client = job.get("client_id", "anonymous")
        user_client = current_user.get("client_id", "anonymous")

        if job_client != user_client:
            raise HTTPException(
                status_code=403,
                detail=f"Job {job_id} belongs to different client"
            )

    # Phase 1: Always allow access
    pass


# Placeholder for future role-based checks
def require_role(role: str):
    """
    Decorator for role-based access control (Phase 2).

    Usage:
        @router.post("/admin/reset")
        @require_role("admin")
        async def reset_database():
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Phase 2: Check user role
            # if current_user.role != role:
            #     raise HTTPException(403, "Insufficient permissions")
            return await func(*args, **kwargs)
        return wrapper
    return decorator
