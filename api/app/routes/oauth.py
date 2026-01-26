"""
OAuth 2.0 Routes (ADR-054)

API endpoints for OAuth 2.0 client management and token flows.

Admin endpoints (requires admin role):
- POST /auth/oauth/clients - Register new OAuth client
- GET /auth/oauth/clients - List OAuth clients
- GET /auth/oauth/clients/{client_id} - Get client details
- PATCH /auth/oauth/clients/{client_id} - Update client
- DELETE /auth/oauth/clients/{client_id} - Delete client
- POST /auth/oauth/clients/{client_id}/rotate-secret - Rotate client secret
- GET /auth/oauth/tokens - List all tokens (admin)
- DELETE /auth/oauth/tokens/{token_hash} - Revoke specific token (admin)

OAuth flow endpoints (public or authenticated):
- GET /auth/oauth/authorize - Authorization endpoint (web flow)
- POST /auth/oauth/device - Device authorization request (CLI flow)
- POST /auth/oauth/token - Token endpoint (all flows)
- POST /auth/oauth/revoke - Revoke token
- GET /auth/oauth/device-status/{user_code} - Check device code status (for UI)
"""

import os
from datetime import datetime
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form, Query, Response
from fastapi.responses import RedirectResponse
import psycopg2

from api.app.lib.auth import get_password_hash, verify_password
from api.app.lib.datetime_utils import utcnow
from api.app.lib.oauth_utils import (
    generate_authorization_code,
    generate_device_code,
    generate_user_code,
    generate_access_token,
    generate_refresh_token,
    generate_client_secret,
    hash_token,
    validate_pkce_challenge,
    get_authorization_code_expiry,
    get_device_code_expiry,
    get_access_token_expiry,
    get_refresh_token_expiry,
    is_token_expired,
    validate_scopes,
    parse_scope_string,
    format_scope_list,
)
from api.app.models.oauth import (
    OAuthClientCreate,
    OAuthClientUpdate,
    OAuthClientRead,
    OAuthClientWithSecret,
    OAuthClientListResponse,
    RotateSecretResponse,
    AuthorizationRequest,
    AuthorizationResponse,
    DeviceAuthorizationRequest,
    DeviceAuthorizationResponse,
    DeviceCodeStatus,
    TokenRequest,
    TokenResponse,
    TokenErrorResponse,
    TokenRevocationRequest,
    TokenRevocationResponse,
    AccessTokenRead,
    RefreshTokenRead,
    TokenListResponse,
)
from api.app.dependencies.auth import (
    get_current_active_user,
    get_db_connection,
    require_role,
    require_permission,
)
from api.app.models.auth import UserInDB

router = APIRouter(prefix="/auth/oauth", tags=["oauth"])

# API server base URL for redirect URIs
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


# =============================================================================
# Personal OAuth Client Endpoint (GitHub CLI-style)
# =============================================================================

@router.post("/clients/personal", response_model=OAuthClientWithSecret, status_code=status.HTTP_201_CREATED)
async def create_personal_oauth_client(
    username: str = Form(..., description="Username for authentication"),
    password: str = Form(..., description="Password for authentication"),
    client_name: Optional[str] = Form(None, description="Optional custom client name"),
    scope: str = Form("read:* write:*", description="Requested OAuth scopes")
):
    """
    Create a personal OAuth client for a user (GitHub CLI-style authentication).

    **Authorization:** Authenticated users (any valid token)

    This endpoint allows users to create long-lived OAuth credentials by authenticating
    with their username and password. The returned client_id and client_secret should be
    stored securely (e.g., ~/.config/kg/config.json) and used for subsequent API requests
    via the client_credentials grant.

    Flow:
    1. User provides username + password
    2. API verifies credentials
    3. API creates personal OAuth client: kg-cli-{username}-{random}
    4. Returns client_id + client_secret (shown once!)
    5. User stores credentials locally
    6. All future API calls use client credentials grant

    Similar to:
    - `gh auth login` (GitHub CLI)
    - `glab auth login` (GitLab CLI)
    - `heroku login` (Heroku CLI)

    **Security:**
    - Client secret is shown only once
    - User can revoke via `kg logout` or web UI
    - User can rotate secret if compromised
    - Each personal client is tracked per user

    **Example:**
    ```bash
    curl -X POST http://localhost:8000/auth/oauth/clients/personal \\
      -F "username=admin" \\
      -F "password=secret" \\
      -F "scope=read:* write:*"
    ```

    Returns:
    ```json
    {
      "client_id": "kg-cli-admin-f8a4b2c1",
      "client_secret": "kg_secret_...",
      "client_name": "kg CLI (admin)",
      "scopes": ["read:*", "write:*"],
      ...
    }
    ```
    """
    import secrets

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Step 1: Verify user credentials
            cur.execute(
                "SELECT id, username, password_hash, primary_role, disabled FROM kg_auth.users WHERE username = %s",
                (username,)
            )
            user_row = cur.fetchone()

            if not user_row:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid username or password"
                )

            user_id, db_username, password_hash, role, disabled = user_row

            if disabled:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is disabled"
                )

            if not verify_password(password, password_hash):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid username or password"
                )

            # Step 2: Parse and validate scopes
            requested_scopes = parse_scope_string(scope)
            allowed_scopes = ["read:*", "write:*", "admin:*"]  # Personal clients can request any scope
            is_valid, validated_scopes = validate_scopes(requested_scopes, allowed_scopes)

            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid scopes requested. Allowed: {', '.join(allowed_scopes)}"
                )

            # Step 3: Generate unique client_id with pattern: kg-cli-{username}-{random}
            random_suffix = secrets.token_hex(4)  # 8 characters
            generated_client_id = f"kg-cli-{db_username}-{random_suffix}"

            # Ensure uniqueness (very unlikely collision, but check anyway)
            cur.execute(
                "SELECT client_id FROM kg_auth.oauth_clients WHERE client_id = %s",
                (generated_client_id,)
            )
            if cur.fetchone():
                # Collision detected, generate new random suffix
                random_suffix = secrets.token_hex(6)  # Try with longer suffix
                generated_client_id = f"kg-cli-{db_username}-{random_suffix}"

            # Step 4: Generate client secret
            client_secret = generate_client_secret()
            client_secret_hash = get_password_hash(client_secret)

            # Step 5: Determine client name
            final_client_name = client_name or f"kg CLI ({db_username})"

            # Step 6: Insert personal OAuth client
            import json
            metadata_json = json.dumps({
                "personal": True,
                "user_id": user_id,
                "username": db_username,
                "description": "Personal OAuth client for kg CLI"
            })

            cur.execute("""
                INSERT INTO kg_auth.oauth_clients
                (client_id, client_secret_hash, client_name, client_type, grant_types, redirect_uris, scopes, created_by, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                RETURNING created_at
            """, (
                generated_client_id,
                client_secret_hash,
                final_client_name,
                "confidential",  # Personal clients are confidential (have secret)
                ["client_credentials"],  # Only support client_credentials grant
                None,  # No redirect URIs needed for client_credentials
                validated_scopes,
                user_id,
                metadata_json
            ))

            created_at = cur.fetchone()[0]
            conn.commit()

            return OAuthClientWithSecret(
                client_id=generated_client_id,
                client_name=final_client_name,
                client_type="confidential",
                client_secret=client_secret,  # Shown only once!
                grant_types=["client_credentials"],
                redirect_uris=None,
                scopes=validated_scopes,
                is_active=True,
                created_at=created_at,
                metadata={
                    "personal": True,
                    "user_id": user_id,
                    "username": db_username
                }
            )

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create personal OAuth client: {str(e)}"
        )
    finally:
        conn.close()


