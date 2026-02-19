"""
GraphFacade - Unified graph traversal with graph_accel acceleration.

Single facade for all graph topology operations. Uses graph_accel
(ADR-201 in-memory extension) when available, falls back to Cypher.

Two-phase query pattern:
  Phase 1: Topology query (graph_accel sub-ms, or Cypher fallback)
  Phase 2: Property hydration (batch SQL for returned IDs)

Connection architecture:
  Uses a module-level pinned connection (_accel_conn) for graph_accel SQL
  calls. graph_accel stores its in-memory graph per Postgres backend, so
  pinning ensures the graph loads once and stays resident across requests.
  On each call, ensure_fresh() checks the generation counter (~0.01ms)
  and only reloads after graph_accel_invalidate() bumps the generation.

  Callers at the route layer add a third phase — grounding/confidence
  hydration — which uses its own generation-aware caches (see
  _hydrate_grounding_batch in routes/queries.py and the two-tier cache
  in age_client/query.py:calculate_grounding_strength_semantic).

Replaces:
  - QueryService.build_related_concepts_query() → neighborhood()
  - PathfindingFacade.find_shortest_path/find_paths() → find_path/find_paths()
  - QueryFacade.match_sources/match_concepts_for_sources_batch() → carried forward
  - get_concept_degree_ranking() pattern → degree()

Access via: client.graph.neighborhood(...)
"""

import logging
import math
import re
import threading
from typing import List, Dict, Optional, Any, Set, Tuple

import psycopg2
from psycopg2 import extras

logger = logging.getLogger(__name__)

# Module-level persistent connection for graph_accel SQL queries.
# graph_accel uses per-backend state (thread_local + RefCell in Rust),
# so we pin a single connection to keep the graph loaded across requests.
# Only reloads when generation changes (Phase 3 cache invalidation).
_accel_conn = None
_accel_conn_lock = threading.Lock()

# Valid Cypher relationship type: uppercase letters, digits, underscores
_VALID_REL_TYPE_RE = re.compile(r'^[A-Z][A-Z0-9_]*$')

# Valid concept ID: sha256 prefix + hex/underscore/alphanumeric (no quotes, no injection)
_VALID_CONCEPT_ID_RE = re.compile(r'^[a-zA-Z0-9:_-]+$')


def _validate_rel_types(types: List[str]) -> None:
    """Validate relationship type names for safe Cypher interpolation."""
    for t in types:
        if not _VALID_REL_TYPE_RE.match(t):
            raise ValueError(f"Invalid relationship type name: {t!r}")


def _validate_concept_ids(ids: List[str]) -> None:
    """Validate concept IDs for safe Cypher interpolation."""
    for cid in ids:
        if not _VALID_CONCEPT_ID_RE.match(cid):
            raise ValueError(f"Invalid concept ID: {cid!r}")


