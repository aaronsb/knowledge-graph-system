"""
RBAC Management Routes (ADR-028)

API endpoints for dynamic role-based access control management.

Admin-only endpoints for managing:
- Resources: Register and configure resource types
- Roles: Create and manage dynamic roles with inheritance
- Permissions: Assign scoped permissions to roles
- User Roles: Assign roles to users with optional scoping
"""

from datetime import datetime
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from psycopg2.extras import RealDictCursor
import psycopg2

from api.app.dependencies.auth import (
    CurrentUser,
    get_current_active_user,
    get_db_connection,
    require_permission,
)
from api.app.models.auth import UserInDB
from api.app.lib.permissions import PermissionChecker
from pydantic import BaseModel, Field


# =============================================================================
# Request/Response Models
# =============================================================================

# Resource Models
class ResourceCreate(BaseModel):
    resource_type: str = Field(..., max_length=100)
    description: Optional[str] = None
    parent_type: Optional[str] = None
    available_actions: List[str] = Field(..., min_items=1)
    supports_scoping: bool = False
    metadata: dict = {}


class ResourceRead(BaseModel):
    resource_type: str
    description: Optional[str]
    parent_type: Optional[str]
    available_actions: List[str]
    supports_scoping: bool
    metadata: dict
    registered_at: datetime
    registered_by: Optional[str]


class ResourceUpdate(BaseModel):
    description: Optional[str] = None
    available_actions: Optional[List[str]] = None
    supports_scoping: Optional[bool] = None
    metadata: Optional[dict] = None


# Role Models
class RoleCreate(BaseModel):
    role_name: str = Field(..., max_length=50)
    display_name: str = Field(..., max_length=100)
    description: Optional[str] = None
    parent_role: Optional[str] = None
    metadata: dict = {}


class RoleRead(BaseModel):
    role_name: str
    display_name: str
    description: Optional[str]
    is_builtin: bool
    is_active: bool
    parent_role: Optional[str]
    created_at: datetime
    created_by: Optional[int]
    metadata: dict


class RoleUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    parent_role: Optional[str] = None
    is_active: Optional[bool] = None
    metadata: Optional[dict] = None


# Permission Models
class PermissionCreate(BaseModel):
    role_name: str
    resource_type: str
    action: str
    scope_type: str = "global"  # global, instance, filter
    scope_id: Optional[str] = None
    scope_filter: Optional[dict] = None
    granted: bool = True


class PermissionRead(BaseModel):
    id: int
    role_name: str
    resource_type: str
    action: str
    scope_type: str
    scope_id: Optional[str]
    scope_filter: Optional[dict]
    granted: bool
    inherited_from: Optional[str]
    created_at: datetime
    created_by: Optional[int]


# User Role Assignment Models
class UserRoleAssign(BaseModel):
    user_id: int
    role_name: str
    scope_type: Optional[str] = "global"
    scope_id: Optional[str] = None
    expires_at: Optional[datetime] = None


class UserRoleRead(BaseModel):
    id: int
    user_id: int
    role_name: str
    scope_type: Optional[str]
    scope_id: Optional[str]
    assigned_at: datetime
    assigned_by: Optional[int]
    expires_at: Optional[datetime]


router = APIRouter(prefix="/rbac", tags=["rbac"])


# =============================================================================
# Resource Management Endpoints
# =============================================================================

@router.get("/resources", response_model=List[ResourceRead])
async def list_resources(
    current_user: CurrentUser,
    _: None = Depends(require_permission("rbac", "read"))
):
    """
    List all registered resource types.

    **Authorization:** Requires `rbac:read` permission

    **Authentication:** Requires admin role
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    resource_type,
                    description,
                    parent_type,
                    available_actions,
                    supports_scoping,
                    metadata,
                    registered_at,
                    registered_by
                FROM kg_auth.resources
                ORDER BY resource_type
            """)

            return [ResourceRead(**row) for row in cur.fetchall()]
    finally:
        conn.close()