@router.post("/clients/personal/new", response_model=OAuthClientWithSecret, status_code=status.HTTP_201_CREATED)
async def create_additional_personal_oauth_client(
    client_name: Optional[str] = Form(None, description="Optional custom client name"),
    scope: str = Form("read:* write:*", description="Requested OAuth scopes"),
    current_user: Annotated[UserInDB, Depends(get_current_active_user)] = None
):
    """
    Create an additional personal OAuth client (requires existing authentication).

    **Authorization:** Authenticated users (any valid token)

    This endpoint allows authenticated users to create additional OAuth clients
    (e.g., for MCP server, scripts) without providing password again.

    Flow:
    1. User is already authenticated with bearer token
    2. API creates new personal OAuth client: kg-cli-{username}-{random}
    3. Returns client_id + client_secret (shown once!)
    4. User can store for MCP or other uses

    **Example:**
    ```bash
    curl -X POST http://localhost:8000/auth/oauth/clients/personal/new \\
      -H "Authorization: Bearer <access_token>" \\
      -F "client_name=kg MCP Server" \\
      -F "scope=read:* write:*"
    ```

    Returns:
    ```json
    {
      "client_id": "kg-cli-admin-f8a4b2c1",
      "client_secret": "kg_secret_...",
      "client_name": "kg MCP Server",
      ...
    }
    ```
    """
    import secrets

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # User is already authenticated, we have current_user from token
            user_id = current_user.id
            db_username = current_user.username
            role = current_user.role

            # Step 1: Parse and validate scopes
            requested_scopes = parse_scope_string(scope)
            allowed_scopes = ["read:*", "write:*", "admin:*"]
            is_valid, validated_scopes = validate_scopes(requested_scopes, allowed_scopes)

            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid scopes requested. Allowed: {', '.join(allowed_scopes)}"
                )

            # Step 2: Generate unique client_id with pattern: kg-cli-{username}-{random}
            random_suffix = secrets.token_hex(4)  # 8 characters
            generated_client_id = f"kg-cli-{db_username}-{random_suffix}"

            # Ensure uniqueness
            cur.execute(
                "SELECT client_id FROM kg_auth.oauth_clients WHERE client_id = %s",
                (generated_client_id,)
            )
            if cur.fetchone():
                random_suffix = secrets.token_hex(6)
                generated_client_id = f"kg-cli-{db_username}-{random_suffix}"

            # Step 3: Generate client secret
            client_secret = generate_client_secret()
            client_secret_hash = get_password_hash(client_secret)

            # Step 4: Determine client name
            final_client_name = client_name or f"kg CLI ({db_username})"

            # Step 5: Insert personal OAuth client
            import json
            metadata_json = json.dumps({
                "personal": True,
                "user_id": user_id,
                "username": db_username,
                "description": "Personal OAuth client"
            })

            cur.execute("""
                INSERT INTO kg_auth.oauth_clients
                (client_id, client_secret_hash, client_name, client_type, grant_types, redirect_uris, scopes, created_by, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                RETURNING created_at
            """, (
                generated_client_id,
                client_secret_hash,
                final_client_name,
                "confidential",
                ["client_credentials"],
                None,
                validated_scopes,
                user_id,
                metadata_json
            ))

            created_at = cur.fetchone()[0]
            conn.commit()

            return OAuthClientWithSecret(
                client_id=generated_client_id,
                client_name=final_client_name,
                client_type="confidential",
                client_secret=client_secret,  # Shown only once!
                grant_types=["client_credentials"],
                redirect_uris=None,
                scopes=validated_scopes,
                is_active=True,
                created_at=created_at,
                metadata={
                    "personal": True,
                    "user_id": user_id,
                    "username": db_username
                }
            )

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create personal OAuth client: {str(e)}"
        )
    finally:
        conn.close()


