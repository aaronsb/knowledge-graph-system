"""
Grants and Groups Routes (ADR-082)

API endpoints for group management and resource access grants.
"""

from fastapi import APIRouter, HTTPException, Query, Depends, status
from typing import Optional
import logging

from ..models.grants import (
    GroupCreate,
    GroupRead,
    GroupList,
    GroupMember,
    GroupMemberList,
    AddMemberRequest,
    GrantCreate,
    GrantRead,
    GrantList,
    GrantCreateResponse
)
from ..models.auth import UserInDB
from ..dependencies.auth import get_current_user, get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(tags=["grants"])

# System user ID (reserved for system-owned resources)
SYSTEM_USER_ID = 1


def verify_resource_ownership(
    cur,
    resource_type: str,
    resource_id: str,
    user_id: int,
    user_role: str
) -> tuple[bool, Optional[int]]:
    """
    Verify if a user owns a resource or has admin privileges.

    Returns:
        (is_authorized, owner_id) - is_authorized is True if user can manage grants,
        owner_id is the actual owner of the resource (None if resource not found)

    Authorization rules:
    - Admins can always manage grants
    - Resource owners can manage grants for their resources
    - System resources (owner_id=1) can only be managed by admins
    """
    # Admins can always manage grants
    if user_role in ("admin", "platform_admin"):
        # Still need to verify resource exists
        owner_id = _get_resource_owner(cur, resource_type, resource_id)
        return (owner_id is not None, owner_id)

    # Get resource owner
    owner_id = _get_resource_owner(cur, resource_type, resource_id)

    if owner_id is None:
        # Resource doesn't exist
        return (False, None)

    # System resources can only be managed by admins (already checked above)
    if owner_id == SYSTEM_USER_ID:
        return (False, owner_id)

    # Check if user is the owner
    return (owner_id == user_id, owner_id)


def _get_resource_owner(cur, resource_type: str, resource_id: str) -> Optional[int]:
    """
    Get the owner_id for a resource.

    Returns None if resource doesn't exist.
    """
    # Map resource types to their tables and owner columns
    resource_tables = {
        "artifact": ("kg_api.artifacts", "id", "owner_id"),
        "query_definition": ("kg_api.query_definitions", "id", "owner_id"),
        # Future: ontology, projection, etc.
    }

    if resource_type not in resource_tables:
        # Unknown resource type - could be external or future type
        # For now, only admins can grant on unknown types (handled by caller)
        return None

    table, id_col, owner_col = resource_tables[resource_type]

    try:
        resource_id_int = int(resource_id)
    except ValueError:
        # Non-integer ID for a table that uses integer IDs
        return None

    cur.execute(
        f"SELECT {owner_col} FROM {table} WHERE {id_col} = %s",
        (resource_id_int,)
    )
    row = cur.fetchone()

    if row is None:
        return None

    # Return owner_id (could be None for legacy/system resources)
    # Treat NULL owner as system-owned
    return row[0] if row[0] is not None else SYSTEM_USER_ID


# =============================================================================
# Group Endpoints
# =============================================================================

