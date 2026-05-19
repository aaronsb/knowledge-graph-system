"""
EpochFacade — read-side surface for the ADR-203 graph epoch event log.

Mirrors the construction style of GraphFacade and GraphQueryFacade:
attached lazily as a property on AGEClient (`client.epochs`), takes the
client in its constructor, and exposes typed, parameterized methods so
route handlers never need an `execute_raw` escape hatch.

Two-phase pattern for per-concept lifetime:
  Phase 1: Cypher (via client._execute_cypher) to walk EVIDENCED_BY
  Phase 2: SQL (via client.pool) to hydrate event metadata in one shot

Analytics signals (anchor / hot / stale / acceleration) are derivable
from the primitives here but are deliberately not part of this surface;
they will land as either follow-up facade methods or composable program
nodes after the underlying data has been exercised in practice.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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

    def get_concept_lifetime(self, concept_id: str) -> Optional[Dict[str, Any]]:
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
                    },
                    ...
                ],
                "total_instances": int,
                "distinct_epochs": int,
                "pre_epoch_count": int,  # NULL-event_id cohort
            }

        Returns None if the concept does not exist.

        Instances are ordered by event_id ascending (NULL last — the
        "pre-epoch cohort" trails the chronologically-tagged stream).
        """
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

        instance_rows = self._client._execute_cypher(
            """
            MATCH (c:Concept {concept_id: $concept_id})-[:EVIDENCED_BY]->(i:Instance)
            OPTIONAL MATCH (i)-[:FROM_SOURCE]->(s:Source)
            RETURN
                i.instance_id AS instance_id,
                i.quote AS quote,
                s.source_id AS source_id,
                i.created_at_event_id AS event_id
            """,
            params={"concept_id": concept_id},
            fetch_one=False,
        ) or []

        event_ids: List[int] = sorted({
            row["event_id"] for row in instance_rows
            if isinstance(row.get("event_id"), int)
        })
        epoch_lookup = self._hydrate_epochs(event_ids)

        instances: List[Dict[str, Any]] = []
        pre_epoch = 0
        for row in instance_rows:
            eid = row.get("event_id")
            if not isinstance(eid, int):
                pre_epoch += 1
                eid_val = None
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
            })

        instances.sort(
            key=lambda i: (
                i["event_id"] is None,
                i["event_id"] or 0,
                i.get("instance_id") or "",
            )
        )

        return {
            "concept_id": concept_id,
            "label": label,
            "instances": instances,
            "total_instances": len(instances),
            "distinct_epochs": len(event_ids),
            "pre_epoch_count": pre_epoch,
        }

    # -------------------------------------------------------------------------
    # Event log pagination
    # -------------------------------------------------------------------------

    def list_epochs(
        self,
        kind: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        actor: Optional[str] = None,
        cursor: Optional[int] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Cursor-paginated read of kg_api.graph_epochs.

        Cursor semantics: `cursor` is the *last* event_id from the previous
        page. The next page returns events with `event_id < cursor` in
        descending order. The response's `next_cursor` is the smallest
        event_id in the returned page (None if no more pages).

        Filters apply in addition to the cursor. Wall-clock filters
        (`since`/`until`) apply regardless of `kind`; callers wanting
        "ingestion history within window" should pass both.

        Returns:
            {
                "events": [ ... ],
                "next_cursor": int | None,
                "limit": int,
            }
        """
        limit = max(1, min(int(limit), 500))

        clauses: List[str] = []
        params: Dict[str, Any] = {"limit": limit}

        if kind is not None:
            clauses.append("kind = %(kind)s")
            params["kind"] = kind
        if since is not None:
            clauses.append("occurred_at >= %(since)s")
            params["since"] = since
        if until is not None:
            clauses.append("occurred_at <= %(until)s")
            params["until"] = until
        if actor is not None:
            clauses.append("actor = %(actor)s")
            params["actor"] = actor
        if cursor is not None:
            clauses.append("event_id < %(cursor)s")
            params["cursor"] = int(cursor)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        sql = f"""
            SELECT event_id, occurred_at, kind, actor, counter_after, metadata
            FROM kg_api.graph_epochs
            {where}
            ORDER BY event_id DESC
            LIMIT %(limit)s
        """

        rows = self._execute_sql(sql, params)

        events = [
            {
                "event_id": row[0],
                "occurred_at": row[1].isoformat() if row[1] else None,
                "kind": row[2],
                "actor": row[3],
                "counter_after": row[4],
                "metadata": row[5] or {},
            }
            for row in rows
        ]
        next_cursor = events[-1]["event_id"] if len(events) == limit else None
        return {"events": events, "next_cursor": next_cursor, "limit": limit}

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _hydrate_epochs(self, event_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Batch-fetch epoch metadata for a list of event_ids."""
        if not event_ids:
            return {}
        rows = self._execute_sql(
            "SELECT event_id, occurred_at, kind, actor "
            "FROM kg_api.graph_epochs WHERE event_id = ANY(%(ids)s)",
            {"ids": event_ids},
        )
        return {
            row[0]: {
                "occurred_at": row[1].isoformat() if row[1] else None,
                "kind": row[2],
                "actor": row[3],
            }
            for row in rows
        }

    def _execute_sql(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[tuple]:
        """Run parameterized SQL via the AGEClient's connection pool."""
        conn = self._client.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params or {})
                return cur.fetchall()
        finally:
            conn.commit()
            self._client.pool.putconn(conn)
