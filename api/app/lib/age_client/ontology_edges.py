"""
Ontology edge and proposal execution mixin.

Manages inter-ontology edges (OVERLAPS, SPECIALIZES, GENERALIZES) and
the proposal execution primitives used by the annealing pipeline to
promote concepts and build ontology-to-ontology relationships.

Inter-ontology edges have two sources:
- "annealing_worker": Computed edges from cross-ontology affinity analysis
- "manual": Human-curated edges

Proposal primitives support ADR-200 Phase 4 (promotion/demotion execution):
- get_concept_node(): Fetch concept properties for promotion scoring
- create_anchored_by_edge(): Link ontology to its anchor concept
- get_first_order_source_ids(): Collect sources for promotion execution
"""

import json
import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class OntologyEdgesMixin:
    """Inter-ontology edges and proposal execution primitives."""

    VALID_ONTOLOGY_EDGE_TYPES = ("OVERLAPS", "SPECIALIZES", "GENERALIZES")
    VALID_ONTOLOGY_EDGE_SOURCES = ("annealing_worker", "manual")

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
