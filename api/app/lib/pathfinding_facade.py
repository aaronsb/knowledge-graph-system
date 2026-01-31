"""
PathfindingFacade - Optimized Graph Pathfinding

Implements Bidirectional Breadth-First Search (BFS) for efficient
shortest path discovery in Apache AGE graphs.

Part of ADR-076: Pathfinding Optimization for Apache AGE

Why Bidirectional BFS?
----------------------
Apache AGE doesn't support shortestPath() and variable-length patterns
like -[*1..N]- enumerate ALL paths (exponential: O(b^d)).

Bidirectional BFS expands from both endpoints simultaneously, meeting
in the middle. Complexity: O(b^(d/2)) instead of O(b^d).

For branching factor b=20, depth d=6:
- Exhaustive: 64,000,000 node lookups
- Bidirectional: 8,000 node lookups

Usage:
    from api.app.lib.pathfinding_facade import PathfindingFacade

    facade = PathfindingFacade(age_client)

    # Find shortest path between concepts
    path = facade.find_shortest_path(
        from_id="concept_abc",
        to_id="concept_xyz",
        max_hops=6
    )

    # Find multiple paths (returns up to 5)
    paths = facade.find_paths(
        from_id="concept_abc",
        to_id="concept_xyz",
        max_hops=6,
        allowed_rel_types=["SUPPORTS", "IMPLIES"]
    )
"""

from typing import List, Dict, Optional, Any, Set, Tuple
import logging
import re

logger = logging.getLogger(__name__)

# Valid Cypher relationship type: uppercase letters, digits, underscores
_VALID_REL_TYPE_RE = re.compile(r'^[A-Z][A-Z0-9_]*$')


def _validate_rel_types(types: List[str]) -> None:
    """Validate relationship type names for safe Cypher interpolation."""
    for t in types:
        if not _VALID_REL_TYPE_RE.match(t):
            raise ValueError(f"Invalid relationship type name: {t!r}")


