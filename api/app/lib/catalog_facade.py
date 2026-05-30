"""
Catalog Facade (ADR-501)

Read surface for hierarchical browse of the ontology -> document -> concept
hierarchy. The AGE graph is the source of truth; this facade maintains a
materialized index (kg_api.catalog_node + kg_api.catalog_edge) that is rebuilt
whenever the graph epoch (graph_change_counter) advances.

Membership is always derived from the graph's CANONICAL edges — never from the
denormalized Source.document string, which lags during annealing reassignment
(ADR-200):

    (o:Ontology)<-[:SCOPED_BY]-(s:Source)              ontology contains source
    (d:DocumentMeta)-[:HAS_SOURCE]->(s:Source)         document groups sources
    (c:Concept)-[:APPEARS]->(s:Source)                 concept appears in source

Derived hierarchy edges:
    ontology -> document   via  (o)<-[:SCOPED_BY]-(s)<-[:HAS_SOURCE]-(d)
    document -> concept    via  (d)-[:HAS_SOURCE]->(s)<-[:APPEARS]-(c)

Concepts are DAG nodes: one concept may belong to many documents/ontologies.
That is why membership lives in catalog_edge rather than a parent column.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# Advisory-lock key for serializing rebuilds across workers. Arbitrary constant,
# namespaced to the catalog. Only one worker rebuilds at a time; others serve
# the (slightly) stale index until the rebuild commits.
_CATALOG_REBUILD_LOCK = 0x0CA7A106  # "CATALOG" mnemonic

# Sort fields accepted by list_children, mapped to safe ORDER BY clauses.
# Whitelist only — never interpolate caller input into SQL.
_SORT_SQL = {
    "name": "n.name ASC",
    "child_count": "n.child_count DESC, n.name ASC",
    "created": "(n.properties->>'creation_epoch')::bigint DESC NULLS LAST, n.indexed_at ASC, n.name ASC",
}


class CatalogFacade:
    """Materialized-index read surface for catalog browse (ADR-501).

    Constructed with an AGEClient; reuses its connection pool. Browse reads come
    from the relational index; the index is rebuilt from the graph on epoch
    advance via ensure_fresh().
    """

    def __init__(self, client):
        """Store the AGE client and reuse its connection pool."""
        self.client = client

    # ------------------------------------------------------------------ epochs

    def _current_epoch(self, cur) -> int:
        """Current graph_change_counter — the same freshness signal artifacts use."""
        cur.execute("SELECT kg_api.get_graph_epoch()")
        row = cur.fetchone()
        # RealDictCursor returns a dict; plain cursor a tuple.
        if row is None:
            return 0
        val = list(row.values())[0] if isinstance(row, dict) else row[0]
        return int(val) if val is not None else 0

    def _index_epoch(self, cur) -> Optional[int]:
        """Epoch the index was last built at, or None if never built."""
        cur.execute("SELECT MAX(graph_epoch) AS e FROM kg_api.catalog_node")
        row = cur.fetchone()
        val = row["e"] if isinstance(row, dict) else (row[0] if row else None)
        return int(val) if val is not None else None

    # --------------------------------------------------------------- freshness

    def ensure_fresh(self) -> Tuple[bool, int]:
        """Rebuild the index if the graph has advanced past it.

        Returns (served_stale, current_epoch). served_stale is True when the
        index lagged but another worker holds the rebuild lock, so this call
        serves the older snapshot rather than blocking.
        """
        conn = self.client.pool.getconn()
        try:
            # Fast path: read epochs without the lock.
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                current = self._current_epoch(cur)
                indexed = self._index_epoch(cur)
            conn.rollback()  # close the read txn cleanly

            if indexed is not None and indexed >= current:
                return (False, current)

            # Stale (or empty). Claim a TRANSACTION-scoped advisory lock: it is
            # released automatically when this transaction commits or rolls back
            # (including on exception), so there is no orphaned-lock risk and no
            # dependency on a manual unlock or on reusing one connection. The
            # rebuild's TRUNCATE+INSERT runs in this same transaction, so the
            # lock is held for exactly the rebuild's duration and the single
            # commit both publishes the new index and frees the lock.
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT pg_try_advisory_xact_lock(%s) AS got", (_CATALOG_REBUILD_LOCK,)
                )
                got_lock = cur.fetchone()["got"]
                if not got_lock:
                    # Another worker is rebuilding — serve what we have.
                    conn.rollback()
                    return (indexed is not None, current)

                # Re-check under lock: another worker may have just rebuilt.
                indexed = self._index_epoch(cur)
                current = self._current_epoch(cur)
                if indexed is not None and indexed >= current:
                    conn.rollback()  # releases the lock
                    return (False, current)

            # Same transaction (lock still held): rebuild, then commit once.
            self._rebuild(conn, current)
            conn.commit()  # publishes the index and releases the xact lock
            return (False, current)
        except Exception as e:
            logger.error(f"catalog ensure_fresh failed: {e}", exc_info=True)
            conn.rollback()  # releases the lock if held
            # Best-effort: report stale with epoch 0 so callers still serve
            # whatever index exists rather than erroring the browse request.
            return (True, 0)
        finally:
            self.client.pool.putconn(conn)

    # ----------------------------------------------------------------- rebuild

    def _rebuild(self, conn, epoch: int) -> None:
        """Full rebuild of catalog_node + catalog_edge from the graph.

        Runs three bounded aggregate Cypher passes (ontologies, documents,
        concepts), projects them to rows via _project, and replaces the index
        atomically. Membership comes only from canonical edges.
        """
        logger.info(f"Rebuilding catalog index at epoch {epoch}")

        ontologies = self._fetch_ontologies()
        documents = self._fetch_documents()
        concepts = self._fetch_concepts()

        nodes, edges, stats = self._project(ontologies, documents, concepts, epoch)

        if stats["sourceless_docs"]:
            logger.warning(
                f"catalog rebuild: {stats['sourceless_docs']} DocumentMeta node(s) had "
                f"no resolvable parent ontology via :SCOPED_BY — omitted from tree"
            )
        if stats["orphan_concepts"]:
            logger.info(
                f"catalog rebuild: {stats['orphan_concepts']} concept(s) not reachable "
                f"from any DocumentMeta (no :HAS_SOURCE path) — present in search, "
                f"absent from document drill-down"
            )

        # Atomic swap: truncate + bulk insert. The caller (ensure_fresh) owns
        # the transaction and the advisory lock — it commits once after this
        # returns, which both publishes the index and releases the lock. We do
        # NOT commit here, so a failure leaves the prior index intact on rollback.
        from psycopg2.extras import execute_values, Json

        with conn.cursor() as cur:
            cur.execute("TRUNCATE kg_api.catalog_node, kg_api.catalog_edge")
            if nodes:
                execute_values(
                    cur,
                    """
                    INSERT INTO kg_api.catalog_node
                        (kind, node_id, name, name_lower, child_count,
                         content_type, properties, graph_epoch)
                    VALUES %s
                    """,
                    [
                        (k, nid, nm, nl, cc, ct, Json(pr), ep)
                        for (k, nid, nm, nl, cc, ct, pr, ep) in nodes
                    ],
                    page_size=1000,
                )
            if edges:
                execute_values(
                    cur,
                    """
                    INSERT INTO kg_api.catalog_edge
                        (parent_kind, parent_id, child_kind, child_id, graph_epoch)
                    VALUES %s
                    ON CONFLICT DO NOTHING
                    """,
                    edges,
                    page_size=1000,
                )

        logger.info(
            f"catalog rebuild complete: {len(nodes)} nodes, {len(edges)} edges "
            f"at epoch {epoch}"
        )

    @staticmethod
    def _project(
        ontologies: List[Dict[str, Any]],
        documents: List[Dict[str, Any]],
        concepts: List[Dict[str, Any]],
        epoch: int,
    ) -> Tuple[List[Tuple], List[Tuple], Dict[str, int]]:
        """Pure projection: graph fetch results -> (node rows, edge rows, stats).

        Separated from DB I/O so the DAG invariants can be unit-tested:
        a concept appearing in N documents yields N edges; an ontology's
        child_count is its document count; sourceless documents and orphan
        concepts are counted, not silently dropped.

        Node tuple:  (kind, node_id, name, name_lower, child_count,
                      content_type, properties, epoch)
        Edge tuple:  (parent_kind, parent_id, child_kind, child_id, epoch)
        """
        nodes: List[Tuple] = []
        edges: List[Tuple] = []
        sourceless_docs = 0
        orphan_concepts = 0

        # Ontologies (root level) — children are documents.
        for o in ontologies:
            oid = o.get("id")
            if not oid:
                continue
            name = o.get("name") or oid
            props = {
                k: o[k]
                for k in ("lifecycle_state", "creation_epoch")
                if o.get(k) is not None
            }
            nodes.append((
                "ontology", oid, name, name.lower(),
                int(o.get("doc_count") or 0), None, props, epoch,
            ))

        # Documents — parent = ontology (via SCOPED_BY), children = concepts.
        for d in documents:
            did = d.get("id")
            if not did:
                continue
            name = d.get("name") or did
            content_type = d.get("content_type")
            props = {
                k: d[k]
                for k in ("source_count", "source_type", "ontology")
                if d.get(k) is not None
            }
            nodes.append((
                "document", did, name, name.lower(),
                int(d.get("concept_count") or 0), content_type, props, epoch,
            ))
            parent_ids = [p for p in (d.get("parent_ontology_ids") or []) if p]
            if not parent_ids:
                sourceless_docs += 1
            for pid in parent_ids:
                edges.append(("ontology", pid, "document", did, epoch))

        # Concepts — leaf (child_count 0); a concept may have many parent docs.
        for c in concepts:
            cid = c.get("id")
            if not cid:
                continue
            name = c.get("name") or cid
            nodes.append((
                "concept", cid, name, name.lower(), 0, None, {}, epoch,
            ))
            parent_ids = [p for p in (c.get("parent_document_ids") or []) if p]
            if not parent_ids:
                orphan_concepts += 1
            for pid in parent_ids:
                edges.append(("document", pid, "concept", cid, epoch))

        stats = {
            "sourceless_docs": sourceless_docs,
            "orphan_concepts": orphan_concepts,
        }
        return nodes, edges, stats

    # ------------------------------------------------------- graph fetch passes

    def _fetch_ontologies(self) -> List[Dict[str, Any]]:
        """Ontology nodes with their direct document counts."""
        rows = self.client._execute_cypher("""
            MATCH (o:Ontology)
            OPTIONAL MATCH (o)<-[:SCOPED_BY]-(:Source)<-[:HAS_SOURCE]-(d:DocumentMeta)
            RETURN o.ontology_id AS id,
                   o.name AS name,
                   o.lifecycle_state AS lifecycle_state,
                   o.creation_epoch AS creation_epoch,
                   count(DISTINCT d) AS doc_count
        """) or []
        return rows

    def _fetch_documents(self) -> List[Dict[str, Any]]:
        """DocumentMeta nodes with parent ontology ids and concept counts.

        The parent-ontology and concept legs are aggregated in SEPARATE WITH
        stages rather than two OPTIONAL MATCHes off the same Source. Combining
        them produces a sources×ontologies×concepts Cartesian fan-out that
        DISTINCT/count collapse to the right values but only after materializing
        the product — pathological on large documents. Sequential aggregation
        keeps each leg's cost additive.
        """
        rows = self.client._execute_cypher("""
            MATCH (d:DocumentMeta)
            OPTIONAL MATCH (d)-[:HAS_SOURCE]->(s:Source)-[:SCOPED_BY]->(o:Ontology)
            WITH d, collect(DISTINCT o.ontology_id) AS parent_ontology_ids
            OPTIONAL MATCH (d)-[:HAS_SOURCE]->(s2:Source)<-[:APPEARS]-(c:Concept)
            WITH d, parent_ontology_ids, count(DISTINCT c) AS concept_count
            RETURN d.document_id AS id,
                   d.filename AS name,
                   d.content_type AS content_type,
                   d.source_count AS source_count,
                   d.source_type AS source_type,
                   d.ontology AS ontology,
                   parent_ontology_ids,
                   concept_count
        """) or []
        return rows

    def _fetch_concepts(self) -> List[Dict[str, Any]]:
        """Concept nodes with the document ids they appear in (DAG parents)."""
        rows = self.client._execute_cypher("""
            MATCH (c:Concept)
            OPTIONAL MATCH (c)-[:APPEARS]->(:Source)<-[:HAS_SOURCE]-(d:DocumentMeta)
            RETURN c.concept_id AS id,
                   c.label AS name,
                   collect(DISTINCT d.document_id) AS parent_document_ids
        """) or []
        return rows

    # -------------------------------------------------------------- browse API

    def list_children(
        self,
        parent_id: Optional[str],
        parent_kind: Optional[str],
        child_kind: str,
        q: Optional[str] = None,
        sort: str = "name",
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List the children of a node (or root ontologies when parent_id is None).

        Returns a dict shaped for CatalogChildrenResponse: nodes, total, and the
        pagination/echo fields. Fragment filter `q` is a case-insensitive
        substring match on child names via the pg_trgm-backed index.
        """
        served_stale, _ = self.ensure_fresh()
        order_by = _SORT_SQL.get(sort, _SORT_SQL["name"])
        like = f"%{q.lower()}%" if q else None

        conn = self.client.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if parent_id is None:
                    # Root: top-level ontologies straight from catalog_node.
                    where = ["n.kind = %s"]
                    params: List[Any] = [child_kind]
                    if like:
                        where.append("n.name_lower LIKE %s")
                        params.append(like)
                    where_sql = " AND ".join(where)

                    cur.execute(
                        f"SELECT count(*) AS c FROM kg_api.catalog_node n WHERE {where_sql}",
                        params,
                    )
                    total = cur.fetchone()["c"]

                    cur.execute(
                        f"""
                        SELECT n.kind, n.node_id, n.name, n.child_count,
                               n.content_type, n.properties
                        FROM kg_api.catalog_node n
                        WHERE {where_sql}
                        ORDER BY {order_by}
                        LIMIT %s OFFSET %s
                        """,
                        params + [limit, offset],
                    )
                    rows = cur.fetchall()
                else:
                    where = [
                        "e.parent_kind = %s",
                        "e.parent_id = %s",
                        "e.child_kind = %s",
                    ]
                    params = [parent_kind, parent_id, child_kind]
                    if like:
                        where.append("n.name_lower LIKE %s")
                        params.append(like)
                    where_sql = " AND ".join(where)

                    cur.execute(
                        f"""
                        SELECT count(*) AS c
                        FROM kg_api.catalog_edge e
                        JOIN kg_api.catalog_node n
                          ON n.kind = e.child_kind AND n.node_id = e.child_id
                        WHERE {where_sql}
                        """,
                        params,
                    )
                    total = cur.fetchone()["c"]

                    cur.execute(
                        f"""
                        SELECT n.kind, n.node_id, n.name, n.child_count,
                               n.content_type, n.properties
                        FROM kg_api.catalog_edge e
                        JOIN kg_api.catalog_node n
                          ON n.kind = e.child_kind AND n.node_id = e.child_id
                        WHERE {where_sql}
                        ORDER BY {order_by}
                        LIMIT %s OFFSET %s
                        """,
                        params + [limit, offset],
                    )
                    rows = cur.fetchall()
                conn.commit()
        finally:
            self.client.pool.putconn(conn)

        nodes = [self._row_to_node(r, parent_id) for r in rows]
        return {
            "parent_id": parent_id,
            "parent_kind": parent_kind,
            "child_kind": child_kind,
            "nodes": nodes,
            "total": total,
            "limit": limit,
            "offset": offset,
            "query": q,
            "stale": served_stale,
        }

    def get_node(self, node_id: str, kind: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Fetch a single node's full metadata (the stat/detail call).

        If `kind` is omitted, resolves by node_id across kinds (ids are unique
        in practice within their kind; ambiguity returns the first by kind order
        ontology < document < concept).
        """
        self.ensure_fresh()
        conn = self.client.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if kind:
                    cur.execute(
                        """
                        SELECT kind, node_id, name, child_count, content_type,
                               properties, graph_epoch, indexed_at
                        FROM kg_api.catalog_node
                        WHERE kind = %s AND node_id = %s
                        """,
                        (kind, node_id),
                    )
                else:
                    cur.execute(
                        """
                        SELECT kind, node_id, name, child_count, content_type,
                               properties, graph_epoch, indexed_at
                        FROM kg_api.catalog_node
                        WHERE node_id = %s
                        ORDER BY CASE kind
                            WHEN 'ontology' THEN 0
                            WHEN 'document' THEN 1
                            WHEN 'concept'  THEN 2 END
                        LIMIT 1
                        """,
                        (node_id,),
                    )
                row = cur.fetchone()
                if not row:
                    conn.commit()
                    return None

                # First parent (breadcrumb) — a concept may have many; pick one.
                cur.execute(
                    """
                    SELECT parent_kind, parent_id
                    FROM kg_api.catalog_edge
                    WHERE child_kind = %s AND child_id = %s
                    LIMIT 1
                    """,
                    (row["kind"], row["node_id"]),
                )
                parent = cur.fetchone()
                conn.commit()
        finally:
            self.client.pool.putconn(conn)

        node = self._row_to_node(row, parent["parent_id"] if parent else None)
        node["graph_epoch"] = row.get("graph_epoch")
        node["indexed_at"] = row.get("indexed_at")
        return node

    # ----------------------------------------------------------------- helpers

    @staticmethod
    def _row_to_node(row: Dict[str, Any], parent_id: Optional[str]) -> Dict[str, Any]:
        """Map a catalog_node row to the CatalogNode dict shape."""
        props = row.get("properties")
        if isinstance(props, str):
            import json as _json
            try:
                props = _json.loads(props)
            except (ValueError, TypeError):
                props = {}
        return {
            "kind": row["kind"],
            "id": row["node_id"],
            "name": row["name"],
            "parent_id": parent_id,
            "child_count": row.get("child_count"),
            "content_type": row.get("content_type"),
            "properties": props or {},
        }
