"""
Authentication Routes (ADR-027, updated by ADR-054)

API endpoints for user authentication and management.

Public endpoints:
- POST /auth/register - Create new user

Authenticated endpoints:
- PUT /auth/me - Update own profile

Admin endpoints (requires OAuth token):
- GET /users/me - Get current user from OAuth token
- GET /users - List all users
- GET /users/{user_id} - Get user details
- PUT /users/{user_id} - Update user
- DELETE /users/{user_id} - Delete user

UNIFIED OAUTH AUTHENTICATION STRATEGY (ADR-054):
All clients use OAuth 2.0 flows - NO JWT sessions, NO multiple auth systems.

- kg CLI: Personal OAuth clients (POST /auth/oauth/clients/personal → client_credentials grant)
- MCP: Client credentials grant (POST /auth/oauth/token)
- viz-app: Authorization Code + PKCE flow (GET /auth/oauth/authorize → POST /auth/oauth/token)
- Third-party tools: Device authorization flow (POST /auth/oauth/device → POST /auth/oauth/token)

Future: External OAuth providers (Google, Microsoft, GitHub) for viz-app social login.

For all OAuth endpoints, see src/api/routes/oauth.py
"""

import os
from datetime import datetime
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
import psycopg2

from api.api.lib.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    validate_password_strength,
    generate_api_key,
    hash_api_key,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from api.api.models.auth import (
    UserCreate,
    UserRead,
    UserUpdate,
    UserInDB,
    UserListResponse,
    LoginRequest,
    LoginResponse,
    Token,
    APIKeyCreate,
    APIKeyRead,
    APIKeyResponse,
)
from api.api.dependencies.auth import (
    CurrentUser,
    get_current_user,
    get_current_active_user,
    get_db_connection,
    require_role,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
admin_router = APIRouter(prefix="/users", tags=["admin"])


# =============================================================================
# Public Endpoints (No Authentication)
# =============================================================================

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate):
    """
    Register a new user account.

    Password requirements:
    - Minimum 8 characters
    - Must contain uppercase, lowercase, digit, and special character

    Returns user details (password hash excluded).
    """
    # Validate password strength
    is_valid, error_message = validate_password_strength(user.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_message
        )

    # Hash password
    password_hash = get_password_hash(user.password)

    # Insert user into database
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check if username already exists
            cur.execute(
                "SELECT id FROM kg_auth.users WHERE username = %s",
                (user.username,)
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Username '{user.username}' already exists"
                )

            # Insert new user
            cur.execute("""
                INSERT INTO kg_auth.users (username, password_hash, primary_role, created_at)
                VALUES (%s, %s, %s, NOW())
                RETURNING id, username, primary_role, created_at, last_login, disabled
            """, (user.username, password_hash, user.role))

            row = cur.fetchone()
            conn.commit()

            return UserRead(
                id=row[0],
                username=row[1],
                role=row[2],
                created_at=row[3],
                last_login=row[4],
                disabled=row[5]
            )
    finally:
        conn.close()


# =============================================================================
# REMOVED: POST /auth/login (ADR-054 - Unified OAuth Architecture)
# =============================================================================
# ALL authentication (including viz-app) now uses OAuth 2.0 flows.
# This eliminates multiple auth systems and reduces attack surface.
#
# OAuth Flows by Client:
# - kg CLI: Personal OAuth clients (client_credentials grant)
#   → POST /auth/oauth/clients/personal → store client_id + client_secret
# - MCP: Client credentials grant (confidential client)
#   → POST /auth/oauth/token (grant_type=client_credentials)
# - viz-app: Authorization Code + PKCE flow
#   → GET /auth/oauth/authorize → POST /auth/oauth/token (grant_type=authorization_code)
# - Third-party tools: Device authorization flow
#   → POST /auth/oauth/device → POST /auth/oauth/token (grant_type=device_code)
#
# Future: External OAuth providers (Google, Microsoft, GitHub) for viz-app social login.
#
# See src/api/routes/oauth.py for all OAuth endpoints.


# =============================================================================
# Authenticated Endpoints (Require OAuth Token)
# =============================================================================

# =============================================================================
# REMOVED: GET /auth/me (ADR-054)
# =============================================================================
# Replaced by GET /users/me which uses OAuth token authentication
# See admin_router.get("/me") below


