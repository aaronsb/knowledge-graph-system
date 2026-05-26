"""
Shared graph-generation probe (ADR-201 Phase 5f).

The grounding/confidence caching layer keys cache entries on
`(concept_id, graph_generation)`. Generation comes from one of two sources,
in priority order:

1. `graph_accel.generation` — bumped by `graph_accel_invalidate` after
   any mutation that affects topology. Authoritative when the extension
   is loaded on the connection.
2. `graph_metrics.vocabulary_change_counter` — the legacy counter that
   predates graph_accel. Used as a fallback so cache keys stay sane on
   connections that haven't loaded the extension yet (different pool
   conns acquire the extension lazily).

The probe runs inside a `SAVEPOINT` so a "graph_accel.generation table
doesn't exist" failure on this connection rolls back cleanly without
aborting the outer transaction.

Pre-#277 this logic lived in three places: query.py's QueryMixin had
the cursor variant; confidence_analyzer.py had both a cursor variant
(_get_graph_generation_on_cursor) and a connection-acquiring variant
(_get_graph_generation). All three had identical bodies modulo
savepoint names. Drift risk was the issue the reviewer flagged on
PR #276 — adding a new tier or changing the fallback table would need
three coordinated edits. One free function now, the caller decides
whether to acquire a connection.
"""

from typing import Any


def get_graph_generation(cur: Any, savepoint_name: str = "gen_check") -> int:
    """
    Read the current graph generation using a caller-provided cursor.

    Args:
        cur: psycopg2 cursor (RealDictCursor expected for `row['key']` access).
        savepoint_name: SQL identifier for the savepoint. Callers that nest
            this probe inside other savepoint scopes should pass a distinct
            name so rollback targets the right frame.

    Returns:
        Generation counter — either graph_accel's value, or the legacy
        vocabulary_change_counter, or 0 if both queries fail.
    """
    # Tier 1: graph_accel.generation (authoritative when extension is loaded).
    try:
        cur.execute(f"SAVEPOINT {savepoint_name}")
        cur.execute(
            "SELECT current_generation FROM graph_accel.generation "
            "WHERE graph_name = 'knowledge_graph'"
        )
        row = cur.fetchone()
        cur.execute(f"RELEASE SAVEPOINT {savepoint_name}")
        if row:
            return int(row["current_generation"])
    except Exception:
        try:
            cur.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
        except Exception:
            pass

    # Tier 2: legacy vocabulary_change_counter.
    try:
        cur.execute(
            "SELECT counter FROM graph_metrics "
            "WHERE metric_name = 'vocabulary_change_counter'"
        )
        row = cur.fetchone()
        return int(row["counter"]) if row else 0
    except Exception:
        return 0
