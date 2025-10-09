"""
Query service for graph operations.

Centralizes Cypher query construction and execution with explicit,
well-documented query building.
"""

from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


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
            MATCH (node)-[:APPEARS_IN]->(s:Source)
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
                OPTIONAL MATCH (c)-[:APPEARS_IN]->(s:Source)
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
                    s.source_id as source_id
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
    ) -> str:
        """
        Build query for related concepts traversal.

        Query flow:
        1. Variable-length path traversal from starting concept
        2. Filter by relationship types if specified
        3. Exclude self-loops (start <> related)
        4. Calculate minimum distance to each concept
        5. Collect relationship types in path

        Args:
            max_depth: Maximum traversal depth (1-5)
            relationship_types: Optional list of relationship types to filter

        Returns:
            Cypher query string with relationship filter applied
        """
        # Build relationship type filter
        rel_filter = ""
        if relationship_types:
            # Join types with | for Cypher union syntax: [:TYPE1|TYPE2|TYPE3]
            rel_types = "|".join(relationship_types)
            rel_filter = f":{rel_types}"

        # Explicit string composition for clarity
        query = f"""
            MATCH path = (start:Concept {{concept_id: $concept_id}})-[r{rel_filter}*1..{max_depth}]-(related:Concept)
            WHERE start <> related
            WITH related,
                 min(length(path)) as min_distance,
                 [rel in relationships(path) | type(rel)] as path_types
            RETURN DISTINCT
                related.concept_id as concept_id,
                related.label as label,
                min_distance as distance,
                path_types
            ORDER BY min_distance, label
        """

        return query

    @staticmethod
    def build_shortest_path_query(max_hops: int) -> str:
        """
        Build shortest path query between two concepts (AGE-compatible).

        Query flow:
        1. Find all variable-length paths up to max_hops
        2. Extract node IDs/labels and relationship types
        3. Calculate path length
        4. Sort by length (shortest first)
        5. Limit to 5 paths for performance

        Note: AGE doesn't support Neo4j's shortestPath() function,
        so we use variable-length patterns with sorting.

        Args:
            max_hops: Maximum path length (1-10)

        Returns:
            Cypher query string
        """
        return f"""
            MATCH path = (from:Concept {{concept_id: $from_id}})-[*1..{max_hops}]-(to:Concept {{concept_id: $to_id}})
            WITH path,
                 [node in nodes(path) | {{id: node.concept_id, label: node.label}}] as path_nodes,
                 [rel in relationships(path) | type(rel)] as rel_types,
                 length(path) as hops
            RETURN path_nodes, rel_types, hops
            ORDER BY hops ASC
            LIMIT 5
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
