"""
Grants and Groups Models (ADR-082)

Pydantic models for groups and resource grants API endpoints.
"""

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


# =============================================================================
# Group Models
# =============================================================================

class GroupCreate(BaseModel):
    """Request model for creating a group."""
    group_name: str = Field(..., min_length=1, max_length=100, description="Unique group identifier")
    display_name: Optional[str] = Field(None, max_length=200, description="Human-readable display name")
    description: Optional[str] = Field(None, description="Group description")

    class Config:
        json_schema_extra = {
            "example": {
                "group_name": "research-team",
                "display_name": "Research Team",
                "description": "Members of the research department"
            }
        }


class GroupRead(BaseModel):
    """Response model for group data."""
    id: int
    group_name: str
    display_name: Optional[str]
    description: Optional[str]
    is_system: bool = Field(..., description="System groups cannot be deleted")
    created_at: datetime
    created_by: Optional[int]
    member_count: Optional[int] = Field(None, description="Number of members (when included)")


class GroupList(BaseModel):
    """Response model for listing groups."""
    groups: List[GroupRead]
    total: int


class GroupMember(BaseModel):
    """Response model for group member."""
    user_id: int
    username: str
    added_at: datetime
    added_by: Optional[int]


class GroupMemberList(BaseModel):
    """Response model for listing group members."""
    group_id: int
    group_name: str
    members: List[GroupMember]
    total: int
    implicit_membership: bool = Field(
        False,
        description="True if members shown are implicit (e.g., public group has all users as implicit members)"
    )


class AddMemberRequest(BaseModel):
    """Request model for adding a member to a group."""
    user_id: int = Field(..., description="User ID to add to the group")


# =============================================================================
# Grant Models
# =============================================================================

PermissionLevel = Literal["read", "write", "admin"]
PrincipalType = Literal["user", "group"]


class GrantCreate(BaseModel):
    """Request model for creating a resource grant."""
    resource_type: str = Field(..., description="Type of resource (ontology, artifact, etc.)")
    resource_id: str = Field(..., description="Specific resource identifier")
    principal_type: PrincipalType = Field(..., description="Grant to user or group")
    principal_id: int = Field(..., description="User or group ID")
    permission: PermissionLevel = Field(..., description="Permission level: read, write, or admin")

    class Config:
        json_schema_extra = {
            "example": {
                "resource_type": "ontology",
                "resource_id": "my-research",
                "principal_type": "group",
                "principal_id": 1000,
                "permission": "read"
            }
        }


class GrantRead(BaseModel):
    """Response model for grant data."""
    id: int
    resource_type: str
    resource_id: str
    principal_type: PrincipalType
    principal_id: int
    principal_name: Optional[str] = Field(None, description="Username or group name")
    permission: PermissionLevel
    granted_at: datetime
    granted_by: Optional[int]
    granted_by_name: Optional[str] = Field(None, description="Username of granter")


class GrantList(BaseModel):
    """Response model for listing grants."""
    grants: List[GrantRead]
    total: int


class GrantCreateResponse(BaseModel):
    """Response model for grant creation."""
    id: int
    resource_type: str
    resource_id: str
    principal_type: PrincipalType
    principal_id: int
    permission: PermissionLevel
    granted_at: datetime
