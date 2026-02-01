"""
Ontology scoring and annealing mixin.

Handles analytics queries (stats, degree ranking, cross-ontology affinity),
score caching, and structural mutations that reshape the ontology landscape:
source reassignment, dissolution, and batch operations.

These operations support the annealing pipeline (ADR-200 Phase 3a) which
periodically recomputes ontology health scores and proposes merges/splits.

Key operations:
- get_ontology_stats(): Raw counts for mass scoring (concepts, sources, edges)
- get_concept_degree_ranking(): Top concepts by connectivity within an ontology
- get_cross_ontology_affinity(): Shared concept overlap between ontologies
- reassign_sources(): Move sources between ontologies (with frozen-state guard)
- dissolve_ontology(): Non-destructive demotion (move sources, delete node)
"""

import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class OntologyScoringMixin:
    """Ontology scoring, analytics, annealing mutations, and batch operations."""

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