class PathfindingFacade:
    """
    Optimized pathfinding using Bidirectional BFS.

    Replaces exhaustive Cypher variable-length patterns with
    application-level graph traversal for dramatic performance gains.
    """

    def __init__(self, age_client):
        """
        Initialize facade with AGEClient instance.

        Args:
            age_client: Instance of AGEClient from api.app.lib.age_client
        """
        self.db = age_client

    def find_shortest_path(
        self,
        from_id: str,
        to_id: str,
        max_hops: int = 6,
        allowed_rel_types: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find the shortest path between two concepts using Bidirectional BFS.

        Time complexity: O(b^(d/2)) where b=branching factor, d=depth
        vs O(b^d) for exhaustive Cypher patterns.

        Args:
            from_id: Starting concept ID
            to_id: Target concept ID
            max_hops: Maximum path length (1-10, default 6)
            allowed_rel_types: Optional list of relationship types to traverse

        Returns:
            Path dictionary with nodes, relationships, and hops count,
            or None if no path found within max_hops.

            Format:
            {
                "path_nodes": [
                    {"concept_id": "...", "label": "...", "description": "..."},
                    ...
                ],
                "path_rels": [
                    {"label": "SUPPORTS", "properties": {...}},
                    ...
                ],
                "hops": 3
            }
        """
        # Edge case: same node
        if from_id == to_id:
            node_data = self._get_concept_data(from_id)
            if node_data:
                return {
                    "path_nodes": [node_data],
                    "path_rels": [],
                    "hops": 0
                }
            return None

        # Verify both endpoints exist
        if not self._concept_exists(from_id) or not self._concept_exists(to_id):
            return None

        # Initialize frontiers and parent tracking
        # parents maps: {node_id: (parent_id, relationship_type, relationship_props)}
        parents_forward: Dict[str, Optional[Tuple[str, str, Dict]]] = {from_id: None}
        parents_backward: Dict[str, Optional[Tuple[str, str, Dict]]] = {to_id: None}

        frontier_forward: Set[str] = {from_id}
        frontier_backward: Set[str] = {to_id}

        # BFS loop - alternate expanding each frontier
        for depth in range(max_hops):
            # Always expand the smaller frontier (optimization)
            if len(frontier_forward) <= len(frontier_backward):
                meeting_point = self._expand_frontier(
                    frontier_forward,
                    parents_forward,
                    parents_backward,
                    allowed_rel_types,
                    direction="forward"
                )
                if meeting_point:
                    return self._reconstruct_path(
                        meeting_point,
                        parents_forward,
                        parents_backward,
                        from_id,
                        to_id
                    )
            else:
                meeting_point = self._expand_frontier(
                    frontier_backward,
                    parents_backward,
                    parents_forward,
                    allowed_rel_types,
                    direction="backward"
                )
                if meeting_point:
                    return self._reconstruct_path(
                        meeting_point,
                        parents_forward,
                        parents_backward,
                        from_id,
                        to_id
                    )

            # Check if both frontiers are exhausted
            if not frontier_forward and not frontier_backward:
                break

        return None  # No path found within max_hops

    def find_paths(
        self,
        from_id: str,
        to_id: str,
        max_hops: int = 6,
        max_paths: int = 5,
        allowed_rel_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Find multiple paths between two concepts.

        Uses Bidirectional BFS for the shortest path. For additional paths,
        uses iterative BFS with edge exclusion (avoids exhaustive Cypher).

        Args:
            from_id: Starting concept ID
            to_id: Target concept ID
            max_hops: Maximum path length
            max_paths: Maximum number of paths to return (default 5)
            allowed_rel_types: Optional relationship type filter

        Returns:
            List of path dictionaries, sorted by length (shortest first)
        """
        # Find shortest path via Bidirectional BFS
        shortest = self.find_shortest_path(from_id, to_id, max_hops, allowed_rel_types)

        if not shortest:
            return []

        paths = [shortest]

        # Try to find additional paths by running BFS with edge exclusion
        # This avoids the expensive exhaustive Cypher fallback
        if max_paths > 1 and shortest["hops"] > 0:
            excluded_edges = self._extract_edges(shortest)

            for _ in range(max_paths - 1):
                additional = self._find_path_excluding_edges(
                    from_id,
                    to_id,
                    max_hops,
                    allowed_rel_types,
                    excluded_edges
                )
                if additional:
                    paths.append(additional)
                    # Add new path's edges to exclusion set
                    excluded_edges.update(self._extract_edges(additional))
                else:
                    break  # No more alternative paths

        return paths[:max_paths]

    def _expand_frontier(
        self,
        frontier: Set[str],
        current_parents: Dict[str, Optional[Tuple[str, str, Dict]]],
        other_parents: Dict[str, Optional[Tuple[str, str, Dict]]],
        allowed_rel_types: Optional[List[str]],
        direction: str
    ) -> Optional[str]:
        """
        Expand one frontier by one hop, checking for intersection.

        Args:
            frontier: Set of node IDs to expand
            current_parents: Parent tracking for this direction
            other_parents: Parent tracking for opposite direction
            allowed_rel_types: Optional relationship type filter
            direction: "forward" or "backward" (for relationship direction)

        Returns:
            Meeting point node ID if frontiers intersect, None otherwise
        """
        if not frontier:
            return None

        # Batch query all neighbors for the entire frontier
        current_ids = list(frontier)
        neighbors = self._get_neighbors_batch(current_ids, allowed_rel_types, direction)

        next_frontier: Set[str] = set()

        for neighbor_id, parent_id, rel_type, rel_props in neighbors:
            # Check for intersection with other frontier
            if neighbor_id in other_parents:
                # Record the connection
                current_parents[neighbor_id] = (parent_id, rel_type, rel_props)
                return neighbor_id

            # Not visited yet on this side - add to frontier
            if neighbor_id not in current_parents:
                current_parents[neighbor_id] = (parent_id, rel_type, rel_props)
                next_frontier.add(neighbor_id)

        # Update frontier in place
        frontier.clear()
        frontier.update(next_frontier)

        return None

    def _get_neighbors_batch(
        self,
        node_ids: List[str],
        allowed_rel_types: Optional[List[str]],
        direction: str
    ) -> List[Tuple[str, str, str, Dict]]:
        """
        Batch query to get all neighbors for a set of nodes.

        Only traverses to :Concept nodes (excludes Source, Instance).

        Args:
            node_ids: List of concept IDs to get neighbors for
            allowed_rel_types: Optional relationship type filter
            direction: "forward" (outgoing) or "backward" (incoming)

        Returns:
            List of (neighbor_id, parent_id, rel_type, rel_props) tuples
        """
        if not node_ids:
            return []

        # Build relationship type filter
        rel_filter = ""
        if allowed_rel_types and len(allowed_rel_types) > 0:
            _validate_rel_types(allowed_rel_types)
            type_list = ", ".join([f"'{t}'" for t in allowed_rel_types])
            rel_filter = f"AND type(r) IN [{type_list}]"

        # Build direction-aware query
        # Both directions since relationships can be traversed either way
        # AGE stores directed edges, but for pathfinding we typically want undirected
        query = f"""
            MATCH (current:Concept)-[r]-(neighbor:Concept)
            WHERE current.concept_id IN $ids {rel_filter}
            RETURN
                current.concept_id as parent,
                neighbor.concept_id as child,
                type(r) as rel_type,
                properties(r) as rel_props
        """

        # Execute via AGEClient - need to manually substitute the list
        # since AGE doesn't handle list parameters well
        ids_str = ", ".join([f"'{id}'" for id in node_ids])
        query_substituted = query.replace("$ids", f"[{ids_str}]")

        try:
            results = self.db._execute_cypher(query_substituted)
        except Exception as e:
            logger.error(f"Neighbor query failed: {e}")
            return []

        neighbors = []
        for row in (results or []):
            neighbors.append((
                row['child'],
                row['parent'],
                row['rel_type'],
                row.get('rel_props', {})
            ))

        return neighbors

    def _reconstruct_path(
        self,
        meeting_point: str,
        parents_forward: Dict[str, Optional[Tuple[str, str, Dict]]],
        parents_backward: Dict[str, Optional[Tuple[str, str, Dict]]],
        from_id: str,
        to_id: str
    ) -> Dict[str, Any]:
        """
        Reconstruct full path from forward and backward parent chains.

        Args:
            meeting_point: Node where frontiers met
            parents_forward: Parent tracking from start
            parents_backward: Parent tracking from end
            from_id: Original start node
            to_id: Original end node

        Returns:
            Path dictionary with nodes, relationships, hops
        """
        # Trace path from meeting point back to start
        path_to_start = []
        current = meeting_point
        while current is not None:
            parent_info = parents_forward.get(current)
            if parent_info is None:
                path_to_start.append(current)
                break
            parent_id, rel_type, rel_props = parent_info
            path_to_start.append((current, rel_type, rel_props))
            current = parent_id

        # Trace path from meeting point to end
        path_to_end = []
        current = meeting_point
        while current is not None:
            parent_info = parents_backward.get(current)
            if parent_info is None:
                break  # Meeting point already added
            parent_id, rel_type, rel_props = parent_info
            path_to_end.append((parent_id, rel_type, rel_props))
            current = parent_id

        # Combine: reverse path_to_start + path_to_end
        path_to_start.reverse()

        # Extract node IDs and relationship types
        node_ids = []
        rel_infos = []

        # Process path_to_start (now start -> meeting)
        for item in path_to_start:
            if isinstance(item, str):
                node_ids.append(item)
            else:
                node_id, rel_type, rel_props = item
                node_ids.append(node_id)
                rel_infos.append({"label": rel_type, "properties": rel_props or {}})

        # Process path_to_end (meeting -> end)
        for item in path_to_end:
            node_id, rel_type, rel_props = item
            node_ids.append(node_id)
            rel_infos.append({"label": rel_type, "properties": rel_props or {}})

        # Fetch full node data
        path_nodes = []
        for nid in node_ids:
            node_data = self._get_concept_data(nid)
            if node_data:
                path_nodes.append(node_data)
            else:
                # Fallback for missing nodes
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

    def _get_concept_data(self, concept_id: str) -> Optional[Dict[str, Any]]:
        """Fetch concept node data."""
        query = """
            MATCH (c:Concept {concept_id: $cid})
            RETURN c.concept_id as concept_id, c.label as label, c.description as description
        """
        try:
            results = self.db._execute_cypher(query, params={"cid": concept_id}, fetch_one=True)
            return results if results else None
        except Exception:
            return None

    def _concept_exists(self, concept_id: str) -> bool:
        """Check if concept exists."""
        query = """
            MATCH (c:Concept {concept_id: $cid})
            RETURN count(c) as cnt
        """
        try:
            result = self.db._execute_cypher(query, params={"cid": concept_id}, fetch_one=True)
            return result and result.get('cnt', 0) > 0
        except Exception:
            return False

    def _extract_edges(self, path: Dict[str, Any]) -> Set[Tuple[str, str]]:
        """Extract edge pairs from a path for exclusion."""
        edges = set()
        nodes = path.get("path_nodes", [])
        for i in range(len(nodes) - 1):
            from_node = nodes[i].get("concept_id", "")
            to_node = nodes[i + 1].get("concept_id", "")
            if from_node and to_node:
                # Add both directions since we traverse undirected
                edges.add((from_node, to_node))
                edges.add((to_node, from_node))
        return edges

    def _find_path_excluding_edges(
        self,
        from_id: str,
        to_id: str,
        max_hops: int,
        allowed_rel_types: Optional[List[str]],
        excluded_edges: Set[Tuple[str, str]]
    ) -> Optional[Dict[str, Any]]:
        """
        Find a path avoiding specific edges using modified BFS.

        Args:
            from_id: Starting concept ID
            to_id: Target concept ID
            max_hops: Maximum path length
            allowed_rel_types: Optional relationship type filter
            excluded_edges: Set of (from_id, to_id) tuples to avoid

        Returns:
            Path dictionary or None if no alternative path found
        """
        if from_id == to_id:
            return None  # No alternative to self-path

        # Initialize frontiers and parent tracking
        parents_forward: Dict[str, Optional[Tuple[str, str, Dict]]] = {from_id: None}
        parents_backward: Dict[str, Optional[Tuple[str, str, Dict]]] = {to_id: None}

        frontier_forward: Set[str] = {from_id}
        frontier_backward: Set[str] = {to_id}

        for depth in range(max_hops):
            if len(frontier_forward) <= len(frontier_backward):
                meeting_point = self._expand_frontier_excluding(
                    frontier_forward,
                    parents_forward,
                    parents_backward,
                    allowed_rel_types,
                    excluded_edges,
                    direction="forward"
                )
                if meeting_point:
                    return self._reconstruct_path(
                        meeting_point,
                        parents_forward,
                        parents_backward,
                        from_id,
                        to_id
                    )
            else:
                meeting_point = self._expand_frontier_excluding(
                    frontier_backward,
                    parents_backward,
                    parents_forward,
                    allowed_rel_types,
                    excluded_edges,
                    direction="backward"
                )
                if meeting_point:
                    return self._reconstruct_path(
                        meeting_point,
                        parents_forward,
                        parents_backward,
                        from_id,
                        to_id
                    )

            if not frontier_forward and not frontier_backward:
                break

        return None

    def _expand_frontier_excluding(
        self,
        frontier: Set[str],
        current_parents: Dict[str, Optional[Tuple[str, str, Dict]]],
        other_parents: Dict[str, Optional[Tuple[str, str, Dict]]],
        allowed_rel_types: Optional[List[str]],
        excluded_edges: Set[Tuple[str, str]],
        direction: str
    ) -> Optional[str]:
        """Expand frontier while avoiding excluded edges."""
        if not frontier:
            return None

        current_ids = list(frontier)
        neighbors = self._get_neighbors_batch(current_ids, allowed_rel_types, direction)

        next_frontier: Set[str] = set()

        for neighbor_id, parent_id, rel_type, rel_props in neighbors:
            # Skip excluded edges
            if (parent_id, neighbor_id) in excluded_edges:
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

    def _find_additional_paths(
        self,
        from_id: str,
        to_id: str,
        max_hops: int,
        max_paths: int,
        allowed_rel_types: Optional[List[str]],
        exclude_edges: Set[Tuple[str, str]]
    ) -> List[Dict[str, Any]]:
        """
        Find additional paths avoiding certain edges.

        Simplified k-shortest paths using iterative BFS with edge exclusion.
        """
        # For simplicity, fall back to exhaustive Cypher for additional paths
        # This is acceptable since we only need a few extra paths
        # and the first (shortest) path is found efficiently

        # Build relationship filter
        rel_filter = ""
        if allowed_rel_types and len(allowed_rel_types) > 0:
            _validate_rel_types(allowed_rel_types)
            type_pattern = "|".join(allowed_rel_types)
            rel_filter = f":{type_pattern}"

        # Parameterize concept IDs; rel_filter and integers can't use $params
        # in Cypher pattern syntax but are validated above
        result_limit = max_paths + 5
        query = f"""
            MATCH path = (from:Concept {{concept_id: $from_id}})-[{rel_filter}*1..{max_hops}]-(to:Concept {{concept_id: $to_id}})
            WITH path, length(path) as hops
            RETURN nodes(path) as path_nodes, relationships(path) as path_rels, hops
            ORDER BY hops ASC
            LIMIT {result_limit}
        """

        try:
            results = self.db._execute_cypher(
                query, params={"from_id": from_id, "to_id": to_id}
            )
        except Exception as e:
            logger.warning(f"Additional paths query failed: {e}")
            return []

        paths = []
        for record in (results or []):
            # Convert AGE vertex/edge format to our format
            nodes = []
            for node in record.get('path_nodes', []):
                if isinstance(node, dict):
                    props = node.get('properties', {})
                    nodes.append({
                        "concept_id": props.get('concept_id', ''),
                        "label": props.get('label', ''),
                        "description": props.get('description', '')
                    })

            rels = []
            for rel in record.get('path_rels', []):
                if isinstance(rel, dict):
                    rels.append({
                        "label": rel.get('label', ''),
                        "properties": rel.get('properties', {})
                    })

            # Check if this path uses excluded edges
            uses_excluded = False
            for i in range(len(nodes) - 1):
                edge = (nodes[i].get("concept_id"), nodes[i + 1].get("concept_id"))
                if edge in exclude_edges:
                    uses_excluded = True
                    break

            if not uses_excluded and nodes:
                paths.append({
                    "path_nodes": nodes,
                    "path_rels": rels,
                    "hops": record.get('hops', len(rels))
                })

        return paths[:max_paths]