@router.delete("/clients/personal/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_personal_oauth_client(
    client_id: str,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)]
):
    """
    Delete a personal OAuth client (requires authentication).

    **Authorization:** Authenticated users (any valid token)

    Allows users to revoke their own personal OAuth clients.
    This is called by `kg logout` to clean up OAuth credentials.

    Security:
    - User can only delete their own personal clients
    - Cannot delete system clients or other users' clients
    - Deletion cascades to all associated tokens

    Returns 204 No Content on success.

    **Example:**
    ```bash
    curl -X DELETE http://localhost:8000/auth/oauth/clients/personal/kg-cli-admin-f8a4b2c1 \\
      -H "Authorization: Bearer <access_token>"
    ```
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Verify client exists and is a personal client owned by current user
            cur.execute("""
                SELECT metadata
                FROM kg_auth.oauth_clients
                WHERE client_id = %s
            """, (client_id,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"OAuth client '{client_id}' not found"
                )

            metadata = row[0] or {}

            # Check if this is a personal client
            if not metadata.get("personal"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot delete non-personal OAuth client. Use admin endpoints."
                )

            # Check if client belongs to current user
            if metadata.get("user_id") != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot delete another user's OAuth client"
                )

            # Delete the client (cascades to tokens, codes, etc.)
            cur.execute(
                "DELETE FROM kg_auth.oauth_clients WHERE client_id = %s",
                (client_id,)
            )

            conn.commit()

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete personal OAuth client: {str(e)}"
        )
    finally:
        conn.close()


@router.post("/clients/personal/{client_id}/rotate-secret", response_model=RotateSecretResponse)
async def rotate_personal_client_secret(
    client_id: str,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)]
):
    """
    Rotate secret for a personal OAuth client (requires authentication).

    **Authorization:** Authenticated users (any valid token)

    Allows users to rotate the secret for their own personal OAuth clients.
    Returns new secret (shown only once). Old secret is immediately invalidated.

    Security:
    - User can only rotate secrets for their own personal clients
    - Cannot rotate secrets for system clients or other users' clients

    **Example:**
    ```bash
    curl -X POST http://localhost:8000/auth/oauth/clients/personal/kg-cli-admin-f8a4b2c1/rotate-secret \\
      -H "Authorization: Bearer <access_token>"
    ```
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Verify client exists and get metadata
            cur.execute("""
                SELECT client_type, metadata, client_name
                FROM kg_auth.oauth_clients
                WHERE client_id = %s
            """, (client_id,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"OAuth client '{client_id}' not found"
                )

            client_type, metadata, client_name = row
            metadata = metadata or {}

            # Check if this is a personal client
            if not metadata.get("personal"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot rotate secret for non-personal OAuth client. Use admin endpoints."
                )

            # Check if client belongs to current user
            if metadata.get("user_id") != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot rotate secret for another user's OAuth client"
                )

            # Verify it's a confidential client (has a secret to rotate)
            if client_type != "confidential":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Cannot rotate secret for public client '{client_id}'"
                )

            # Generate new secret
            new_secret = generate_client_secret()
            new_secret_hash = get_password_hash(new_secret)

            # Update client
            cur.execute(
                "UPDATE kg_auth.oauth_clients SET client_secret_hash = %s WHERE client_id = %s",
                (new_secret_hash, client_id)
            )

            conn.commit()

            return RotateSecretResponse(
                client_id=client_id,
                client_secret=new_secret,
                client_name=client_name,
                rotated_at=utcnow()
            )

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rotate personal client secret: {str(e)}"
        )
    finally:
        conn.close()


@router.get("/clients/personal", response_model=OAuthClientListResponse)
async def list_personal_oauth_clients(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)]
):
    """
    List all personal OAuth clients for the current user.

    **Authorization:** Authenticated users (any valid token)

    Returns OAuth clients owned by the authenticated user.
    Useful for managing multiple clients (CLI, MCP, scripts, etc.)

    Security:
    - User can only see their own personal clients
    - Client secrets are NOT returned (shown only once during creation)

    **Example:**
    ```bash
    curl http://localhost:8000/auth/oauth/clients/personal \\
      -H "Authorization: Bearer <access_token>"
    ```
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Get all personal clients for current user
            cur.execute("""
                SELECT
                    client_id,
                    client_name,
                    client_type,
                    grant_types,
                    redirect_uris,
                    scopes,
                    is_active,
                    created_at,
                    created_by,
                    metadata
                FROM kg_auth.oauth_clients
                WHERE metadata->>'personal' = 'true'
                  AND (metadata->>'user_id')::int = %s
                ORDER BY created_at DESC
            """, (current_user.id,))

            clients = []
            for row in cur.fetchall():
                clients.append(OAuthClientRead(
                    client_id=row[0],
                    client_name=row[1],
                    client_type=row[2],
                    grant_types=row[3],
                    redirect_uris=row[4],
                    scopes=row[5],
                    is_active=row[6],
                    created_at=row[7],
                    created_by=row[8],
                    updated_at=None,  # No updated_at column
                    metadata=row[9]
                ))

            return OAuthClientListResponse(
                clients=clients,
                total=len(clients)
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list personal OAuth clients: {str(e)}"
        )
    finally:
        conn.close()


# =============================================================================
# OAuth Client Management Endpoints (Admin Only)
# =============================================================================

@router.post("/clients", response_model=OAuthClientWithSecret, status_code=status.HTTP_201_CREATED)
async def create_oauth_client(
    client: OAuthClientCreate,
    current_user: Annotated[UserInDB, Depends(require_permission("oauth_clients", "create"))]
):
    """
    Register a new OAuth client application (admin only).

    **Authorization:** Requires `oauth_clients:create` permission

    For confidential clients, returns client_secret (shown only once).
    For public clients, client_secret is None.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check if client_id already exists
            cur.execute(
                "SELECT client_id FROM kg_auth.oauth_clients WHERE client_id = %s",
                (client.client_id,)
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Client ID '{client.client_id}' already exists"
                )

            # Generate client secret for confidential clients
            client_secret = None
            client_secret_hash = None
            if client.client_type == "confidential":
                client_secret = generate_client_secret()
                client_secret_hash = get_password_hash(client_secret)

            # Insert client
            cur.execute("""
                INSERT INTO kg_auth.oauth_clients
                (client_id, client_secret_hash, client_name, client_type, grant_types, redirect_uris, scopes, created_by, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING created_at
            """, (
                client.client_id,
                client_secret_hash,
                client.client_name,
                client.client_type,
                client.grant_types,
                client.redirect_uris,
                client.scopes,
                current_user.id,
                client.metadata or {}
            ))

            created_at = cur.fetchone()[0]
            conn.commit()

            return OAuthClientWithSecret(
                client_id=client.client_id,
                client_name=client.client_name,
                client_type=client.client_type,
                client_secret=client_secret or "N/A (public client)",
                grant_types=client.grant_types,
                redirect_uris=client.redirect_uris,
                scopes=client.scopes,
                is_active=True,
                created_at=created_at,
                metadata=client.metadata or {}
            )

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create OAuth client: {str(e)}"
        )
    finally:
        conn.close()


