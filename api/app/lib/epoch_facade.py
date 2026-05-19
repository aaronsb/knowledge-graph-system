"""
EpochFacade — read-side surface for the ADR-203 graph epoch event log.

Mirrors the construction style of GraphFacade and GraphQueryFacade:
attached lazily as a property on AGEClient (`client.epochs`), takes the
client in its constructor, and exposes typed, parameterized methods so
route handlers never need an `execute_raw` escape hatch.

Two-phase pattern for per-concept lifetime:
  Phase 1: Cypher (via client._execute_cypher) to walk EVIDENCED_BY
           with ORDER BY / SKIP / LIMIT pushed into the graph engine.
  Phase 2: SQL (via client.pool, RealDictCursor) to hydrate event
           metadata in one round-trip and pick up the
           `semantic_wallclock` discriminator from migration 064's
           graph_epoch_kinds lookup table.

Analytics signals (anchor / hot / stale / acceleration) are derivable
from the primitives here but are deliberately not part of this surface;
they will land as either follow-up facade methods or composable program
nodes after the underlying data has been exercised in practice.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from psycopg2 import extras

logger = logging.getLogger(__name__)

# Defaults / hard caps for lifetime pagination.
# A concept's re-evidence chain is unbounded in principle, so the route
# must impose a ceiling — see code review #2 (PR #382).
LIFETIME_DEFAULT_LIMIT = 200
LIFETIME_MAX_LIMIT = 1000


class EpochFacade:
    """ADR-203 epoch event log read surface."""

    def __init__(self, client):
        """
        Args:
            client: AGEClient instance (provides _execute_cypher and pool)
        """
        self._client = client

    # -------------------------------------------------------------------------
    # Per-concept re-evidence stream
    # -------------------------------------------------------------------------

    def get_concept_lifetime(
        self,
        concept_id: str,
        limit: int = LIFETIME_DEFAULT_LIMIT,
        offset: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """
        Return the ordered re-evidence stream for a single Concept.

        Output shape:
            {
                "concept_id": str,
                "label": str | None,
                "instances": [
                    {
                        "instance_id": str,
                        "quote": str,
                        "source_id": str | None,
                        "event_id": int | None,
                        "occurred_at": str | None,  # ISO-8601 UTC
                        "kind": str | None,
                        "actor": str | None,
                        "semantic_wallclock": bool | None,
                    },
                    ...
                ],
                "total_instances": int,      # Full chain size (independent of paging)
                "returned_instances": int,   # len(instances) for this page
                "distinct_epochs": int,      # In returned page only
                "pre_epoch_count": int,      # In returned page only
                "limit": int,
                "offset": int,
                "has_more": bool,
            }

        Returns None if the concept does not exist.

        Instances are ordered by `i.created_at_event_id ASC NULLS LAST` in
        Cypher, then `i.instance_id ASC` as a deterministic tiebreaker —
        the pre-epoch (NULL event_id) cohort trails the chronologically
        tagged stream.
        """
        limit = max(1, min(int(limit), LIFETIME_MAX_LIMIT))
        offset = max(0, int(offset))

        label_row = self._client._execute_cypher(
            """
            MATCH (c:Concept {concept_id: $concept_id})
            RETURN c.label AS label
            """,
            params={"concept_id": concept_id},
            fetch_one=True,
        )
        if not label_row:
            return None
        label = label_row.get("label")

        # Total count for paging metadata. Independent of limit/offset so
        # callers always know the true chain size. count(DISTINCT i)
        # defends against duplicate :EVIDENCED_BY edges; the unioned
        # number is what corresponds to the deduplicated page query.
        total_row = self._client._execute_cypher(
            """
            MATCH (c:Concept {concept_id: $concept_id})-[:EVIDENCED_BY]->(i:Instance)
            RETURN count(DISTINCT i) AS total
            """,
            params={"concept_id": concept_id},
            fetch_one=True,
        )
        total_instances = int(total_row.get("total", 0)) if total_row else 0

        # Page query. Fetch limit+1 to set has_more without a second count.
        # Sort is in Cypher to avoid materializing the whole chain in Python.
        # RETURN DISTINCT defends against duplicate :FROM_SOURCE or
        # :EVIDENCED_BY edges in the graph (visible on installs with
        # broken/retried ingests) — without it the join fans out and
        # corrupts both the page contents and the has_more reckoning.
        instance_rows = self._client._execute_cypher(
            """
            MATCH (c:Concept {concept_id: $concept_id})-[:EVIDENCED_BY]->(i:Instance)
            OPTIONAL MATCH (i)-[:FROM_SOURCE]->(s:Source)
            RETURN DISTINCT
                i.instance_id AS instance_id,
                i.quote AS quote,
                s.source_id AS source_id,
                i.created_at_event_id AS event_id
            ORDER BY i.created_at_event_id, i.instance_id
            SKIP $offset
            LIMIT $page_size
            """,
            params={
                "concept_id": concept_id,
                "offset": offset,
                "page_size": limit + 1,
            },
            fetch_one=False,
        ) or []

        has_more = len(instance_rows) > limit
        page_rows = instance_rows[:limit]

        event_ids: List[int] = sorted({
            row["event_id"] for row in page_rows
            if isinstance(row.get("event_id"), int)
        })
        epoch_lookup = self._hydrate_epochs(event_ids)

        instances: List[Dict[str, Any]] = []
        pre_epoch = 0
        for row in page_rows:
            eid = row.get("event_id")
            if not isinstance(eid, int):
                pre_epoch += 1
                eid_val: Optional[int] = None
            else:
                eid_val = eid
            meta = epoch_lookup.get(eid_val, {}) if eid_val is not None else {}
            instances.append({
                "instance_id": row.get("instance_id"),
                "quote": row.get("quote"),
                "source_id": row.get("source_id"),
                "event_id": eid_val,
                "occurred_at": meta.get("occurred_at"),
                "kind": meta.get("kind"),
                "actor": meta.get("actor"),
                "semantic_wallclock": meta.get("semantic_wallclock"),
            })

        return {
            "concept_id": concept_id,
            "label": label,
            "instances": instances,
            "total_instances": total_instances,
            "returned_instances": len(instances),
            "distinct_epochs": len(event_ids),
            "pre_epoch_count": pre_epoch,
            "limit": limit,
            "offset": offset,
            "has_more": has_more,
        }

    # -------------------------------------------------------------------------
    # Event log pagination
    # -------------------------------------------------------------------------

    def list_epochs(
        self,
        kind: Optional[str] = None,
        since: Optional[Union[datetime, str]] = None,
        until: Optional[Union[datetime, str]] = None,
        actor: Optional[str] = None,
        cursor: Optional[int] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Cursor-paginated read of kg_api.graph_epochs, joined to
        graph_epoch_kinds so callers receive `semantic_wallclock` per row.

        Cursor semantics: `cursor` is the *last* event_id from the previous
        page. The next page returns events with `event_id < cursor` in
        descending order. The response's `next_cursor` is the smallest
        event_id in the returned page (None if no more pages).

        Cursor (rather than limit/offset) is used here intentionally:
        event_id is monotonic, and cursor pagination is stable under
        concurrent inserts. Limit/offset is the project default for
        non-monotonic lists; this endpoint diverges for that specific
        reason.

        Returns:
            {
                "events": [ ... ],         # each row has semantic_wallclock
                "next_cursor": int | None,
                "limit": int,
            }
        """
        limit = max(1, min(int(limit), 500))

        clauses: List[str] = []
        params: Dict[str, Any] = {"limit": limit}

        if kind is not None:
            clauses.append("e.kind = %(kind)s")
            params["kind"] = kind
        if since is not None:
            clauses.append("e.occurred_at >= %(since)s")
            params["since"] = since
        if until is not None:
            clauses.append("e.occurred_at <= %(until)s")
            params["until"] = until
        if actor is not None:
            clauses.append("e.actor = %(actor)s")
            params["actor"] = actor
        if cursor is not None:
            clauses.append("e.event_id < %(cursor)s")
            params["cursor"] = int(cursor)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        sql = f"""
            SELECT
                e.event_id,
                e.occurred_at,
                e.kind,
                e.actor,
                e.counter_after,
                e.metadata,
                k.semantic_wallclock
            FROM kg_api.graph_epochs e
            LEFT JOIN kg_api.graph_epoch_kinds k ON k.kind = e.kind
            {where}
            ORDER BY e.event_id DESC
            LIMIT %(limit)s
        """

        rows = self._execute_sql(sql, params)

        events = [
            {
                "event_id": row["event_id"],
                "occurred_at": (
                    row["occurred_at"].isoformat() if row["occurred_at"] else None
                ),
                "kind": row["kind"],
                "actor": row["actor"],
                "counter_after": row["counter_after"],
                "metadata": row["metadata"] or {},
                "semantic_wallclock": row["semantic_wallclock"],
            }
            for row in rows
        ]
        next_cursor = events[-1]["event_id"] if len(events) == limit else None
        return {"events": events, "next_cursor": next_cursor, "limit": limit}

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _hydrate_epochs(self, event_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Batch-fetch epoch metadata for a list of event_ids, joining the
        kinds lookup so callers get `semantic_wallclock` without a second
        round-trip."""
        if not event_ids:
            return {}
        rows = self._execute_sql(
            """
            SELECT
                e.event_id,
                e.occurred_at,
                e.kind,
                e.actor,
                k.semantic_wallclock
            FROM kg_api.graph_epochs e
            LEFT JOIN kg_api.graph_epoch_kinds k ON k.kind = e.kind
            WHERE e.event_id = ANY(%(ids)s)
            """,
            {"ids": event_ids},
        )
        return {
            row["event_id"]: {
                "occurred_at": (
                    row["occurred_at"].isoformat() if row["occurred_at"] else None
                ),
                "kind": row["kind"],
                "actor": row["actor"],
                "semantic_wallclock": row["semantic_wallclock"],
            }
            for row in rows
        }

    def _execute_sql(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Run parameterized SQL via the AGEClient's connection pool.

        Returns dict-shaped rows (RealDictCursor) so consumers index by
        column name and stay robust under SELECT-column reordering — the
        idiom used by GraphFacade._execute_sql.
        """
        conn = self._client.pool.getconn()
        try:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                cur.execute(query, params or {})
                return cur.fetchall()
        finally:
            conn.commit()
            self._client.pool.putconn(conn)
