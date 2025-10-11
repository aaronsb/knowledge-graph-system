"""
Authentication Dependencies (ADR-027)

FastAPI dependency injection for authentication and authorization.

Provides:
- get_current_user: Extract and validate JWT token
- get_current_active_user: Ensure user is not disabled
- require_role: Check user has required role
- get_api_key_user: Authenticate via API key
"""

import os
from typing import Optional, Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
import psycopg2

from src.api.lib.auth import decode_access_token, verify_api_key
from src.api.models.auth import UserInDB, TokenData


# =============================================================================
# Security Schemes
# =============================================================================

# OAuth2 password flow (for JWT tokens)
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login",
    scheme_name="JWT",
    description="JWT token from /auth/login"
)

# HTTP Bearer (for API keys)
api_key_scheme = HTTPBearer(
    scheme_name="API Key",
    description="API key from /auth/api-keys"
)


# =============================================================================
# Database Connection Helper
# =============================================================================

def get_db_connection():
    """
    Get PostgreSQL database connection.

    Uses environment variables for configuration.
    """
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "knowledge_graph"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD", "password")
    )


# =============================================================================
# User Retrieval
# =============================================================================

def get_user_by_username(username: str) -> Optional[UserInDB]:
    """
    Retrieve user from database by username.

    Args:
        username: Username to look up

    Returns:
        UserInDB instance if found, None otherwise
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, username, password_hash, role, created_at, last_login, disabled
                FROM kg_auth.users
                WHERE username = %s
            """, (username,))

            row = cur.fetchone()
            if row is None:
                return None

            return UserInDB(
                id=row[0],
                username=row[1],
                password_hash=row[2],
                role=row[3],
                created_at=row[4],
                last_login=row[5],
                disabled=row[6]
            )
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[UserInDB]:
    """
    Retrieve user from database by ID.

    Args:
        user_id: User ID to look up

    Returns:
        UserInDB instance if found, None otherwise
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, username, password_hash, role, created_at, last_login, disabled
                FROM kg_auth.users
                WHERE id = %s
            """, (user_id,))

            row = cur.fetchone()
            if row is None:
                return None

            return UserInDB(
                id=row[0],
                username=row[1],
                password_hash=row[2],
                role=row[3],
                created_at=row[4],
                last_login=row[5],
                disabled=row[6]
            )
    finally:
        conn.close()


# =============================================================================
# JWT Token Authentication
# =============================================================================

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> UserInDB:
    """
    Get current user from JWT token.

    Validates JWT token and retrieves user from database.

    Args:
        token: JWT token from Authorization header

    Returns:
        UserInDB instance

    Raises:
        HTTPException 401: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Decode JWT token
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    # Extract username from token
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    # Get user from database
    user = get_user_by_username(username)
    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: Annotated[UserInDB, Depends(get_current_user)]
) -> UserInDB:
    """
    Get current active user (not disabled).

    Args:
        current_user: Current user from get_current_user

    Returns:
        UserInDB instance

    Raises:
        HTTPException 403: If user account is disabled
    """
    if current_user.disabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    return current_user


# =============================================================================
# API Key Authentication
# =============================================================================

async def get_api_key_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(api_key_scheme)]
) -> UserInDB:
    """
    Authenticate user via API key.

    Validates API key and retrieves associated user.

    Args:
        credentials: HTTP Bearer credentials containing API key

    Returns:
        UserInDB instance

    Raises:
        HTTPException 401: If API key is invalid or expired
    """
    api_key = credentials.credentials

    # Check if this looks like an API key
    if not api_key.startswith("kg_sk_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Find API key in database
            cur.execute("""
                SELECT k.id, k.key_hash, k.user_id, k.expires_at,
                       u.id, u.username, u.password_hash, u.role,
                       u.created_at, u.last_login, u.disabled
                FROM kg_auth.api_keys k
                JOIN kg_auth.users u ON k.user_id = u.id
                WHERE k.key_hash = crypt(%s, k.key_hash)
            """, (api_key,))

            row = cur.fetchone()
            if row is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Check expiration
            key_id, key_hash, user_id, expires_at = row[0], row[1], row[2], row[3]
            if expires_at and expires_at < psycopg2.Timestamp.now():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key has expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Update last_used timestamp
            cur.execute("""
                UPDATE kg_auth.api_keys
                SET last_used = NOW()
                WHERE id = %s
            """, (key_id,))
            conn.commit()

            # Return user
            return UserInDB(
                id=row[4],
                username=row[5],
                password_hash=row[6],
                role=row[7],
                created_at=row[8],
                last_login=row[9],
                disabled=row[10]
            )
    finally:
        conn.close()


# =============================================================================
# Flexible Authentication (JWT or API Key)
# =============================================================================

async def get_current_user_flexible(
    token: Annotated[str, Depends(oauth2_scheme)] = None
) -> UserInDB:
    """
    Get current user from either JWT token or API key.

    Tries JWT first, falls back to API key if JWT fails and token looks like API key.

    Args:
        token: JWT token or API key from Authorization header

    Returns:
        UserInDB instance

    Raises:
        HTTPException 401: If authentication fails
    """
    # Try JWT first
    try:
        payload = decode_access_token(token)
        if payload is not None:
            username = payload.get("sub")
            if username:
                user = get_user_by_username(username)
                if user:
                    return user
    except:
        pass

    # If token looks like API key, try API key auth
    if token and token.startswith("kg_sk_"):
        from fastapi.security import HTTPAuthorizationCredentials
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        return await get_api_key_user(credentials)

    # Both failed
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


# =============================================================================
# Role-Based Access Control
# =============================================================================

def require_role(*allowed_roles: str):
    """
    Dependency factory for role-based access control.

    Usage:
        @router.get("/admin/users", dependencies=[Depends(require_role("admin"))])
        async def list_users():
            ...

    Args:
        *allowed_roles: Roles that are allowed to access the endpoint

    Returns:
        Dependency function that checks user role
    """
    async def check_role(
        current_user: Annotated[UserInDB, Depends(get_current_active_user)]
    ) -> UserInDB:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(allowed_roles)}"
            )
        return current_user

    return check_role


def check_permission(user: UserInDB, resource: str, action: str) -> bool:
    """
    Check if user has permission for action on resource.

    Queries kg_auth.role_permissions table.

    Args:
        user: User to check permissions for
        resource: Resource name (concepts, vocabulary, jobs, users)
        action: Action (read, write, delete, approve)

    Returns:
        True if permission granted, False otherwise
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT granted
                FROM kg_auth.role_permissions
                WHERE role = %s AND resource = %s AND action = %s
            """, (user.role, resource, action))

            row = cur.fetchone()
            return row[0] if row else False
    finally:
        conn.close()


async def require_permission(resource: str, action: str):
    """
    Dependency factory for permission-based access control.

    Usage:
        @router.delete("/concepts/{id}")
        async def delete_concept(
            id: str,
            _: Annotated[UserInDB, Depends(require_permission("concepts", "delete"))]
        ):
            ...

    Args:
        resource: Resource name
        action: Action name

    Returns:
        Dependency function that checks permission
    """
    async def check_user_permission(
        current_user: Annotated[UserInDB, Depends(get_current_active_user)]
    ) -> UserInDB:
        if not check_permission(current_user, resource, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {action} on {resource}"
            )
        return current_user

    return check_user_permission