@router.get("/clients", response_model=OAuthClientListResponse)
async def list_oauth_clients(
    current_user: Annotated[UserInDB, Depends(require_permission("oauth_clients", "read"))],
    active_only: bool = Query(False, description="Filter active clients only")
):
    """
    List all OAuth client applications (admin only).

    **Authorization:** Requires `oauth_clients:read` permission
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT client_id, client_name, client_type, grant_types, redirect_uris, scopes,
                       is_active, created_by, created_at, metadata
                FROM kg_auth.oauth_clients
            """
            params = []

            if active_only:
                query += " WHERE is_active = %s"
                params.append(True)

            query += " ORDER BY created_at DESC"

            cur.execute(query, params)
            rows = cur.fetchall()

            clients = [
                OAuthClientRead(
                    client_id=row[0],
                    client_name=row[1],
                    client_type=row[2],
                    grant_types=row[3],
                    redirect_uris=row[4],
                    scopes=row[5],
                    is_active=row[6],
                    created_by=row[7],
                    created_at=row[8],
                    metadata=row[9]
                )
                for row in rows
            ]

            return OAuthClientListResponse(clients=clients, total=len(clients))

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list OAuth clients: {str(e)}"
        )
    finally:
        conn.close()


@router.get("/clients/{client_id}", response_model=OAuthClientRead)
async def get_oauth_client(
    client_id: str,
    current_user: Annotated[UserInDB, Depends(require_permission("oauth_clients", "read"))]
):
    """
    Get OAuth client details (admin only).

    **Authorization:** Requires `oauth_clients:read` permission
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT client_id, client_name, client_type, grant_types, redirect_uris, scopes,
                       is_active, created_by, created_at, metadata
                FROM kg_auth.oauth_clients
                WHERE client_id = %s
            """, (client_id,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"OAuth client '{client_id}' not found"
                )

            return OAuthClientRead(
                client_id=row[0],
                client_name=row[1],
                client_type=row[2],
                grant_types=row[3],
                redirect_uris=row[4],
                scopes=row[5],
                is_active=row[6],
                created_by=row[7],
                created_at=row[8],
                metadata=row[9]
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get OAuth client: {str(e)}"
        )
    finally:
        conn.close()


@router.patch("/clients/{client_id}", response_model=OAuthClientRead)
async def update_oauth_client(
    client_id: str,
    update: OAuthClientUpdate,
    current_user: Annotated[UserInDB, Depends(require_permission("oauth_clients", "write"))]
):
    """
    Update OAuth client configuration (admin only).

    **Authorization:** Requires `oauth_clients:write` permission

    Cannot update client_type or regenerate secret (use rotate-secret endpoint).
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Build dynamic UPDATE query
            updates = []
            params = []

            if update.client_name is not None:
                updates.append("client_name = %s")
                params.append(update.client_name)
            if update.grant_types is not None:
                updates.append("grant_types = %s")
                params.append(update.grant_types)
            if update.redirect_uris is not None:
                updates.append("redirect_uris = %s")
                params.append(update.redirect_uris)
            if update.scopes is not None:
                updates.append("scopes = %s")
                params.append(update.scopes)
            if update.is_active is not None:
                updates.append("is_active = %s")
                params.append(update.is_active)
            if update.metadata is not None:
                updates.append("metadata = %s")
                params.append(update.metadata)

            if not updates:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="No fields to update"
                )

            params.append(client_id)
            query = f"""
                UPDATE kg_auth.oauth_clients
                SET {', '.join(updates)}
                WHERE client_id = %s
                RETURNING client_id, client_name, client_type, grant_types, redirect_uris, scopes,
                          is_active, created_by, created_at, metadata
            """

            cur.execute(query, params)
            row = cur.fetchone()

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"OAuth client '{client_id}' not found"
                )

            conn.commit()

            return OAuthClientRead(
                client_id=row[0],
                client_name=row[1],
                client_type=row[2],
                grant_types=row[3],
                redirect_uris=row[4],
                scopes=row[5],
                is_active=row[6],
                created_by=row[7],
                created_at=row[8],
                metadata=row[9]
            )

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update OAuth client: {str(e)}"
        )
    finally:
        conn.close()


@router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_oauth_client(
    client_id: str,
    current_user: Annotated[UserInDB, Depends(require_permission("oauth_clients", "delete"))]
):
    """
    Delete OAuth client (admin only).

    **Authorization:** Requires `oauth_clients:delete` permission

    Cascades to all associated tokens, codes, etc.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM kg_auth.oauth_clients WHERE client_id = %s RETURNING client_id",
                (client_id,)
            )

            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"OAuth client '{client_id}' not found"
                )

            conn.commit()

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete OAuth client: {str(e)}"
        )
    finally:
        conn.close()


