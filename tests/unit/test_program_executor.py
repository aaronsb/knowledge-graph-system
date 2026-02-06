"""
GraphProgram Executor Tests (ADR-500 Phase 3).

Tests for the executor orchestration with mocked dispatch. Verifies
statement sequencing, operator application, conditional branching,
assert abort, step logging, and timeout handling.

These tests run WITHOUT Docker, database, or API server.

Run:
    pytest tests/unit/test_program_executor.py -v
"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from api.app.models.program import (
    GraphProgram,
    Statement,
    CypherOp,
    ApiOp,
    ConditionalOp,
    HasResultsCondition,
    EmptyCondition,
    CountGteCondition,
    ProgramMetadata,
    WorkingGraph,
    RawNode,
    RawLink,
)
from api.app.services.program_executor import execute_program


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node(cid: str) -> RawNode:
    return RawNode(concept_id=cid, label=cid)


def _program(statements: list) -> GraphProgram:
    return GraphProgram(
        version=1,
        metadata=ProgramMetadata(name="test"),
        statements=statements,
    )


def _cypher_stmt(op: str, query: str = "MATCH (n) RETURN n") -> Statement:
    return Statement(op=op, operation=CypherOp(type='cypher', query=query))


def _api_stmt(op: str, endpoint: str = "/search/concepts", params: dict = None) -> Statement:
    return Statement(
        op=op,
        operation=ApiOp(type='api', endpoint=endpoint, params=params or {"query": "test"}),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSequentialExecution:

    @pytest.mark.asyncio
    async def test_three_statements_in_order(self):
        """Statements execute sequentially, each adding to W."""
        program = _program([
            _cypher_stmt('+'),
            _cypher_stmt('+'),
            _cypher_stmt('+'),
        ])

        call_count = [0]

        def mock_dispatch(ctx, op):
            call_count[0] += 1
            return WorkingGraph(
                nodes=[_node(f"n{call_count[0]}")],
                links=[],
            )

        client = MagicMock()
        with patch('api.app.services.program_executor.dispatch_cypher', side_effect=mock_dispatch):
            result = await execute_program(program, client)

        assert len(result.result.nodes) == 3
        assert len(result.log) == 3
        assert result.aborted is None

    @pytest.mark.asyncio
    async def test_difference_removes_nodes(self):
        """A - operator removes nodes added by prior +."""
        program = _program([
            _cypher_stmt('+'),
            _cypher_stmt('-'),
        ])

        results = [
            WorkingGraph(nodes=[_node("a"), _node("b")], links=[]),
            WorkingGraph(nodes=[_node("b")], links=[]),
        ]
        idx = [0]

        def mock_dispatch(ctx, op):
            r = results[idx[0]]
            idx[0] += 1
            return r

        client = MagicMock()
        with patch('api.app.services.program_executor.dispatch_cypher', side_effect=mock_dispatch):
            result = await execute_program(program, client)

        assert len(result.result.nodes) == 1
        assert result.result.nodes[0].concept_id == "a"


class TestAssertAbort:

    @pytest.mark.asyncio
    async def test_abort_on_empty_assert(self):
        """! operator aborts when result is empty."""
        program = _program([
            _cypher_stmt('+'),
            _cypher_stmt('!'),
        ])

        results = [
            WorkingGraph(nodes=[_node("a")], links=[]),
            WorkingGraph(nodes=[], links=[]),  # empty → abort
        ]
        idx = [0]

        def mock_dispatch(ctx, op):
            r = results[idx[0]]
            idx[0] += 1
            return r

        client = MagicMock()
        with patch('api.app.services.program_executor.dispatch_cypher', side_effect=mock_dispatch):
            result = await execute_program(program, client)

        assert result.aborted is not None
        assert result.aborted["statement"] == 1
        assert "empty result" in result.aborted["reason"]
        # W should retain pre-failure state (node "a" from first statement)
        assert len(result.result.nodes) == 1
        assert result.result.nodes[0].concept_id == "a"

    @pytest.mark.asyncio
    async def test_assert_nonempty_continues(self):
        """! operator with non-empty result applies union and continues."""
        program = _program([
            _cypher_stmt('!'),
        ])

        def mock_dispatch(ctx, op):
            return WorkingGraph(nodes=[_node("a")], links=[])

        client = MagicMock()
        with patch('api.app.services.program_executor.dispatch_cypher', side_effect=mock_dispatch):
            result = await execute_program(program, client)

        assert result.aborted is None
        assert len(result.result.nodes) == 1


class TestConditionalBranching:

    @pytest.mark.asyncio
    async def test_then_branch_when_nonempty(self):
        """Conditional takes 'then' branch when W has nodes."""
        # First add a node, then conditional checks has_results
        program = _program([
            _cypher_stmt('+'),
            Statement(
                op='+',
                operation=ConditionalOp(
                    type='conditional',
                    condition=HasResultsCondition(test='has_results'),
                    then=[_cypher_stmt('+')],
                    **{'else': [_cypher_stmt('+')]},
                ),
            ),
        ])

        call_count = [0]

        def mock_dispatch(ctx, op):
            call_count[0] += 1
            return WorkingGraph(nodes=[_node(f"n{call_count[0]}")], links=[])

        client = MagicMock()
        with patch('api.app.services.program_executor.dispatch_cypher', side_effect=mock_dispatch):
            result = await execute_program(program, client)

        # Check the conditional log entry
        conditional_log = [e for e in result.log if e.operation_type == 'conditional']
        assert len(conditional_log) == 1
        assert conditional_log[0].branch_taken == 'then'

    @pytest.mark.asyncio
    async def test_else_branch_when_empty(self):
        """Conditional takes 'else' branch when W is empty."""
        program = _program([
            Statement(
                op='+',
                operation=ConditionalOp(
                    type='conditional',
                    condition=HasResultsCondition(test='has_results'),
                    then=[_cypher_stmt('+')],
                    **{'else': [_cypher_stmt('+')]},
                ),
            ),
        ])

        def mock_dispatch(ctx, op):
            return WorkingGraph(nodes=[_node("from_else")], links=[])

        client = MagicMock()
        with patch('api.app.services.program_executor.dispatch_cypher', side_effect=mock_dispatch):
            result = await execute_program(program, client)

        conditional_log = [e for e in result.log if e.operation_type == 'conditional']
        assert len(conditional_log) == 1
        assert conditional_log[0].branch_taken == 'else'


class TestStepLog:

    @pytest.mark.asyncio
    async def test_log_entries_shape(self):
        """Log entries have correct fields and ordering."""
        program = _program([
            _cypher_stmt('+'),
            _api_stmt('?'),
        ])

        def mock_cypher(ctx, op):
            return WorkingGraph(nodes=[_node("a")], links=[])

        def mock_api(ctx, op):
            return WorkingGraph(nodes=[], links=[])

        client = MagicMock()
        with (
            patch('api.app.services.program_executor.dispatch_cypher', side_effect=mock_cypher),
            patch('api.app.services.program_executor.dispatch_api', side_effect=mock_api),
        ):
            result = await execute_program(program, client)

        assert len(result.log) == 2

        log0 = result.log[0]
        assert log0.statement == 0
        assert log0.op == '+'
        assert log0.operation_type == 'cypher'
        assert log0.nodes_affected == 1
        assert log0.w_size == {"nodes": 1, "links": 0}
        assert log0.duration_ms >= 0

        log1 = result.log[1]
        assert log1.statement == 1
        assert log1.op == '?'
        assert log1.operation_type == 'api'
        assert log1.nodes_affected == 0  # optional with empty = no-op


class TestErrorHandling:

    @pytest.mark.asyncio
    async def test_dispatch_error_returns_partial(self):
        """A dispatch error mid-program returns partial W and aborted info."""
        program = _program([
            _cypher_stmt('+'),
            _cypher_stmt('+'),
        ])

        call_count = [0]

        def mock_dispatch(ctx, op):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("Connection lost")
            return WorkingGraph(nodes=[_node("a")], links=[])

        client = MagicMock()
        with patch('api.app.services.program_executor.dispatch_cypher', side_effect=mock_dispatch):
            result = await execute_program(program, client)

        assert result.aborted is not None
        assert "Connection lost" in result.aborted["reason"]
        assert len(result.result.nodes) == 1  # partial W from first statement
