"""
Authentication Routes (ADR-027)

API endpoints for user authentication and management.

Public endpoints:
- POST /auth/register - Create new user
- POST /auth/login - User login

Authenticated endpoints:
- GET /auth/me - Get current user profile
- PUT /auth/me - Update own profile
- POST /auth/logout - Logout (optional)
- GET /auth/api-keys - List own API keys
- POST /auth/api-keys - Create API key
- DELETE /auth/api-keys/{key_id} - Revoke API key

Admin endpoints:
- GET /users - List all users
- GET /users/{user_id} - Get user details
- PUT /users/{user_id} - Update user
- DELETE /users/{user_id} - Delete user
"""

import os
from datetime import datetime
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
import psycopg2

from src.api.lib.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    validate_password_strength,
    generate_api_key,
    hash_api_key,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from src.api.models.auth import (
    UserCreate,
    UserRead,
    UserUpdate,
    UserInDB,
    UserListResponse,
    LoginResponse,
    Token,
    APIKeyCreate,
    APIKeyRead,
    APIKeyResponse,
)
from src.api.dependencies.auth import (
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


@router.post("/login", response_model=LoginResponse)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """
    User login with username and password.

    Returns JWT access token and user details.

    OAuth2 password flow compatible (for OpenAPI docs).
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Get user from database
            cur.execute("""
                SELECT id, username, password_hash, primary_role, created_at, last_login, disabled
                FROM kg_auth.users
                WHERE username = %s
            """, (form_data.username,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            user = UserInDB(
                id=row[0],
                username=row[1],
                password_hash=row[2],
                role=row[3],
                created_at=row[4],
                last_login=row[5],
                disabled=row[6]
            )

            # Verify password
            if not verify_password(form_data.password, user.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Check if user is disabled
            if user.disabled:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is disabled"
                )

            # Update last_login timestamp
            cur.execute("""
                UPDATE kg_auth.users
                SET last_login = NOW()
                WHERE id = %s
            """, (user.id,))
            conn.commit()

            # Create JWT token
            access_token = create_access_token(
                data={"sub": user.username, "role": user.role}
            )

            return LoginResponse(
                access_token=access_token,
                token_type="bearer",
                expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                user=UserRead(
                    id=user.id,
                    username=user.username,
                    role=user.role,
                    created_at=user.created_at,
                    last_login=datetime.now(),
                    disabled=user.disabled
                )
            )
    finally:
        conn.close()


# =============================================================================
# Authenticated Endpoints (Require JWT Token)
# =============================================================================

@router.get("/me", response_model=UserRead)
async def get_current_user_profile(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)]
):
    """
    Get current user profile.

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

@router.get("/api-keys", response_model=List[APIKeyRead])
async def list_api_keys(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)]
):
    """
    List current user's API keys.

    Returns list of API keys (plaintext key NOT included).
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, scopes, created_at, last_used, expires_at
                FROM kg_auth.api_keys
                WHERE user_id = %s
                ORDER BY created_at DESC
            """, (current_user.id,))

            keys = []
            for row in cur.fetchall():
                keys.append(APIKeyRead(
                    id=row[0],
                    name=row[1],
                    scopes=row[2],
                    created_at=row[3],
                    last_used=row[4],
                    expires_at=row[5]
                ))
            return keys
    finally:
        conn.close()


@router.post("/api-keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)]
):
    """
    Create a new API key.

    Returns the plaintext API key (shown ONCE - save it!).
    """
    # Generate API key
    api_key = generate_api_key()
    key_hash = hash_api_key(api_key)

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO kg_auth.api_keys (key_hash, user_id, name, scopes, created_at, expires_at)
                VALUES (%s, %s, %s, %s, NOW(), %s)
                RETURNING id, name, scopes, created_at, last_used, expires_at
            """, (key_hash, current_user.id, key_data.name, key_data.scopes, key_data.expires_at))

            row = cur.fetchone()
            conn.commit()

            return APIKeyResponse(
                id=row[0],
                key=api_key,  # Plaintext key (shown once!)
                name=row[1],
                scopes=row[2],
                created_at=row[3],
                last_used=row[4],
                expires_at=row[5]
            )
    finally:
        conn.close()


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)]
):
    """
    Revoke (delete) an API key.

    Users can only revoke their own API keys.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check ownership
            cur.execute("""
                SELECT user_id FROM kg_auth.api_keys WHERE id = %s
            """, (key_id,))
            row = cur.fetchone()

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="API key not found"
                )

            if row[0] != current_user.id and current_user.role != 'admin':
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Can only revoke own API keys"
                )

            # Delete API key
            cur.execute("DELETE FROM kg_auth.api_keys WHERE id = %s", (key_id,))
            conn.commit()
    finally:
        conn.close()


# =============================================================================
# Admin User Management Endpoints
# =============================================================================

@admin_router.get("", response_model=UserListResponse)
async def list_users(
    skip: int = 0,
    limit: int = 100,
    role: Optional[str] = None,
    _: Annotated[UserInDB, Depends(require_role("admin"))] = None
):
    """
    List all users (admin only).

    Supports pagination and filtering by role.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Build query with optional role filter
            query = "SELECT id, username, primary_role, created_at, last_login, disabled FROM kg_auth.users"
            params = []

            if role:
                query += " WHERE primary_role = %s"
                params.append(role)

            query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
            params.extend([limit, skip])

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
            count_query = "SELECT COUNT(*) FROM kg_auth.users"
            if role:
                count_query += " WHERE primary_role = %s"
                cur.execute(count_query, [role] if role else [])
            else:
                cur.execute(count_query)
            total = cur.fetchone()[0]

            return UserListResponse(
                users=users,
                total=total,
                skip=skip,
                limit=limit
            )
    finally:
        conn.close()


@admin_router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: int,
    _: Annotated[UserInDB, Depends(require_role("admin"))] = None
):
    """
    Get user details (admin only).
    """
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
    _: Annotated[UserInDB, Depends(require_role("admin"))] = None
):
    """
    Update user (admin only).

    Can update role, disabled status, and password.
    """
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
    current_user: Annotated[UserInDB, Depends(require_role("admin"))]
):
    """
    Delete user (admin only).

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
