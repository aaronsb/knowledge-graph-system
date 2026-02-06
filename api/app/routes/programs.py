"""
Program notarization, execution, and chain endpoints (ADR-500).

Server-side validation, storage, retrieval, execution, and chained execution
of GraphProgram ASTs. Programs are notarized (validated + signed) before storage.

Endpoints:
  POST /programs          — validate + store → ID + notarized program
  POST /programs/validate — dry-run validation (no storage)
  GET  /programs          — list stored programs (with optional search)
  GET  /programs/{id}     — retrieve a notarized program
  POST /programs/execute  — execute or chain programs server-side

@verified 0000000
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status, Depends
import logging
import psycopg2.extras

from ..models.program import (
    ProgramSubmission,
    ProgramCreateResponse,
    ProgramReadResponse,
    ProgramExecuteRequest,
    ProgramResult,
    BatchProgramResult,
    ProgramListItem,
    GraphProgram,
    WorkingGraph,
)
from ..services.program_validator import (
    validate_program,
    ValidationResult,
)
from ..services.program_executor import execute_program
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
            detail="Failed to store program",
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


@router.post(
    "/execute",
    summary="Execute or chain programs server-side",
)
async def execute_program_endpoint(
    request: ProgramExecuteRequest,
    current_user: UserInDB = Depends(get_current_user),
):
    """
    Execute a GraphProgram or chain of programs server-side.

    Single mode: provide program_id or inline program AST.
    Chain mode: provide a deck array of program references. W threads through
    each program sequentially — program N's output becomes program N+1's input.

    All programs are re-validated before execution (defense in depth).
    """
    # Chain mode (deck)
    if request.deck is not None:
        if request.program_id is not None or request.program is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide deck OR (program_id/program), not both",
            )
        if len(request.deck) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Deck must contain at least one entry",
            )
        if len(request.deck) > 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Deck too large: {len(request.deck)} entries (max 10)",
            )
        return await _execute_deck(request.deck, current_user)

    # Single mode (existing behavior)
    if request.program_id is not None and request.program is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide program_id or program, not both",
        )
    if request.program_id is None and request.program is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide program_id or program",
        )

    # Resolve program data
    if request.program_id is not None:
        program_data = _load_program_definition(request.program_id, current_user)
    else:
        program_data = request.program

    # Re-validate (defense in depth)
    validation = validate_program(program_data)
    if not validation.valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Program validation failed",
                "validation": validation.model_dump(),
            },
        )

    program = GraphProgram.model_validate(program_data)

    # Execute
    from ..lib.age_client import AGEClient
    client = AGEClient()
    try:
        result = await execute_program(program, client, params=request.params)
        return result
    finally:
        client.close()


async def _execute_deck(deck, current_user) -> BatchProgramResult:
    """Execute a chain of programs, threading W through each."""
    from ..lib.age_client import AGEClient

    # Resolve and validate all programs upfront before executing any
    validated_programs = []
    for i, entry in enumerate(deck):
        if entry.program_id is not None and entry.program is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Deck entry {i}: provide program_id or program, not both",
            )
        if entry.program_id is None and entry.program is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Deck entry {i}: provide program_id or program",
            )

        if entry.program_id is not None:
            program_data = _load_program_definition(entry.program_id, current_user)
        else:
            program_data = entry.program

        validation = validate_program(program_data)
        if not validation.valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": f"Deck entry {i}: program validation failed",
                    "validation": validation.model_dump(),
                },
            )

        validated_programs.append((
            GraphProgram.model_validate(program_data),
            entry.params,
        ))

    # Execute chain: thread W through each program
    client = AGEClient()
    try:
        w = WorkingGraph()
        program_results = []

        for program, params in validated_programs:
            result = await execute_program(
                program, client, params=params, initial_w=w,
            )
            program_results.append(result)

            if result.aborted:
                return BatchProgramResult(
                    result=result.result,
                    programs=program_results,
                    aborted=result.aborted,
                )

            # Thread W forward
            w = result.result

        return BatchProgramResult(
            result=w,
            programs=program_results,
        )
    finally:
        client.close()


def _load_program_definition(program_id: int, current_user: UserInDB) -> dict:
    """Load a program's raw definition from the database."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT definition, owner_id
                FROM kg_api.query_definitions
                WHERE id = %s AND definition_type = 'program'
            """, (program_id,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Program not found: {program_id}",
                )

            owner_id = row[1]
            if owner_id is not None and owner_id != current_user.id:
                if current_user.role not in ("admin", "platform_admin"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied to this program",
                    )

            return row[0]
    finally:
        conn.close()


@router.get(
    "",
    response_model=List[ProgramListItem],
    summary="List stored programs",
)
async def list_programs(
    search: Optional[str] = Query(None, description="Search name/description"),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserInDB = Depends(get_current_user),
):
    """
    List stored programs with optional text search.

    Returns lightweight metadata (id, name, description, statement_count).
    Search matches against program name and metadata description.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if search:
                cur.execute("""
                    SELECT id, name,
                           definition->'metadata'->>'description' as description,
                           jsonb_array_length(definition->'statements') as stmt_count,
                           created_at
                    FROM kg_api.query_definitions
                    WHERE definition_type = 'program'
                      AND (owner_id IS NULL OR owner_id = %s
                           OR %s IN ('admin', 'platform_admin'))
                      AND (name ILIKE %s
                           OR definition->'metadata'->>'description' ILIKE %s)
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (
                    current_user.id, current_user.role,
                    f'%{search}%', f'%{search}%',
                    limit,
                ))
            else:
                cur.execute("""
                    SELECT id, name,
                           definition->'metadata'->>'description' as description,
                           jsonb_array_length(definition->'statements') as stmt_count,
                           created_at
                    FROM kg_api.query_definitions
                    WHERE definition_type = 'program'
                      AND (owner_id IS NULL OR owner_id = %s
                           OR %s IN ('admin', 'platform_admin'))
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (current_user.id, current_user.role, limit))

            rows = cur.fetchall()
            return [
                ProgramListItem(
                    id=row[0],
                    name=row[1],
                    description=row[2],
                    statement_count=row[3] or 0,
                    created_at=str(row[4]),
                )
                for row in rows
            ]
    finally:
        conn.close()


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

            # Check ownership (NULL owner_id = system-created, accessible to all authed users)
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
