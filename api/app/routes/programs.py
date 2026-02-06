"""
Program notarization endpoints (ADR-500 Phase 2b).

Server-side validation, storage, and retrieval of GraphProgram ASTs.
Programs are notarized (validated + signed) before storage. Only notarized
programs can be retrieved and executed by clients.

Three endpoints:
  POST /programs          — validate + store → ID + notarized program
  POST /programs/validate — dry-run validation (no storage)
  GET  /programs/{id}     — retrieve a notarized program

@verified 0000000
"""

from fastapi import APIRouter, HTTPException, status, Depends
import logging
import psycopg2.extras

from ..models.program import (
    ProgramSubmission,
    ProgramCreateResponse,
    ProgramReadResponse,
    GraphProgram,
)
from ..services.program_validator import (
    validate_program,
    ValidationResult,
)
from ..models.auth import UserInDB
from ..dependencies.auth import get_current_user, get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/programs", tags=["programs"])


@router.post(
    "",
    response_model=ProgramCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Notarize and store a program",
)
async def create_program(
    submission: ProgramSubmission,
    current_user: UserInDB = Depends(get_current_user),
):
    """
    Validate a GraphProgram and store it as a notarized program.

    The program AST is validated through all layers (deserialization,
    structural, safety). If valid, it is stored in query_definitions
    with definition_type='program' and returned with a storage ID.

    Invalid programs return 400 with structured validation errors.
    """
    result = validate_program(submission.program)

    if not result.valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Program validation failed",
                "validation": result.model_dump(),
            },
        )

    # Deserialize the validated program for storage
    program = GraphProgram.model_validate(submission.program)

    # Use metadata name, submission name, or fallback
    name = (
        submission.name
        or (program.metadata.name if program.metadata else None)
        or "Untitled program"
    )

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO kg_api.query_definitions
                    (name, definition_type, definition, owner_id)
                VALUES (%s, 'program', %s, %s)
                RETURNING id, created_at, updated_at
            """, (
                name,
                psycopg2.extras.Json(program.model_dump()),
                current_user.id,
            ))

            row = cur.fetchone()
            conn.commit()

            logger.info(
                f"Notarized program '{name}' (ID {row[0]}) by user {current_user.id}"
            )

            return ProgramCreateResponse(
                id=row[0],
                name=name,
                program=program,
                valid=True,
                created_at=str(row[1]),
                updated_at=str(row[2]),
            )
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to store program: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store program: {str(e)}",
        )
    finally:
        conn.close()


@router.post(
    "/validate",
    response_model=ValidationResult,
    summary="Validate a program (dry run)",
)
async def validate_program_endpoint(
    submission: ProgramSubmission,
    current_user: UserInDB = Depends(get_current_user),
):
    """
    Validate a GraphProgram without storing it.

    Returns the full validation result including errors and warnings.
    Useful for real-time editor feedback before committing to storage.
    """
    return validate_program(submission.program)


@router.get(
    "/{program_id}",
    response_model=ProgramReadResponse,
    summary="Retrieve a notarized program",
)
async def get_program(
    program_id: int,
    current_user: UserInDB = Depends(get_current_user),
):
    """
    Retrieve a notarized program by ID.

    Only the owner or admins can access the program.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, definition, owner_id, created_at, updated_at
                FROM kg_api.query_definitions
                WHERE id = %s AND definition_type = 'program'
            """, (program_id,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Program not found: {program_id}",
                )

            # Check ownership
            owner_id = row[3]
            if owner_id is not None and owner_id != current_user.id:
                if current_user.role not in ("admin", "platform_admin"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied to this program",
                    )

            program = GraphProgram.model_validate(row[2])

            return ProgramReadResponse(
                id=row[0],
                name=row[1],
                program=program,
                owner_id=row[3],
                created_at=str(row[4]),
                updated_at=str(row[5]),
            )
    finally:
        conn.close()