@router.post("/clients/{client_id}/rotate-secret", response_model=RotateSecretResponse)
async def rotate_client_secret(
    client_id: str,
    current_user: Annotated[UserInDB, Depends(require_permission("oauth_clients", "write"))]
):
    """
    Rotate client secret for confidential clients (admin only).

    **Authorization:** Requires `oauth_clients:write` permission

    Returns new secret (shown only once). Old secret is immediately invalidated.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check client exists and is confidential
            cur.execute(
                "SELECT client_type, client_name FROM kg_auth.oauth_clients WHERE client_id = %s",
                (client_id,)
            )
            row = cur.fetchone()

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"OAuth client '{client_id}' not found"
                )

            client_type, client_name = row

            if client_type != "confidential":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Cannot rotate secret for public client '{client_id}'"
                )

            # Generate new secret
            new_secret = generate_client_secret()
            new_secret_hash = get_password_hash(new_secret)

            # Update client
            cur.execute(
                "UPDATE kg_auth.oauth_clients SET client_secret_hash = %s WHERE client_id = %s",
                (new_secret_hash, client_id)
            )

            conn.commit()

            return RotateSecretResponse(
                client_id=client_id,
                client_name=client_name,
                client_secret=new_secret,
                rotated_at=utcnow()
            )

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rotate client secret: {str(e)}"
        )
    finally:
        conn.close()


# =============================================================================
# OAuth Authorization Code Flow (Web Apps)
# =============================================================================

# NOTE: This endpoint is a placeholder. Full implementation requires:
# 1. User authentication UI (login page)
# 2. User consent UI (authorization page)
# 3. Session management
# For now, we'll implement the token exchange endpoint which is more critical

@router.get("/authorize")
async def authorize(
    response_type: str = Query(..., description="Must be 'code'"),
    client_id: str = Query(..., description="OAuth client ID"),
    redirect_uri: str = Query(..., description="Redirect URI"),
    scope: Optional[str] = Query(None, description="Space-separated scopes"),
    state: Optional[str] = Query(None, description="Client state"),
    code_challenge: Optional[str] = Query(None, description="PKCE code challenge"),
    code_challenge_method: Optional[str] = Query("S256", description="PKCE method")
):
    """
    Authorization endpoint for OAuth Authorization Code flow (web apps).

    **NOT FULLY IMPLEMENTED** - Requires user authentication and consent UI.

    This endpoint should:
    1. Verify client_id exists and redirect_uri matches
    2. Authenticate user (redirect to login if needed)
    3. Show consent screen (if needed)
    4. Generate authorization code
    5. Redirect to redirect_uri with code and state
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Authorization code flow not yet implemented (requires web UI)"
    )


@router.post("/login-and-authorize")
async def login_and_authorize(
    username: str = Form(..., description="Username"),
    password: str = Form(..., description="Password"),
    client_id: str = Form(..., description="OAuth client ID"),
    redirect_uri: str = Form(..., description="Redirect URI"),
    scope: str = Form("read:* write:*", description="Requested scopes"),
    code_challenge: str = Form(..., description="PKCE code challenge"),
    code_challenge_method: str = Form("S256", description="PKCE method (S256 or plain)"),
    state: Optional[str] = Form(None, description="Client state for CSRF protection")
):
    """
    Combined login and authorization endpoint for first-party web apps.

    Simplified OAuth flow that combines authentication and authorization in one step:
    1. Verifies user credentials
    2. Validates OAuth client and redirect URI
    3. Generates authorization code with PKCE
    4. Returns code (client handles redirect)

    This is a simplified alternative to traditional OAuth with separate login/consent pages.
    Suitable for first-party applications (viz-app, mobile apps) where we trust the client.

    **Security:**
    - Requires PKCE (code_challenge) for public clients
    - Validates redirect_uri against registered URIs
    - Returns authorization code (short-lived, single-use)
    - Client must exchange code for token via /auth/oauth/token

    **Example:**
    ```bash
    curl -X POST http://localhost:8000/auth/oauth/login-and-authorize \\
      -F "username=admin" \\
      -F "password=secret" \\
      -F "client_id=kg-web" \\
      -F "redirect_uri=http://localhost:3000/callback" \\
      -F "scope=read:* write:*" \\
      -F "code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM" \\
      -F "code_challenge_method=S256"
    ```

    Returns:
    ```json
    {
      "code": "auth_abc123...",
      "state": "client-provided-state"
    }
    ```
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Step 1: Verify user credentials
            cur.execute(
                "SELECT id, username, password_hash, primary_role, disabled FROM kg_auth.users WHERE username = %s",
                (username,)
            )
            user_row = cur.fetchone()

            if not user_row:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid username or password"
                )

            user_id, db_username, password_hash, role, disabled = user_row

            if disabled:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is disabled"
                )

            if not verify_password(password, password_hash):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid username or password"
                )

            # Step 2: Validate OAuth client
            cur.execute("""
                SELECT client_type, grant_types, redirect_uris, scopes, is_active
                FROM kg_auth.oauth_clients
                WHERE client_id = %s
            """, (client_id,))

            client_row = cur.fetchone()
            if not client_row:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"OAuth client '{client_id}' not found"
                )

            client_type, grant_types, allowed_redirect_uris, allowed_scopes, is_active = client_row

            if not is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"OAuth client '{client_id}' is inactive"
                )

            # Step 3: Validate grant type
            if "authorization_code" not in grant_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Client '{client_id}' does not support authorization_code grant"
                )

            # Step 4: Validate redirect_uri
            if redirect_uri not in allowed_redirect_uris:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Redirect URI '{redirect_uri}' not registered for client '{client_id}'"
                )

            # Step 5: Validate scopes
            requested_scopes = parse_scope_string(scope)
            is_valid, granted_scopes = validate_scopes(requested_scopes, allowed_scopes)

            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Requested scopes not allowed for this client"
                )

            # Step 6: Validate PKCE (required for public clients)
            if client_type == "public" and not code_challenge:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="PKCE code_challenge required for public clients"
                )

            # Step 7: Generate authorization code
            auth_code = generate_authorization_code()
            expires_at = get_authorization_code_expiry()

            # Step 8: Store authorization code
            cur.execute("""
                INSERT INTO kg_auth.oauth_authorization_codes
                (code, client_id, user_id, redirect_uri, scopes, code_challenge, code_challenge_method, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                auth_code,
                client_id,
                user_id,
                redirect_uri,
                granted_scopes,
                code_challenge,
                code_challenge_method,
                expires_at
            ))

            conn.commit()

            # Step 9: Return authorization code
            return {
                "code": auth_code,
                "state": state  # Echo back client's state for CSRF protection
            }

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to authorize: {str(e)}"
        )
    finally:
        conn.close()


