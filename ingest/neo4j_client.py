"""
Neo4j client for knowledge graph operations.

Handles all database interactions including node creation, relationship management,
and vector similarity search.
"""

import os
from typing import List, Dict, Optional, Any
from neo4j import GraphDatabase, Driver, Session
from neo4j.exceptions import ServiceUnavailable, AuthError


class Neo4jClient:
    """Client for interacting with Neo4j knowledge graph database."""

    def __init__(
        self,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Initialize Neo4j client with connection details.

        Args:
            uri: Neo4j connection URI (defaults to NEO4J_URI env var)
            username: Neo4j username (defaults to NEO4J_USER env var)
            password: Neo4j password (defaults to NEO4J_PASSWORD env var)

        Raises:
            ValueError: If connection details are missing
            ServiceUnavailable: If cannot connect to Neo4j
            AuthError: If authentication fails
        """
        self.uri = uri or os.getenv("NEO4J_URI")
        self.username = username or os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME")
        self.password = password or os.getenv("NEO4J_PASSWORD")

        if not all([self.uri, self.username, self.password]):
            raise ValueError(
                "Missing Neo4j connection details. Provide via parameters or "
                "set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD environment variables."
            )

        try:
            self.driver: Driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password)
            )
            # Test connection
            self.driver.verify_connectivity()
        except ServiceUnavailable as e:
            raise ServiceUnavailable(f"Cannot connect to Neo4j at {self.uri}: {e}")
        except AuthError as e:
            raise AuthError(f"Authentication failed for Neo4j: {e}")

    def close(self):
        """Close the database connection."""
        if self.driver:
            self.driver.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def create_source_node(
        self,
        source_id: str,
        document: str,
        paragraph: int,
        full_text: str,
        file_path: str = None
    ) -> Dict[str, Any]:
        """
        Create a Source node in the graph.

        Args:
            source_id: Unique identifier for the source
            document: Document/ontology name for logical grouping
            paragraph: Paragraph/chunk number in the document
            full_text: Full text content of the paragraph
            file_path: Path to the source file (optional)

        Returns:
            Dictionary with created node properties

        Raises:
            Exception: If node creation fails
        """
        query = """
        CREATE (s:Source {
            source_id: $source_id,
            document: $document,
            paragraph: $paragraph,
            full_text: $full_text,
            file_path: $file_path
        })
        RETURN s
        """

        try:
            with self.driver.session() as session:
                result = session.run(
                    query,
                    source_id=source_id,
                    document=document,
                    paragraph=paragraph,
                    full_text=full_text,
                    file_path=file_path
                )
                record = result.single()
                return dict(record["s"]) if record else {}
        except Exception as e:
            raise Exception(f"Failed to create Source node {source_id}: {e}")

    def create_concept_node(
        self,
        concept_id: str,
        label: str,
        embedding: List[float],
        search_terms: List[str]
    ) -> Dict[str, Any]:
        """
        Create a Concept node in the graph.

        Args:
            concept_id: Unique identifier for the concept
            label: Human-readable concept label
            embedding: Vector embedding for similarity search
            search_terms: Alternative terms/phrases for the concept

        Returns:
            Dictionary with created node properties

        Raises:
            Exception: If node creation fails
        """
        query = """
        CREATE (c:Concept {
            concept_id: $concept_id,
            label: $label,
            embedding: $embedding,
            search_terms: $search_terms
        })
        RETURN c
        """

        try:
            with self.driver.session() as session:
                result = session.run(
                    query,
                    concept_id=concept_id,
                    label=label,
                    embedding=embedding,
                    search_terms=search_terms
                )
                record = result.single()
                return dict(record["c"]) if record else {}
        except Exception as e:
            raise Exception(f"Failed to create Concept node {concept_id}: {e}")

    def create_instance_node(
        self,
        instance_id: str,
        quote: str
    ) -> Dict[str, Any]:
        """
        Create an Instance node in the graph.

        Args:
            instance_id: Unique identifier for the instance
            quote: Exact quote from the source text

        Returns:
            Dictionary with created node properties

        Raises:
            Exception: If node creation fails
        """
        query = """
        CREATE (i:Instance {
            instance_id: $instance_id,
            quote: $quote
        })
        RETURN i
        """

        try:
            with self.driver.session() as session:
                result = session.run(
                    query,
                    instance_id=instance_id,
                    quote=quote
                )
                record = result.single()
                return dict(record["i"]) if record else {}
        except Exception as e:
            raise Exception(f"Failed to create Instance node {instance_id}: {e}")

    def link_concept_to_source(
        self,
        concept_id: str,
        source_id: str
    ) -> bool:
        """
        Create APPEARS_IN relationship from Concept to Source.

        Args:
            concept_id: ID of the concept node
            source_id: ID of the source node

        Returns:
            True if relationship created successfully

        Raises:
            Exception: If relationship creation fails
        """
        query = """
        MATCH (c:Concept {concept_id: $concept_id})
        MATCH (s:Source {source_id: $source_id})
        MERGE (c)-[:APPEARS_IN]->(s)
        RETURN c, s
        """

        try:
            with self.driver.session() as session:
                result = session.run(
                    query,
                    concept_id=concept_id,
                    source_id=source_id
                )
                return result.single() is not None
        except Exception as e:
            raise Exception(
                f"Failed to link Concept {concept_id} to Source {source_id}: {e}"
            )

    def link_instance_to_concept_and_source(
        self,
        instance_id: str,
        concept_id: str,
        source_id: str
    ) -> bool:
        """
        Create EVIDENCED_BY (Concept->Instance) and FROM_SOURCE (Instance->Source) relationships.

        Args:
            instance_id: ID of the instance node
            concept_id: ID of the concept node
            source_id: ID of the source node

        Returns:
            True if relationships created successfully

        Raises:
            Exception: If relationship creation fails
        """
        query = """
        MATCH (c:Concept {concept_id: $concept_id})
        MATCH (i:Instance {instance_id: $instance_id})
        MATCH (s:Source {source_id: $source_id})
        MERGE (c)-[:EVIDENCED_BY]->(i)
        MERGE (i)-[:FROM_SOURCE]->(s)
        RETURN c, i, s
        """

        try:
            with self.driver.session() as session:
                result = session.run(
                    query,
                    instance_id=instance_id,
                    concept_id=concept_id,
                    source_id=source_id
                )
                return result.single() is not None
        except Exception as e:
            raise Exception(
                f"Failed to link Instance {instance_id} to Concept {concept_id} "
                f"and Source {source_id}: {e}"
            )

    def create_concept_relationship(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        confidence: float
    ) -> bool:
        """
        Create a relationship between two concepts.

        Args:
            from_id: Source concept ID
            to_id: Target concept ID
            rel_type: Relationship type (IMPLIES, CONTRADICTS, SUPPORTS, PART_OF)
            confidence: Confidence score (0.0-1.0)

        Returns:
            True if relationship created successfully

        Raises:
            ValueError: If rel_type is invalid or confidence out of range
            Exception: If relationship creation fails
        """
        valid_types = ["IMPLIES", "CONTRADICTS", "SUPPORTS", "PART_OF"]
        if rel_type not in valid_types:
            raise ValueError(
                f"Invalid relationship type: {rel_type}. Must be one of {valid_types}"
            )

        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {confidence}")

        query = f"""
        MATCH (c1:Concept {{concept_id: $from_id}})
        MATCH (c2:Concept {{concept_id: $to_id}})
        MERGE (c1)-[r:{rel_type} {{confidence: $confidence}}]->(c2)
        RETURN c1, r, c2
        """

        try:
            with self.driver.session() as session:
                result = session.run(
                    query,
                    from_id=from_id,
                    to_id=to_id,
                    confidence=confidence
                )
                return result.single() is not None
        except Exception as e:
            raise Exception(
                f"Failed to create {rel_type} relationship from {from_id} to {to_id}: {e}"
            )

    def vector_search(
        self,
        embedding: List[float],
        threshold: float = 0.85,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for similar concepts using vector similarity.

        Args:
            embedding: Query embedding vector
            threshold: Minimum similarity threshold (0.0-1.0)
            limit: Maximum number of results to return

        Returns:
            List of dictionaries with concept_id, label, and similarity score

        Raises:
            ValueError: If threshold is out of range
            Exception: If search fails
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"Threshold must be between 0.0 and 1.0, got {threshold}")

        # Using native vector index for similarity search
        query = """
        CALL db.index.vector.queryNodes('concept-embeddings', $limit, $embedding)
        YIELD node AS c, score
        WHERE score >= $threshold
        RETURN c.concept_id AS concept_id,
               c.label AS label,
               score AS similarity
        ORDER BY similarity DESC
        """

        try:
            with self.driver.session() as session:
                result = session.run(
                    query,
                    embedding=embedding,
                    threshold=threshold,
                    limit=limit
                )
                return [
                    {
                        "concept_id": record["concept_id"],
                        "label": record["label"],
                        "similarity": record["similarity"]
                    }
                    for record in result
                ]
        except Exception as e:
            raise Exception(f"Vector search failed: {e}")

    def get_document_concepts(
        self,
        document_name: str,
        limit: int = 50,
        recent_chunks_only: Optional[int] = None,
        warn_on_empty: bool = False
    ) -> tuple[List[Dict[str, Any]], bool]:
        """
        Retrieve concepts from a specific document for context awareness.

        Args:
            document_name: Name of the document
            limit: Maximum number of concepts to return
            recent_chunks_only: If set, only get concepts from last N chunks/paragraphs
            warn_on_empty: If True, returns flag indicating empty database warnings

        Returns:
            Tuple of (list of concept dicts, has_empty_db_warnings)

        Raises:
            Exception: If query fails
        """
        if recent_chunks_only:
            # Get concepts from recent chunks only
            query = """
            MATCH (c:Concept)-[:APPEARS_IN]->(s:Source {document: $document})
            WITH c, s
            ORDER BY s.paragraph DESC
            LIMIT $chunk_limit
            WITH DISTINCT c
            RETURN c.concept_id AS concept_id, c.label AS label
            LIMIT $limit
            """
            params = {
                "document": document_name,
                "chunk_limit": recent_chunks_only * 10,  # Assume ~10 concepts per chunk
                "limit": limit
            }
        else:
            # Get all concepts from document
            query = """
            MATCH (c:Concept)-[:APPEARS_IN]->(s:Source {document: $document})
            RETURN DISTINCT c.concept_id AS concept_id, c.label AS label
            LIMIT $limit
            """
            params = {
                "document": document_name,
                "limit": limit
            }

        try:
            with self.driver.session() as session:
                result = session.run(query, **params)
                concepts = [
                    {
                        "concept_id": record["concept_id"],
                        "label": record["label"]
                    }
                    for record in result
                ]

                # Check for notifications about missing schema elements (empty DB)
                has_empty_warnings = False
                if warn_on_empty and hasattr(result, '_summary') and result._summary:
                    notifications = getattr(result._summary, 'notifications', [])
                    if notifications:
                        # Check if warnings are about missing labels/relationships
                        for notif in notifications:
                            if hasattr(notif, 'description'):
                                desc = str(notif.description).lower()
                                if 'not available' in desc or 'missing' in desc:
                                    has_empty_warnings = True
                                    break

                return concepts, has_empty_warnings
        except Exception as e:
            raise Exception(f"Failed to get document concepts: {e}")