@router.post("/resources", response_model=ResourceRead, status_code=status.HTTP_201_CREATED)
async def create_resource(
    resource: ResourceCreate,
    current_user: CurrentUser,
    _: None = Depends(require_permission("rbac", "create"))
):
    """
    Register a new resource type.

    **Authorization:** Requires `rbac:create` permission

    **Authentication:** Requires admin role
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check if resource already exists
            cur.execute(
                "SELECT resource_type FROM kg_auth.resources WHERE resource_type = %s",
                (resource.resource_type,)
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Resource type '{resource.resource_type}' already exists"
                )

            # Insert new resource
            cur.execute("""
                INSERT INTO kg_auth.resources (
                    resource_type, description, parent_type,
                    available_actions, supports_scoping, metadata,
                    registered_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING
                    resource_type, description, parent_type,
                    available_actions, supports_scoping, metadata,
                    registered_at, registered_by
            """, (
                resource.resource_type,
                resource.description,
                resource.parent_type,
                resource.available_actions,
                resource.supports_scoping,
                psycopg2.extras.Json(resource.metadata),
                current_user.username
            ))

            row = cur.fetchone()
            conn.commit()

            return ResourceRead(**row)
    finally:
        conn.close()


@router.get("/resources/{resource_type}", response_model=ResourceRead)
async def get_resource(
    resource_type: str,
    current_user: CurrentUser,
    _: None = Depends(require_permission("rbac", "read"))
):
    """
    Get resource type details.

    **Authorization:** Requires `rbac:read` permission

    **Authentication:** Requires admin role
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    resource_type, description, parent_type,
                    available_actions, supports_scoping, metadata,
                    registered_at, registered_by
                FROM kg_auth.resources
                WHERE resource_type = %s
            """, (resource_type,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Resource type '{resource_type}' not found"
                )

            return ResourceRead(**row)
    finally:
        conn.close()


@router.put("/resources/{resource_type}", response_model=ResourceRead)
async def update_resource(
    resource_type: str,
    update: ResourceUpdate,
    current_user: CurrentUser,
    _: None = Depends(require_permission("rbac", "write"))
):
    """
    Update resource type configuration.

    Cannot update builtin resources.

    **Authorization:** Requires `rbac:write` permission

    **Authentication:** Requires admin role
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Build update query
            updates = []
            params = []

            if update.description is not None:
                updates.append("description = %s")
                params.append(update.description)

            if update.available_actions is not None:
                updates.append("available_actions = %s")
                params.append(update.available_actions)

            if update.supports_scoping is not None:
                updates.append("supports_scoping = %s")
                params.append(update.supports_scoping)

            if update.metadata is not None:
                updates.append("metadata = %s")
                params.append(psycopg2.extras.Json(update.metadata))

            if not updates:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="No fields to update"
                )

            params.append(resource_type)
            cur.execute(
                f"UPDATE kg_auth.resources SET {', '.join(updates)} WHERE resource_type = %s RETURNING resource_type",
                params
            )

            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Resource type '{resource_type}' not found"
                )

            conn.commit()

            # Return updated resource
            cur.execute("""
                SELECT
                    resource_type, description, parent_type,
                    available_actions, supports_scoping, metadata,
                    registered_at, registered_by
                FROM kg_auth.resources
                WHERE resource_type = %s
            """, (resource_type,))

            return ResourceRead(**cur.fetchone())
    finally:
        conn.close()