# =============================================================================
# OAuth Device Authorization Flow (CLI)
# =============================================================================

@router.post("/device", response_model=DeviceAuthorizationResponse)
async def device_authorization(request: DeviceAuthorizationRequest):
    """
    Device authorization endpoint for CLI tools.

    Returns device_code (for polling) and user_code (for user to enter).
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Verify client exists and supports device flow
            cur.execute("""
                SELECT client_type, grant_types, scopes
                FROM kg_auth.oauth_clients
                WHERE client_id = %s AND is_active = true
            """, (request.client_id,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"OAuth client '{request.client_id}' not found or inactive"
                )

            client_type, grant_types, allowed_scopes = row

            if "urn:ietf:params:oauth:grant-type:device_code" not in grant_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Client '{request.client_id}' does not support device authorization grant"
                )

            # Validate requested scopes
            requested_scopes = parse_scope_string(request.scope) if request.scope else ["read:*"]
            is_valid, granted_scopes = validate_scopes(requested_scopes, allowed_scopes)

            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Requested scopes not allowed for this client"
                )

            # Generate codes
            device_code = generate_device_code()
            user_code = generate_user_code()
            expires_at = get_device_code_expiry()

            # Store device authorization
            cur.execute("""
                INSERT INTO kg_auth.oauth_device_codes
                (device_code, user_code, client_id, scopes, expires_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (device_code, user_code, request.client_id, granted_scopes, expires_at))

            conn.commit()

            # Return device authorization response
            verification_uri = f"{API_BASE_URL}/auth/device"
            verification_uri_complete = f"{verification_uri}?user_code={user_code}"

            return DeviceAuthorizationResponse(
                device_code=device_code,
                user_code=user_code,
                verification_uri=verification_uri,
                verification_uri_complete=verification_uri_complete,
                expires_in=600,  # 10 minutes
                interval=5  # Poll every 5 seconds
            )

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create device authorization: {str(e)}"
        )
    finally:
        conn.close()


@router.get("/device-status/{user_code}", response_model=DeviceCodeStatus)
async def get_device_code_status(user_code: str):
    """
    Check device code status (for device authorization UI).

    Returns current status: pending, authorized, denied, or expired.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT status, user_code, expires_at
                FROM kg_auth.oauth_device_codes
                WHERE user_code = %s
            """, (user_code,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User code '{user_code}' not found"
                )

            status_val, user_code, expires_at = row

            # Check if expired
            if is_token_expired(expires_at) and status_val == "pending":
                # Update status to expired
                cur.execute(
                    "UPDATE kg_auth.oauth_device_codes SET status = 'expired' WHERE user_code = %s",
                    (user_code,)
                )
                conn.commit()
                status_val = "expired"

            return DeviceCodeStatus(
                status=status_val,
                user_code=user_code,
                expires_at=expires_at
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get device code status: {str(e)}"
        )
    finally:
        conn.close()


# =============================================================================
# OAuth Token Endpoint (All Grant Types)
# =============================================================================

@router.post("/token", response_model=TokenResponse)
async def token_endpoint(
    grant_type: str = Form(...),
    # Authorization Code grant
    code: Optional[str] = Form(None),
    redirect_uri: Optional[str] = Form(None),
    code_verifier: Optional[str] = Form(None),
    # Device Code grant
    device_code: Optional[str] = Form(None),
    # Client Credentials grant
    client_id: Optional[str] = Form(None),
    client_secret: Optional[str] = Form(None),
    # Refresh Token grant
    refresh_token: Optional[str] = Form(None),
    # Common
    scope: Optional[str] = Form(None),
):
    """
    Token endpoint for all OAuth grant types.

    Supported grant types:
    - authorization_code: Exchange authorization code for tokens
    - urn:ietf:params:oauth:grant-type:device_code: Poll for device authorization
    - client_credentials: Machine-to-machine authentication
    - refresh_token: Refresh access token
    """
    if grant_type == "authorization_code":
        return await _handle_authorization_code_grant(code, redirect_uri, code_verifier, scope)
    elif grant_type == "urn:ietf:params:oauth:grant-type:device_code":
        return await _handle_device_code_grant(device_code)
    elif grant_type == "client_credentials":
        return await _handle_client_credentials_grant(client_id, client_secret, scope)
    elif grant_type == "refresh_token":
        return await _handle_refresh_token_grant(refresh_token, scope)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported grant_type: {grant_type}"
        )


async def _handle_authorization_code_grant(
    code: Optional[str],
    redirect_uri: Optional[str],
    code_verifier: Optional[str],
    scope: Optional[str]
) -> TokenResponse:
    """Handle authorization code grant."""
    if not code or not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required parameters: code, redirect_uri"
        )

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Fetch authorization code
            cur.execute("""
                SELECT client_id, user_id, redirect_uri, scopes, code_challenge, code_challenge_method,
                       expires_at, used
                FROM kg_auth.oauth_authorization_codes
                WHERE code = %s
            """, (code,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid authorization code"
                )

            client_id, user_id, stored_redirect_uri, scopes, code_challenge, code_challenge_method, expires_at, used = row

            # Validate code not expired
            if is_token_expired(expires_at):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Authorization code expired"
                )

            # Validate code not already used
            if used:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Authorization code already used"
                )

            # Validate redirect URI matches
            if redirect_uri != stored_redirect_uri:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Redirect URI mismatch"
                )

            # Validate PKCE if code_challenge was provided
            if code_challenge:
                if not code_verifier:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Missing code_verifier for PKCE"
                    )

                if not validate_pkce_challenge(code_verifier, code_challenge, code_challenge_method):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid PKCE code_verifier"
                    )

            # Mark code as used
            cur.execute(
                "UPDATE kg_auth.oauth_authorization_codes SET used = true WHERE code = %s",
                (code,)
            )

            # Get client type for refresh token expiry
            cur.execute(
                "SELECT client_type FROM kg_auth.oauth_clients WHERE client_id = %s",
                (client_id,)
            )
            client_type = cur.fetchone()[0]

            # Generate tokens
            access_token = generate_access_token()
            refresh_token_str = generate_refresh_token()
            access_token_hash = hash_token(access_token)
            refresh_token_hash = hash_token(refresh_token_str)

            # Store access token
            cur.execute("""
                INSERT INTO kg_auth.oauth_access_tokens
                (token_hash, client_id, user_id, scopes, expires_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (access_token_hash, client_id, user_id, scopes, get_access_token_expiry()))

            # Store refresh token
            cur.execute("""
                INSERT INTO kg_auth.oauth_refresh_tokens
                (token_hash, client_id, user_id, scopes, access_token_hash, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (refresh_token_hash, client_id, user_id, scopes, access_token_hash, get_refresh_token_expiry(client_type)))

            conn.commit()

            return TokenResponse(
                access_token=access_token,
                token_type="Bearer",
                expires_in=3600,
                refresh_token=refresh_token_str,
                scope=format_scope_list(scopes)
            )

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to issue tokens: {str(e)}"
        )
    finally:
        conn.close()


