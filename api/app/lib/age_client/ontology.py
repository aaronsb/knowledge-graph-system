"""
Ontology mixin for knowledge domain management.

Ontology nodes (ADR-200) are first-class graph entities that organize
Source nodes via :SCOPED_BY edges. This mixin covers the full lifecycle:
creation, lifecycle state management, scoring, annealing operations,
and inter-ontology edge management.

Sections:
- Legacy source-level rename (pre-ADR-200 compat)
- Ontology node CRUD (create, get, list, delete, rename, ensure_exists)
- Lifecycle management (active/pinned/frozen states, embeddings)
- Scoring & analytics (stats, degree ranking, affinity, epoch tracking)
- Annealing operations (score updates, source reassignment, dissolution)
- Batch operations (scoped_by edges, first-order source collection)
- Inter-ontology edges (OVERLAPS/SPECIALIZES/GENERALIZES, anchored_by)
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class OntologyMixin:
    """Ontology node CRUD, lifecycle, scoring, annealing, and inter-ontology edges."""

    VALID_ONTOLOGY_EDGE_TYPES = ("OVERLAPS", "SPECIALIZES", "GENERALIZES")
    VALID_ONTOLOGY_EDGE_SOURCES = ("annealing_worker", "manual")

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

    # =========================================================================
    # Ontology Scoring & Annealing Controls (ADR-200 Phase 3a)
    # =========================================================================

    def get_ontology_stats(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get raw counts for mass scoring of an ontology.

        Returns concept_count, source_count, file_count, evidence_count,
        internal_relationship_count, cross_ontology_relationship_count.

        Args:
            name: Ontology name

        Returns:
            Dictionary with counts, or None if ontology not found
        """
        # Verify ontology exists
        node = self.get_ontology_node(name)
        if not node:
            return None

        stats = {
            "ontology": name,
            "concept_count": 0,
            "source_count": 0,
            "file_count": 0,
            "evidence_count": 0,
            "internal_relationship_count": 0,
            "cross_ontology_relationship_count": 0,
        }

        try:
            # Source and file counts
            source_query = """
            MATCH (s:Source)-[:SCOPED_BY]->(o:Ontology {name: $name})
            RETURN count(s) as source_count,
                   count(DISTINCT s.file_path) as file_count
            """
            result = self._execute_cypher(
                source_query, params={"name": name}, fetch_one=True
            )
            if result:
                stats["source_count"] = int(str(result.get("source_count", 0)))
                stats["file_count"] = int(str(result.get("file_count", 0)))

            # Concept count: concepts connected to sources scoped to this ontology
            concept_query = """
            MATCH (c:Concept)-->(s:Source)-[:SCOPED_BY]->(o:Ontology {name: $name})
            RETURN count(DISTINCT c) as concept_count
            """
            result = self._execute_cypher(
                concept_query, params={"name": name}, fetch_one=True
            )
            if result:
                stats["concept_count"] = int(str(result.get("concept_count", 0)))

            # Evidence count: instances from sources in this ontology
            evidence_query = """
            MATCH (i:Instance)-->(s:Source)-[:SCOPED_BY]->(o:Ontology {name: $name})
            RETURN count(i) as evidence_count
            """
            result = self._execute_cypher(
                evidence_query, params={"name": name}, fetch_one=True
            )
            if result:
                stats["evidence_count"] = int(str(result.get("evidence_count", 0)))

            # Internal relationships: both endpoints in this ontology's sources
            internal_query = """
            MATCH (c1:Concept)-->(s1:Source)-[:SCOPED_BY]->(o1:Ontology {name: $name})
            MATCH (c1)-[r]->(c2:Concept)
            MATCH (c2)-->(s2:Source)-[:SCOPED_BY]->(o2:Ontology {name: $name})
            RETURN count(DISTINCT r) as internal_count
            """
            result = self._execute_cypher(
                internal_query, params={"name": name}, fetch_one=True
            )
            if result:
                stats["internal_relationship_count"] = int(
                    str(result.get("internal_count", 0))
                )

            # Cross-ontology relationships: one endpoint in this ontology, other in different
            cross_query = """
            MATCH (c1:Concept)-->(s1:Source)-[:SCOPED_BY]->(o1:Ontology {name: $name})
            MATCH (c1)-[r]->(c2:Concept)
            MATCH (c2)-->(s2:Source)-[:SCOPED_BY]->(o2:Ontology)
            WHERE o2.name <> $name
            RETURN count(DISTINCT r) as cross_count
            """
            result = self._execute_cypher(
                cross_query, params={"name": name}, fetch_one=True
            )
            if result:
                stats["cross_ontology_relationship_count"] = int(
                    str(result.get("cross_count", 0))
                )

            return stats
        except Exception as e:
            logger.error(f"Failed to get ontology stats for {name}: {e}")
            return stats  # Return partial stats rather than None

    def get_concept_degree_ranking(
        self, ontology_name: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get top concepts by degree centrality within an ontology.

        Args:
            ontology_name: Ontology name
            limit: Max concepts to return (default 20)

        Returns:
            List of {concept_id, label, degree, in_degree, out_degree}
        """
        query = """
        MATCH (c:Concept)-->(s:Source)-[:SCOPED_BY]->(o:Ontology {name: $name})
        WITH DISTINCT c
        OPTIONAL MATCH (c)-[r_out]->(:Concept)
        OPTIONAL MATCH (:Concept)-[r_in]->(c)
        WITH c,
             count(DISTINCT r_out) as out_degree,
             count(DISTINCT r_in) as in_degree
        RETURN c.concept_id as concept_id,
               c.label as label,
               out_degree + in_degree as degree,
               in_degree,
               out_degree
        ORDER BY out_degree + in_degree DESC
        LIMIT $limit
        """

        try:
            results = self._execute_cypher(
                query, params={"name": ontology_name, "limit": limit}
            )
            concepts = []
            for row in results:
                concepts.append({
                    "concept_id": str(row.get("concept_id", "")),
                    "label": str(row.get("label", "")),
                    "degree": int(str(row.get("degree", 0))),
                    "in_degree": int(str(row.get("in_degree", 0))),
                    "out_degree": int(str(row.get("out_degree", 0))),
                })
            return concepts
        except Exception as e:
            logger.error(
                f"Failed to get concept degree ranking for {ontology_name}: {e}"
            )
            return []

    def get_cross_ontology_affinity(
        self, ontology_name: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get cross-ontology concept overlap (shared concept affinity).

        Finds ontologies that share concepts with the target ontology,
        ranked by affinity_score = shared_count / total_concepts_in_target.

        Args:
            ontology_name: Ontology name
            limit: Max other ontologies to return

        Returns:
            List of {other_ontology, shared_concept_count, total_concepts, affinity_score}
        """
        query = """
        MATCH (c:Concept)-->(s1:Source)-[:SCOPED_BY]->(o1:Ontology {name: $name})
        WITH collect(DISTINCT c) as my_concepts, count(DISTINCT c) as my_total
        UNWIND my_concepts as c
        MATCH (c)-->(s2:Source)-[:SCOPED_BY]->(o2:Ontology)
        WHERE o2.name <> $name
        WITH o2.name as other_ontology,
             count(DISTINCT c) as shared_count,
             my_total
        RETURN other_ontology,
               shared_count as shared_concept_count,
               my_total as total_concepts,
               toFloat(shared_count) / toFloat(my_total) as affinity_score
        ORDER BY toFloat(shared_count) / toFloat(my_total) DESC
        LIMIT $limit
        """

        try:
            results = self._execute_cypher(
                query, params={"name": ontology_name, "limit": limit}
            )
            affinities = []
            for row in results:
                affinities.append({
                    "other_ontology": str(row.get("other_ontology", "")),
                    "shared_concept_count": int(
                        str(row.get("shared_concept_count", 0))
                    ),
                    "total_concepts": int(str(row.get("total_concepts", 0))),
                    "affinity_score": float(str(row.get("affinity_score", 0.0))),
                })
            return affinities
        except Exception as e:
            logger.error(
                f"Failed to get cross-ontology affinity for {ontology_name}: {e}"
            )
            return []

    def get_all_ontology_scores(self) -> List[Dict[str, Any]]:
        """
        Read cached score properties from all Ontology nodes.

        Returns:
            List of {ontology, mass_score, coherence_score, raw_exposure,
                     weighted_exposure, protection_score, last_evaluated_epoch}
        """
        query = """
        MATCH (o:Ontology)
        RETURN o.name as ontology,
               o.mass_score as mass_score,
               o.coherence_score as coherence_score,
               o.raw_exposure as raw_exposure,
               o.weighted_exposure as weighted_exposure,
               o.protection_score as protection_score,
               o.last_evaluated_epoch as last_evaluated_epoch
        ORDER BY o.protection_score DESC
        """

        try:
            results = self._execute_cypher(query)
            scores = []
            for row in results:
                scores.append({
                    "ontology": str(row.get("ontology", "")),
                    "mass_score": float(str(row.get("mass_score", 0) or 0)),
                    "coherence_score": float(
                        str(row.get("coherence_score", 0) or 0)
                    ),
                    "raw_exposure": float(str(row.get("raw_exposure", 0) or 0)),
                    "weighted_exposure": float(
                        str(row.get("weighted_exposure", 0) or 0)
                    ),
                    "protection_score": float(
                        str(row.get("protection_score", 0) or 0)
                    ),
                    "last_evaluated_epoch": int(
                        str(row.get("last_evaluated_epoch", 0) or 0)
                    ),
                })
            return scores
        except Exception as e:
            logger.error(f"Failed to get all ontology scores: {e}")
            return []

    def get_current_epoch(self) -> int:
        """
        Get the current global epoch from graph_metrics.

        Returns:
            Current document_ingestion_counter value, or 0 if unavailable
        """
        try:
            conn = self.pool.getconn()
            try:
                self._setup_age(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT counter FROM graph_metrics "
                        "WHERE metric_name = 'document_ingestion_counter'"
                    )
                    row = cur.fetchone()
                    if row:
                        return row[0] or 0
            finally:
                conn.commit()
                self.pool.putconn(conn)
        except Exception:
            pass
        return 0

    def get_ontology_concept_embeddings(
        self, ontology_name: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get concept embeddings for concepts in an ontology.
        Used for coherence scoring (pairwise similarity).

        Args:
            ontology_name: Ontology name
            limit: Max concepts (sampling for large ontologies)

        Returns:
            List of {concept_id, label, embedding}
        """
        query = """
        MATCH (c:Concept)-->(s:Source)-[:SCOPED_BY]->(o:Ontology {name: $name})
        WHERE c.embedding IS NOT NULL
        RETURN DISTINCT c.concept_id as concept_id,
               c.label as label,
               c.embedding as embedding
        LIMIT $limit
        """

        try:
            results = self._execute_cypher(
                query, params={"name": ontology_name, "limit": limit}
            )
            concepts = []
            for row in results:
                embedding = row.get("embedding")
                if embedding:
                    # Parse AGE embedding format
                    if isinstance(embedding, str):
                        try:
                            embedding = json.loads(embedding)
                        except (json.JSONDecodeError, TypeError):
                            continue
                    concepts.append({
                        "concept_id": str(row.get("concept_id", "")),
                        "label": str(row.get("label", "")),
                        "embedding": embedding,
                    })
            return concepts
        except Exception as e:
            logger.error(
                f"Failed to get concept embeddings for {ontology_name}: {e}"
            )
            return []

    # -------------------------------------------------------------------------
    # Ontology Annealing Write Controls (ADR-200 Phase 3a)
    # -------------------------------------------------------------------------

    def update_ontology_scores(
        self,
        name: str,
        mass: float,
        coherence: float,
        protection: float,
        raw_exposure: float = 0.0,
        weighted_exposure: float = 0.0,
        epoch: int = 0,
    ) -> bool:
        """
        Cache computed scores on the Ontology node.

        Args:
            name: Ontology name
            mass: Mass score 0.0-1.0
            coherence: Coherence score 0.0-1.0
            protection: Protection score (can be negative)
            raw_exposure: Raw exposure 0.0-1.0
            weighted_exposure: Weighted exposure 0.0-1.0
            epoch: Epoch when scores were computed

        Returns:
            True if updated, False if not found
        """
        query = """
        MATCH (o:Ontology {name: $name})
        SET o.mass_score = $mass,
            o.coherence_score = $coherence,
            o.protection_score = $protection,
            o.raw_exposure = $raw_exposure,
            o.weighted_exposure = $weighted_exposure,
            o.last_evaluated_epoch = $epoch
        RETURN o.ontology_id as ontology_id
        """

        try:
            result = self._execute_cypher(
                query,
                params={
                    "name": name,
                    "mass": mass,
                    "coherence": coherence,
                    "protection": protection,
                    "raw_exposure": raw_exposure,
                    "weighted_exposure": weighted_exposure,
                    "epoch": epoch,
                },
                fetch_one=True,
            )
            return result is not None and result.get("ontology_id") is not None
        except Exception as e:
            logger.error(f"Failed to update ontology scores for {name}: {e}")
            return False

    def reassign_sources(
        self,
        source_ids: List[str],
        from_ontology: str,
        to_ontology: str,
    ) -> Dict[str, Any]:
        """
        Move sources from one ontology to another.

        Updates s.document property and SCOPED_BY edges.
        Batched in chunks of 50 source IDs.

        Args:
            source_ids: Source IDs to move
            from_ontology: Source ontology name
            to_ontology: Destination ontology name

        Returns:
            {sources_reassigned: int, success: bool, error: str|None}
        """
        # Verify both ontologies exist
        from_node = self.get_ontology_node(from_ontology)
        if not from_node:
            return {
                "sources_reassigned": 0,
                "success": False,
                "error": f"Source ontology '{from_ontology}' not found",
            }

        to_node = self.get_ontology_node(to_ontology)
        if not to_node:
            return {
                "sources_reassigned": 0,
                "success": False,
                "error": f"Target ontology '{to_ontology}' not found",
            }

        # Check frozen state — cannot move FROM frozen
        if from_node.get("lifecycle_state") == "frozen":
            return {
                "sources_reassigned": 0,
                "success": False,
                "error": f"Source ontology '{from_ontology}' is frozen",
            }

        total_reassigned = 0
        batch_size = 50

        try:
            for i in range(0, len(source_ids), batch_size):
                batch = source_ids[i : i + batch_size]

                # Update s.document on Source nodes
                update_query = """
                MATCH (s:Source)
                WHERE s.source_id IN $source_ids AND s.document = $from_name
                SET s.document = $to_name
                RETURN count(s) as updated
                """
                result = self._execute_cypher(
                    update_query,
                    params={
                        "source_ids": batch,
                        "from_name": from_ontology,
                        "to_name": to_ontology,
                    },
                    fetch_one=True,
                )
                updated = int(str(result.get("updated", 0))) if result else 0

                # Delete old SCOPED_BY edges
                delete_edge_query = """
                MATCH (s:Source)-[r:SCOPED_BY]->(o:Ontology {name: $from_name})
                WHERE s.source_id IN $source_ids
                DELETE r
                RETURN count(*) as deleted
                """
                self._execute_cypher(
                    delete_edge_query,
                    params={"source_ids": batch, "from_name": from_ontology},
                    fetch_one=True,
                )

                # Create new SCOPED_BY edges
                create_edge_query = """
                MATCH (s:Source), (o:Ontology {name: $to_name})
                WHERE s.source_id IN $source_ids AND s.document = $to_name
                MERGE (s)-[:SCOPED_BY]->(o)
                RETURN count(*) as created
                """
                self._execute_cypher(
                    create_edge_query,
                    params={"source_ids": batch, "to_name": to_ontology},
                    fetch_one=True,
                )

                total_reassigned += updated

            return {
                "sources_reassigned": total_reassigned,
                "success": True,
                "error": None,
            }
        except Exception as e:
            logger.error(
                f"Failed to reassign sources from {from_ontology} to {to_ontology}: {e}"
            )
            return {
                "sources_reassigned": total_reassigned,
                "success": False,
                "error": str(e),
            }

    def dissolve_ontology(
        self, name: str, target_ontology: str
    ) -> Dict[str, Any]:
        """
        Non-destructive ontology demotion: move all sources to target, then remove node.

        This is the key primitive for ontology demotion in the annealing cycle.
        Unlike delete_ontology (which cascade-deletes sources), dissolve preserves
        all data by moving it first.

        Args:
            name: Ontology to dissolve
            target_ontology: Default ontology to receive sources

        Returns:
            {dissolved_ontology, sources_reassigned, ontology_node_deleted,
             reassignment_targets, success, error}
        """
        node = self.get_ontology_node(name)
        if not node:
            return {
                "dissolved_ontology": name,
                "sources_reassigned": 0,
                "ontology_node_deleted": False,
                "reassignment_targets": [],
                "success": False,
                "error": f"Ontology '{name}' not found",
            }

        lifecycle = node.get("lifecycle_state", "active")
        if lifecycle in ("pinned", "frozen"):
            return {
                "dissolved_ontology": name,
                "sources_reassigned": 0,
                "ontology_node_deleted": False,
                "reassignment_targets": [],
                "success": False,
                "error": f"Ontology '{name}' is {lifecycle} — cannot dissolve",
            }

        # Get all source IDs in this ontology
        source_query = """
        MATCH (s:Source)-[:SCOPED_BY]->(o:Ontology {name: $name})
        RETURN s.source_id as source_id
        """
        try:
            results = self._execute_cypher(
                source_query, params={"name": name}
            )
            all_source_ids = [
                str(row.get("source_id", ""))
                for row in results
                if row.get("source_id")
            ]
        except Exception as e:
            return {
                "dissolved_ontology": name,
                "sources_reassigned": 0,
                "ontology_node_deleted": False,
                "reassignment_targets": [],
                "success": False,
                "error": f"Failed to list sources: {e}",
            }

        # Reassign all sources to target
        total_reassigned = 0
        targets = set()

        if all_source_ids:
            result = self.reassign_sources(all_source_ids, name, target_ontology)
            total_reassigned = result.get("sources_reassigned", 0)
            if not result.get("success"):
                return {
                    "dissolved_ontology": name,
                    "sources_reassigned": total_reassigned,
                    "ontology_node_deleted": False,
                    "reassignment_targets": [],
                    "success": False,
                    "error": result.get("error"),
                }
            targets.add(target_ontology)

        # Remove the Ontology node (only the node + its edges, not Sources)
        node_deleted = self.delete_ontology_node(name)

        return {
            "dissolved_ontology": name,
            "sources_reassigned": total_reassigned,
            "ontology_node_deleted": node_deleted,
            "reassignment_targets": sorted(targets),
            "success": True,
            "error": None,
        }

    def batch_create_scoped_by_edges(
        self, source_ids: List[str], ontology_name: str
    ) -> int:
        """
        Batch create SCOPED_BY edges from multiple sources to an ontology.

        Args:
            source_ids: List of source IDs
            ontology_name: Ontology name

        Returns:
            Number of edges created/verified
        """
        if not source_ids:
            return 0

        query = """
        MATCH (o:Ontology {name: $ontology_name})
        WITH o
        MATCH (s:Source)
        WHERE s.source_id IN $source_ids
        MERGE (s)-[:SCOPED_BY]->(o)
        RETURN count(*) as created
        """

        try:
            result = self._execute_cypher(
                query,
                params={
                    "source_ids": source_ids,
                    "ontology_name": ontology_name,
                },
                fetch_one=True,
            )
            return int(str(result.get("created", 0))) if result else 0
        except Exception as e:
            logger.error(
                f"Failed to batch create SCOPED_BY edges for {ontology_name}: {e}"
            )
            return 0

    # =========================================================================
    # Proposal Execution Primitives (ADR-200 Phase 4)
    # =========================================================================

    def get_concept_node(self, concept_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a Concept node's properties by ID.

        Args:
            concept_id: Concept ID

        Returns:
            Dict with concept_id, label, description, embedding or None
        """
        query = """
        MATCH (c:Concept {concept_id: $cid})
        RETURN c.concept_id as concept_id, c.label as label,
               c.description as description, c.embedding as embedding
        """
        try:
            result = self._execute_cypher(
                query,
                params={"cid": concept_id},
                fetch_one=True,
            )
            return result if result else None
        except Exception as e:
            logger.error(f"Failed to get concept node {concept_id}: {e}")
            return None

    def create_anchored_by_edge(
        self, ontology_name: str, concept_id: str
    ) -> bool:
        """
        Create (:Ontology)-[:ANCHORED_BY]->(:Concept) edge.

        Links a promoted ontology to its founding concept.
        The concept survives independently — it existed before and continues after.

        Args:
            ontology_name: The ontology's name
            concept_id: The anchor concept ID

        Returns:
            True if edge created, False on failure
        """
        query = """
        MATCH (o:Ontology {name: $name}), (c:Concept {concept_id: $cid})
        MERGE (o)-[:ANCHORED_BY]->(c)
        RETURN o.name as name
        """
        try:
            result = self._execute_cypher(
                query,
                params={"name": ontology_name, "cid": concept_id},
                fetch_one=True,
            )
            return result is not None
        except Exception as e:
            logger.error(
                f"Failed to create ANCHORED_BY edge "
                f"{ontology_name} -> {concept_id}: {e}"
            )
            return False

    def get_first_order_source_ids(
        self, concept_id: str, ontology_name: str
    ) -> List[str]:
        """
        Get source IDs from a concept and its first-order neighbors within an ontology.

        Used during promotion execution to find which sources to reassign.
        Follows any edge type between the anchor concept and its neighbor concepts,
        then finds sources of those neighbors scoped to the given ontology.

        Args:
            concept_id: The anchor concept ID
            ontology_name: Only return sources scoped to this ontology

        Returns:
            List of source_id strings
        """
        query = """
        MATCH (anchor:Concept {concept_id: $cid})-[]-(neighbor:Concept)
        MATCH (neighbor)-->(s:Source)-[:SCOPED_BY]->(o:Ontology {name: $ontology})
        WITH collect(DISTINCT s.source_id) as neighbor_sources
        OPTIONAL MATCH (anchor2:Concept {concept_id: $cid})-->(s2:Source)-[:SCOPED_BY]->(o2:Ontology {name: $ontology})
        WITH neighbor_sources + collect(DISTINCT s2.source_id) as all_sources
        UNWIND all_sources as sid
        RETURN DISTINCT sid as source_id
        """
        try:
            rows = self._execute_cypher(
                query,
                params={"cid": concept_id, "ontology": ontology_name},
            )
            return [row["source_id"] for row in (rows or []) if row.get("source_id")]
        except Exception as e:
            logger.error(
                f"Failed to get first-order source IDs for "
                f"{concept_id} in {ontology_name}: {e}"
            )
            return []

    # =========================================================================
    # Ontology-to-Ontology Edge Methods (ADR-200 Phase 5)
    # =========================================================================


    def upsert_ontology_edge(
        self,
        from_name: str,
        to_name: str,
        edge_type: str,
        score: float,
        shared_concept_count: int,
        epoch: int,
        source: str = "annealing_worker",
    ) -> bool:
        """
        Create or update an edge between two Ontology nodes.

        Uses MERGE to upsert — creates if absent, updates properties if exists.

        Args:
            from_name: Source ontology name
            to_name: Target ontology name
            edge_type: OVERLAPS, SPECIALIZES, or GENERALIZES
            score: Affinity strength (0.0-1.0)
            shared_concept_count: Number of shared concepts
            epoch: Global epoch when computed
            source: 'annealing_worker' or 'manual'

        Returns:
            True if edge was upserted successfully
        """
        if edge_type not in self.VALID_ONTOLOGY_EDGE_TYPES:
            raise ValueError(
                f"Invalid ontology edge type: {edge_type!r}. "
                f"Must be one of {self.VALID_ONTOLOGY_EDGE_TYPES}"
            )
        if source not in self.VALID_ONTOLOGY_EDGE_SOURCES:
            raise ValueError(
                f"Invalid ontology edge source: {source!r}. "
                f"Must be one of {self.VALID_ONTOLOGY_EDGE_SOURCES}"
            )

        query = f"""
        MATCH (a:Ontology {{name: $from_name}})
        MATCH (b:Ontology {{name: $to_name}})
        MERGE (a)-[r:{edge_type}]->(b)
        SET r.score = $score,
            r.shared_concept_count = $shared_count,
            r.computed_at_epoch = $epoch,
            r.source = $source
        RETURN type(r) as edge_type
        """

        try:
            result = self._execute_cypher(
                query,
                params={
                    "from_name": from_name,
                    "to_name": to_name,
                    "score": score,
                    "shared_count": shared_concept_count,
                    "epoch": epoch,
                    "source": source,
                },
                fetch_one=True,
            )
            return result is not None
        except Exception as e:
            logger.error(
                f"Failed to upsert {edge_type} edge "
                f"{from_name} -> {to_name}: {e}"
            )
            return False

    def get_ontology_edges(
        self, ontology_name: str
    ) -> List[Dict[str, Any]]:
        """
        Get all ontology-to-ontology edges for an ontology (both directions).

        Args:
            ontology_name: Ontology name

        Returns:
            List of edge dicts with: from_ontology, to_ontology, edge_type,
            score, shared_concept_count, computed_at_epoch, source, direction
        """
        query = """
        MATCH (o:Ontology {name: $name})
        OPTIONAL MATCH (o)-[out]->(other:Ontology)
        WHERE type(out) IN ['OVERLAPS', 'SPECIALIZES', 'GENERALIZES']
        WITH o, collect({
            from_ontology: $name,
            to_ontology: other.name,
            edge_type: type(out),
            score: out.score,
            shared_concept_count: out.shared_concept_count,
            computed_at_epoch: out.computed_at_epoch,
            source: out.source,
            direction: 'outgoing'
        }) as outgoing
        OPTIONAL MATCH (other2:Ontology)-[inc]->(o)
        WHERE type(inc) IN ['OVERLAPS', 'SPECIALIZES', 'GENERALIZES']
        WITH outgoing, collect({
            from_ontology: other2.name,
            to_ontology: $name,
            edge_type: type(inc),
            score: inc.score,
            shared_concept_count: inc.shared_concept_count,
            computed_at_epoch: inc.computed_at_epoch,
            source: inc.source,
            direction: 'incoming'
        }) as incoming
        RETURN outgoing + incoming as edges
        """

        try:
            result = self._execute_cypher(
                query, params={"name": ontology_name}, fetch_one=True
            )
            if not result or not result.get("edges"):
                return []
            # Filter out entries with null edge_type (from empty OPTIONAL MATCH)
            return [
                e for e in result["edges"]
                if e.get("edge_type") is not None
            ]
        except Exception as e:
            logger.error(
                f"Failed to get ontology edges for {ontology_name}: {e}"
            )
            return []

    def delete_derived_ontology_edges(
        self, ontology_name: str, edge_type: str = None
    ) -> int:
        """
        Delete derived (annealing_worker) ontology edges. Manual edges are preserved.

        Args:
            ontology_name: Ontology name
            edge_type: Optional specific type to delete (OVERLAPS, SPECIALIZES,
                       GENERALIZES). If None, deletes all derived types.

        Returns:
            Number of edges deleted
        """
        if edge_type and edge_type not in self.VALID_ONTOLOGY_EDGE_TYPES:
            raise ValueError(f"Invalid ontology edge type: {edge_type!r}")

        # Delete derived edges in both directions for this ontology
        types_to_delete = [edge_type] if edge_type else list(self.VALID_ONTOLOGY_EDGE_TYPES)
        total_deleted = 0

        for etype in types_to_delete:
            # Outgoing
            out_query = f"""
            MATCH (o:Ontology {{name: $name}})-[r:{etype}]->(other:Ontology)
            WHERE r.source = 'annealing_worker'
            DELETE r
            RETURN count(r) as deleted
            """
            # Incoming
            in_query = f"""
            MATCH (other:Ontology)-[r:{etype}]->(o:Ontology {{name: $name}})
            WHERE r.source = 'annealing_worker'
            DELETE r
            RETURN count(r) as deleted
            """

            try:
                for query in [out_query, in_query]:
                    result = self._execute_cypher(
                        query, params={"name": ontology_name}, fetch_one=True
                    )
                    if result:
                        total_deleted += int(str(result.get("deleted", 0)))
            except Exception as e:
                logger.error(
                    f"Failed to delete derived {etype} edges "
                    f"for {ontology_name}: {e}"
                )

        return total_deleted

    def delete_all_derived_ontology_edges(self) -> int:
        """
        Delete ALL derived ontology-to-ontology edges across the graph.

        Called at the start of a annealing cycle to refresh edges from scratch.

        Returns:
            Number of edges deleted
        """
        total_deleted = 0
        for etype in self.VALID_ONTOLOGY_EDGE_TYPES:
            query = f"""
            MATCH (:Ontology)-[r:{etype}]->(:Ontology)
            WHERE r.source = 'annealing_worker'
            DELETE r
            RETURN count(r) as deleted
            """
            try:
                result = self._execute_cypher(query, fetch_one=True)
                if result:
                    total_deleted += int(str(result.get("deleted", 0)))
            except Exception as e:
                logger.error(f"Failed to delete all derived {etype} edges: {e}")

        return total_deleted

    def delete_ontology_edge(
        self, from_name: str, to_name: str, edge_type: str
    ) -> int:
        """
        Delete a specific ontology-to-ontology edge (any source).

        Args:
            from_name: Source ontology name
            to_name: Target ontology name
            edge_type: OVERLAPS, SPECIALIZES, or GENERALIZES

        Returns:
            Number of edges deleted (0 or 1)
        """
        if edge_type not in self.VALID_ONTOLOGY_EDGE_TYPES:
            raise ValueError(
                f"Invalid ontology edge type: {edge_type!r}. "
                f"Must be one of {self.VALID_ONTOLOGY_EDGE_TYPES}"
            )

        query = f"""
        MATCH (a:Ontology {{name: $from_name}})-[r:{edge_type}]->(b:Ontology {{name: $to_name}})
        DELETE r
        RETURN count(r) as deleted
        """
        try:
            result = self._execute_cypher(
                query,
                params={"from_name": from_name, "to_name": to_name},
                fetch_one=True,
            )
            return int(str(result.get("deleted", 0))) if result else 0
        except Exception as e:
            logger.error(
                f"Failed to delete {edge_type} edge "
                f"{from_name} -> {to_name}: {e}"
            )
            return 0