@router.delete("/resources/{resource_type}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(
    resource_type: str,
    current_user: CurrentUser,
    _: None = Depends(require_permission("rbac", "delete"))
):
    """
    Delete a resource type.

    Cannot delete builtin resources or resources with existing permissions.

    **Authorization:** Requires `rbac:delete` permission

    **Authentication:** Requires admin role
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check if resource has permissions
            cur.execute(
                "SELECT COUNT(*) FROM kg_auth.role_permissions WHERE resource_type = %s",
                (resource_type,)
            )
            if cur.fetchone()[0] > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot delete resource type with existing permissions"
                )

            # Delete resource
            cur.execute("DELETE FROM kg_auth.resources WHERE resource_type = %s", (resource_type,))
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Resource type '{resource_type}' not found"
                )

            conn.commit()
    finally:
        conn.close()


# =============================================================================
# Role Management Endpoints
# =============================================================================

@router.get("/roles", response_model=List[RoleRead])
async def list_roles(
    current_user: CurrentUser,
    _: None = Depends(require_permission("rbac", "read")),
    include_inactive: bool = False
):
    """
    List all roles.

    **Authorization:** Requires `rbac:read` permission

    **Authentication:** Requires admin role
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT
                    role_name, display_name, description,
                    is_builtin, is_active, parent_role,
                    created_at, created_by, metadata
                FROM kg_auth.roles
            """
            if not include_inactive:
                query += " WHERE is_active = TRUE"
            query += " ORDER BY role_name"

            cur.execute(query)
            return [RoleRead(**row) for row in cur.fetchall()]
    finally:
        conn.close()


@router.post("/roles", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
async def create_role(
    role: RoleCreate,
    current_user: CurrentUser,
    _: None = Depends(require_permission("rbac", "create"))
):
    """
    Create a new role.

    **Authorization:** Requires `rbac:create` permission

    **Authentication:** Requires admin role
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check if role already exists
            cur.execute(
                "SELECT role_name FROM kg_auth.roles WHERE role_name = %s",
                (role.role_name,)
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Role '{role.role_name}' already exists"
                )

            # Insert new role
            cur.execute("""
                INSERT INTO kg_auth.roles (
                    role_name, display_name, description,
                    parent_role, created_by, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING
                    role_name, display_name, description,
                    is_builtin, is_active, parent_role,
                    created_at, created_by, metadata
            """, (
                role.role_name,
                role.display_name,
                role.description,
                role.parent_role,
                current_user.id,
                psycopg2.extras.Json(role.metadata)
            ))

            row = cur.fetchone()
            conn.commit()

            return RoleRead(**row)
    finally:
        conn.close()


@router.get("/roles/{role_name}", response_model=RoleRead)
async def get_role(
    role_name: str,
    current_user: CurrentUser,
    _: None = Depends(require_permission("rbac", "read"))
):
    """
    Get role details.

    **Authorization:** Requires `rbac:read` permission

    **Authentication:** Requires admin role
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    role_name, display_name, description,
                    is_builtin, is_active, parent_role,
                    created_at, created_by, metadata
                FROM kg_auth.roles
                WHERE role_name = %s
            """, (role_name,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Role '{role_name}' not found"
                )

            return RoleRead(**row)
    finally:
        conn.close()


@router.put("/roles/{role_name}", response_model=RoleRead)
async def update_role(
    role_name: str,
    update: RoleUpdate,
    current_user: CurrentUser,
    _: None = Depends(require_permission("rbac", "write"))
):
    """
    Update role configuration.

    Cannot modify builtin roles.

    **Authorization:** Requires `rbac:write` permission

    **Authentication:** Requires admin role
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check if role is builtin
            cur.execute(
                "SELECT is_builtin FROM kg_auth.roles WHERE role_name = %s",
                (role_name,)
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Role '{role_name}' not found"
                )
            if row['is_builtin']:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot modify builtin roles"
                )

            # Build update query
            updates = []
            params = []

            if update.display_name is not None:
                updates.append("display_name = %s")
                params.append(update.display_name)

            if update.description is not None:
                updates.append("description = %s")
                params.append(update.description)

            if update.parent_role is not None:
                updates.append("parent_role = %s")
                params.append(update.parent_role)

            if update.is_active is not None:
                updates.append("is_active = %s")
                params.append(update.is_active)

            if update.metadata is not None:
                updates.append("metadata = %s")
                params.append(psycopg2.extras.Json(update.metadata))

            if not updates:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="No fields to update"
                )

            params.append(role_name)
            cur.execute(
                f"UPDATE kg_auth.roles SET {', '.join(updates)} WHERE role_name = %s",
                params
            )
            conn.commit()

            # Return updated role
            cur.execute("""
                SELECT
                    role_name, display_name, description,
                    is_builtin, is_active, parent_role,
                    created_at, created_by, metadata
                FROM kg_auth.roles
                WHERE role_name = %s
            """, (role_name,))

            return RoleRead(**cur.fetchone())
    finally:
        conn.close()


@router.delete("/roles/{role_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_name: str,
    current_user: CurrentUser,
    _: None = Depends(require_permission("rbac", "delete"))
):
    """
    Delete a role.

    Cannot delete builtin roles or roles with users/permissions.

    **Authorization:** Requires `rbac:delete` permission

    **Authentication:** Requires admin role
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check if role is builtin
            cur.execute(
                "SELECT is_builtin FROM kg_auth.roles WHERE role_name = %s",
                (role_name,)
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Role '{role_name}' not found"
                )
            if row['is_builtin']:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot delete builtin roles"
                )

            # Check if role has users
            cur.execute(
                "SELECT COUNT(*) FROM kg_auth.user_roles WHERE role_name = %s",
                (role_name,)
            )
            if cur.fetchone()[0] > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot delete role with assigned users"
                )

            # Delete role (permissions cascade)
            cur.execute("DELETE FROM kg_auth.roles WHERE role_name = %s", (role_name,))
            conn.commit()
    finally:
        conn.close()


