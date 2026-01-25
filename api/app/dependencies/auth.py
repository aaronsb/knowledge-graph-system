"""
Authentication Dependencies (ADR-027, ADR-028, ADR-054, ADR-060)

FastAPI dependency injection for authentication and authorization.

Provides:
- get_current_user: Validate OAuth 2.0 access token (ADR-054)
- get_current_active_user: Ensure user is not disabled
- require_role: Check user has required role (legacy - use require_permission for dynamic RBAC)
- require_permission: Dynamic permission checking with scoping support
- get_api_key_user: Authenticate via API key

Type Aliases (ADR-060 - FastAPI Full-Stack Template Pattern):
- CurrentUser: Type-annotated dependency for authenticated user
- TokenDep: Type-annotated dependency for raw token
- Used for cleaner endpoint signatures per industry standard pattern

ADR-054: OAuth 2.0 Authentication
- All authentication uses OAuth 2.0 flows (client credentials, device code, personal clients)
- Single middleware validates OAuth access tokens
- JWT support removed (OAuth-only since Phase 4 completion)

ADR-060: Endpoint Security Architecture
- Per-endpoint dependency injection following FastAPI Full-Stack Template
- Type-annotated dependencies for cleaner signatures
- Three security levels: PUBLIC, USER, ADMIN
"""

import os
from typing import Optional, Annotated, Dict, Any
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
import psycopg2

from api.app.lib.auth import decode_access_token, verify_api_key
from api.app.lib.oauth_utils import hash_token
from api.app.models.auth import UserInDB, TokenData


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
                SELECT id, username, password_hash, primary_role, created_at, last_login, disabled
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
                SELECT id, username, password_hash, primary_role, created_at, last_login, disabled
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


def validate_oauth_access_token(token: str) -> Optional[UserInDB]:
    """
    Validate OAuth 2.0 access token and return associated user (ADR-054).

    Checks the kg_auth.oauth_access_tokens table for a valid, non-expired token.
    Tokens are stored as hashes for security.

    Args:
        token: OAuth access token from Authorization header

    Returns:
        UserInDB instance if token is valid, None otherwise
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Hash the token to look it up (tokens are stored as hashes)
            token_hash_value = hash_token(token)

            # Find token in database and join with user
            cur.execute("""
                SELECT
                    u.id, u.username, u.password_hash, u.primary_role,
                    u.created_at, u.last_login, u.disabled,
                    t.expires_at
                FROM kg_auth.oauth_access_tokens t
                JOIN kg_auth.users u ON t.user_id = u.id
                WHERE t.token_hash = %s
                  AND t.revoked = false
            """, (token_hash_value,))

            row = cur.fetchone()
            if row is None:
                return None

            # Check if token is expired
            from datetime import datetime, timezone
            expires_at = row[7]
            if expires_at and datetime.now(timezone.utc) > expires_at:
                return None

            # Return user
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
# OAuth 2.0 Authentication (ADR-054)
# =============================================================================

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> UserInDB:
    """
    Get current user from OAuth 2.0 access token (ADR-054).

    Validates OAuth access token and retrieves user from database.
    All authentication now uses OAuth 2.0 - JWT support has been removed.

    Args:
        token: OAuth 2.0 access token from Authorization header

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

    # Validate OAuth access token (ADR-054)
    user = validate_oauth_access_token(token)
    if user is not None:
        return user

    # Token validation failed
    raise credentials_exception


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
                       u.id, u.username, u.password_hash, u.primary_role,
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


def check_permission(
    user: UserInDB,
    resource_type: str,
    action: str,
    resource_id: Optional[str] = None,
    resource_context: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Check if user has permission for action on resource (ADR-028 dynamic RBAC).

    Uses PermissionChecker for scoped permission checking with support for:
    - Global permissions
    - Instance-scoped permissions
    - Filter-scoped permissions
    - Explicit denies
    - Role inheritance

    Args:
        user: User to check permissions for
        resource_type: Resource type (concepts, vocabulary, jobs, users, roles, resources)
        action: Action (read, write, delete, approve, execute)
        resource_id: Optional specific resource instance ID
        resource_context: Optional context for filter-scoped permissions
                         (e.g., {"ontology": "memory:user_123", "status": "active"})

    Returns:
        True if permission granted, False otherwise
    """
    from api.app.lib.permissions import PermissionChecker

    conn = get_db_connection()
    try:
        checker = PermissionChecker(conn)
        return checker.can_user(
            user_id=user.id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_context=resource_context
        )
    finally:
        conn.close()


def require_permission(
    resource_type: str,
    action: str,
    resource_id_param: Optional[str] = None,
    resource_context: Optional[Dict[str, Any]] = None
):
    """
    Dependency factory for dynamic permission-based access control (ADR-028).

    Supports scoped permissions:
    - Global: Check permission on resource type (e.g., "read concepts")
    - Instance: Check permission on specific resource (e.g., "delete concept_123")
    - Filter: Check permission with context filters (e.g., "write concepts in ontology:memory:user_1")

    Usage:
        # Global permission check
        @router.get("/concepts")
        async def list_concepts(
            _: Annotated[UserInDB, Depends(require_permission("concepts", "read"))]
        ):
            ...

        # Instance-scoped permission check
        @router.delete("/concepts/{concept_id}")
        async def delete_concept(
            concept_id: str,
            _: Annotated[UserInDB, Depends(require_permission("concepts", "delete", "concept_id"))]
        ):
            ...

        # Filter-scoped permission check
        @router.post("/concepts")
        async def create_concept(
            concept: ConceptCreate,
            _: Annotated[UserInDB, Depends(require_permission(
                "concepts", "write",
                resource_context={"ontology": concept.ontology}
            ))]
        ):
            ...

    Args:
        resource_type: Resource type name
        action: Action name
        resource_id_param: Optional path parameter name containing resource ID
        resource_context: Optional context dict for filter-scoped permissions

    Returns:
        Dependency function that checks permission
    """
    async def check_user_permission(
        request: Request,
        current_user: Annotated[UserInDB, Depends(get_current_active_user)]
    ) -> UserInDB:
        # Extract resource_id from path params if specified
        resource_id = None
        if resource_id_param:
            resource_id = request.path_params.get(resource_id_param)

        if not check_permission(current_user, resource_type, action, resource_id, resource_context):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {action} on {resource_type}"
            )
        return current_user

    return check_user_permission


# =============================================================================
# Type Aliases (ADR-060 - FastAPI Full-Stack Template Pattern)
# =============================================================================

# Type alias for raw OAuth token (FastAPI template pattern)
TokenDep = Annotated[str, Depends(oauth2_scheme)]

# Type alias for authenticated user (FastAPI template pattern)
CurrentUser = Annotated[UserInDB, Depends(get_current_active_user)]
