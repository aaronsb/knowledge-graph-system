"""
Unit tests for the shared graph_generation helper (ADR-201 Phase 5f, #277).

Pre-#277 this two-tier probe lived in three places — query.py's QueryMixin
plus two methods on confidence_analyzer. PR #276's review flagged the drift
risk: a change to the generation source would need three coordinated edits.
This test locks in the single-helper contract by exercising each tier
directly, so any future drift in the SQL or the fallback chain surfaces
here instead of in opaque cache-invalidation bugs.
"""

import pytest

from api.app.lib.age_client.graph_generation import get_graph_generation


class FakeCursor:
    """
    Minimal scriptable cursor that records execute() calls and returns
    pre-programmed rows from fetchone(). Implements just enough of the
    psycopg2 interface to drive get_graph_generation; fakes over mocks
    so the test exercises real control flow (per the project mocking way).
    """

    def __init__(self, script):
        """
        Args:
            script: List of fetchone() return values OR Exception instances.
                Each call to execute() advances the script pointer; the next
                fetchone() returns/raises whatever sits at that index.
                Exceptions raised on execute() simulate Postgres errors
                (e.g. "relation graph_accel.generation does not exist").
        """
        self._script = script
        self._idx = -1
        self.executed = []  # SQL strings, in order, for assertions

    def execute(self, sql):
        self.executed.append(sql)
        self._idx += 1
        # Sentinel: an exception scripted at this index is raised from
        # the SELECT (not the SAVEPOINT/RELEASE/ROLLBACK).
        if self._idx < len(self._script) and isinstance(
            self._script[self._idx], Exception
        ):
            raise self._script[self._idx]

    def fetchone(self):
        if self._idx < 0 or self._idx >= len(self._script):
            return None
        value = self._script[self._idx]
        if isinstance(value, Exception):
            return None
        return value


class TestGraphGenerationHelper:
    """Three branches: tier-1 hit, tier-2 fallback, both fail."""

    def test_tier_1_hit_returns_graph_accel_generation(self):
        """
        Happy path: graph_accel.generation table exists, row present.
        Returns its current_generation as int. Fallback query never runs.
        """
        # execute() sequence: SAVEPOINT, SELECT graph_accel, RELEASE.
        # fetchone() returns the row after the SELECT.
        cur = FakeCursor(script=[
            None,                            # SAVEPOINT
            {"current_generation": 42},      # SELECT graph_accel
            None,                            # RELEASE
        ])

        result = get_graph_generation(cur)

        assert result == 42
        # Fallback SELECT was never issued — tier 1 short-circuits.
        assert not any("vocabulary_change_counter" in sql for sql in cur.executed)
        # Savepoint was released, not rolled back.
        assert any("RELEASE SAVEPOINT" in sql for sql in cur.executed)
        assert not any("ROLLBACK TO SAVEPOINT" in sql for sql in cur.executed)

    def test_tier_1_miss_falls_back_to_vocabulary_change_counter(self):
        """
        graph_accel.generation query raises (relation doesn't exist) → savepoint
        rolls back, fallback reads vocabulary_change_counter.
        """
        # execute() sequence: SAVEPOINT, SELECT graph_accel (raises),
        #                     ROLLBACK, SELECT graph_metrics
        # fetchone() returns the row after the second SELECT.
        cur = FakeCursor(script=[
            None,                                       # SAVEPOINT
            Exception("relation graph_accel.generation does not exist"),
            None,                                       # ROLLBACK
            {"counter": 17},                            # SELECT graph_metrics
        ])

        result = get_graph_generation(cur)

        assert result == 17
        assert any("ROLLBACK TO SAVEPOINT" in sql for sql in cur.executed)
        assert any("vocabulary_change_counter" in sql for sql in cur.executed)

    def test_both_tiers_fail_returns_zero(self):
        """
        Both graph_accel and graph_metrics raise — last-resort sentinel of 0
        keeps callers' cache invariants intact (a constant generation key
        won't churn the cache, even if it's a meaningless one).
        """
        cur = FakeCursor(script=[
            None,                            # SAVEPOINT
            Exception("graph_accel missing"),
            None,                            # ROLLBACK
            Exception("graph_metrics missing"),
        ])

        result = get_graph_generation(cur)

        assert result == 0

    def test_tier_1_row_present_with_zero_returns_zero(self):
        """
        Boundary: tier-1 returns a row with current_generation=0 (fresh DB).
        Helper returns 0 from tier 1 — does NOT fall through to tier 2.
        Critical for cache correctness: 0 is a valid generation, not absence.
        """
        cur = FakeCursor(script=[
            None,                            # SAVEPOINT
            {"current_generation": 0},       # SELECT graph_accel returns 0
            None,                            # RELEASE
        ])

        result = get_graph_generation(cur)

        assert result == 0
        # Fallback was NOT consulted — 0 is the authoritative answer.
        assert not any("vocabulary_change_counter" in sql for sql in cur.executed)

    def test_savepoint_name_threading(self):
        """
        Callers nesting this probe in larger savepoint scopes pass a distinct
        name. The helper has to emit that exact name in SAVEPOINT/RELEASE/
        ROLLBACK so rollback targets the correct frame.
        """
        cur = FakeCursor(script=[
            None,
            Exception("missing"),
            None,
            {"counter": 1},
        ])

        get_graph_generation(cur, savepoint_name="custom_name")

        # All three savepoint-related statements use the caller's name.
        assert "SAVEPOINT custom_name" in cur.executed[0]
        assert "ROLLBACK TO SAVEPOINT custom_name" in cur.executed[2]