# =============================================================================
# Permission Management Endpoints
# =============================================================================

@router.get("/permissions", response_model=List[PermissionRead])
async def list_permissions(
    current_user: CurrentUser,
    _: None = Depends(require_permission("rbac", "read")),
    role_name: Optional[str] = None,
    resource_type: Optional[str] = None
):
    """
    List role permissions with optional filtering.

    **Authorization:** Requires `rbac:read` permission

    **Authentication:** Requires admin role
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT
                    id, role_name, resource_type, action,
                    scope_type, scope_id, scope_filter,
                    granted, inherited_from, created_at, created_by
                FROM kg_auth.role_permissions
                WHERE 1=1
            """
            params = []

            if role_name:
                query += " AND role_name = %s"
                params.append(role_name)

            if resource_type:
                query += " AND resource_type = %s"
                params.append(resource_type)

            query += " ORDER BY role_name, resource_type, action"

            cur.execute(query, params)
            return [PermissionRead(**row) for row in cur.fetchall()]
    finally:
        conn.close()


@router.post("/permissions", response_model=PermissionRead, status_code=status.HTTP_201_CREATED)
async def create_permission(
    permission: PermissionCreate,
    current_user: CurrentUser,
    _: None = Depends(require_permission("rbac", "create"))
):
    """
    Grant a permission to a role.

    **Authorization:** Requires `rbac:create` permission

    **Authentication:** Requires admin role
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Validate role exists
            cur.execute("SELECT role_name FROM kg_auth.roles WHERE role_name = %s", (permission.role_name,))
            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Role '{permission.role_name}' not found"
                )

            # Validate resource exists
            cur.execute("SELECT resource_type FROM kg_auth.resources WHERE resource_type = %s", (permission.resource_type,))
            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Resource type '{permission.resource_type}' not found"
                )

            # Insert permission
            cur.execute("""
                INSERT INTO kg_auth.role_permissions (
                    role_name, resource_type, action,
                    scope_type, scope_id, scope_filter,
                    granted, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING
                    id, role_name, resource_type, action,
                    scope_type, scope_id, scope_filter,
                    granted, inherited_from, created_at, created_by
            """, (
                permission.role_name,
                permission.resource_type,
                permission.action,
                permission.scope_type,
                permission.scope_id,
                psycopg2.extras.Json(permission.scope_filter) if permission.scope_filter else None,
                permission.granted,
                current_user.id
            ))

            row = cur.fetchone()
            conn.commit()

            return PermissionRead(**row)
    except psycopg2.IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Permission already exists with this scope"
        )
    finally:
        conn.close()


@router.delete("/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_permission(
    permission_id: int,
    current_user: CurrentUser,
    _: None = Depends(require_permission("rbac", "delete"))
):
    """
    Revoke a permission from a role.

    **Authorization:** Requires `rbac:delete` permission

    **Authentication:** Requires admin role
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM kg_auth.role_permissions WHERE id = %s", (permission_id,))
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Permission not found"
                )
            conn.commit()
    finally:
        conn.close()


