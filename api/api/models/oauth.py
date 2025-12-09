"""
OAuth 2.0 Models (ADR-054)

Pydantic models for OAuth 2.0 client management and token flows.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, validator


# =============================================================================
# OAuth Client Models
# =============================================================================

class OAuthClientCreate(BaseModel):
    """Request model for creating an OAuth client."""
    client_id: str = Field(..., min_length=3, max_length=255, description="Unique client identifier")
    client_name: str = Field(..., min_length=1, max_length=255, description="Human-readable client name")
    client_type: str = Field(..., description="Client type: 'public' or 'confidential'")
    grant_types: List[str] = Field(..., min_items=1, description="Allowed OAuth grant types")
    redirect_uris: Optional[List[str]] = Field(None, description="Redirect URIs for authorization code flow")
    scopes: List[str] = Field(default_factory=lambda: ["read:*"], description="Allowed scopes")
    metadata: Optional[dict] = Field(default_factory=dict, description="Additional client metadata")

    @validator("client_type")
    def validate_client_type(cls, v):
        if v not in ["public", "confidential"]:
            raise ValueError("client_type must be 'public' or 'confidential'")
        return v

    @validator("grant_types")
    def validate_grant_types(cls, v):
        valid_grants = {
            "authorization_code",
            "urn:ietf:params:oauth:grant-type:device_code",
            "client_credentials",
            "refresh_token"
        }
        for grant in v:
            if grant not in valid_grants:
                raise ValueError(f"Invalid grant type: {grant}")
        return v


class OAuthClientUpdate(BaseModel):
    """Request model for updating an OAuth client."""
    client_name: Optional[str] = Field(None, min_length=1, max_length=255)
    grant_types: Optional[List[str]] = Field(None, min_items=1)
    redirect_uris: Optional[List[str]] = None
    scopes: Optional[List[str]] = Field(None, min_items=1)
    is_active: Optional[bool] = None
    metadata: Optional[dict] = None

    @validator("grant_types")
    def validate_grant_types(cls, v):
        if v is None:
            return v
        valid_grants = {
            "authorization_code",
            "urn:ietf:params:oauth:grant-type:device_code",
            "client_credentials",
            "refresh_token"
        }
        for grant in v:
            if grant not in valid_grants:
                raise ValueError(f"Invalid grant type: {grant}")
        return v


class OAuthClientRead(BaseModel):
    """Response model for OAuth client (excludes secret hash)."""
    client_id: str
    client_name: str
    client_type: str
    grant_types: List[str]
    redirect_uris: Optional[List[str]]
    scopes: List[str]
    is_active: bool
    created_by: Optional[int]
    created_at: datetime
    metadata: dict


class OAuthClientWithSecret(BaseModel):
    """Response model for newly created confidential client (includes secret once)."""
    client_id: str
    client_name: str
    client_type: str
    client_secret: str = Field(..., description="Client secret (shown only once)")
    grant_types: List[str]
    redirect_uris: Optional[List[str]]
    scopes: List[str]
    is_active: bool
    created_at: datetime
    metadata: dict


class OAuthClientListResponse(BaseModel):
    """Response model for listing OAuth clients."""
    clients: List[OAuthClientRead]
    total: int


class RotateSecretResponse(BaseModel):
    """Response model for rotating client secret."""
    client_id: str
    client_name: Optional[str] = Field(None, description="Client name for display")
    client_secret: str = Field(..., description="New client secret (shown only once)")
    rotated_at: datetime


# =============================================================================
# OAuth Authorization Code Flow Models
# =============================================================================

class AuthorizationRequest(BaseModel):
    """Request model for authorization endpoint."""
    response_type: str = Field(..., description="Must be 'code'")
    client_id: str = Field(..., description="OAuth client ID")
    redirect_uri: str = Field(..., description="Redirect URI (must match registered URI)")
    scope: Optional[str] = Field(None, description="Space-separated scopes")
    state: Optional[str] = Field(None, description="Client state for CSRF protection")
    code_challenge: Optional[str] = Field(None, description="PKCE code challenge")
    code_challenge_method: Optional[str] = Field(None, description="PKCE method: 'S256' or 'plain'")

    @validator("response_type")
    def validate_response_type(cls, v):
        if v != "code":
            raise ValueError("response_type must be 'code'")
        return v


class AuthorizationResponse(BaseModel):
    """Response model for authorization endpoint (redirect)."""
    code: str = Field(..., description="Authorization code")
    state: Optional[str] = Field(None, description="Client state (if provided)")


# =============================================================================
# OAuth Device Authorization Flow Models
# =============================================================================

class DeviceAuthorizationRequest(BaseModel):
    """Request model for device authorization."""
    client_id: str = Field(..., description="OAuth client ID")
    scope: Optional[str] = Field(None, description="Space-separated scopes")


class DeviceAuthorizationResponse(BaseModel):
    """Response model for device authorization."""
    device_code: str = Field(..., description="Device code for polling")
    user_code: str = Field(..., description="User-friendly code to enter")
    verification_uri: str = Field(..., description="URL where user enters code")
    verification_uri_complete: Optional[str] = Field(None, description="URL with code pre-filled")
    expires_in: int = Field(..., description="Seconds until codes expire (600 = 10 minutes)")
    interval: int = Field(default=5, description="Polling interval in seconds")


class DeviceCodeStatus(BaseModel):
    """Response model for device code status check."""
    status: str = Field(..., description="pending, authorized, denied, or expired")
    user_code: str
    expires_at: datetime


# =============================================================================
# OAuth Token Endpoint Models
# =============================================================================

class TokenRequest(BaseModel):
    """Request model for token endpoint (all grant types)."""
    grant_type: str = Field(..., description="OAuth grant type")

    # Authorization Code grant
    code: Optional[str] = Field(None, description="Authorization code")
    redirect_uri: Optional[str] = Field(None, description="Redirect URI (must match)")
    code_verifier: Optional[str] = Field(None, description="PKCE code verifier")

    # Device Code grant
    device_code: Optional[str] = Field(None, description="Device code from device authorization")

    # Client Credentials grant
    client_id: Optional[str] = Field(None, description="Client ID")
    client_secret: Optional[str] = Field(None, description="Client secret")

    # Refresh Token grant
    refresh_token: Optional[str] = Field(None, description="Refresh token")

    # Common
    scope: Optional[str] = Field(None, description="Space-separated scopes")

    @validator("grant_type")
    def validate_grant_type(cls, v):
        valid_grants = {
            "authorization_code",
            "urn:ietf:params:oauth:grant-type:device_code",
            "client_credentials",
            "refresh_token"
        }
        if v not in valid_grants:
            raise ValueError(f"Invalid grant_type: {v}")
        return v


class TokenResponse(BaseModel):
    """Response model for token endpoint."""
    access_token: str = Field(..., description="OAuth access token")
    token_type: str = Field(default="Bearer", description="Token type (always 'Bearer')")
    expires_in: int = Field(..., description="Seconds until token expires (3600 = 1 hour)")
    refresh_token: Optional[str] = Field(None, description="Refresh token (for user-delegated grants)")
    scope: str = Field(..., description="Space-separated granted scopes")


class TokenErrorResponse(BaseModel):
    """Error response for token endpoint (OAuth 2.0 standard format)."""
    error: str = Field(..., description="Error code")
    error_description: Optional[str] = Field(None, description="Human-readable error description")
    error_uri: Optional[str] = Field(None, description="URI with error information")


# =============================================================================
# OAuth Token Revocation Models
# =============================================================================

class TokenRevocationRequest(BaseModel):
    """Request model for token revocation."""
    token: str = Field(..., description="Token to revoke (access or refresh)")
    token_type_hint: Optional[str] = Field(None, description="'access_token' or 'refresh_token'")
    client_id: Optional[str] = Field(None, description="Client ID")
    client_secret: Optional[str] = Field(None, description="Client secret (for confidential clients)")


class TokenRevocationResponse(BaseModel):
    """Response model for token revocation."""
    revoked: bool = Field(..., description="Whether token was successfully revoked")
    message: str


# =============================================================================
# OAuth Token Management Models (Admin)
# =============================================================================

class AccessTokenRead(BaseModel):
    """Response model for access token (admin view)."""
    token_hash: str
    client_id: str
    user_id: Optional[int]
    scopes: List[str]
    expires_at: datetime
    revoked: bool
    created_at: datetime


class RefreshTokenRead(BaseModel):
    """Response model for refresh token (admin view)."""
    token_hash: str
    client_id: str
    user_id: int
    scopes: List[str]
    expires_at: datetime
    revoked: bool
    created_at: datetime
    last_used: Optional[datetime]


class TokenListResponse(BaseModel):
    """Response model for listing tokens."""
    access_tokens: List[AccessTokenRead]
    refresh_tokens: List[RefreshTokenRead]
    total_access: int
    total_refresh: int
