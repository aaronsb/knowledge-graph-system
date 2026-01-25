"""
Query Definitions Routes (ADR-083)

API endpoints for managing saved query definitions - recipes that can be re-executed.
"""

from fastapi import APIRouter, HTTPException, Query, Depends, status
from typing import Optional
import logging
import psycopg2.extras

from ..models.query_definition import (
    QueryDefinitionCreate,
    QueryDefinitionUpdate,
    QueryDefinitionRead,
    QueryDefinitionList,
    QueryDefinitionCreateResponse,
    DEFINITION_TYPES
)
from ..models.auth import UserInDB
from ..dependencies.auth import get_current_user, get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query-definitions", tags=["query-definitions"])


@router.get(
    "",
    response_model=QueryDefinitionList,
    summary="List query definitions"
)
async def list_query_definitions(
    definition_type: Optional[str] = Query(None, description="Filter by definition type"),
    limit: int = Query(50, ge=1, le=500, description="Maximum definitions to return"),
    offset: int = Query(0, ge=0, description="Number to skip for pagination"),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    List query definitions.

    Returns definitions owned by the current user.
    Admins can see all definitions.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Build query
            query = """
                SELECT id, name, definition_type, definition, metadata, owner_id, created_at, updated_at
                FROM kg_api.query_definitions
                WHERE 1=1
            """
            params = []

            # Filter by owner (unless admin)
            user_id = current_user.id
            user_role = current_user.role

            if user_role not in ("admin", "platform_admin"):
                query += " AND (owner_id = %s OR owner_id IS NULL)"
                params.append(user_id)

            if definition_type:
                if definition_type not in DEFINITION_TYPES:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid definition_type. Must be one of: {DEFINITION_TYPES}"
                    )
                query += " AND definition_type = %s"
                params.append(definition_type)

            # Get total count
            count_query = f"SELECT COUNT(*) FROM ({query}) sub"
            cur.execute(count_query, params)
            total = cur.fetchone()[0]

            # Add ordering and pagination
            query += " ORDER BY updated_at DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])

            cur.execute(query, params)
            rows = cur.fetchall()

            definitions = [
                QueryDefinitionRead(
                    id=row[0],
                    name=row[1],
                    definition_type=row[2],
                    definition=row[3],
                    metadata=row[4],
                    owner_id=row[5],
                    created_at=row[6],
                    updated_at=row[7]
                )
                for row in rows
            ]

            return QueryDefinitionList(
                definitions=definitions,
                total=total,
                limit=limit,
                offset=offset
            )
    finally:
        conn.close()


@router.get(
    "/{definition_id}",
    response_model=QueryDefinitionRead,
    summary="Get query definition"
)
async def get_query_definition(
    definition_id: int,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get a query definition by ID.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, definition_type, definition, metadata, owner_id, created_at, updated_at
                FROM kg_api.query_definitions
                WHERE id = %s
            """, (definition_id,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Query definition not found: {definition_id}"
                )

            # Check ownership
            owner_id = row[5]
            if owner_id is not None and owner_id != current_user.id:
                if current_user.role not in ("admin", "platform_admin"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied to this query definition"
                    )

            return QueryDefinitionRead(
                id=row[0],
                name=row[1],
                definition_type=row[2],
                definition=row[3],
                metadata=row[4],
                owner_id=row[5],
                created_at=row[6],
                updated_at=row[7]
            )
    finally:
        conn.close()


@router.post(
    "",
    response_model=QueryDefinitionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create query definition"
)
async def create_query_definition(
    definition: QueryDefinitionCreate,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Create a new query definition.

    Saves a query recipe that can be re-executed later to generate artifacts.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO kg_api.query_definitions (name, definition_type, definition, metadata, owner_id)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, created_at, updated_at
            """, (
                definition.name,
                definition.definition_type,
                psycopg2.extras.Json(definition.definition),
                psycopg2.extras.Json(definition.metadata) if definition.metadata else None,
                current_user.id
            ))

            row = cur.fetchone()
            conn.commit()

            logger.info(f"Created query definition '{definition.name}' (ID {row[0]}) by user {current_user.id}")

            return QueryDefinitionCreateResponse(
                id=row[0],
                name=definition.name,
                definition_type=definition.definition_type,
                created_at=row[1],
                updated_at=row[2]
            )
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to create query definition: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create query definition: {str(e)}"
        )
    finally:
        conn.close()


@router.put(
    "/{definition_id}",
    response_model=QueryDefinitionRead,
    summary="Update query definition"
)
async def update_query_definition(
    definition_id: int,
    update: QueryDefinitionUpdate,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Update a query definition.

    Only the owner or admins can update a definition.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check exists and ownership
            cur.execute(
                "SELECT owner_id FROM kg_api.query_definitions WHERE id = %s",
                (definition_id,)
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Query definition not found: {definition_id}"
                )

            owner_id = row[0]
            if owner_id is not None and owner_id != current_user.id:
                if current_user.role not in ("admin", "platform_admin"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied to update this query definition"
                    )

            # Build update query
            updates = []
            params = []

            if update.name is not None:
                updates.append("name = %s")
                params.append(update.name)

            if update.definition is not None:
                updates.append("definition = %s")
                params.append(psycopg2.extras.Json(update.definition))

            if update.metadata is not None:
                updates.append("metadata = %s")
                params.append(psycopg2.extras.Json(update.metadata))

            if not updates:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No fields to update"
                )

            params.append(definition_id)
            query = f"""
                UPDATE kg_api.query_definitions
                SET {', '.join(updates)}
                WHERE id = %s
                RETURNING id, name, definition_type, definition, metadata, owner_id, created_at, updated_at
            """

            cur.execute(query, params)
            row = cur.fetchone()
            conn.commit()

            logger.info(f"Updated query definition {definition_id} by user {current_user.id}")

            return QueryDefinitionRead(
                id=row[0],
                name=row[1],
                definition_type=row[2],
                definition=row[3],
                metadata=row[4],
                owner_id=row[5],
                created_at=row[6],
                updated_at=row[7]
            )
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to update query definition: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update query definition: {str(e)}"
        )
    finally:
        conn.close()


@router.delete(
    "/{definition_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete query definition"
)
async def delete_query_definition(
    definition_id: int,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Delete a query definition.

    Only the owner or admins can delete a definition.
    Note: Artifacts linked to this definition will have their query_definition_id set to NULL.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check exists and ownership
            cur.execute(
                "SELECT owner_id FROM kg_api.query_definitions WHERE id = %s",
                (definition_id,)
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Query definition not found: {definition_id}"
                )

            owner_id = row[0]
            if owner_id is not None and owner_id != current_user.id:
                if current_user.role not in ("admin", "platform_admin"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied to delete this query definition"
                    )

            # Delete (artifacts will have FK set to NULL due to ON DELETE SET NULL)
            cur.execute(
                "DELETE FROM kg_api.query_definitions WHERE id = %s",
                (definition_id,)
            )
            conn.commit()

            logger.info(f"Deleted query definition {definition_id} by user {current_user.id}")
    finally:
        conn.close()