# =============================================================================
# User Role Assignment Endpoints
# =============================================================================

@router.get("/user-roles/{user_id}", response_model=List[UserRoleRead])
async def list_user_roles(
    user_id: int,
    current_user: CurrentUser,
    _: None = Depends(require_permission("rbac", "read"))
):
    """
    List roles assigned to a user.

    **Authorization:** Requires `rbac:read` permission

    **Authentication:** Requires admin role
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    id, user_id, role_name, scope_type, scope_id,
                    assigned_at, assigned_by, expires_at
                FROM kg_auth.user_roles
                WHERE user_id = %s
                ORDER BY assigned_at DESC
            """, (user_id,))

            return [UserRoleRead(**row) for row in cur.fetchall()]
    finally:
        conn.close()


@router.post("/user-roles", response_model=UserRoleRead, status_code=status.HTTP_201_CREATED)
async def assign_user_role(
    assignment: UserRoleAssign,
    current_user: CurrentUser,
    _: None = Depends(require_permission("rbac", "create"))
):
    """
    Assign a role to a user.

    **Authorization:** Requires `rbac:create` permission

    **Authentication:** Requires admin role
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Validate user exists
            cur.execute("SELECT id FROM kg_auth.users WHERE id = %s", (assignment.user_id,))
            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User {assignment.user_id} not found"
                )

            # Validate role exists
            cur.execute("SELECT role_name FROM kg_auth.roles WHERE role_name = %s", (assignment.role_name,))
            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Role '{assignment.role_name}' not found"
                )

            # Insert user role assignment
            cur.execute("""
                INSERT INTO kg_auth.user_roles (
                    user_id, role_name, scope_type, scope_id,
                    assigned_by, expires_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING
                    id, user_id, role_name, scope_type, scope_id,
                    assigned_at, assigned_by, expires_at
            """, (
                assignment.user_id,
                assignment.role_name,
                assignment.scope_type,
                assignment.scope_id,
                current_user.id,
                assignment.expires_at
            ))

            row = cur.fetchone()
            conn.commit()

            return UserRoleRead(**row)
    except psycopg2.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already has this role assignment"
        )
    finally:
        conn.close()


@router.delete("/user-roles/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_user_role(
    assignment_id: int,
    current_user: CurrentUser,
    _: None = Depends(require_permission("rbac", "delete"))
):
    """
    Revoke a role assignment from a user.

    **Authorization:** Requires `rbac:delete` permission

    **Authentication:** Requires admin role
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM kg_auth.user_roles WHERE id = %s", (assignment_id,))
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Role assignment not found"
                )
            conn.commit()
    finally:
        conn.close()


# =============================================================================
# Permission Checking Endpoints (Utility)
# =============================================================================

class PermissionCheckRequest(BaseModel):
    user_id: int
    resource_type: str
    action: str
    resource_id: Optional[str] = None
    resource_context: Optional[dict] = None


class PermissionCheckResponse(BaseModel):
    allowed: bool
    reason: Optional[str] = None


@router.post("/check-permission", response_model=PermissionCheckResponse)
async def check_user_permission(
    request: PermissionCheckRequest,
    current_user: CurrentUser,
    _: None = Depends(require_permission("rbac", "read"))
):
    """
    Check if a user has a specific permission (utility endpoint).

    **Authorization:** Authenticated users (any valid token)

    **Authentication:** Requires admin role
    """
    conn = get_db_connection()
    try:
        checker = PermissionChecker(conn)
        allowed = checker.can_user(
            user_id=request.user_id,
            action=request.action,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            resource_context=request.resource_context
        )

        return PermissionCheckResponse(
            allowed=allowed,
            reason="Allowed" if allowed else "Permission denied"
        )
    finally:
        conn.close()
