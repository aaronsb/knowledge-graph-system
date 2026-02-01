"""
Ontology mixin for node CRUD and lifecycle management.

Ontology nodes (ADR-200) are first-class graph entities that organize
Source nodes via :SCOPED_BY edges. This mixin handles the foundational
operations: creation, retrieval, deletion, renaming, and lifecycle
state transitions (active/pinned/frozen).

Also includes the legacy source-level rename (pre-ADR-200) for
backward compatibility.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class OntologyMixin:
    """Ontology node CRUD and lifecycle state management."""

    def rename_ontology(
        self,
        old_name: str,
        new_name: str
    ) -> Dict[str, int]:
        """
        Rename an ontology by updating all Source nodes' document property.

        Ontologies are logical groupings defined by the 'document' property on Source nodes.
        This method updates all Source nodes from old_name to new_name.

        Args:
            old_name: Current ontology name
            new_name: New ontology name

        Returns:
            Dictionary with count: {"sources_updated": N}

        Raises:
            ValueError: If old ontology doesn't exist or new ontology already exists
            Exception: If rename operation fails
        """
        # Check if old ontology exists
        check_old = """
        MATCH (s:Source {document: $old_name})
        RETURN count(s) as source_count
        """

        try:
            old_result = self._execute_cypher(
                check_old,
                params={"old_name": old_name},
                fetch_one=True
            )
            old_count = int(str(old_result.get("source_count", 0)))

            if old_count == 0:
                raise ValueError(f"Ontology '{old_name}' does not exist")
        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"Failed to check old ontology existence: {e}")

        # Check if new ontology already exists
        check_new = """
        MATCH (s:Source {document: $new_name})
        RETURN count(s) as source_count
        """

        try:
            new_result = self._execute_cypher(
                check_new,
                params={"new_name": new_name},
                fetch_one=True
            )
            new_count = int(str(new_result.get("source_count", 0)))

            if new_count > 0:
                raise ValueError(f"Ontology '{new_name}' already exists")
        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"Failed to check new ontology existence: {e}")

        # Rename ontology by updating all Source nodes
        rename_query = """
        MATCH (s:Source {document: $old_name})
        SET s.document = $new_name
        RETURN count(s) as updated_count
        """

        try:
            result = self._execute_cypher(
                rename_query,
                params={
                    "old_name": old_name,
                    "new_name": new_name
                },
                fetch_one=True
            )

            updated_count = int(str(result.get("updated_count", 0)))

            return {"sources_updated": updated_count}
        except Exception as e:
            raise Exception(f"Failed to rename ontology: {e}")

    # =========================================================================
    # Ontology Node Methods (ADR-200)
    # =========================================================================
    # Ontology nodes are first-class graph entities in the same embedding space
    # as concepts. They represent knowledge domains that organize Source nodes
    # via :SCOPED_BY edges. The s.document string on Source nodes is preserved
    # as a denormalized cache — :SCOPED_BY is the source of truth for new code.

    def create_ontology_node(
        self,
        ontology_id: str,
        name: str,
        description: str = "",
        embedding: Optional[List[float]] = None,
        search_terms: Optional[List[str]] = None,
        lifecycle_state: str = "active",
        creation_epoch: int = 0,
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create an Ontology node in the graph.

        Args:
            ontology_id: Unique identifier (ont_<uuid>)
            name: Ontology name (matches s.document on Source nodes)
            description: What this knowledge domain covers
            embedding: 1536-dim vector in the same space as concepts
            search_terms: Alternative names for similarity matching
            lifecycle_state: 'active' | 'pinned' | 'frozen'
            creation_epoch: Global epoch when created
            created_by: Username of the creating user (ADR-200 Phase 2)

        Returns:
            Dictionary with created node properties

        Raises:
            Exception: If node creation fails
        """
        query = """
        CREATE (o:Ontology {
            ontology_id: $ontology_id,
            name: $name,
            description: $description,
            embedding: $embedding,
            search_terms: $search_terms,
            lifecycle_state: $lifecycle_state,
            creation_epoch: $creation_epoch,
            created_by: $created_by
        })
        RETURN o
        """

        try:
            results = self._execute_cypher(
                query,
                params={
                    "ontology_id": ontology_id,
                    "name": name,
                    "description": description,
                    "embedding": embedding,
                    "search_terms": search_terms if search_terms else [],
                    "lifecycle_state": lifecycle_state,
                    "creation_epoch": creation_epoch,
                    "created_by": created_by
                },
                fetch_one=True
            )
            if results:
                agtype_result = results.get('o')
                parsed = self._parse_agtype(agtype_result)
                return parsed.get('properties', {}) if isinstance(parsed, dict) else {}
            return {}
        except Exception as e:
            raise Exception(f"Failed to create Ontology node {name}: {e}")

    def get_ontology_node(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get an Ontology node by name.

        Args:
            name: Ontology name

        Returns:
            Dictionary with node properties, or None if not found
        """
        query = """
        MATCH (o:Ontology {name: $name})
        RETURN o
        """

        try:
            result = self._execute_cypher(
                query,
                params={"name": name},
                fetch_one=True
            )
            if result:
                agtype_result = result.get('o')
                parsed = self._parse_agtype(agtype_result)
                return parsed.get('properties', {}) if isinstance(parsed, dict) else None
            return None
        except Exception as e:
            logger.error(f"Failed to get Ontology node {name}: {e}")
            return None

    def list_ontology_nodes(self) -> List[Dict[str, Any]]:
        """
        List all Ontology nodes in the graph.

        Returns:
            List of dictionaries with ontology node properties
        """
        query = """
        MATCH (o:Ontology)
        RETURN o
        ORDER BY o.name
        """

        try:
            results = self._execute_cypher(query)
            ontologies = []
            for row in results:
                agtype_result = row.get('o')
                parsed = self._parse_agtype(agtype_result)
                if isinstance(parsed, dict) and 'properties' in parsed:
                    ontologies.append(parsed['properties'])
            return ontologies
        except Exception as e:
            logger.error(f"Failed to list Ontology nodes: {e}")
            return []

    def delete_ontology_node(self, name: str) -> bool:
        """
        Delete an Ontology node and its edges (SCOPED_BY, etc).

        Does not delete Source nodes — they retain their s.document property.
        Only removes the :Ontology node and edges connected to it.

        Args:
            name: Ontology name

        Returns:
            True if deleted, False if not found
        """
        query = """
        MATCH (o:Ontology {name: $name})
        DETACH DELETE o
        RETURN count(*) as deleted
        """

        try:
            result = self._execute_cypher(
                query,
                params={"name": name},
                fetch_one=True
            )
            deleted = int(str(result.get("deleted", 0))) if result else 0
            return deleted > 0
        except Exception as e:
            logger.error(f"Failed to delete Ontology node {name}: {e}")
            return False

    def rename_ontology_node(self, old_name: str, new_name: str) -> bool:
        """
        Rename an Ontology node (updates the name property).

        This is called alongside rename_ontology() which updates s.document
        on Source nodes. Both must be kept in sync.

        Args:
            old_name: Current ontology name
            new_name: New ontology name

        Returns:
            True if renamed, False if not found
        """
        query = """
        MATCH (o:Ontology {name: $old_name})
        SET o.name = $new_name
        RETURN o.ontology_id as ontology_id
        """

        try:
            result = self._execute_cypher(
                query,
                params={"old_name": old_name, "new_name": new_name},
                fetch_one=True
            )
            return result is not None and result.get("ontology_id") is not None
        except Exception as e:
            logger.error(f"Failed to rename Ontology node {old_name} -> {new_name}: {e}")
            return False

    def create_scoped_by_edge(self, source_id: str, ontology_name: str) -> bool:
        """
        Create a :SCOPED_BY edge from a Source to an Ontology node.

        Uses MERGE for idempotency — safe to call multiple times.

        Args:
            source_id: Source node identifier
            ontology_name: Ontology node name

        Returns:
            True if edge exists (created or already present)
        """
        query = """
        MATCH (s:Source {source_id: $source_id})
        MATCH (o:Ontology {name: $ontology_name})
        MERGE (s)-[:SCOPED_BY]->(o)
        RETURN s.source_id as source_id
        """

        try:
            result = self._execute_cypher(
                query,
                params={
                    "source_id": source_id,
                    "ontology_name": ontology_name
                },
                fetch_one=True
            )
            return result is not None
        except Exception as e:
            logger.warning(f"Failed to create SCOPED_BY edge {source_id} -> {ontology_name}: {e}")
            return False

    def ensure_ontology_exists(self, name: str, description: str = "", created_by: Optional[str] = None) -> Dict[str, Any]:
        """
        Get or create an Ontology node. Used by ingestion pipeline to ensure
        the target ontology exists before creating Source nodes.

        Args:
            name: Ontology name
            description: Optional description for new ontologies
            created_by: Username of the creating user (ADR-200 Phase 2)

        Returns:
            Dictionary with ontology node properties
        """
        existing = self.get_ontology_node(name)
        if existing:
            return existing

        import uuid
        ontology_id = f"ont_{uuid.uuid4()}"

        # Get current epoch from graph_metrics
        creation_epoch = 0
        try:
            conn = self.pool.getconn()
            try:
                self._setup_age(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT counter FROM graph_metrics WHERE metric_name = 'document_ingestion_counter'"
                    )
                    row = cur.fetchone()
                    if row:
                        creation_epoch = row[0] or 0
            finally:
                conn.commit()
                self.pool.putconn(conn)
        except Exception:
            pass  # Default to 0 if metrics unavailable

        try:
            return self.create_ontology_node(
                ontology_id=ontology_id,
                name=name,
                description=description,
                lifecycle_state="active",
                creation_epoch=creation_epoch,
                created_by=created_by
            )
        except Exception:
            # Race condition: another worker created it between our check and create.
            # Re-fetch the winner's node (same pattern as vocabulary sync races).
            existing = self.get_ontology_node(name)
            if existing:
                return existing
            raise  # Re-raise if it's a genuine failure, not a race

    def update_ontology_lifecycle(
        self,
        name: str,
        new_state: str
    ) -> Optional[Dict[str, Any]]:
        """
        Update the lifecycle_state of an Ontology node.

        Args:
            name: Ontology name
            new_state: Target state ('active', 'pinned', or 'frozen')

        Returns:
            Dictionary with updated node properties, or None if not found

        Raises:
            ValueError: If new_state is not a valid lifecycle state
        """
        valid_states = {"active", "pinned", "frozen"}
        if new_state not in valid_states:
            raise ValueError(f"Invalid lifecycle state '{new_state}'. Must be one of: {valid_states}")

        query = """
        MATCH (o:Ontology {name: $name})
        SET o.lifecycle_state = $new_state
        RETURN o
        """

        try:
            result = self._execute_cypher(
                query,
                params={"name": name, "new_state": new_state},
                fetch_one=True
            )
            if result:
                agtype_result = result.get('o')
                parsed = self._parse_agtype(agtype_result)
                return parsed.get('properties', {}) if isinstance(parsed, dict) else None
            return None
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to update Ontology lifecycle for {name}: {e}")
            return None

    def is_ontology_frozen(self, name: str) -> bool:
        """
        Check if an ontology is in the 'frozen' lifecycle state.

        Returns False for nonexistent ontologies (they have no protection).

        Args:
            name: Ontology name

        Returns:
            True if the ontology exists and is frozen, False otherwise
        """
        node = self.get_ontology_node(name)
        if node is None:
            return False
        return node.get("lifecycle_state") == "frozen"

    def update_ontology_embedding(
        self,
        name: str,
        embedding: List[float]
    ) -> bool:
        """
        Update the embedding on an existing Ontology node.

        Args:
            name: Ontology name
            embedding: 1536-dim vector

        Returns:
            True if updated, False if not found
        """
        query = """
        MATCH (o:Ontology {name: $name})
        SET o.embedding = $embedding
        RETURN o.ontology_id as ontology_id
        """

        try:
            result = self._execute_cypher(
                query,
                params={"name": name, "embedding": embedding},
                fetch_one=True
            )
            return result is not None and result.get("ontology_id") is not None
        except Exception as e:
            logger.error(f"Failed to update Ontology embedding for {name}: {e}")
            return False

