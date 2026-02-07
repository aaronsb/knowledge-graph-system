"""
GraphProgram Executor (ADR-500 Phase 3).

Server-side execution of validated GraphProgram ASTs. Manages the WorkingGraph
lifecycle, statement dispatch, operator application, condition evaluation,
step logging, and abort handling.

Usage:
    from api.app.services.program_executor import execute_program

    result = await execute_program(program, client, params={})
"""

import time
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Union

from api.app.models.program import (
    GraphProgram,
    Statement,
    CypherOp,
    ApiOp,
    ConditionalOp,
    WorkingGraph,
    ProgramResult,
    StepLogEntry,
)
from api.app.services.program_operators import (
    apply_union,
    apply_difference,
    apply_intersect,
    apply_optional,
    apply_assert,
    AssertionAbort,
)
from api.app.services.program_dispatch import (
    DispatchContext,
    dispatch_cypher,
    dispatch_api,
)

PROGRAM_TIMEOUT_SECONDS = 60

logger = logging.getLogger(__name__)


async def execute_program(
    program: GraphProgram,
    client,
    params: Optional[Dict[str, Union[str, int, float]]] = None,
    initial_w: Optional[WorkingGraph] = None,
) -> ProgramResult:
    """Execute a validated GraphProgram server-side.

    Args:
        program: Validated GraphProgram AST.
        client: AGEClient instance (caller manages lifecycle).
        params: Runtime parameter values for $param substitution.
        initial_w: Optional seed WorkingGraph (for chained execution).

    Returns:
        ProgramResult with final WorkingGraph, step log, and optional abort info.
    """
    ctx = DispatchContext(client)
    w = initial_w if initial_w is not None else WorkingGraph()
    log: List[StepLogEntry] = []
    # Mutable counter so nested conditionals share the global statement index
    stmt_counter = [0]

    try:
        await asyncio.wait_for(
            _execute_statements(program.statements, w, ctx, log, stmt_counter),
            timeout=PROGRAM_TIMEOUT_SECONDS,
        )
    except AssertionAbort as e:
        return ProgramResult(
            result=w,
            log=log,
            aborted={"statement": e.statement, "reason": e.reason},
        )
    except asyncio.TimeoutError:
        return ProgramResult(
            result=w,
            log=log,
            aborted={
                "statement": stmt_counter[0],
                "reason": "Program execution timed out",
            },
        )
    except Exception as e:
        logger.error(
            f"Program execution error at statement {stmt_counter[0]}: {e}",
            exc_info=True,
        )
        return ProgramResult(
            result=w,
            log=log,
            aborted={
                "statement": stmt_counter[0],
                "reason": f"Execution error: {str(e)}",
            },
        )

    return ProgramResult(result=w, log=log)


async def _execute_statements(
    statements: List[Statement],
    w: WorkingGraph,
    ctx: DispatchContext,
    log: List[StepLogEntry],
    stmt_counter: List[int],
) -> None:
    """Execute a list of statements sequentially."""
    for stmt in statements:
        await _execute_one(stmt, w, ctx, log, stmt_counter)


async def _execute_one(
    stmt: Statement,
    w: WorkingGraph,
    ctx: DispatchContext,
    log: List[StepLogEntry],
    stmt_counter: List[int],
) -> None:
    """Execute a single statement: dispatch, apply operator, log."""
    index = stmt_counter[0]
    start = time.monotonic()
    op = stmt.operation

    # --- Conditional ---
    if isinstance(op, ConditionalOp):
        branch = _evaluate_condition(op, w)
        branch_stmts = op.then if branch == 'then' else (op.else_ or [])

        for nested_stmt in branch_stmts:
            await _execute_one(nested_stmt, w, ctx, log, stmt_counter)

        duration = (time.monotonic() - start) * 1000
        log.append(StepLogEntry(
            statement=index,
            op=stmt.op,
            operation_type='conditional',
            branch_taken=branch,
            nodes_affected=0,
            links_affected=0,
            w_size={"nodes": len(w.nodes), "links": len(w.links)},
            duration_ms=round(duration, 2),
        ))
        stmt_counter[0] += 1
        return

    # --- CypherOp / ApiOp ---
    if isinstance(op, CypherOp):
        r = await asyncio.to_thread(dispatch_cypher, ctx, op)
        operation_type = 'cypher'
    elif isinstance(op, ApiOp):
        r = await asyncio.to_thread(dispatch_api, ctx, op)
        operation_type = 'api'
    else:
        raise ValueError(f"Unknown operation type: {type(op)}")

    # Apply operator
    nodes_affected, links_affected = _apply_operator(stmt.op, w, r, index)

    duration = (time.monotonic() - start) * 1000
    log.append(StepLogEntry(
        statement=index,
        op=stmt.op,
        operation_type=operation_type,
        nodes_affected=nodes_affected,
        links_affected=links_affected,
        w_size={"nodes": len(w.nodes), "links": len(w.links)},
        duration_ms=round(duration, 2),
    ))
    stmt_counter[0] += 1


def _apply_operator(
    op: str, w: WorkingGraph, r: WorkingGraph, stmt_index: int
) -> Tuple[int, int]:
    """Apply the named operator to W with result R."""
    if op == '+':
        return apply_union(w, r)
    elif op == '-':
        return apply_difference(w, r)
    elif op == '&':
        return apply_intersect(w, r)
    elif op == '?':
        return apply_optional(w, r)
    elif op == '!':
        return apply_assert(w, r, stmt_index)
    else:
        raise ValueError(f"Unknown operator: {op}")


def _evaluate_condition(op: ConditionalOp, w: WorkingGraph) -> str:
    """Evaluate a ConditionalOp's condition against current W.

    Returns 'then' or 'else'.
    """
    cond = op.condition
    test = cond.test

    if test == 'has_results':
        return 'then' if len(w.nodes) > 0 else 'else'
    elif test == 'empty':
        return 'then' if len(w.nodes) == 0 else 'else'
    elif test == 'count_gte':
        return 'then' if len(w.nodes) >= cond.value else 'else'
    elif test == 'count_lte':
        return 'then' if len(w.nodes) <= cond.value else 'else'
    elif test == 'has_ontology':
        has = any(n.ontology == cond.ontology for n in w.nodes)
        return 'then' if has else 'else'
    elif test == 'has_relationship':
        has = any(l.relationship_type == cond.type for l in w.links)
        return 'then' if has else 'else'
    else:
        raise ValueError(f"Unknown condition test: {test}")