@router.put("/me", response_model=UserRead)
async def update_current_user_profile(
    update: UserUpdate,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)]
):
    """
    Update current user profile.

    Users can only update their own password.
    Role and disabled status can only be changed by admins.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Validate password if provided
            if update.password:
                is_valid, error_message = validate_password_strength(update.password)
                if not is_valid:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=error_message
                    )

                password_hash = get_password_hash(update.password)
                cur.execute("""
                    UPDATE kg_auth.users
                    SET password_hash = %s
                    WHERE id = %s
                """, (password_hash, current_user.id))

            # Non-admins cannot change role or disabled status
            if (update.role or update.disabled is not None) and current_user.role != 'admin':
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only admins can change role or disabled status"
                )

            conn.commit()

            # Return updated user
            cur.execute("""
                SELECT id, username, primary_role, created_at, last_login, disabled
                FROM kg_auth.users
                WHERE id = %s
            """, (current_user.id,))
            row = cur.fetchone()

            return UserRead(
                id=row[0],
                username=row[1],
                role=row[2],
                created_at=row[3],
                last_login=row[4],
                disabled=row[5]
            )
    finally:
        conn.close()


# =============================================================================
# API Key Management
# =============================================================================

# =============================================================================
# REMOVED: API Key Endpoints (ADR-054)
# =============================================================================
# API keys have been removed and replaced by OAuth 2.0 tokens:
# - GET /auth/api-keys -> GET /auth/oauth/tokens (admin)
# - POST /auth/api-keys -> OAuth token flows (device, authorization code, client credentials)
# - DELETE /auth/api-keys/{key_id} -> POST /auth/oauth/revoke
#
# OAuth tokens provide:
# - Client identification (know which app/tool accessed the API)
# - Per-client revocation (revoke web app without affecting CLI)
# - Refresh tokens (long-lived sessions without re-authentication)
# - Industry standard security properties
#
# See ADR-054: OAuth 2.0 Client Management for Multi-Client Authentication


# =============================================================================
# Admin User Management Endpoints
# =============================================================================

@admin_router.get("/me", response_model=UserRead)
async def get_current_user_from_oauth(
    current_user: CurrentUser
):
    """
    Get current user profile (ADR-054, ADR-060)

    **Authentication:** Requires valid OAuth token

    Replaces GET /auth/me (ADR-054).
    Returns user details for the authenticated user.
    """
    return UserRead(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
        disabled=current_user.disabled
    )


@admin_router.get("", response_model=UserListResponse)
async def list_users(
    current_user: CurrentUser,
    limit: int = 100,
    offset: int = 0
):
    """
    List all users (ADR-027, ADR-060)

    **Authentication:** Requires valid OAuth token

    Supports pagination and filtering by role.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Build query
            query = "SELECT id, username, primary_role, created_at, last_login, disabled FROM kg_auth.users"
            query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
            params = [limit, offset]

            cur.execute(query, params)
            users = []
            for row in cur.fetchall():
                users.append(UserRead(
                    id=row[0],
                    username=row[1],
                    role=row[2],
                    created_at=row[3],
                    last_login=row[4],
                    disabled=row[5]
                ))

            # Get total count
            cur.execute("SELECT COUNT(*) FROM kg_auth.users")
            total = cur.fetchone()[0]

            return UserListResponse(
                users=users,
                total=total,
                skip=offset,
                limit=limit
            )
    finally:
        conn.close()


@admin_router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: int,
    current_user: CurrentUser
):
    """
    Get user by ID (ADR-027, ADR-060)

    **Authentication:** Requires valid OAuth token
    **Authorization:** Users can view their own profile, admins can view any user
    """
    # Ownership check
    if current_user.id != user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own profile unless you are an admin"
        )

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, username, primary_role, created_at, last_login, disabled
                FROM kg_auth.users
                WHERE id = %s
            """, (user_id,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            return UserRead(
                id=row[0],
                username=row[1],
                role=row[2],
                created_at=row[3],
                last_login=row[4],
                disabled=row[5]
            )
    finally:
        conn.close()


@admin_router.put("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    update: UserUpdate,
    current_user: CurrentUser
):
    """
    Update user by ID (ADR-027, ADR-060)

    **Authentication:** Requires valid OAuth token
    **Authorization:** Users can update their own profile, admins can update any user

    Can update role, disabled status, and password.
    """
    # Ownership check
    if current_user.id != user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only update your own profile unless you are an admin"
        )

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check user exists
            cur.execute("SELECT id FROM kg_auth.users WHERE id = %s", (user_id,))
            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            # Build update query
            updates = []
            params = []

            if update.password:
                is_valid, error_message = validate_password_strength(update.password)
                if not is_valid:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=error_message
                    )
                updates.append("password_hash = %s")
                params.append(get_password_hash(update.password))

            if update.role:
                updates.append("primary_role = %s")
                params.append(update.role)

            if update.disabled is not None:
                updates.append("disabled = %s")
                params.append(update.disabled)

            if not updates:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="No fields to update"
                )

            params.append(user_id)
            cur.execute(
                f"UPDATE kg_auth.users SET {', '.join(updates)} WHERE id = %s",
                params
            )
            conn.commit()

            # Return updated user
            cur.execute("""
                SELECT id, username, primary_role, created_at, last_login, disabled
                FROM kg_auth.users
                WHERE id = %s
            """, (user_id,))
            row = cur.fetchone()

            return UserRead(
                id=row[0],
                username=row[1],
                role=row[2],
                created_at=row[3],
                last_login=row[4],
                disabled=row[5]
            )
    finally:
        conn.close()


@admin_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: CurrentUser,
    _: None = Depends(require_role("admin"))
):
    """
    Delete user by ID (Admin only - ADR-027, ADR-060)

    **Authentication:** Requires admin role

    Cannot delete yourself.
    Cascade deletes API keys, sessions, and OAuth tokens.
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself"
        )

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM kg_auth.users WHERE id = %s", (user_id,))
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            conn.commit()
    finally:
        conn.close()