class GraphFacade:
    """Unified graph traversal with graph_accel acceleration.

    Provides a single interface for BFS neighborhood, shortest path,
    degree centrality, subgraph extraction, and namespace-safe queries.
    Transparently uses graph_accel when the extension is loaded, with
    automatic Cypher fallback when it's not.
    """

    def __init__(self, client):
        """
        Args:
            client: AGEClient instance (provides _execute_cypher, pool)
        """
        self._client = client
        self._accel_available: Optional[bool] = None

    # -------------------------------------------------------------------------
    # Acceleration availability
    # -------------------------------------------------------------------------

    @property
    def _accel_ready(self) -> bool:
        """Check if graph_accel is usable. Cached for facade lifetime."""
        if self._accel_available is None:
            self._accel_available = self._detect_accel()
        return self._accel_available

    def _detect_accel(self) -> bool:
        """Check if graph_accel extension is installed.

        Does NOT try to load the graph here — loading must happen on the
        same connection that will run the query (per-backend state).
        _execute_sql handles per-connection loading automatically.
        """
        try:
            rows = self._execute_sql("SELECT status FROM graph_accel_status()")
            status = rows[0]['status'] if rows else 'unknown'
            logger.debug(f"graph_accel detected: status={status}")
            return True
        except Exception as e:
            logger.debug(f"graph_accel not available: {e}")
            return False

    def is_accelerated(self) -> bool:
        """Whether graph_accel is available and loaded."""
        return self._accel_ready

    def status(self) -> Dict[str, Any]:
        """Extension status. Returns empty dict if not available."""
        try:
            rows = self._execute_sql(
                "SELECT source_graph, status, node_count, edge_count, "
                "memory_bytes, is_stale FROM graph_accel_status()"
            )
            return dict(rows[0]) if rows else {}
        except Exception:
            return {}

    def invalidate(self) -> Optional[int]:
        """Bump graph_accel generation after graph mutations.

        Returns new generation number, or None if extension unavailable.
        Safe to call unconditionally — no-ops when extension absent.
        """
        try:
            rows = self._execute_sql(
                "SELECT graph_accel_invalidate(%s) as generation",
                ('knowledge_graph',)
            )
            return rows[0]['generation'] if rows else None
        except Exception:
            return None

    # -------------------------------------------------------------------------
    # Topology: neighborhood (BFS)
    # -------------------------------------------------------------------------

    def neighborhood(
        self,
        concept_id: str,
        max_depth: int = 2,
        direction: str = 'both',
        min_confidence: Optional[float] = None,
        relationship_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """BFS neighborhood traversal.

        Returns related concepts within max_depth hops, each with:
        concept_id, label, distance, path_types.

        Args:
            concept_id: Starting concept ID
            max_depth: Maximum traversal depth (1-5)
            direction: 'both', 'outgoing', or 'incoming'
            min_confidence: Minimum edge confidence filter (0.0-1.0)
            relationship_types: Filter traversal to these edge types

        Returns:
            List of dicts with concept_id, label, distance, path_types
        """
        if self._accel_ready:
            results = self._neighborhood_accel(
                concept_id, max_depth, direction, min_confidence
            )
            # graph_accel doesn't filter by relationship type at SQL level;
            # post-filter if caller specified types
            if relationship_types:
                type_set = set(relationship_types)
                results = [
                    r for r in results
                    if any(t in type_set for t in (r.get('path_types') or []))
                ]
            return results
        return self._neighborhood_cypher(
            concept_id, max_depth, relationship_types
        )

    def _neighborhood_accel(
        self,
        concept_id: str,
        max_depth: int,
        direction: str,
        min_confidence: Optional[float]
    ) -> List[Dict[str, Any]]:
        """graph_accel fast path for neighborhood."""
        # NaN sentinel means "no filter" in graph_accel
        conf_param = min_confidence if min_confidence is not None else float('nan')

        rows = self._execute_sql(
            "SELECT app_id, label, distance, path_types "
            "FROM graph_accel_neighborhood(%s, %s, %s, %s) "
            "WHERE label = 'Concept' AND distance > 0",
            (concept_id, max_depth, direction, conf_param)
        )

        # graph_accel 'label' is the AGE vertex label ("Concept"), not
        # the concept's display name. Hydrate to get real properties.
        concept_ids = [r['app_id'] for r in rows if r['app_id']]
        hydrated = self._hydrate_concepts(concept_ids) if concept_ids else {}

        return [
            {
                'concept_id': r['app_id'],
                'label': hydrated.get(r['app_id'], {}).get('label', ''),
                'distance': r['distance'],
                'path_types': r['path_types'] or []
            }
            for r in rows
        ]

    def _neighborhood_cypher(
        self,
        concept_id: str,
        max_depth: int,
        relationship_types: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """Cypher fallback for neighborhood.

        Builds per-depth fixed-chain queries (same pattern as
        QueryService.build_related_concepts_query) and merges results.
        """
        rel_filter = ""
        if relationship_types:
            _validate_rel_types(relationship_types)
            rel_filter = ":" + "|".join(relationship_types)

        # Execute per-depth queries, merge keeping minimum distance
        seen: Dict[str, Dict] = {}

        for depth in range(1, max_depth + 1):
            rel_vars = [f"r{i}" for i in range(depth)]
            parts = []
            for i in range(depth):
                rel = f"[{rel_vars[i]}{rel_filter}]"
                if i < depth - 1:
                    parts.append(f"{rel}-(h{i+1}:Concept)")
                else:
                    parts.append(f"{rel}-(target:Concept)")
            chain = "-".join(parts)
            type_exprs = ", ".join(f"type({v})" for v in rel_vars)

            query = f"""
                MATCH (start:Concept {{concept_id: $concept_id}})-{chain}
                WHERE start <> target
                WITH DISTINCT target.concept_id as concept_id,
                    target.label as label,
                    [{type_exprs}] as path_types
                RETURN concept_id, label, {depth} as distance, path_types
            """

            try:
                results = self._client._execute_cypher(
                    query, params={"concept_id": concept_id}
                )
                for record in (results or []):
                    cid = record['concept_id']
                    dist = record['distance']
                    if cid not in seen or dist < seen[cid]['distance']:
                        seen[cid] = record
            except Exception as e:
                logger.warning(f"Neighborhood depth {depth} query failed: {e}")

        return sorted(seen.values(), key=lambda r: (r['distance'], r.get('label', '')))

    # -------------------------------------------------------------------------
    # Topology: pathfinding
    # -------------------------------------------------------------------------

    def find_path(
        self,
        from_id: str,
        to_id: str,
        max_hops: int = 6,
        direction: str = 'both',
        min_confidence: Optional[float] = None,
        relationship_types: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Find shortest path between two concepts.

        Returns path dict with path_nodes, path_rels, hops — or None.
        """
        if from_id == to_id:
            node_data = self._get_concept_data(from_id)
            if node_data:
                return {"path_nodes": [node_data], "path_rels": [], "hops": 0}
            return None

        if self._accel_ready:
            logger.debug(f"find_path: using graph_accel ({from_id} → {to_id}, max_hops={max_hops})")
            result = self._find_path_accel(
                from_id, to_id, max_hops, direction, min_confidence
            )
            if result is not None:
                logger.debug(f"find_path: graph_accel returned path with {result['hops']} hops")
                return result
            logger.debug("find_path: graph_accel returned no path, falling through to BFS")
        else:
            logger.debug("find_path: graph_accel not available, using Cypher BFS")

        return self._find_path_bfs(from_id, to_id, max_hops, relationship_types)

    def find_paths(
        self,
        from_id: str,
        to_id: str,
        max_hops: int = 6,
        max_paths: int = 5,
        relationship_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Find multiple paths between two concepts.

        Uses graph_accel_paths (Yen's k-shortest) when available,
        falls back to BFS with edge exclusion.

        Returns list of path dicts sorted by length.
        """
        if from_id == to_id:
            node_data = self._get_concept_data(from_id)
            if node_data:
                return [{"path_nodes": [node_data], "path_rels": [], "hops": 0}]
            return []

        if self._accel_ready:
            logger.debug(
                f"find_paths: graph_accel ({from_id} → {to_id}, "
                f"max_hops={max_hops}, max_paths={max_paths})"
            )
            paths = self._find_paths_accel(from_id, to_id, max_hops, max_paths)
            if relationship_types:
                type_set = set(relationship_types)
                paths = [
                    p for p in paths
                    if all(r.get('label', '') in type_set
                           for r in p.get('path_rels', []))
                ]
            paths = paths[:max_paths]
            logger.debug(f"find_paths: graph_accel returned {len(paths)} paths")
            return paths

        # Cypher BFS fallback
        logger.debug("find_paths: using Cypher BFS fallback")
        shortest = self.find_path(
            from_id, to_id, max_hops,
            relationship_types=relationship_types
        )
        if not shortest:
            return []

        paths = [shortest]

        if max_paths > 1 and shortest["hops"] > 0:
            excluded_edges = self._extract_edges(shortest)
            for _ in range(max_paths - 1):
                additional = self._find_path_bfs_excluding(
                    from_id, to_id, max_hops,
                    relationship_types, excluded_edges
                )
                if additional:
                    paths.append(additional)
                    excluded_edges.update(self._extract_edges(additional))
                else:
                    break

        return paths[:max_paths]

    def _find_path_accel(
        self,
        from_id: str,
        to_id: str,
        max_hops: int,
        direction: str,
        min_confidence: Optional[float]
    ) -> Optional[Dict[str, Any]]:
        """graph_accel fast path for shortest path."""
        conf_param = min_confidence if min_confidence is not None else float('nan')

        rows = self._execute_sql(
            "SELECT step, app_id, label, rel_type, direction "
            "FROM graph_accel_path(%s, %s, %s, %s, %s)",
            (from_id, to_id, max_hops, direction, conf_param)
        )

        if not rows:
            return None

        return self._accel_path_rows_to_dict(rows)

    def _accel_path_rows_to_dict(self, rows: List[Dict]) -> Optional[Dict[str, Any]]:
        """Convert graph_accel_path rows to the path dict format.

        graph_accel returns: step, app_id, label, rel_type, direction
        We need: path_nodes [{concept_id, label, description}],
                 path_rels [{label, properties}], hops

        Returns None if the path traverses non-Concept nodes (phantom
        references from dangling edges to Source/Instance/Ontology).
        """
        if any(not row.get('app_id') for row in rows):
            return None

        node_ids = [row['app_id'] for row in rows]
        path_rels = []

        for row in rows:
            if row['rel_type']:
                path_rels.append({
                    "label": row['rel_type'],
                    "properties": {}
                })

        # Batch hydrate concept data for nodes with app_id
        hydrated = self._hydrate_concepts(
            [nid for nid in node_ids if nid]
        ) if any(node_ids) else {}

        path_nodes = []
        for row in rows:
            nid = row['app_id']
            data = hydrated.get(nid) if nid else None
            if data:
                path_nodes.append(data)
            else:
                path_nodes.append({
                    "concept_id": nid or '',
                    "label": row.get('label', '') or '',
                    "description": ''
                })

        return {
            "path_nodes": path_nodes,
            "path_rels": path_rels,
            "hops": len(path_rels)
        }

    def _find_paths_accel(
        self,
        from_id: str,
        to_id: str,
        max_hops: int,
        max_paths: int
    ) -> List[Dict[str, Any]]:
        """graph_accel multi-path via Yen's k-shortest-paths."""
        rows = self._execute_sql(
            "SELECT path_index, step, app_id, label, rel_type, direction "
            "FROM graph_accel_paths(%s, %s, %s, %s)",
            (from_id, to_id, max_hops, max_paths)
        )

        if not rows:
            return []

        # Group rows by path_index
        paths_by_index: Dict[int, List[Dict]] = {}
        for row in rows:
            pi = row['path_index']
            paths_by_index.setdefault(pi, []).append(row)

        # Collect all unique node IDs across all paths for batch hydration
        all_node_ids = list({
            row['app_id'] for row in rows if row.get('app_id')
        })
        hydrated = self._hydrate_concepts(all_node_ids) if all_node_ids else {}

        # Convert each path group to the standard path dict format
        result = []
        for pi in sorted(paths_by_index.keys()):
            path_rows = paths_by_index[pi]

            # Skip paths containing non-Concept nodes (phantom references
            # from dangling edges to Source/Instance/Ontology nodes that
            # aren't loaded in the in-memory graph).
            if any(not row.get('app_id') for row in path_rows):
                continue

            path_nodes = []
            path_rels = []

            for row in path_rows:
                nid = row['app_id']
                data = hydrated.get(nid) if nid else None
                if data:
                    path_nodes.append(data)
                else:
                    path_nodes.append({
                        "concept_id": nid or '',
                        "label": row.get('label', '') or '',
                        "description": ''
                    })

                if row['rel_type']:
                    path_rels.append({
                        "label": row['rel_type'],
                        "properties": {}
                    })

            result.append({
                "path_nodes": path_nodes,
                "path_rels": path_rels,
                "hops": len(path_rels)
            })

        return result

    # -------------------------------------------------------------------------
    # Cypher BFS fallback (from PathfindingFacade)
    # -------------------------------------------------------------------------

    def _find_path_bfs(
        self,
        from_id: str,
        to_id: str,
        max_hops: int,
        relationship_types: Optional[List[str]]
    ) -> Optional[Dict[str, Any]]:
        """Bidirectional BFS shortest path (Cypher fallback)."""
        if not self._concept_exists(from_id) or not self._concept_exists(to_id):
            return None

        parents_fwd: Dict[str, Optional[Tuple[str, str, Dict]]] = {from_id: None}
        parents_bwd: Dict[str, Optional[Tuple[str, str, Dict]]] = {to_id: None}
        frontier_fwd: Set[str] = {from_id}
        frontier_bwd: Set[str] = {to_id}

        for _ in range(max_hops):
            if len(frontier_fwd) <= len(frontier_bwd):
                mp = self._expand_frontier(
                    frontier_fwd, parents_fwd, parents_bwd, relationship_types
                )
            else:
                mp = self._expand_frontier(
                    frontier_bwd, parents_bwd, parents_fwd, relationship_types
                )
            if mp:
                return self._reconstruct_path(
                    mp, parents_fwd, parents_bwd, from_id, to_id
                )
            if not frontier_fwd and not frontier_bwd:
                break

        return None

    def _find_path_bfs_excluding(
        self,
        from_id: str,
        to_id: str,
        max_hops: int,
        relationship_types: Optional[List[str]],
        excluded_edges: Set[Tuple[str, str]]
    ) -> Optional[Dict[str, Any]]:
        """BFS with edge exclusion for finding alternative paths."""
        if from_id == to_id:
            return None

        parents_fwd: Dict[str, Optional[Tuple[str, str, Dict]]] = {from_id: None}
        parents_bwd: Dict[str, Optional[Tuple[str, str, Dict]]] = {to_id: None}
        frontier_fwd: Set[str] = {from_id}
        frontier_bwd: Set[str] = {to_id}

        for _ in range(max_hops):
            if len(frontier_fwd) <= len(frontier_bwd):
                mp = self._expand_frontier(
                    frontier_fwd, parents_fwd, parents_bwd,
                    relationship_types, excluded_edges
                )
            else:
                mp = self._expand_frontier(
                    frontier_bwd, parents_bwd, parents_fwd,
                    relationship_types, excluded_edges
                )
            if mp:
                return self._reconstruct_path(
                    mp, parents_fwd, parents_bwd, from_id, to_id
                )
            if not frontier_fwd and not frontier_bwd:
                break

        return None

    def _expand_frontier(
        self,
        frontier: Set[str],
        current_parents: Dict[str, Optional[Tuple[str, str, Dict]]],
        other_parents: Dict[str, Optional[Tuple[str, str, Dict]]],
        relationship_types: Optional[List[str]],
        excluded_edges: Optional[Set[Tuple[str, str]]] = None
    ) -> Optional[str]:
        """Expand one BFS frontier by one hop."""
        if not frontier:
            return None

        neighbors = self._get_neighbors_batch(list(frontier), relationship_types)
        next_frontier: Set[str] = set()

        for neighbor_id, parent_id, rel_type, rel_props in neighbors:
            if excluded_edges and (parent_id, neighbor_id) in excluded_edges:
                continue
            if neighbor_id in other_parents:
                current_parents[neighbor_id] = (parent_id, rel_type, rel_props)
                return neighbor_id
            if neighbor_id not in current_parents:
                current_parents[neighbor_id] = (parent_id, rel_type, rel_props)
                next_frontier.add(neighbor_id)

        frontier.clear()
        frontier.update(next_frontier)
        return None

    def _get_neighbors_batch(
        self,
        node_ids: List[str],
        relationship_types: Optional[List[str]]
    ) -> List[Tuple[str, str, str, Dict]]:
        """Batch-fetch neighbors for BFS frontier expansion."""
        if not node_ids:
            return []

        rel_filter = ""
        if relationship_types:
            _validate_rel_types(relationship_types)
            type_list = ", ".join(f"'{t}'" for t in relationship_types)
            rel_filter = f"AND type(r) IN [{type_list}]"

        query = f"""
            MATCH (current:Concept)-[r]-(neighbor:Concept)
            WHERE current.concept_id IN $ids {rel_filter}
            RETURN
                current.concept_id as parent,
                neighbor.concept_id as child,
                type(r) as rel_type,
                properties(r) as rel_props
        """

        _validate_concept_ids(node_ids)
        ids_str = ", ".join(f"'{id}'" for id in node_ids)
        query_substituted = query.replace("$ids", f"[{ids_str}]")

        try:
            results = self._client._execute_cypher(query_substituted)
        except Exception as e:
            logger.error(f"Neighbor batch query failed: {e}")
            return []

        return [
            (row['child'], row['parent'], row['rel_type'], row.get('rel_props', {}))
            for row in (results or [])
        ]

    def _reconstruct_path(
        self,
        meeting_point: str,
        parents_fwd: Dict[str, Optional[Tuple[str, str, Dict]]],
        parents_bwd: Dict[str, Optional[Tuple[str, str, Dict]]],
        from_id: str,
        to_id: str
    ) -> Dict[str, Any]:
        """Reconstruct path from BFS parent chains and hydrate nodes."""
        # Trace from meeting point back to start
        path_to_start = []
        current = meeting_point
        while current is not None:
            parent_info = parents_fwd.get(current)
            if parent_info is None:
                path_to_start.append(current)
                break
            parent_id, rel_type, rel_props = parent_info
            path_to_start.append((current, rel_type, rel_props))
            current = parent_id

        # Trace from meeting point to end
        path_to_end = []
        current = meeting_point
        while current is not None:
            parent_info = parents_bwd.get(current)
            if parent_info is None:
                break
            parent_id, rel_type, rel_props = parent_info
            path_to_end.append((parent_id, rel_type, rel_props))
            current = parent_id

        path_to_start.reverse()

        # Extract node IDs and relationships
        node_ids = []
        rel_infos = []

        for item in path_to_start:
            if isinstance(item, str):
                node_ids.append(item)
            else:
                node_id, rel_type, rel_props = item
                node_ids.append(node_id)
                rel_infos.append({"label": rel_type, "properties": rel_props or {}})

        for item in path_to_end:
            node_id, rel_type, rel_props = item
            node_ids.append(node_id)
            rel_infos.append({"label": rel_type, "properties": rel_props or {}})

        # Batch hydrate all path nodes
        hydrated = self._hydrate_concepts(node_ids)
        path_nodes = []
        for nid in node_ids:
            data = hydrated.get(nid)
            if data:
                path_nodes.append(data)
            else:
                path_nodes.append({
                    "concept_id": nid,
                    "label": "",
                    "description": ""
                })

        return {
            "path_nodes": path_nodes,
            "path_rels": rel_infos,
            "hops": len(rel_infos)
        }

    # -------------------------------------------------------------------------
    # Topology: degree centrality
    # -------------------------------------------------------------------------

    def degree(
        self,
        top_n: int = 100,
        label_filter: str = 'Concept'
    ) -> List[Dict[str, Any]]:
        """Degree centrality ranking.

        Returns top_n nodes by total degree (out + in).

        Args:
            top_n: Number of top nodes to return
            label_filter: Node label to filter (default: 'Concept')

        Returns:
            List of dicts with app_id, out_degree, in_degree, total_degree
        """
        if self._accel_ready:
            rows = self._execute_sql(
                "SELECT app_id, out_degree, in_degree, total_degree "
                "FROM graph_accel_degree(%s) WHERE label = %s",
                (top_n, label_filter)
            )
            return [dict(r) for r in rows]

        # Cypher fallback: count relationships per concept
        query = """
            MATCH (c:Concept)
            OPTIONAL MATCH (c)-[r_out]->(:Concept)
            OPTIONAL MATCH (c)<-[r_in]-(:Concept)
            WITH c.concept_id as app_id,
                 count(DISTINCT r_out) as out_degree,
                 count(DISTINCT r_in) as in_degree
            RETURN app_id, out_degree, in_degree,
                   out_degree + in_degree as total_degree
            ORDER BY total_degree DESC
            LIMIT $limit
        """
        try:
            results = self._client._execute_cypher(
                query, params={"limit": top_n}
            )
            return results or []
        except Exception as e:
            logger.error(f"Degree centrality query failed: {e}")
            return []

    # -------------------------------------------------------------------------
    # Topology: subgraph extraction
    # -------------------------------------------------------------------------

    def subgraph(
        self,
        start_id: str,
        max_depth: int = 3,
        direction: str = 'both',
        min_confidence: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Edge list within neighborhood.

        Returns edges between nodes reachable from start_id.

        Args:
            start_id: Starting concept ID
            max_depth: BFS depth for node discovery
            direction: Traversal direction filter
            min_confidence: Minimum edge confidence

        Returns:
            List of dicts with from_app_id, to_app_id, rel_type
        """
        if self._accel_ready:
            conf_param = min_confidence if min_confidence is not None else float('nan')
            rows = self._execute_sql(
                "SELECT from_app_id, from_label, to_app_id, to_label, rel_type "
                "FROM graph_accel_subgraph(%s, %s, %s, %s)",
                (start_id, max_depth, direction, conf_param)
            )
            return [dict(r) for r in rows]

        # Cypher fallback: get neighborhood then fetch edges between them
        neighbors = self._neighborhood_cypher(start_id, max_depth, None)
        if not neighbors:
            return []

        neighbor_ids = [n['concept_id'] for n in neighbors]
        neighbor_ids.append(start_id)
        _validate_concept_ids(neighbor_ids)
        ids_str = ", ".join(f"'{id}'" for id in neighbor_ids)

        query = f"""
            MATCH (a:Concept)-[r]->(b:Concept)
            WHERE a.concept_id IN [{ids_str}]
            AND b.concept_id IN [{ids_str}]
            RETURN a.concept_id as from_app_id,
                   b.concept_id as to_app_id,
                   type(r) as rel_type
        """
        try:
            results = self._client._execute_cypher(query)
            return results or []
        except Exception as e:
            logger.error(f"Subgraph query failed: {e}")
            return []

    # -------------------------------------------------------------------------
    # Namespace-safe queries (carried from QueryFacade)
    # -------------------------------------------------------------------------

    def match_sources(
        self,
        where: Optional[str] = None,
        params: Optional[Dict] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Match source nodes with explicit :Source label (ADR-048)."""
        query = "MATCH (s:Source)"
        if where:
            query += f" WHERE {where}"
        query += " RETURN s"
        if limit:
            query += f" LIMIT {limit}"
        return self._client._execute_cypher(query, params)

    def match_concepts_for_sources_batch(
        self,
        source_ids: List[str]
    ) -> Dict[str, List[Dict]]:
        """Batch-fetch concepts for multiple sources (N+1 prevention).

        Returns: {source_id: [{concept_id, label, description, instance_quote}]}
        """
        if not source_ids:
            return {}

        query = """
            MATCH (s:Source)
            WHERE s.source_id IN $source_ids
            MATCH (c:Concept)-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s)
            RETURN DISTINCT
                s.source_id as source_id,
                c.concept_id as concept_id,
                c.label as label,
                c.description as description,
                i.quote as instance_quote
            ORDER BY s.source_id, c.label
        """
        results = self._client._execute_cypher(query, params={"source_ids": source_ids})

        concepts_by_source: Dict[str, List[Dict]] = {sid: [] for sid in source_ids}
        for row in (results or []):
            source_id = row["source_id"]
            concepts_by_source[source_id].append({
                "concept_id": row["concept_id"],
                "label": row["label"],
                "description": row.get("description"),
                "instance_quote": row["instance_quote"]
            })
        return concepts_by_source

    # -------------------------------------------------------------------------
    # Hydration helpers
    # -------------------------------------------------------------------------

    def _hydrate_concepts(
        self, concept_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Batch-fetch concept properties for a list of IDs.

        Returns: {concept_id: {concept_id, label, description}}
        """
        if not concept_ids:
            return {}

        # Deduplicate while preserving order
        unique_ids = list(dict.fromkeys(cid for cid in concept_ids if cid))
        if not unique_ids:
            return {}

        _validate_concept_ids(unique_ids)
        ids_str = ", ".join(f"'{cid}'" for cid in unique_ids)
        query = f"""
            MATCH (c:Concept)
            WHERE c.concept_id IN [{ids_str}]
            RETURN c.concept_id as concept_id,
                   c.label as label,
                   c.description as description
        """
        try:
            results = self._client._execute_cypher(query)
        except Exception as e:
            logger.warning(f"Concept hydration failed: {e}")
            return {}

        return {
            r['concept_id']: {
                'concept_id': r['concept_id'],
                'label': r.get('label', ''),
                'description': r.get('description', '')
            }
            for r in (results or [])
        }

    def _get_concept_data(self, concept_id: str) -> Optional[Dict[str, Any]]:
        """Fetch single concept node data."""
        hydrated = self._hydrate_concepts([concept_id])
        return hydrated.get(concept_id)

    def _concept_exists(self, concept_id: str) -> bool:
        """Check if a concept exists in the graph."""
        query = """
            MATCH (c:Concept {concept_id: $cid})
            RETURN count(c) as cnt
        """
        try:
            result = self._client._execute_cypher(
                query, params={"cid": concept_id}, fetch_one=True
            )
            return result and result.get('cnt', 0) > 0
        except Exception:
            return False

    def _extract_edges(self, path: Dict[str, Any]) -> Set[Tuple[str, str]]:
        """Extract edge pairs from a path for exclusion."""
        edges: Set[Tuple[str, str]] = set()
        nodes = path.get("path_nodes", [])
        for i in range(len(nodes) - 1):
            from_node = nodes[i].get("concept_id", "")
            to_node = nodes[i + 1].get("concept_id", "")
            if from_node and to_node:
                edges.add((from_node, to_node))
                edges.add((to_node, from_node))
        return edges

    # -------------------------------------------------------------------------
    # SQL execution (for graph_accel calls)
    # -------------------------------------------------------------------------

    def _get_accel_connection(self):
        """Get or create the persistent connection for graph_accel queries.

        graph_accel uses per-backend state, so we pin a single connection
        to keep the graph loaded across requests. The connection is
        module-level: one per worker process, shared across all facade
        instances. GUCs are set once on creation.
        """
        global _accel_conn

        if _accel_conn is not None and not _accel_conn.closed:
            return _accel_conn

        client = self._client
        _accel_conn = psycopg2.connect(
            host=client.host,
            port=client.port,
            database=client.database,
            user=client.user,
            password=client.password
        )
        _accel_conn.autocommit = True

        with _accel_conn.cursor() as cur:
            cur.execute("SET graph_accel.node_id_property = 'concept_id'")

        logger.info("graph_accel: created dedicated connection")
        return _accel_conn

    # Provenance/bookkeeping edge types that connect Concepts to
    # infrastructure nodes (Source, Instance, Ontology). Loading these
    # creates phantom paths through co-occurrence rather than semantics.
    _INFRA_EDGE_TYPES = frozenset({
        'APPEARS', 'EVIDENCED_BY', 'FROM_SOURCE',
        'SCOPED_BY', 'HAS_SOURCE', 'IMAGES',
    })

    def _set_accel_gucs(self, cur) -> None:
        """Set graph_accel GUCs for semantic-only graph loading.

        Called after graph_accel_status() has loaded the shared library
        (which registers the GUCs), but before graph_accel_load().
        """
        cur.execute("SET graph_accel.node_labels = 'Concept'")
        # Build edge type include list by excluding infrastructure types
        cur.execute(
            "SELECT l.name FROM ag_catalog.ag_label l "
            "JOIN ag_catalog.ag_graph g ON l.graph = g.graphid "
            "WHERE g.name = 'knowledge_graph' AND l.kind = 'e' "
            "AND l.name NOT LIKE '\\_%'"  # skip internal _ag_label_edge
        )
        all_edge_types = {row['name'] for row in cur.fetchall()}
        semantic_types = sorted(all_edge_types - self._INFRA_EDGE_TYPES)
        if semantic_types:
            edge_types_csv = ','.join(semantic_types)
            cur.execute(f"SET graph_accel.edge_types = %s", (edge_types_csv,))
        else:
            logger.warning(
                "graph_accel: no semantic edge types found — "
                "edge_types GUC not set (defaults to *)"
            )
        logger.info(
            f"graph_accel: GUCs set — node_labels=Concept, "
            f"edge_types={len(semantic_types)} semantic / "
            f"{len(all_edge_types)} total"
        )

    def _execute_sql(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """Execute raw SQL via the dedicated graph_accel connection.

        Uses a pinned connection so the in-memory graph stays loaded
        across requests. The graph loads once on first query, then
        graph_accel's ensure_fresh() handles generation-based reload
        (~0.01ms check per call, only reloads after invalidation).
        """
        global _accel_conn

        with _accel_conn_lock:
            conn = self._get_accel_connection()
            try:
                with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                    # Ensure graph is loaded in this backend.
                    # graph_accel_status() triggers library loading, which
                    # registers GUCs — must call this before setting GUCs.
                    cur.execute("SELECT status FROM graph_accel_status()")
                    status_row = cur.fetchone()
                    backend_status = status_row['status'] if status_row else 'unknown'
                    if backend_status == 'not_loaded':
                        logger.info("graph_accel: loading graph...")
                        # Set GUCs now that the library is loaded and GUCs
                        # are registered. These filter what gets loaded into
                        # the in-memory graph.
                        self._set_accel_gucs(cur)
                        cur.execute(
                            "SELECT * FROM graph_accel_load(%s)",
                            ('knowledge_graph',)
                        )
                        load_result = cur.fetchall()
                        if load_result:
                            r = load_result[0]
                            logger.info(
                                f"graph_accel: loaded {r.get('node_count', '?')} nodes / "
                                f"{r.get('edge_count', '?')} edges in "
                                f"{r.get('load_time_ms', '?'):.0f}ms"
                            )

                    # Run the actual query
                    if params:
                        cur.execute(query, params)
                    else:
                        cur.execute(query)
                    if cur.description is not None:
                        return [dict(row) for row in cur.fetchall()]
                    return []
            except Exception as e:
                # Connection broken — close and reconnect on next call
                logger.warning(f"graph_accel: SQL error, will reconnect: {e}")
                try:
                    conn.close()
                except Exception:
                    pass
                _accel_conn = None
                raise
