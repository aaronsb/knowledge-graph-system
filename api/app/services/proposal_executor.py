"""
Proposal Executor — executes approved annealing proposals (ADR-200 Phase 4 / ADR-206).

Wires together existing primitives. After ADR-206 the executor dispatches on
the closed 6-verb vocabulary (CLEAVE, DISSOLVE, MERGE, RENAME, NO_ACTION,
ESCALATE). The two structural verbs read their parameters from the proposal's
`params` JSONB; legacy rows that lack params fall back to the typed columns
(anchor_concept_id, target_ontology, etc.) for backward compatibility.

Primitives this module composes:
- create_ontology_node()        → CLEAVE: create new ontology
- create_anchored_by_edge()     → CLEAVE: link ontology to founding concept
- get_first_order_source_ids()  → CLEAVE: find sources to reassign
- reassign_sources()            → CLEAVE: move sources to new/existing ontology
- dissolve_ontology()           → DISSOLVE: per-source routing + remove node
- get_cross_ontology_affinity() → DISSOLVE: affinity-based routing fallback
- rename_ontology_node()        → RENAME: update Ontology node name
- rename_ontology()             → RENAME: update s.document on Source nodes

ADR-206 invariant: the executor performs no interpretation. All decisions
(cluster strategy, target ontology, routing) are encoded in `params` by the
annealing decision service — the executor only validates and executes.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Mirrors AnnealingManager._NON_TERMINAL_JOB_STATUSES and _INGESTION_JOB_TYPES.
# Kept in sync rather than imported to avoid a circular dep (the manager
# already imports from this module's execution surface via the worker).
_NON_TERMINAL_JOB_STATUSES = (
    "pending",
    "awaiting_approval",
    "approved",
    "queued",
    "running",
    "processing",
)
_INGESTION_JOB_TYPES = ("ingestion", "ingest_image")


class ProposalExecutor:
    """Executes approved annealing proposals against the graph.

    Public surface (ADR-206 6-verb vocabulary):
        execute_cleave    — split a parent ontology around an anchor concept
        execute_dissolve  — dissolve an ontology, per-source affinity routing
        execute_merge     — merge ≥2 donor ontologies into a target
        execute_rename    — rename an ontology
        execute_no_action — record a no-op decision (no graph mutation)
        execute_escalate  — record an escalation (no graph mutation)

    Legacy shims retained for callers still using the v1 names:
        execute_promotion → execute_cleave
        execute_demotion  → execute_dissolve
    """

    def __init__(self, age_client):
        self.client = age_client

    # ------------------------------------------------------------------
    # CLEAVE
    # ------------------------------------------------------------------
    def execute_cleave(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an approved CLEAVE proposal (ADR-206).

        CLEAVE splits a parent ontology around an anchor concept. The target
        ontology may be newly created (target.kind='new') or pre-existing
        (target.kind='existing'); the latter reaches a schema slot that was
        previously unreachable in the v1 promotion flow.

        Cluster materialization is driven by params.cluster_selection:
            - first_order      → get_first_order_source_ids (existing primitive)
            - embedding_radius → not yet implemented (returns clean failure)
            - named_concepts   → not yet implemented (returns clean failure)

        Parameters (from proposal['params']):
            anchor_concept_id  : str
            source_ontology    : str (parent — legacy promotions: primordial)
            cluster_selection  : {first_order, embedding_radius, named_concepts}
            cluster_params     : dict (strategy-specific)
            target             : {kind: 'new'|'existing', ...}
                'new'      : new_name, new_description
                'existing' : existing_ontology

        Legacy fallback (v1 promotion rows without params):
            Reads anchor_concept_id, ontology_name (as source), suggested_name,
            suggested_description from typed columns.
        """
        params = proposal.get("params") or {}

        # ---- Resolve anchor + source ontology (v2 params win, v1 fallback) ----
        anchor_id = (
            params.get("anchor_concept_id")
            or proposal.get("anchor_concept_id")
        )
        source_ontology = (
            params.get("source_ontology")
            or proposal.get("ontology_name")
        )

        if not anchor_id:
            return {
                "success": False,
                "error": "CLEAVE proposal missing anchor_concept_id",
            }

        # ---- Resolve target shape (v2 params, with v1 fallback to suggested_*) ----
        target = params.get("target")
        if not target:
            # v1 promotion: always implicit 'new' target with suggested_name/desc.
            target = {
                "kind": "new",
                "new_name": proposal.get("suggested_name"),
                "new_description": proposal.get("suggested_description"),
            }

        target_kind = target.get("kind")
        if target_kind not in ("new", "existing"):
            return {
                "success": False,
                "error": (
                    f"CLEAVE target.kind must be 'new' or 'existing', "
                    f"got {target_kind!r}"
                ),
            }

        # ---- Phase 1 validation: short-circuit before any graph mutation ----
        concept = self.client.get_concept_node(anchor_id)
        if not concept:
            return {
                "success": False,
                "error": f"Anchor concept '{anchor_id}' no longer exists",
            }

        if target_kind == "new":
            new_name = (
                target.get("new_name")
                or concept.get("label", "unnamed")
            )
            if self.client.get_ontology_node(new_name):
                return {
                    "success": False,
                    "error": f"Ontology '{new_name}' already exists",
                }
            target_name = new_name
        else:  # existing
            existing_name = target.get("existing_ontology")
            if not existing_name:
                return {
                    "success": False,
                    "error": "CLEAVE target.kind='existing' requires existing_ontology",
                }
            if existing_name == source_ontology:
                return {
                    "success": False,
                    "error": (
                        f"CLEAVE target '{existing_name}' equals source "
                        f"ontology — choose a different destination"
                    ),
                }
            existing_node = self.client.get_ontology_node(existing_name)
            if not existing_node:
                return {
                    "success": False,
                    "error": f"CLEAVE target '{existing_name}' does not exist",
                }
            target_name = existing_name

        # ---- Cluster materialization ----
        cluster_selection = params.get("cluster_selection", "first_order")
        cluster_params = params.get("cluster_params") or {}

        if cluster_selection == "first_order":
            source_ids = self.client.get_first_order_source_ids(
                anchor_id, source_ontology
            )
        elif cluster_selection == "embedding_radius":
            return {
                "success": False,
                "error": (
                    "embedding_radius cluster strategy not yet implemented"
                ),
            }
        elif cluster_selection == "named_concepts":
            return {
                "success": False,
                "error": "named_concepts cluster strategy not yet implemented",
            }
        else:
            return {
                "success": False,
                "error": (
                    f"Unknown cluster_selection '{cluster_selection}' "
                    f"(expected first_order|embedding_radius|named_concepts)"
                ),
            }

        # ---- Execute ----
        ontology_id: Optional[str] = None
        anchored = False

        if target_kind == "new":
            embedding = concept.get("embedding")
            description = (
                target.get("new_description")
                or concept.get("description", "")
                or f"Domain anchored by concept '{concept.get('label', '')}'."
            )
            ontology_id = f"ont_{uuid.uuid4().hex[:12]}"
            create_result = self.client.create_ontology_node(
                ontology_id=ontology_id,
                name=target_name,
                description=description,
                embedding=embedding,
                lifecycle_state="active",
                created_by="annealing_worker",
            )
            if not create_result:
                return {
                    "success": False,
                    "error": f"Failed to create ontology node '{target_name}'",
                }
            logger.info(
                f"CLEAVE created ontology '{target_name}' ({ontology_id}) "
                f"from concept '{anchor_id}'"
            )

            anchored = self.client.create_anchored_by_edge(target_name, anchor_id)
            if not anchored:
                logger.warning(
                    f"Failed to create ANCHORED_BY edge for '{target_name}' "
                    f"-> '{anchor_id}' (ontology created but not linked)"
                )

        sources_reassigned = 0
        if source_ids:
            result = self.client.reassign_sources(
                source_ids, source_ontology, target_name
            )
            sources_reassigned = result.get("sources_reassigned", 0)
            if not result.get("success"):
                logger.warning(
                    f"Partial CLEAVE: target '{target_name}' "
                    f"({'created' if target_kind == 'new' else 'reused'}) "
                    f"but source reassignment failed: {result.get('error')}"
                )
                return {
                    "success": False,
                    "error": (
                        f"Target {target_kind} but source reassignment failed: "
                        f"{result.get('error')}"
                    ),
                    "ontology_created": target_name if target_kind == "new" else None,
                    "ontology_id": ontology_id,
                    "target_ontology": target_name,
                    "target_kind": target_kind,
                    "sources_reassigned": sources_reassigned,
                    "sources_found": len(source_ids),
                    "anchored": anchored,
                    "partial": True,
                }

        logger.info(
            f"CLEAVE complete: target='{target_name}' ({target_kind}) "
            f"with {sources_reassigned} sources from '{source_ontology}'"
        )

        return {
            "success": True,
            "error": None,
            "action": "cleave",
            "ontology_created": target_name if target_kind == "new" else None,
            "ontology_id": ontology_id,
            "target_ontology": target_name,
            "target_kind": target_kind,
            "sources_found": len(source_ids),
            "sources_reassigned": sources_reassigned,
            "parent_ontology": source_ontology,
            "anchor_concept_id": anchor_id,
            "anchored": anchored,
        }

    # ------------------------------------------------------------------
    # DISSOLVE — closes #252
    # ------------------------------------------------------------------
    def execute_dissolve(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an approved DISSOLVE proposal with per-source affinity routing (#252).

        Per ADR-206 §Phase 1: every source in the donor ontology is routed
        to its individual best destination, not absorbed into a single
        target. force_primordial=True overrides affinity and routes
        everything to the primordial pool.

        Pre-flight (unchanged from v1):
            1. Ontology exists and is not pinned/frozen
            2. Queue-aware veto re-check (#402 PR-404 finding #2)

        Per-source routing (NEW, #252):
            - Enumerate sources scoped to the donor ontology.
            - If force_primordial: every source routes to primordial pool.
            - Otherwise: build per-source affinity routing; sources with no
              cross-ontology affinity fall back to the primordial pool.

        Parameters (from proposal['params']):
            source_ontology  : str (donor — falls back to ontology_name)
            force_primordial : bool (default False)
            rationale        : str (informational only)
        """
        params = proposal.get("params") or {}

        ontology_name = (
            params.get("source_ontology")
            or proposal.get("ontology_name")
        )
        if not ontology_name:
            return {
                "success": False,
                "error": "DISSOLVE proposal missing source_ontology",
            }

        force_primordial = bool(params.get("force_primordial", False))

        # ---- 1. Validate ontology still exists ----
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
                "error": (
                    f"Ontology '{ontology_name}' is {lifecycle} — cannot dissolve"
                ),
            }

        # ---- 2. Queue-aware veto re-check ----
        inflight = self._inflight_ingestion_jobs(ontology_name)
        if inflight:
            logger.warning(
                f"DISSOLVE execution vetoed for '{ontology_name}' — "
                f"{len(inflight)} in-flight ingestion job(s) enqueued "
                f"after proposal creation: {inflight}"
            )
            return {
                "success": False,
                "retry_later": True,
                "error": (
                    f"Demotion of '{ontology_name}' vetoed at execute time: "
                    f"{len(inflight)} in-flight ingestion job(s) "
                    f"({', '.join(inflight)}) — proposal will be retried "
                    f"in a later cycle once the queue clears"
                ),
                "vetoed_for_inflight_ingestion": inflight,
            }

        # ---- 3. Build per-source routing map ----
        primordial = self._get_primordial_pool_name()
        # Ensure the primordial pool exists if we may route to it.
        self._ensure_primordial_pool(primordial)

        if force_primordial:
            routing_map = self._build_force_primordial_routing(
                ontology_name, primordial
            )
        else:
            routing_map = self._build_affinity_routing(
                ontology_name, primordial_fallback=primordial
            )

        if not routing_map:
            # Empty ontology — still drop the node, but no sources to route.
            logger.info(
                f"DISSOLVE '{ontology_name}': no sources to route, "
                f"proceeding to delete ontology node"
            )

        # ---- 4. Execute dissolve with the routing map ----
        result = self.client.dissolve_ontology(
            ontology_name,
            routing_map=routing_map or None,
            force_primordial=force_primordial,
        )

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error"),
                "dissolved_ontology": ontology_name,
                "sources_reassigned": result.get("sources_reassigned", 0),
                "routing_targets": result.get("routing_targets", []),
                "force_primordial": force_primordial,
            }

        logger.info(
            f"DISSOLVE complete: '{ontology_name}' dissolved "
            f"({result.get('sources_reassigned', 0)} sources routed to "
            f"{result.get('routing_targets', [])})"
        )

        return {
            "success": True,
            "error": None,
            "action": "dissolve",
            "dissolved_ontology": ontology_name,
            # Back-compat for callers that read absorbed_into. If exactly one
            # target was used, surface it under the v1 key; multi-target
            # dissolves leave it None.
            "absorbed_into": (
                result.get("routing_targets", [None])[0]
                if len(result.get("routing_targets", []) or []) == 1
                else None
            ),
            "routing_targets": result.get("routing_targets", []),
            "sources_reassigned": result.get("sources_reassigned", 0),
            "ontology_node_deleted": result.get("ontology_node_deleted", False),
            "force_primordial": force_primordial,
        }

    def _build_force_primordial_routing(
        self, source_ontology: str, primordial: str
    ) -> Dict[str, str]:
        """Build routing_map for force_primordial mode.

        Every source in the donor ontology maps to the primordial pool,
        regardless of affinity. This is the explicit override path —
        operators / curators ask for it when they want a hard reset rather
        than the (possibly noisy) affinity ranking.

        Returns:
            dict[source_id, primordial] — possibly empty if the ontology
            has no sources.
        """
        source_ids = self._list_source_ids(source_ontology)
        return {sid: primordial for sid in source_ids}

    def _build_affinity_routing(
        self,
        source_ontology: str,
        primordial_fallback: str,
    ) -> Dict[str, str]:
        """Build per-source routing using cross-ontology affinity.

        Returns a dict mapping `source_id → target_ontology` for every
        source currently scoped to `source_ontology`. The decision
        principle (ADR-206) is "every source picks the destination that
        has the strongest claim on it"; sources with no positive
        cross-ontology affinity fall through to `primordial_fallback`.

        Known limitation (degraded mode, documented for follow-up):
            This commit uses a *donor-level* affinity ranking — every
            source in the donor is offered the same target list, ranked by
            the donor's overall overlap with other ontologies. A true
            per-source signal (each source's concepts re-ranked against
            every other ontology's concept set) is a refinement of the
            affinity primitive itself, not the executor. The dict shape
            and the routing_map contract are what #252 needs; refining
            the per-source signal is follow-up work that won't change
            this surface.
        """
        source_ids = self._list_source_ids(source_ontology)
        if not source_ids:
            return {}

        # Use the donor-level affinity ranking as a per-source proxy.
        # affinity_score > 0.0 means at least one shared concept.
        try:
            affinities = self.client.get_cross_ontology_affinity(
                source_ontology, limit=10
            )
        except Exception as e:
            logger.warning(
                f"DISSOLVE: failed to fetch affinity for '{source_ontology}', "
                f"falling back to primordial for all sources: {e}"
            )
            affinities = []

        ranked_targets = [
            a.get("other_ontology")
            for a in (affinities or [])
            if a.get("other_ontology") and a.get("affinity_score", 0.0) > 0.0
        ]

        # Filter ranked targets to those that still exist and aren't frozen.
        viable: List[str] = []
        for cand in ranked_targets:
            node = self.client.get_ontology_node(cand)
            if not node:
                continue
            if node.get("lifecycle_state") == "frozen":
                continue
            viable.append(cand)

        best_target = viable[0] if viable else primordial_fallback
        return {sid: best_target for sid in source_ids}

    def _list_source_ids(self, ontology_name: str) -> List[str]:
        """List source IDs scoped to an ontology.

        Mirrors the SCOPED_BY-based listing dissolve_ontology already uses;
        broken out so the executor can build a routing_map *before*
        calling dissolve_ontology.
        """
        query = """
        MATCH (s:Source)-[:SCOPED_BY]->(o:Ontology {name: $name})
        RETURN s.source_id as source_id
        """
        try:
            results = self.client._execute_cypher(
                query, params={"name": ontology_name}
            )
            return [
                str(row.get("source_id", ""))
                for row in (results or [])
                if row.get("source_id")
            ]
        except Exception as e:
            logger.error(
                f"Failed to list sources for ontology '{ontology_name}': {e}"
            )
            return []

    def _ensure_primordial_pool(self, name: str) -> None:
        """Create the primordial pool node if it doesn't already exist."""
        try:
            if not self.client.get_ontology_node(name):
                pool_id = f"ont_{uuid.uuid4().hex[:12]}"
                self.client.create_ontology_node(
                    ontology_id=pool_id,
                    name=name,
                    description="Default pool for unroutable sources",
                    lifecycle_state="active",
                    created_by="annealing_worker",
                )
                logger.info(f"Auto-created primordial pool '{name}'")
        except Exception as e:
            logger.warning(
                f"Failed to ensure primordial pool '{name}' exists: {e}"
            )

    # ------------------------------------------------------------------
    # MERGE
    # ------------------------------------------------------------------
    def execute_merge(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an approved MERGE proposal (ADR-206).

        MERGE folds ≥2 donor ontologies into a single target. The target
        may be newly created (target.kind='new') or pre-existing
        (target.kind='existing'). Each donor is dissolved with all of its
        sources routed to the target — affinity is bypassed because the
        decision was already made at proposal-creation time.

        Parameters (from proposal['params']):
            donor_ontologies : list[str] (≥2)
            target           : {kind: 'new'|'existing', ...}
                'new'      : new_name, new_description
                'existing' : existing_ontology
        """
        params = proposal.get("params") or {}

        donors = params.get("donor_ontologies") or []
        if len(donors) < 2:
            return {
                "success": False,
                "error": "MERGE proposal requires donor_ontologies with at least 2 entries",
            }

        target = params.get("target") or {}
        target_kind = target.get("kind")
        if target_kind not in ("new", "existing"):
            return {
                "success": False,
                "error": (
                    f"MERGE target.kind must be 'new' or 'existing', "
                    f"got {target_kind!r}"
                ),
            }

        # ---- Validate donors ----
        for donor in donors:
            node = self.client.get_ontology_node(donor)
            if not node:
                return {
                    "success": False,
                    "error": f"MERGE donor '{donor}' does not exist",
                }
            lifecycle = node.get("lifecycle_state", "active")
            if lifecycle in ("pinned", "frozen"):
                return {
                    "success": False,
                    "error": (
                        f"MERGE donor '{donor}' is {lifecycle} — cannot merge"
                    ),
                }

        # ---- Resolve target name + ensure it exists ----
        if target_kind == "new":
            target_name = target.get("new_name")
            if not target_name:
                return {
                    "success": False,
                    "error": "MERGE target.kind='new' requires new_name",
                }
            if target_name in donors:
                return {
                    "success": False,
                    "error": (
                        f"MERGE target name '{target_name}' "
                        f"collides with a donor"
                    ),
                }
            if self.client.get_ontology_node(target_name):
                return {
                    "success": False,
                    "error": f"MERGE target ontology '{target_name}' already exists",
                }
            # Create empty target node (no anchor concept for MERGE).
            ontology_id = f"ont_{uuid.uuid4().hex[:12]}"
            description = (
                target.get("new_description")
                or f"Merged from {', '.join(donors)}"
            )
            create_result = self.client.create_ontology_node(
                ontology_id=ontology_id,
                name=target_name,
                description=description,
                lifecycle_state="active",
                created_by="annealing_worker",
            )
            if not create_result:
                return {
                    "success": False,
                    "error": f"Failed to create MERGE target '{target_name}'",
                }
        else:
            target_name = target.get("existing_ontology")
            if not target_name:
                return {
                    "success": False,
                    "error": "MERGE target.kind='existing' requires existing_ontology",
                }
            if target_name in donors:
                return {
                    "success": False,
                    "error": (
                        f"MERGE target '{target_name}' "
                        f"is also listed as a donor"
                    ),
                }
            if not self.client.get_ontology_node(target_name):
                return {
                    "success": False,
                    "error": f"MERGE target '{target_name}' does not exist",
                }
            ontology_id = None

        # ---- Dissolve each donor into the target ----
        total_reassigned = 0
        dissolved: List[str] = []
        for donor in donors:
            source_ids = self._list_source_ids(donor)
            routing_map = {sid: target_name for sid in source_ids}
            result = self.client.dissolve_ontology(
                donor,
                routing_map=routing_map or None,
                force_primordial=False,
            )
            if not result.get("success"):
                return {
                    "success": False,
                    "error": (
                        f"MERGE failed dissolving donor '{donor}': "
                        f"{result.get('error')}"
                    ),
                    "action": "merge",
                    "target_ontology": target_name,
                    "donors_dissolved": dissolved,
                    "sources_reassigned": total_reassigned,
                    "partial": True,
                }
            total_reassigned += result.get("sources_reassigned", 0)
            dissolved.append(donor)

        logger.info(
            f"MERGE complete: {len(dissolved)} donor(s) dissolved into "
            f"'{target_name}' ({total_reassigned} sources reassigned)"
        )

        return {
            "success": True,
            "error": None,
            "action": "merge",
            "target_ontology": target_name,
            "target_kind": target_kind,
            "ontology_id": ontology_id,
            "donors_dissolved": dissolved,
            "sources_reassigned": total_reassigned,
        }

    # ------------------------------------------------------------------
    # RENAME
    # ------------------------------------------------------------------
    def execute_rename(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an approved RENAME proposal (ADR-206).

        Updates the Ontology node's `name` plus the denormalized `document`
        property on every Source scoped to it. The primordial pool name is
        invariant — renames targeting it are rejected.

        Parameters (from proposal['params']):
            ontology        : str (current name)
            new_name        : str
            new_description : str (optional)
        """
        params = proposal.get("params") or {}

        old_name = (
            params.get("ontology")
            or proposal.get("ontology_name")
        )
        new_name = params.get("new_name")
        new_description = params.get("new_description")

        if not old_name:
            return {
                "success": False,
                "error": "RENAME proposal missing ontology name",
            }
        if not new_name:
            return {
                "success": False,
                "error": "RENAME proposal missing new_name",
            }
        if new_name == old_name:
            return {
                "success": False,
                "error": f"RENAME new_name '{new_name}' equals current name",
            }

        primordial = self._get_primordial_pool_name()
        if old_name == primordial:
            return {
                "success": False,
                "error": (
                    f"Cannot rename the primordial pool "
                    f"('{primordial}' is invariant)"
                ),
            }

        node = self.client.get_ontology_node(old_name)
        if not node:
            return {
                "success": False,
                "error": f"Ontology '{old_name}' does not exist",
            }
        lifecycle = node.get("lifecycle_state", "active")
        if lifecycle in ("pinned", "frozen"):
            return {
                "success": False,
                "error": f"Ontology '{old_name}' is {lifecycle} — cannot rename",
            }

        if self.client.get_ontology_node(new_name):
            return {
                "success": False,
                "error": f"Ontology '{new_name}' already exists",
            }

        # Update the Ontology node's name.
        node_renamed = self.client.rename_ontology_node(old_name, new_name)
        if not node_renamed:
            return {
                "success": False,
                "error": f"Failed to rename ontology node '{old_name}'",
            }

        # Update s.document on every Source scoped to the old name.
        sources_updated = 0
        try:
            source_result = self.client.rename_ontology(old_name, new_name)
            sources_updated = source_result.get("sources_updated", 0)
        except Exception as e:
            # Node has already been renamed; log the partial state for ops.
            logger.warning(
                f"RENAME of '{old_name}' → '{new_name}': node renamed but "
                f"source-level document update failed: {e}"
            )
            return {
                "success": False,
                "error": (
                    f"Ontology node renamed but source document update failed: {e}"
                ),
                "action": "rename",
                "old_name": old_name,
                "new_name": new_name,
                "partial": True,
            }

        # Update the description if provided (optional — separate from rename).
        description_updated = False
        if new_description is not None:
            description_updated = self._update_ontology_description(
                new_name, new_description
            )

        logger.info(
            f"RENAME complete: '{old_name}' → '{new_name}' "
            f"({sources_updated} sources updated)"
        )

        return {
            "success": True,
            "error": None,
            "action": "rename",
            "old_name": old_name,
            "new_name": new_name,
            "sources_updated": sources_updated,
            "description_updated": description_updated,
        }

    def _update_ontology_description(self, name: str, description: str) -> bool:
        """SET o.description on an Ontology node. Best-effort."""
        query = """
        MATCH (o:Ontology {name: $name})
        SET o.description = $description
        RETURN o.ontology_id as ontology_id
        """
        try:
            result = self.client._execute_cypher(
                query,
                params={"name": name, "description": description},
                fetch_one=True,
            )
            return result is not None and result.get("ontology_id") is not None
        except Exception as e:
            logger.warning(
                f"Failed to update description for ontology '{name}': {e}"
            )
            return False

    # ------------------------------------------------------------------
    # NO_ACTION
    # ------------------------------------------------------------------
    def execute_no_action(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an approved NO_ACTION proposal (ADR-206).

        The Sonnet tier explicitly chose to do nothing this epoch. No graph
        mutation; the reasoning is preserved in the proposal's audit trail.
        """
        params = proposal.get("params") or {}
        reasoning = params.get("reasoning") or proposal.get("reasoning")
        logger.info(
            f"NO_ACTION recorded for proposal {proposal.get('id')}: {reasoning}"
        )
        return {
            "success": True,
            "error": None,
            "action": "no_action",
            "reasoning": reasoning,
        }

    # ------------------------------------------------------------------
    # ESCALATE
    # ------------------------------------------------------------------
    def execute_escalate(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an approved ESCALATE proposal (ADR-206).

        ESCALATE is the Sonnet-tier admission of uncertainty — the proposal
        is recorded but not executed against the graph. Phase 2 wiring
        (Opus / human follow-up) is out of scope for this commit; the
        candidate actions and confidence surface to the audit trail so a
        human reviewer has the full context.
        """
        params = proposal.get("params") or {}
        logger.info(
            f"ESCALATE recorded for proposal {proposal.get('id')}: "
            f"recommended={params.get('recommended_action')} "
            f"confidence={params.get('confidence')}"
        )
        return {
            "success": True,
            "error": None,
            "action": "escalate",
            "candidate_actions": params.get("candidate_actions", []),
            "recommended_action": params.get("recommended_action"),
            "confidence": params.get("confidence"),
            "what_i_know": params.get("what_i_know"),
            "what_i_dont_know": params.get("what_i_dont_know"),
            "escalation_recorded": True,
        }

    # ADR-206 §Phase 3 safety rails. Operators may tune these from the
    # admin UI; Opus is NEVER allowed to via ADJUST_CONTROL. Listed
    # explicitly rather than "everything except this set" because adding a
    # new safety rail without amending this list would silently widen
    # autonomy — the system cannot widen its own autonomy is the
    # self-regulation invariant.
    _SAFETY_RAIL_KEYS = frozenset({
        "automation_level",
        "escalation_chain",
        "opus_confidence",
        "phone_a_friend_cost_budget",
    })

    def execute_adjust_control(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an approved ADJUST_CONTROL proposal (ADR-206 §Phase 3).

        Updates one row in kg_api.annealing_options. Rejects any control_key
        that lives on the safety-rail list — Opus may tune operational
        knobs (cadence, cooldowns, eligibility thresholds) but never
        safety knobs (automation_level, escalation_chain, opus_confidence,
        phone_a_friend_cost_budget). The self-regulation invariant: the
        system can regulate its own cadence, but cannot widen its own
        autonomy.
        """
        params = proposal.get("params") or {}
        control_key = params.get("control_key")
        recommended_value = params.get("recommended_value")

        if not control_key:
            return {"success": False, "error": "ADJUST_CONTROL missing control_key"}
        if recommended_value is None:
            return {"success": False, "error": "ADJUST_CONTROL missing recommended_value"}

        if control_key in self._SAFETY_RAIL_KEYS:
            return {
                "success": False,
                "error": (
                    f"control_key '{control_key}' is a safety rail — "
                    f"only operators can tune it (ADR-206 §Phase 3 self-regulation invariant)"
                ),
                "control_key": control_key,
                "rejected_reason": "safety_rail",
            }

        try:
            conn = self.client.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT 1 FROM kg_api.annealing_options WHERE key = %s",
                        (control_key,),
                    )
                    if not cur.fetchone():
                        return {
                            "success": False,
                            "error": f"control_key '{control_key}' not found in annealing_options",
                            "control_key": control_key,
                        }
                    cur.execute(
                        """
                        UPDATE kg_api.annealing_options
                        SET value = %s, updated_at = NOW()
                        WHERE key = %s
                        RETURNING value
                        """,
                        (str(recommended_value), control_key),
                    )
                    row = cur.fetchone()
                    conn.commit()
                    new_value = row[0] if row else None
            finally:
                self.client.pool.putconn(conn)
        except Exception as exc:
            logger.error(f"ADJUST_CONTROL update failed for '{control_key}': {exc}")
            return {
                "success": False,
                "error": str(exc),
                "control_key": control_key,
            }

        logger.info(
            f"ADJUST_CONTROL applied: {control_key} → {new_value} "
            f"(was {params.get('current_value')!r}, "
            f"defense={params.get('defense', '')!r})"
        )
        return {
            "success": True,
            "error": None,
            "action": "adjust_control",
            "control_key": control_key,
            "previous_value": params.get("current_value"),
            "new_value": new_value,
        }

    # ------------------------------------------------------------------
    # Legacy shims — callers using v1 names get the v2 implementations.
    # ------------------------------------------------------------------
    def execute_promotion(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """Deprecated v1 alias for execute_cleave. Retained for callers."""
        return self.execute_cleave(proposal)

    def execute_demotion(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """Deprecated v1 alias for execute_dissolve. Retained for callers."""
        return self.execute_dissolve(proposal)

    # ------------------------------------------------------------------
    # Helpers (preserved from v1)
    # ------------------------------------------------------------------
    def _inflight_ingestion_jobs(self, ontology_name: str) -> List[str]:
        """Job IDs of non-terminal ingestion jobs targeting `ontology_name`.

        Mirrors AnnealingManager._get_inflight_ingestion_targets for a single
        ontology — used by execute_dissolve to re-check the queue veto at
        execute time (#402 PR-404 review, finding #2).

        Returns an empty list on DB error so a transient failure doesn't
        block legitimate demotions; the worker's unconditional tombstone
        check + VANISHED raise remain the downstream backstop.
        """
        try:
            conn = self.client.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT job_id
                        FROM kg_api.jobs
                        WHERE job_type = ANY(%s)
                          AND status = ANY(%s)
                          AND ontology = %s
                        """,
                        (
                            list(_INGESTION_JOB_TYPES),
                            list(_NON_TERMINAL_JOB_STATUSES),
                            ontology_name,
                        ),
                    )
                    rows = cur.fetchall()
                conn.commit()
                return [row[0] for row in rows if row and row[0]]
            finally:
                self.client.pool.putconn(conn)
        except Exception as e:
            logger.error(
                f"Failed to read in-flight ingestion targets for "
                f"'{ontology_name}' veto re-check: {e}"
            )
            return []

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
