"""
Proposal Executor — executes approved annealing proposals (ADR-200 Phase 4).

Wires together existing primitives:
- create_ontology_node()      → promotion: create new ontology
- create_anchored_by_edge()   → promotion: link ontology to founding concept
- get_first_order_source_ids()→ promotion: find sources to reassign
- reassign_sources()          → promotion: move sources to new ontology
- dissolve_ontology()         → demotion: reassign sources + remove node
- get_ontology_edges()        → demotion: find absorption target (Phase 5)
- get_cross_ontology_affinity()→ demotion: fallback absorption target

All execution primitives were built in Phases 3a/5. This module is plumbing.
"""

import json
import logging
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ProposalExecutor:
    """Executes approved annealing proposals against the graph."""

    def __init__(self, age_client):
        self.client = age_client

    def execute_promotion(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an approved promotion proposal.

        Steps:
            1. Validate: anchor concept exists, ontology name not taken
            2. Get anchor concept's embedding for the new ontology
            3. create_ontology_node() with name from suggested_name or label
            4. create_anchored_by_edge() linking ontology to anchor concept
            5. get_first_order_source_ids() to find sources to reassign
            6. reassign_sources() from parent ontology to new one

        Args:
            proposal: Dict with proposal fields from annealing_proposals table

        Returns:
            {success, ontology_created, sources_reassigned, ...}
        """
        anchor_id = proposal.get("anchor_concept_id")
        parent_ontology = proposal.get("ontology_name")

        if not anchor_id:
            return {
                "success": False,
                "error": "Promotion proposal missing anchor_concept_id",
            }

        # 1. Validate anchor concept still exists
        concept = self.client.get_concept_node(anchor_id)
        if not concept:
            return {
                "success": False,
                "error": f"Anchor concept '{anchor_id}' no longer exists",
            }

        # Determine name for new ontology
        ontology_name = (
            proposal.get("suggested_name")
            or concept.get("label", "unnamed")
        )

        # Check name not already taken
        existing = self.client.get_ontology_node(ontology_name)
        if existing:
            return {
                "success": False,
                "error": f"Ontology '{ontology_name}' already exists",
            }

        # 2. Get embedding from anchor concept
        embedding = concept.get("embedding")
        description = (
            proposal.get("suggested_description")
            or concept.get("description", "")
            or f"Domain anchored by concept '{concept.get('label', '')}'."
        )

        # 3. Create ontology node
        ontology_id = f"ont_{uuid.uuid4().hex[:12]}"
        create_result = self.client.create_ontology_node(
            ontology_id=ontology_id,
            name=ontology_name,
            description=description,
            embedding=embedding,
            lifecycle_state="active",
            created_by="annealing_worker",
        )

        if not create_result:
            return {
                "success": False,
                "error": f"Failed to create ontology node '{ontology_name}'",
            }

        logger.info(
            f"Created ontology '{ontology_name}' ({ontology_id}) "
            f"from concept '{anchor_id}'"
        )

        # 4. Create ANCHORED_BY edge
        anchored = self.client.create_anchored_by_edge(ontology_name, anchor_id)
        if not anchored:
            logger.warning(
                f"Failed to create ANCHORED_BY edge for '{ontology_name}' "
                f"-> '{anchor_id}' (ontology created but not linked)"
            )

        # 5. Find first-order sources to reassign
        source_ids = self.client.get_first_order_source_ids(
            anchor_id, parent_ontology
        )

        sources_reassigned = 0
        if source_ids:
            # 6. Reassign sources (already batched in 50s by reassign_sources)
            result = self.client.reassign_sources(
                source_ids, parent_ontology, ontology_name
            )
            sources_reassigned = result.get("sources_reassigned", 0)

            if not result.get("success"):
                logger.warning(
                    f"Partial promotion: ontology '{ontology_name}' created "
                    f"but source reassignment failed: {result.get('error')}"
                )
                return {
                    "success": False,
                    "error": (
                        f"Ontology created but source reassignment failed: "
                        f"{result.get('error')}"
                    ),
                    "ontology_created": ontology_name,
                    "ontology_id": ontology_id,
                    "sources_reassigned": sources_reassigned,
                    "sources_found": len(source_ids),
                    "anchored": anchored,
                    "partial": True,
                }

        logger.info(
            f"Promotion complete: '{ontology_name}' with "
            f"{sources_reassigned} sources from '{parent_ontology}'"
        )

        return {
            "success": True,
            "error": None,
            "ontology_created": ontology_name,
            "ontology_id": ontology_id,
            "sources_found": len(source_ids),
            "sources_reassigned": sources_reassigned,
            "parent_ontology": parent_ontology,
            "anchor_concept_id": anchor_id,
            "anchored": anchored,
        }

    def execute_demotion(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an approved demotion proposal.

        Steps:
            1. Validate: ontology still exists, not pinned/frozen
            2. Determine absorption target (cascading fallback)
            3. dissolve_ontology() → reassign sources + remove node

        Args:
            proposal: Dict with proposal fields from annealing_proposals table

        Returns:
            {success, absorbed_into, sources_reassigned, ...}
        """
        ontology_name = proposal.get("ontology_name")
        if not ontology_name:
            return {
                "success": False,
                "error": "Demotion proposal missing ontology_name",
            }

        # 1. Validate ontology still exists
        node = self.client.get_ontology_node(ontology_name)
        if not node:
            return {
                "success": False,
                "error": f"Ontology '{ontology_name}' no longer exists",
            }

        lifecycle = node.get("lifecycle_state", "active")
        if lifecycle in ("pinned", "frozen"):
            return {
                "success": False,
                "error": f"Ontology '{ontology_name}' is {lifecycle} — cannot demote",
            }

        # 2. Determine absorption target
        proposed_target = proposal.get("target_ontology")
        target = self._determine_absorption_target(ontology_name, proposed_target)

        if not target:
            return {
                "success": False,
                "error": (
                    f"No valid absorption target found for '{ontology_name}' "
                    f"(no overlapping ontologies or primordial pool)"
                ),
            }

        # Verify target exists (create primordial pool if needed)
        target_node = self.client.get_ontology_node(target)
        if not target_node:
            if target == self._get_primordial_pool_name():
                # Auto-create primordial pool
                pool_id = f"ont_{uuid.uuid4().hex[:12]}"
                self.client.create_ontology_node(
                    ontology_id=pool_id,
                    name=target,
                    description="Default pool for unroutable sources",
                    lifecycle_state="active",
                    created_by="annealing_worker",
                )
                logger.info(f"Auto-created primordial pool '{target}'")
            else:
                return {
                    "success": False,
                    "error": f"Absorption target '{target}' does not exist",
                }

        # 3. Dissolve — reassign sources + remove ontology node
        result = self.client.dissolve_ontology(ontology_name, target)

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error"),
                "absorbed_into": target,
                "sources_reassigned": result.get("sources_reassigned", 0),
            }

        logger.info(
            f"Demotion complete: '{ontology_name}' dissolved into '{target}' "
            f"({result.get('sources_reassigned', 0)} sources moved)"
        )

        return {
            "success": True,
            "error": None,
            "dissolved_ontology": ontology_name,
            "absorbed_into": target,
            "sources_reassigned": result.get("sources_reassigned", 0),
            "ontology_node_deleted": result.get("ontology_node_deleted", False),
        }

    def _determine_absorption_target(
        self, ontology_name: str, proposed_target: Optional[str]
    ) -> Optional[str]:
        """
        Find the best absorption target for a demotion, with cascading fallback.

        Priority:
            1. Proposal's target_ontology (LLM-suggested)
            2. Highest OVERLAPS edge score (Phase 5 materialized)
            3. Highest affinity from traversal query
            4. Primordial pool name from annealing_options
        """
        # 1. Use proposal's suggestion if the target still exists
        if proposed_target:
            target_node = self.client.get_ontology_node(proposed_target)
            if target_node:
                lifecycle = target_node.get("lifecycle_state", "active")
                if lifecycle != "frozen":
                    return proposed_target
                logger.info(
                    f"Proposed target '{proposed_target}' is frozen, "
                    f"falling back"
                )
            else:
                logger.info(
                    f"Proposed target '{proposed_target}' no longer exists, "
                    f"falling back"
                )

        # 2. Check Phase 5 materialized edges (OVERLAPS)
        try:
            edges = self.client.get_ontology_edges(ontology_name)
            overlaps = [
                e for e in edges
                if e.get("edge_type") == "OVERLAPS"
                and e.get("score", 0) > 0
            ]
            if overlaps:
                best = max(overlaps, key=lambda e: e.get("score", 0))
                target = (
                    best.get("to_ontology")
                    if best.get("from_ontology") == ontology_name
                    else best.get("from_ontology")
                )
                if target:
                    return target
        except Exception as e:
            logger.warning(f"Failed to query ontology edges: {e}")

        # 3. Fall back to affinity query
        try:
            affinities = self.client.get_cross_ontology_affinity(
                ontology_name, limit=1
            )
            if affinities:
                return affinities[0].get("other_ontology")
        except Exception as e:
            logger.warning(f"Failed to query cross-ontology affinity: {e}")

        # 4. Last resort: primordial pool
        return self._get_primordial_pool_name()

    def _get_primordial_pool_name(self) -> str:
        """Read primordial pool name from annealing_options, default 'primordial'."""
        try:
            conn = self.client.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT value FROM kg_api.annealing_options "
                        "WHERE key = 'primordial_pool_name'"
                    )
                    row = cur.fetchone()
                    return row[0] if row else "primordial"
            finally:
                self.client.pool.putconn(conn)
        except Exception:
            return "primordial"
