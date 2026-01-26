"""
Authentication Models (ADR-027)

Pydantic models for authentication request/response schemas.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


# =============================================================================
# User Models
# =============================================================================

class UserBase(BaseModel):
    """Base user schema with common fields"""
    username: str = Field(..., min_length=3, max_length=100, description="Unique username")
    role: str = Field(..., description="User role: read_only, contributor, curator, admin, platform_admin")

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Ensure role is one of the allowed values (ADR-074: includes platform_admin)"""
        allowed_roles = ['read_only', 'contributor', 'curator', 'admin', 'platform_admin']
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of: {', '.join(allowed_roles)}")
        return v


class UserCreate(UserBase):
    """Schema for creating a new user"""
    password: str = Field(..., min_length=8, description="Password (will be hashed)")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "username": "alice",
                "password": "SecurePass123!",
                "role": "contributor"
            }]
        }
    }


class UserRead(UserBase):
    """Schema for reading user data (excludes password)"""
    id: int = Field(..., description="User ID")
    created_at: datetime = Field(..., description="Account creation timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    disabled: bool = Field(False, description="Whether account is disabled")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [{
                "id": 42,
                "username": "alice",
                "role": "curator",
                "created_at": "2025-10-11T12:00:00Z",
                "last_login": "2025-10-11T15:30:00Z",
                "disabled": False
            }]
        }
    }


class UserUpdate(BaseModel):
    """Schema for updating user data"""
    password: Optional[str] = Field(None, min_length=8, description="New password (optional)")
    role: Optional[str] = Field(None, description="New role (admin only)")
    disabled: Optional[bool] = Field(None, description="Disable/enable account (admin only)")

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        """Ensure role is one of the allowed values (ADR-074: includes platform_admin)"""
        if v is None:
            return v
        allowed_roles = ['read_only', 'contributor', 'curator', 'admin', 'platform_admin']
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of: {', '.join(allowed_roles)}")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "password": "NewSecurePass456!",
                "role": "curator",
                "disabled": False
            }]
        }
    }


class UserInDB(UserRead):
    """Internal model including password hash (never returned to client)"""
    password_hash: str = Field(..., description="Bcrypt password hash")


# =============================================================================
# Authentication Token Models
# =============================================================================

class Token(BaseModel):
    """OAuth2 password flow token response"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")
    expires_in: int = Field(..., description="Token expiration time in seconds")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 3600
            }]
        }
    }


class TokenData(BaseModel):
    """Data extracted from JWT token payload"""
    username: Optional[str] = None
    role: Optional[str] = None


# =============================================================================
# Login Models
# =============================================================================

class LoginRequest(BaseModel):
    """Login request (alternative to OAuth2PasswordRequestForm)"""
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "username": "alice",
                "password": "SecurePass123!"
            }]
        }
    }


class LoginResponse(Token):
    """Login response with user details"""
    user: UserRead = Field(..., description="Authenticated user details")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 3600,
                "user": {
                    "id": 42,
                    "username": "alice",
                    "role": "curator",
                    "created_at": "2025-10-11T12:00:00Z",
                    "last_login": "2025-10-11T15:30:00Z",
                    "disabled": False
                }
            }]
        }
    }


# =============================================================================
# API Key Models
# =============================================================================

class APIKeyCreate(BaseModel):
    """Schema for creating a new API key"""
    name: str = Field(..., min_length=1, max_length=200, description="Human-readable key name")
    scopes: Optional[List[str]] = Field(default=None, description="Optional permission scopes")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration date")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "name": "CI/CD Pipeline",
                "scopes": ["read:concepts", "write:ingest"],
                "expires_at": "2026-01-01T00:00:00Z"
            }]
        }
    }


class APIKeyRead(BaseModel):
    """Schema for reading API key data (excludes actual key)"""
    id: int = Field(..., description="API key ID")
    name: str = Field(..., description="Key name")
    scopes: Optional[List[str]] = Field(None, description="Permission scopes")
    created_at: datetime = Field(..., description="Creation timestamp")
    last_used: Optional[datetime] = Field(None, description="Last usage timestamp")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [{
                "id": 123,
                "name": "CI/CD Pipeline",
                "scopes": ["read:concepts", "write:ingest"],
                "created_at": "2025-10-11T12:00:00Z",
                "last_used": "2025-10-11T15:30:00Z",
                "expires_at": "2026-01-01T00:00:00Z"
            }]
        }
    }


class APIKeyResponse(APIKeyRead):
    """Response when creating API key (includes plaintext key ONCE)"""
    key: str = Field(..., description="Plaintext API key (SAVE THIS - shown only once!)")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "id": 123,
                "key": "kg_sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6",
                "name": "CI/CD Pipeline",
                "scopes": ["read:concepts", "write:ingest"],
                "created_at": "2025-10-11T12:00:00Z",
                "last_used": None,
                "expires_at": "2026-01-01T00:00:00Z"
            }]
        }
    }


# =============================================================================
# Permission Models
# =============================================================================

class Permission(BaseModel):
    """Permission definition"""
    resource: str = Field(..., description="Resource name (concepts, vocabulary, jobs, users)")
    action: str = Field(..., description="Action (read, write, delete, approve)")
    granted: bool = Field(..., description="Whether permission is granted")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "resource": "vocabulary",
                "action": "approve",
                "granted": True
            }]
        }
    }


class RolePermissions(BaseModel):
    """All permissions for a role"""
    role: str = Field(..., description="Role name")
    permissions: List[Permission] = Field(..., description="List of permissions")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "role": "curator",
                "permissions": [
                    {"resource": "concepts", "action": "read", "granted": True},
                    {"resource": "concepts", "action": "write", "granted": True},
                    {"resource": "vocabulary", "action": "approve", "granted": True}
                ]
            }]
        }
    }


# =============================================================================
# Error Response Models
# =============================================================================

class ErrorDetail(BaseModel):
    """Standard error response"""
    detail: str = Field(..., description="Error message")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "detail": "Invalid credentials"
            }]
        }
    }


class ValidationError(BaseModel):
    """Validation error details"""
    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Validation error message")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "field": "password",
                "message": "Password must be at least 8 characters long"
            }]
        }
    }


# =============================================================================
# Password Reset Models
# =============================================================================

class AdminPasswordReset(BaseModel):
    """Admin password reset request - sets a new password for a user"""
    new_password: str = Field(..., min_length=8, description="New password for the user")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "new_password": "NewSecurePass456!"
            }]
        }
    }


class PasswordResetResponse(BaseModel):
    """Password reset response"""
    success: bool = Field(..., description="Whether the reset was successful")
    message: str = Field(..., description="Result message")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "success": True,
                "message": "Password reset successfully"
            }]
        }
    }


# =============================================================================
# Pagination Models (for admin user list)
# =============================================================================

class UserListResponse(BaseModel):
    """Paginated list of users"""
    users: List[UserRead] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")
    skip: int = Field(0, description="Number of users skipped")
    limit: int = Field(100, description="Maximum users returned")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "users": [
                    {
                        "id": 1,
                        "username": "admin",
                        "role": "admin",
                        "created_at": "2025-10-10T00:00:00Z",
                        "last_login": "2025-10-11T15:30:00Z",
                        "disabled": False
                    },
                    {
                        "id": 2,
                        "username": "alice",
                        "role": "curator",
                        "created_at": "2025-10-11T12:00:00Z",
                        "last_login": "2025-10-11T15:30:00Z",
                        "disabled": False
                    }
                ],
                "total": 2,
                "skip": 0,
                "limit": 100
            }]
        }
    }
