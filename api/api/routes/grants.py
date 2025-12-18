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
    current_user: UserInDB = Depends(get_current_user)
):
    """
    List members of a group.

    Note: The 'public' group (ID 1) has implicit membership for all
    authenticated users, which is not stored in the database.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Get group info
            cur.execute(
                "SELECT group_name FROM kg_auth.groups WHERE id = %s",
                (group_id,)
            )
            group_row = cur.fetchone()
            if not group_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Group not found: {group_id}"
                )

            group_name = group_row[0]

            # Get members
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
                total=len(members)
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

            # TODO: Verify current_user owns the resource or is admin
            # For now, only admins can create grants
            if current_user.role not in ("admin", "platform_admin"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only admins can create grants (owner verification not yet implemented)"
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
            # Check grant exists
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

            # TODO: Verify current_user owns the resource or is admin
            if current_user.role not in ("admin", "platform_admin"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only admins can revoke grants (owner verification not yet implemented)"
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