async def _handle_device_code_grant(device_code: Optional[str]) -> TokenResponse:
    """Handle device code grant (polling)."""
    if not device_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required parameter: device_code"
        )

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Fetch device code
            cur.execute("""
                SELECT client_id, user_id, scopes, status, expires_at
                FROM kg_auth.oauth_device_codes
                WHERE device_code = %s
            """, (device_code,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid device_code"
                )

            client_id, user_id, scopes, status_val, expires_at = row

            # Check if expired
            if is_token_expired(expires_at):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Device code expired"
                )

            # Check status
            if status_val == "pending":
                # OAuth 2.0 error response for polling
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="authorization_pending"
                )
            elif status_val == "denied":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="access_denied"
                )
            elif status_val != "authorized":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid device code status"
                )

            # Get client type for refresh token expiry
            cur.execute(
                "SELECT client_type FROM kg_auth.oauth_clients WHERE client_id = %s",
                (client_id,)
            )
            client_type = cur.fetchone()[0]

            # Generate tokens
            access_token = generate_access_token()
            refresh_token_str = generate_refresh_token()
            access_token_hash = hash_token(access_token)
            refresh_token_hash = hash_token(refresh_token_str)

            # Store access token
            cur.execute("""
                INSERT INTO kg_auth.oauth_access_tokens
                (token_hash, client_id, user_id, scopes, expires_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (access_token_hash, client_id, user_id, scopes, get_access_token_expiry()))

            # Store refresh token
            cur.execute("""
                INSERT INTO kg_auth.oauth_refresh_tokens
                (token_hash, client_id, user_id, scopes, access_token_hash, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (refresh_token_hash, client_id, user_id, scopes, access_token_hash, get_refresh_token_expiry(client_type)))

            # Mark device code as used (delete it)
            cur.execute("DELETE FROM kg_auth.oauth_device_codes WHERE device_code = %s", (device_code,))

            conn.commit()

            return TokenResponse(
                access_token=access_token,
                token_type="Bearer",
                expires_in=3600,
                refresh_token=refresh_token_str,
                scope=format_scope_list(scopes)
            )

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to issue tokens: {str(e)}"
        )
    finally:
        conn.close()


async def _handle_client_credentials_grant(
    client_id: Optional[str],
    client_secret: Optional[str],
    scope: Optional[str]
) -> TokenResponse:
    """Handle client credentials grant (machine-to-machine)."""
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required parameters: client_id, client_secret"
        )

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Fetch client (include metadata for personal OAuth clients)
            cur.execute("""
                SELECT client_secret_hash, client_type, grant_types, scopes, is_active, metadata
                FROM kg_auth.oauth_clients
                WHERE client_id = %s
            """, (client_id,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid client credentials"
                )

            client_secret_hash, client_type, grant_types, allowed_scopes, is_active, metadata = row

            # Validate client is active
            if not is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Client is inactive"
                )

            # Validate client is confidential
            if client_type != "confidential":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Client credentials grant requires confidential client"
                )

            # Validate grant type
            if "client_credentials" not in grant_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Client does not support client_credentials grant"
                )

            # Verify client secret
            if not verify_password(client_secret, client_secret_hash):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid client credentials"
                )

            # Validate scopes
            requested_scopes = parse_scope_string(scope) if scope else allowed_scopes
            is_valid, granted_scopes = validate_scopes(requested_scopes, allowed_scopes)

            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Requested scopes not allowed for this client"
                )

            # Generate access token (no refresh token for client_credentials)
            access_token = generate_access_token()
            access_token_hash = hash_token(access_token)

            # For personal OAuth clients, associate token with user
            # Otherwise, user_id is NULL for machine-to-machine authentication
            user_id = None
            if metadata and isinstance(metadata, dict) and metadata.get("personal"):
                user_id = metadata.get("user_id")

            # Store access token
            cur.execute("""
                INSERT INTO kg_auth.oauth_access_tokens
                (token_hash, client_id, user_id, scopes, expires_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (access_token_hash, client_id, user_id, granted_scopes, get_access_token_expiry()))

            conn.commit()

            return TokenResponse(
                access_token=access_token,
                token_type="Bearer",
                expires_in=3600,
                refresh_token=None,  # No refresh token for client_credentials
                scope=format_scope_list(granted_scopes)
            )

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to issue tokens: {str(e)}"
        )
    finally:
        conn.close()


async def _handle_refresh_token_grant(
    refresh_token: Optional[str],
    scope: Optional[str]
) -> TokenResponse:
    """Handle refresh token grant."""
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required parameter: refresh_token"
        )

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Fetch refresh token
            refresh_token_hash = hash_token(refresh_token)
            cur.execute("""
                SELECT client_id, user_id, scopes, expires_at, revoked
                FROM kg_auth.oauth_refresh_tokens
                WHERE token_hash = %s
            """, (refresh_token_hash,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid refresh_token"
                )

            client_id, user_id, scopes, expires_at, revoked = row

            # Validate token not expired
            if is_token_expired(expires_at):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Refresh token expired"
                )

            # Validate token not revoked
            if revoked:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Refresh token revoked"
                )

            # Get client type
            cur.execute(
                "SELECT client_type FROM kg_auth.oauth_clients WHERE client_id = %s",
                (client_id,)
            )
            client_type = cur.fetchone()[0]

            # Generate new access token
            new_access_token = generate_access_token()
            new_access_token_hash = hash_token(new_access_token)

            # Store new access token
            cur.execute("""
                INSERT INTO kg_auth.oauth_access_tokens
                (token_hash, client_id, user_id, scopes, expires_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (new_access_token_hash, client_id, user_id, scopes, get_access_token_expiry()))

            # Update refresh token last_used
            cur.execute(
                "UPDATE kg_auth.oauth_refresh_tokens SET last_used = NOW() WHERE token_hash = %s",
                (refresh_token_hash,)
            )

            conn.commit()

            return TokenResponse(
                access_token=new_access_token,
                token_type="Bearer",
                expires_in=3600,
                refresh_token=refresh_token,  # Return same refresh token
                scope=format_scope_list(scopes)
            )

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh token: {str(e)}"
        )
    finally:
        conn.close()


