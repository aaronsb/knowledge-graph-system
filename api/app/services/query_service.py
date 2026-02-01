"""
Query service for graph operations.

Centralizes Cypher query construction and execution with explicit,
well-documented query building.
"""

from typing import List, Dict, Optional, Any
import logging
import re

logger = logging.getLogger(__name__)

# Valid Cypher relationship type: uppercase letters, digits, underscores
_VALID_REL_TYPE_RE = re.compile(r'^[A-Z][A-Z0-9_]*$')


def _validate_rel_types(types: List[str]) -> List[str]:
    """Validate relationship type names for safe Cypher interpolation.

    Relationship types are interpolated into Cypher patterns ([:TYPE1|TYPE2])
    which cannot use $param syntax. This ensures only valid identifiers are used.
    """
    for t in types:
        if not _VALID_REL_TYPE_RE.match(t):
            raise ValueError(f"Invalid relationship type name: {t!r}")
    return types


class QueryService:
    """Service for building and executing graph queries"""

    @staticmethod
    def build_search_query(limit: int, min_similarity: float) -> str:
        """
        Build vector similarity search query.

        Query flow:
        1. Call vector index to get similar concepts
        2. Filter by minimum similarity threshold
        3. Join to Source nodes to get document names
        4. Count evidence instances
        5. Return concept metadata with scores

        Args:
            limit: Maximum results to return
            min_similarity: Minimum cosine similarity (0.0-1.0)

        Returns:
            Cypher query string
        """
        return """
            CALL db.index.vector.queryNodes('concept-embeddings', $limit, $embedding)
            YIELD node, score
            WHERE score > $min_similarity
            WITH node, score
            MATCH (node)-[:APPEARS]->(s:Source)
            WITH node, score, collect(DISTINCT s.document) as documents
            OPTIONAL MATCH (node)-[:EVIDENCED_BY]->(i:Instance)
            WITH node, score, documents, count(DISTINCT i) as evidence_count
            RETURN
                node.concept_id as concept_id,
                node.label as label,
                score,
                documents,
                evidence_count
            ORDER BY score DESC
        """

    @staticmethod
    def build_concept_details_query() -> Dict[str, str]:
        """
        Build queries for concept details retrieval.

        Returns 3 separate queries for clarity:
        - concept_query: Get concept node and associated documents
        - instances_query: Get evidence instances with source context
        - relationships_query: Get outgoing relationships

        Returns:
            Dict with query names as keys, Cypher queries as values
        """
        return {
            "concept": """
                MATCH (c:Concept {concept_id: $concept_id})
                OPTIONAL MATCH (c)-[:APPEARS]->(s:Source)
                WITH c, collect(DISTINCT s.document) as documents
                RETURN c, documents
            """,
            "instances": """
                MATCH (c:Concept {concept_id: $concept_id})-[:EVIDENCED_BY]->(i:Instance)
                MATCH (i)-[:FROM_SOURCE]->(s:Source)
                RETURN
                    i.quote as quote,
                    s.document as document,
                    s.paragraph as paragraph,
                    s.source_id as source_id,
                    s.full_text as full_text,
                    s.file_path as file_path
                ORDER BY s.document, s.paragraph
            """,
            "relationships": """
                MATCH (c:Concept {concept_id: $concept_id})-[r]->(related:Concept)
                RETURN
                    related.concept_id as to_id,
                    related.label as to_label,
                    type(r) as rel_type,
                    properties(r) as props
            """
        }

    @staticmethod
    def build_related_concepts_query(
        max_depth: int,
        relationship_types: Optional[List[str]] = None
    ) -> List[tuple]:
        """
        Build queries for related concepts traversal.

        Uses iterative fixed-depth matches instead of variable-length paths
        to avoid combinatorial path explosion in cyclic graphs. Returns one
        query per depth level, each producing O(nodes) rows instead of O(paths).

        Args:
            max_depth: Maximum traversal depth (1-5)
            relationship_types: Optional list of relationship types to filter

        Returns:
            List of (query_string, depth) tuples. Execute each separately
            and merge results, keeping minimum distance per concept.
        """
        # Build relationship type filter
        rel_filter = ""
        if relationship_types:
            _validate_rel_types(relationship_types)
            rel_types = "|".join(relationship_types)
            rel_filter = f":{rel_types}"

        # Build per-depth queries to avoid variable-length path explosion.
        # The old query used [*1..N] which enumerates ALL paths (combinatorial
        # in cyclic graphs), then collect(path) materialized them all in memory.
        # Fixed-depth chains produce O(nodes) distinct results per level.
        #
        # Returns a list of (query, depth) tuples — one per depth level.
        # AGE's column spec parser can't handle UNION ALL, so each depth
        # is executed as a separate query and merged in Python.
        queries = []
        for depth in range(1, max_depth + 1):
            # Build explicit hop chain with named relationship variables
            # depth 1: (start)-[r0]-(target:Concept)
            # depth 2: (start)-[r0]-(h1:Concept)-[r1]-(target:Concept)
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

            # Use WITH to build the path_types array before RETURN.
            # The column spec parser splits on commas, so [type(r0), type(r1)]
            # in RETURN would be misparse as extra columns.
            queries.append((f"""
                MATCH (start:Concept {{concept_id: $concept_id}})-{chain}
                WHERE start <> target
                WITH DISTINCT target.concept_id as concept_id,
                    target.label as label,
                    [{type_exprs}] as path_types
                RETURN concept_id, label, {depth} as distance, path_types
            """, depth))

        return queries

    @staticmethod
    def build_shortest_path_query(
        max_hops: int,
        allowed_rel_types: Optional[List[str]] = None
    ) -> str:
        """
        Build shortest path query between two concepts (AGE-compatible).

        Query flow:
        1. Find all variable-length paths up to max_hops
        2. Filter by relationship types if provided (ADR-065: epistemic status filtering)
        3. Return the path itself (nodes and relationships as AGE vertex/edge objects)
        4. Sort by length (shortest first)
        5. Limit to 10 paths for performance (filtered to 5 in Python)

        Note: AGE doesn't support Neo4j's shortestPath(), all() predicate, or
        advanced list comprehensions. We fetch paths and filter metadata nodes
        (Source, Instance) in Python post-processing.

        **Metadata Filtering:**
        Python code filters out paths containing non-Concept nodes:
        - Source nodes (document metadata via APPEARS)
        - Instance nodes (evidence quotes via EVIDENCED_BY)
        This ensures paths show only semantic relationships: Concept → Concept

        **Epistemic Status Filtering (ADR-065):**
        When allowed_rel_types is provided (typically from epistemic status filtering),
        only paths using those relationship types are returned. This enables filtering
        like "only AFFIRMATIVE relationships" or "exclude HISTORICAL relationships".

        Args:
            max_hops: Maximum path length (1-10)
            allowed_rel_types: Optional list of allowed relationship types for filtering

        Returns:
            Cypher query string (returns extra paths for post-filtering)
        """
        # Build relationship pattern with type filtering if needed
        if allowed_rel_types and len(allowed_rel_types) > 0:
            _validate_rel_types(allowed_rel_types)
            # Build OR-based type filter for variable-length path
            type_pattern = "|".join(allowed_rel_types)
            rel_pattern = f"[:{type_pattern}*1..{max_hops}]"
        else:
            # No filtering - all relationship types
            rel_pattern = f"[*1..{max_hops}]"

        return f"""
            MATCH path = (from:Concept {{concept_id: $from_id}})-{rel_pattern}-(to:Concept {{concept_id: $to_id}})
            WITH path, length(path) as hops
            RETURN nodes(path) as path_nodes, relationships(path) as path_rels, hops
            ORDER BY hops ASC
            LIMIT 10
        """

    @staticmethod
    def execute_search(
        session: Any,
        embedding: List[float],
        limit: int,
        min_similarity: float
    ) -> List[Dict[str, Any]]:
        """
        Execute semantic search query.

        Args:
            session: Neo4j session
            embedding: Query embedding vector
            limit: Maximum results
            min_similarity: Minimum similarity threshold

        Returns:
            List of concept search results
        """
        query = QueryService.build_search_query(limit, min_similarity)
        result = session.run(
            query,
            embedding=embedding,
            limit=limit,
            min_similarity=min_similarity
        )
        return [dict(record) for record in result]

    @staticmethod
    def execute_concept_details(
        session: Any,
        concept_id: str
    ) -> Dict[str, Any]:
        """
        Execute concept details queries.

        Args:
            session: Neo4j session
            concept_id: Concept ID to retrieve

        Returns:
            Dict with concept, instances, and relationships data
        """
        queries = QueryService.build_concept_details_query()

        # Execute concept query
        concept_result = session.run(queries["concept"], concept_id=concept_id)
        concept_record = concept_result.single()

        if not concept_record:
            return None

        # Execute instances query
        instances_result = session.run(queries["instances"], concept_id=concept_id)
        instances = [dict(record) for record in instances_result]

        # Execute relationships query
        rel_result = session.run(queries["relationships"], concept_id=concept_id)
        relationships = [dict(record) for record in rel_result]

        return {
            "concept": dict(concept_record['c']),
            "documents": concept_record['documents'],
            "instances": instances,
            "relationships": relationships
        }

    @staticmethod
    def execute_related_concepts(
        session: Any,
        concept_id: str,
        max_depth: int,
        relationship_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute related concepts query.

        Args:
            session: Neo4j session
            concept_id: Starting concept ID
            max_depth: Maximum traversal depth
            relationship_types: Optional relationship type filter

        Returns:
            List of related concepts with distance information
        """
        query = QueryService.build_related_concepts_query(max_depth, relationship_types)
        result = session.run(query, concept_id=concept_id)
        return [dict(record) for record in result]

    @staticmethod
    def execute_shortest_path(
        session: Any,
        from_id: str,
        to_id: str,
        max_hops: int
    ) -> List[Dict[str, Any]]:
        """
        Execute shortest path query.

        Args:
            session: Neo4j session
            from_id: Starting concept ID
            to_id: Target concept ID
            max_hops: Maximum path length

        Returns:
            List of paths with nodes and relationships
        """
        query = QueryService.build_shortest_path_query(max_hops)
        result = session.run(query, from_id=from_id, to_id=to_id)
        return [dict(record) for record in result]