@router.get(
    "/groups",
    response_model=GroupList,
    summary="List groups"
)
async def list_groups(
    include_system: bool = Query(True, description="Include system groups (public, admins)"),
    include_member_count: bool = Query(True, description="Include member count for each group"),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    List all groups.

    System groups (public, admins) are included by default but can be filtered out.
    Member counts can be included for visibility into group size.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if include_member_count:
                query = """
                    SELECT g.id, g.group_name, g.display_name, g.description,
                           g.is_system, g.created_at, g.created_by,
                           COUNT(ug.user_id) as member_count
                    FROM kg_auth.groups g
                    LEFT JOIN kg_auth.user_groups ug ON g.id = ug.group_id
                """
                if not include_system:
                    query += " WHERE g.is_system = FALSE"
                query += " GROUP BY g.id ORDER BY g.group_name"
            else:
                query = """
                    SELECT g.id, g.group_name, g.display_name, g.description,
                           g.is_system, g.created_at, g.created_by, NULL as member_count
                    FROM kg_auth.groups g
                """
                if not include_system:
                    query += " WHERE g.is_system = FALSE"
                query += " ORDER BY g.group_name"

            cur.execute(query)
            rows = cur.fetchall()

            groups = [
                GroupRead(
                    id=row[0],
                    group_name=row[1],
                    display_name=row[2],
                    description=row[3],
                    is_system=row[4],
                    created_at=row[5],
                    created_by=row[6],
                    member_count=row[7]
                )
                for row in rows
            ]

            return GroupList(groups=groups, total=len(groups))
    finally:
        conn.close()


@router.post(
    "/groups",
    response_model=GroupRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create group"
)
async def create_group(
    group: GroupCreate,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Create a new group.

    Only admins can create groups. Group names must be unique.
    New groups get IDs starting at 1000 (1-999 reserved for system).
    """
    # Check admin permission
    if current_user.role not in ("admin", "platform_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create groups"
        )

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check for duplicate group name
            cur.execute(
                "SELECT id FROM kg_auth.groups WHERE group_name = %s",
                (group.group_name,)
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Group '{group.group_name}' already exists"
                )

            # Insert new group (ID auto-assigned from sequence starting at 1000)
            cur.execute("""
                INSERT INTO kg_auth.groups (group_name, display_name, description, created_by)
                VALUES (%s, %s, %s, %s)
                RETURNING id, group_name, display_name, description, is_system, created_at, created_by
            """, (
                group.group_name,
                group.display_name,
                group.description,
                current_user.id
            ))

            row = cur.fetchone()
            conn.commit()

            logger.info(f"Created group '{group.group_name}' (ID {row[0]}) by user {current_user.id}")

            return GroupRead(
                id=row[0],
                group_name=row[1],
                display_name=row[2],
                description=row[3],
                is_system=row[4],
                created_at=row[5],
                created_by=row[6],
                member_count=0
            )
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to create group: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create group: {str(e)}"
        )
    finally:
        conn.close()


@router.get(
    "/groups/{group_id}/members",
    response_model=GroupMemberList,
    summary="List group members"
)
async def list_group_members(
    group_id: int,
    include_implicit: bool = Query(False, description="For public group, include all users (implicit members)"),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    List members of a group.

    **Public group (ID 1):**
    The 'public' group has implicit membership for all authenticated users.
    By default, returns an empty explicit member list. Use `include_implicit=true`
    to return all users as implicit members of the public group.
    """
    # Public group ID
    PUBLIC_GROUP_ID = 1

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Get group info
            cur.execute(
                "SELECT group_name, is_system FROM kg_auth.groups WHERE id = %s",
                (group_id,)
            )
            group_row = cur.fetchone()
            if not group_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Group not found: {group_id}"
                )

            group_name = group_row[0]
            is_public_group = (group_id == PUBLIC_GROUP_ID)

            # For public group with include_implicit, return all users
            if is_public_group and include_implicit:
                cur.execute("""
                    SELECT u.id, u.username, u.created_at, NULL as added_by
                    FROM kg_auth.users u
                    WHERE u.id >= 1000  -- Exclude system user
                    ORDER BY u.username
                """)

                members = [
                    GroupMember(
                        user_id=row[0],
                        username=row[1],
                        added_at=row[2],  # Use user creation time as "added" time
                        added_by=row[3]
                    )
                    for row in cur.fetchall()
                ]

                return GroupMemberList(
                    group_id=group_id,
                    group_name=group_name,
                    members=members,
                    total=len(members),
                    implicit_membership=True
                )

            # Get explicit members
            cur.execute("""
                SELECT ug.user_id, u.username, ug.added_at, ug.added_by
                FROM kg_auth.user_groups ug
                JOIN kg_auth.users u ON ug.user_id = u.id
                WHERE ug.group_id = %s
                ORDER BY u.username
            """, (group_id,))

            members = [
                GroupMember(
                    user_id=row[0],
                    username=row[1],
                    added_at=row[2],
                    added_by=row[3]
                )
                for row in cur.fetchall()
            ]

            return GroupMemberList(
                group_id=group_id,
                group_name=group_name,
                members=members,
                total=len(members),
                implicit_membership=(is_public_group and not include_implicit)
            )
    finally:
        conn.close()


@router.post(
    "/groups/{group_id}/members",
    response_model=GroupMember,
    status_code=status.HTTP_201_CREATED,
    summary="Add member to group"
)
async def add_group_member(
    group_id: int,
    request: AddMemberRequest,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Add a user to a group.

    Only admins can modify group membership.
    Cannot add members to system groups via API (use operator tools).
    """
    # Check admin permission
    if current_user.role not in ("admin", "platform_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can modify group membership"
        )

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check group exists and is not system
            cur.execute(
                "SELECT group_name, is_system FROM kg_auth.groups WHERE id = %s",
                (group_id,)
            )
            group_row = cur.fetchone()
            if not group_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Group not found: {group_id}"
                )

            # Check user exists
            cur.execute(
                "SELECT username FROM kg_auth.users WHERE id = %s",
                (request.user_id,)
            )
            user_row = cur.fetchone()
            if not user_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User not found: {request.user_id}"
                )

            username = user_row[0]

            # Check not already a member
            cur.execute(
                "SELECT 1 FROM kg_auth.user_groups WHERE user_id = %s AND group_id = %s",
                (request.user_id, group_id)
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"User {request.user_id} is already a member of group {group_id}"
                )

            # Add member
            cur.execute("""
                INSERT INTO kg_auth.user_groups (user_id, group_id, added_by)
                VALUES (%s, %s, %s)
                RETURNING added_at
            """, (request.user_id, group_id, current_user.id))

            added_at = cur.fetchone()[0]
            conn.commit()

            logger.info(f"Added user {request.user_id} to group {group_id} by user {current_user.id}")

            return GroupMember(
                user_id=request.user_id,
                username=username,
                added_at=added_at,
                added_by=current_user.id
            )
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to add group member: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add group member: {str(e)}"
        )
    finally:
        conn.close()


@router.delete(
    "/groups/{group_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove member from group"
)
async def remove_group_member(
    group_id: int,
    user_id: int,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Remove a user from a group.

    Only admins can modify group membership.
    """
    # Check admin permission
    if current_user.role not in ("admin", "platform_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can modify group membership"
        )

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check membership exists
            cur.execute(
                "SELECT 1 FROM kg_auth.user_groups WHERE user_id = %s AND group_id = %s",
                (user_id, group_id)
            )
            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User {user_id} is not a member of group {group_id}"
                )

            # Remove member
            cur.execute(
                "DELETE FROM kg_auth.user_groups WHERE user_id = %s AND group_id = %s",
                (user_id, group_id)
            )
            conn.commit()

            logger.info(f"Removed user {user_id} from group {group_id} by user {current_user.id}")
    finally:
        conn.close()


# =============================================================================
# Grant Endpoints
# =============================================================================

@router.post(
    "/grants",
    response_model=GrantCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create grant"
)
async def create_grant(
    grant: GrantCreate,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Create a resource access grant.

    Grants permission for a user or group to access a specific resource.
    Only resource owners or admins can create grants.

    **Permission levels:**
    - `read`: View the resource
    - `write`: Modify the resource
    - `admin`: Full control including granting access to others
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Verify principal exists
            if grant.principal_type == "user":
                cur.execute(
                    "SELECT username FROM kg_auth.users WHERE id = %s",
                    (grant.principal_id,)
                )
                if not cur.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"User not found: {grant.principal_id}"
                    )
            else:  # group
                cur.execute(
                    "SELECT group_name FROM kg_auth.groups WHERE id = %s",
                    (grant.principal_id,)
                )
                if not cur.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Group not found: {grant.principal_id}"
                    )

            # Verify current_user owns the resource or is admin
            is_authorized, owner_id = verify_resource_ownership(
                cur, grant.resource_type, grant.resource_id,
                current_user.id, current_user.role
            )

            if owner_id is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Resource not found: {grant.resource_type}/{grant.resource_id}"
                )

            if not is_authorized:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You must own the resource or be an admin to create grants"
                )

            # Create grant
            cur.execute("""
                INSERT INTO kg_auth.resource_grants
                    (resource_type, resource_id, principal_type, principal_id, permission, granted_by)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (resource_type, resource_id, principal_type, principal_id, permission)
                DO UPDATE SET granted_at = NOW(), granted_by = EXCLUDED.granted_by
                RETURNING id, granted_at
            """, (
                grant.resource_type,
                grant.resource_id,
                grant.principal_type,
                grant.principal_id,
                grant.permission,
                current_user.id
            ))

            row = cur.fetchone()
            conn.commit()

            logger.info(
                f"Created grant: {grant.principal_type}:{grant.principal_id} -> "
                f"{grant.resource_type}:{grant.resource_id} ({grant.permission}) by user {current_user.id}"
            )

            return GrantCreateResponse(
                id=row[0],
                resource_type=grant.resource_type,
                resource_id=grant.resource_id,
                principal_type=grant.principal_type,
                principal_id=grant.principal_id,
                permission=grant.permission,
                granted_at=row[1]
            )
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to create grant: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create grant: {str(e)}"
        )
    finally:
        conn.close()