# =============================================================================
# OAuth Token Revocation
# =============================================================================

@router.post("/revoke", response_model=TokenRevocationResponse)
async def revoke_token(
    token: str = Form(...),
    token_type_hint: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    client_secret: Optional[str] = Form(None)
):
    """
    Revoke an OAuth access token or refresh token.

    Optional client authentication for confidential clients.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            token_hash = hash_token(token)
            revoked = False

            # Try revoking as access token
            if not token_type_hint or token_type_hint == "access_token":
                cur.execute(
                    "UPDATE kg_auth.oauth_access_tokens SET revoked = true WHERE token_hash = %s RETURNING token_hash",
                    (token_hash,)
                )
                if cur.fetchone():
                    revoked = True

            # Try revoking as refresh token
            if not revoked and (not token_type_hint or token_type_hint == "refresh_token"):
                cur.execute(
                    "UPDATE kg_auth.oauth_refresh_tokens SET revoked = true WHERE token_hash = %s RETURNING token_hash",
                    (token_hash,)
                )
                if cur.fetchone():
                    revoked = True

            conn.commit()

            return TokenRevocationResponse(
                revoked=revoked,
                message="Token revoked successfully" if revoked else "Token not found or already revoked"
            )

    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke token: {str(e)}"
        )
    finally:
        conn.close()


# =============================================================================
# OAuth Token Management (Admin)
# =============================================================================

@router.get("/tokens", response_model=TokenListResponse)
async def list_tokens(
    current_user: Annotated[UserInDB, Depends(require_permission("oauth_clients", "read"))],
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    active_only: bool = Query(True, description="Show only active (non-revoked, non-expired) tokens")
):
    """
    List all OAuth tokens (admin only).

    **Authorization:** Requires `oauth_clients:read` permission
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Build access token query
            access_query = """
                SELECT token_hash, client_id, user_id, scopes, expires_at, revoked, created_at
                FROM kg_auth.oauth_access_tokens
                WHERE 1=1
            """
            access_params = []

            if client_id:
                access_query += " AND client_id = %s"
                access_params.append(client_id)
            if user_id:
                access_query += " AND user_id = %s"
                access_params.append(user_id)
            if active_only:
                access_query += " AND revoked = false AND expires_at > NOW()"

            access_query += " ORDER BY created_at DESC LIMIT 100"

            cur.execute(access_query, access_params)
            access_rows = cur.fetchall()

            # Build refresh token query
            refresh_query = """
                SELECT token_hash, client_id, user_id, scopes, expires_at, revoked, created_at, last_used
                FROM kg_auth.oauth_refresh_tokens
                WHERE 1=1
            """
            refresh_params = []

            if client_id:
                refresh_query += " AND client_id = %s"
                refresh_params.append(client_id)
            if user_id:
                refresh_query += " AND user_id = %s"
                refresh_params.append(user_id)
            if active_only:
                refresh_query += " AND revoked = false AND expires_at > NOW()"

            refresh_query += " ORDER BY created_at DESC LIMIT 100"

            cur.execute(refresh_query, refresh_params)
            refresh_rows = cur.fetchall()

            access_tokens = [
                AccessTokenRead(
                    token_hash=row[0],
                    client_id=row[1],
                    user_id=row[2],
                    scopes=row[3],
                    expires_at=row[4],
                    revoked=row[5],
                    created_at=row[6]
                )
                for row in access_rows
            ]

            refresh_tokens = [
                RefreshTokenRead(
                    token_hash=row[0],
                    client_id=row[1],
                    user_id=row[2],
                    scopes=row[3],
                    expires_at=row[4],
                    revoked=row[5],
                    created_at=row[6],
                    last_used=row[7]
                )
                for row in refresh_rows
            ]

            return TokenListResponse(
                access_tokens=access_tokens,
                refresh_tokens=refresh_tokens,
                total_access=len(access_tokens),
                total_refresh=len(refresh_tokens)
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tokens: {str(e)}"
        )
    finally:
        conn.close()


@router.delete("/tokens/{token_hash}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token_by_hash(
    token_hash: str,
    current_user: Annotated[UserInDB, Depends(require_permission("oauth_clients", "delete"))]
):
    """
    Revoke a specific token by its hash (admin only).

    **Authorization:** Requires `oauth_clients:delete` permission
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Try revoking access token
            cur.execute(
                "UPDATE kg_auth.oauth_access_tokens SET revoked = true WHERE token_hash = %s RETURNING token_hash",
                (token_hash,)
            )
            if cur.fetchone():
                conn.commit()
                return

            # Try revoking refresh token
            cur.execute(
                "UPDATE kg_auth.oauth_refresh_tokens SET revoked = true WHERE token_hash = %s RETURNING token_hash",
                (token_hash,)
            )
            if cur.fetchone():
                conn.commit()
                return

            # Token not found
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Token '{token_hash}' not found"
            )

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke token: {str(e)}"
        )
    finally:
        conn.close()