@router.get(
    "/resources/{resource_type}/{resource_id}/grants",
    response_model=GrantList,
    summary="List grants for resource"
)
async def list_resource_grants(
    resource_type: str,
    resource_id: str,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    List all grants for a specific resource.

    Shows who has access to the resource and at what permission level.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    rg.id, rg.resource_type, rg.resource_id,
                    rg.principal_type, rg.principal_id,
                    CASE
                        WHEN rg.principal_type = 'user' THEN u.username
                        WHEN rg.principal_type = 'group' THEN g.group_name
                    END as principal_name,
                    rg.permission, rg.granted_at, rg.granted_by,
                    granter.username as granted_by_name
                FROM kg_auth.resource_grants rg
                LEFT JOIN kg_auth.users u ON rg.principal_type = 'user' AND rg.principal_id = u.id
                LEFT JOIN kg_auth.groups g ON rg.principal_type = 'group' AND rg.principal_id = g.id
                LEFT JOIN kg_auth.users granter ON rg.granted_by = granter.id
                WHERE rg.resource_type = %s AND rg.resource_id = %s
                ORDER BY rg.principal_type, principal_name
            """, (resource_type, resource_id))

            grants = [
                GrantRead(
                    id=row[0],
                    resource_type=row[1],
                    resource_id=row[2],
                    principal_type=row[3],
                    principal_id=row[4],
                    principal_name=row[5],
                    permission=row[6],
                    granted_at=row[7],
                    granted_by=row[8],
                    granted_by_name=row[9]
                )
                for row in cur.fetchall()
            ]

            return GrantList(grants=grants, total=len(grants))
    finally:
        conn.close()


@router.delete(
    "/grants/{grant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke grant"
)
async def revoke_grant(
    grant_id: int,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Revoke (delete) a resource access grant.

    Only resource owners or admins can revoke grants.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check grant exists and get resource info
            cur.execute(
                "SELECT resource_type, resource_id FROM kg_auth.resource_grants WHERE id = %s",
                (grant_id,)
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Grant not found: {grant_id}"
                )

            resource_type, resource_id = row

            # Verify current_user owns the resource or is admin
            is_authorized, owner_id = verify_resource_ownership(
                cur, resource_type, resource_id,
                current_user.id, current_user.role
            )

            if not is_authorized:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You must own the resource or be an admin to revoke grants"
                )

            # Delete grant
            cur.execute(
                "DELETE FROM kg_auth.resource_grants WHERE id = %s",
                (grant_id,)
            )
            conn.commit()

            logger.info(f"Revoked grant {grant_id} by user {current_user.id}")
    finally:
        conn.close()
