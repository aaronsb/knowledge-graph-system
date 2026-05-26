"""
Annealing Manager — orchestrates ontology annealing cycles (ADR-200 + ADR-206).

Per cycle: score all ontologies → identify candidates → drive the 6-verb
closed action vocabulary through `AnnealingDecisionService` → store the
returned proposal(s) on `kg_api.annealing_proposals`.

In autonomous mode (default), proposals are auto-approved and executed
by the annealing worker. In hitl mode they wait for human review.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Tuple

from psycopg2.extras import Json

from api.app.lib.ontology_scorer import OntologyScorer
from api.app.lib.aggressiveness_curve import AGGRESSIVENESS_CURVES
from .annealing_decision_service import (
    AnnealingDecisionService,
    AnnealingContext,
    AnnealingCandidate,
    OntologySummary,
    AnchorConcept,
    AffinityTarget,
    FailedProposalSummary,
)

logger = logging.getLogger(__name__)


# Ecological-pressure thresholds (avg concepts per ontology). The healthy
# band is empirically wide — operators with different ingestion volumes hit
# very different "comfortable" ratios. These defaults match ADR-200 §9's
# resolution-limit discussion: below ~10 the graph is over-fragmented
# (many stubs), above ~80 ontologies are bloated and need CLEAVE. The
# Bezier-derived score smoothly interpolates between these endpoints
# rather than imposing sharp cutoffs.
_PRESSURE_COMFORT_MIN = 10.0
_PRESSURE_COMFORT_MAX = 80.0
_PRESSURE_EMERGENCY = 150.0
_PRESSURE_CURVE = AGGRESSIVENESS_CURVES["aggressive"]


class AnnealingManager:
    """
    Runs annealing cycles: score, identify candidates, decide, propose.

    Execution is handled by the annealing worker (autonomous mode) or
    human review endpoint (hitl mode).
    """

    def __init__(
        self,
        age_client,
        scorer: OntologyScorer,
        ai_provider=None,
        automation_level: str = "autonomous",
    ):
        self.client = age_client
        self.scorer = scorer
        self.ai_provider = ai_provider
        # In autonomous mode proposals are stored already 'approved' so there
        # is no human-raceable 'pending' window — the annealing worker only
        # dispatches their execution jobs. In hitl mode they are born 'pending'.
        self.automation_level = automation_level

    async def run_annealing_cycle(
        self,
        demotion_threshold: float = 0.15,
        promotion_min_degree: int = 10,
        max_proposals: int = 5,
        dry_run: bool = False,
        derive_edges: bool = True,
        overlap_threshold: float = 0.1,
        specializes_threshold: float = 0.3,
        min_ontology_age_epochs: int = 3,
        min_ontology_concept_count: int = 5,
    ) -> Dict[str, Any]:
        """
        Run a full annealing cycle.

        1. Score all ontologies
        2. Recompute centroids
        3. Derive ontology-to-ontology edges (Phase 5)
        4. Identify demotion candidates (low protection)
        5. Identify promotion candidates (high-degree concepts)
        6. LLM decision via AnnealingDecisionService (unless dry_run)
        7. Store proposals

        Args:
            demotion_threshold: Protection score below which to consider demotion
            promotion_min_degree: Minimum concept degree for promotion candidacy
            max_proposals: Cap on proposals per cycle
            dry_run: If True, identify candidates but don't call LLM or store

        Returns:
            Cycle result summary
        """
        global_epoch = self.client.get_current_epoch()
        logger.info(f"Annealing cycle starting at epoch {global_epoch}")

        # 1. Score all ontologies
        all_scores = self.scorer.score_all_ontologies()
        logger.info(f"Scored {len(all_scores)} ontologies")

        # 1b. Ecological snapshot (ADR-200 Phase 4, observational)
        ecological = self._get_ecological_snapshot(all_scores)
        logger.info(
            f"Ecological snapshot: {ecological['total_ontologies']} ontologies, "
            f"~{ecological['avg_concepts_per_ontology']:.0f} concepts/ontology, "
            f"pressure={ecological['pressure_score']:.2f} ({ecological['pressure_zone']})"
        )
        # Surface Bezier-derived control recommendations for operator review
        # (commit 9 turns these into ADJUST_CONTROL proposals).
        for key, block in ecological["pressure_recommendation"].items():
            if block["delta"] != 0:
                logger.info(
                    f"  pressure_recommendation: {key} "
                    f"{block['current']} → {block['recommended']} "
                    f"(delta {block['delta']:+d})"
                )

        # 2. Recompute centroids
        centroids_updated = self.scorer.recompute_all_centroids()
        logger.info(f"Updated {centroids_updated} ontology centroids")

        # 3. Derive ontology-to-ontology edges (ADR-200 Phase 5)
        edge_result = {"edges_created": 0, "edges_deleted": 0}
        if derive_edges and not dry_run:
            try:
                edge_result = self.scorer.derive_ontology_edges(
                    overlap_threshold=overlap_threshold,
                    specializes_threshold=specializes_threshold,
                )
                logger.info(
                    f"Derived {edge_result['edges_created']} ontology edges "
                    f"(deleted {edge_result['edges_deleted']} stale)"
                )
            except Exception as e:
                logger.warning(f"Edge derivation failed (non-fatal): {e}")

        # 4. Identify demotion candidates
        demotion_candidates = self._find_demotion_candidates(
            all_scores,
            demotion_threshold,
            current_epoch=global_epoch,
            min_age_epochs=min_ontology_age_epochs,
            min_concept_count=min_ontology_concept_count,
        )
        logger.info(f"Found {len(demotion_candidates)} demotion candidates")

        # 5. Identify promotion candidates
        promotion_candidates = self._find_promotion_candidates(
            all_scores,
            promotion_min_degree,
            current_epoch=global_epoch,
            min_age_epochs=min_ontology_age_epochs,
            min_concept_count=min_ontology_concept_count,
        )
        logger.info(f"Found {len(promotion_candidates)} promotion candidates")

        if dry_run:
            return {
                "proposals_generated": 0,
                "demotion_candidates": len(demotion_candidates),
                "promotion_candidates": len(promotion_candidates),
                "scores_updated": len(all_scores),
                "centroids_updated": centroids_updated,
                "edges_created": edge_result.get("edges_created", 0),
                "edges_deleted": edge_result.get("edges_deleted", 0),
                "cycle_epoch": global_epoch,
                "dry_run": True,
                "candidates": {
                    "demotions": [
                        {"ontology": c["ontology"], "protection": c["protection_score"]}
                        for c in demotion_candidates
                    ],
                    "promotions": [
                        {"concept": c["label"], "ontology": c["ontology"], "degree": c["degree"]}
                        for c in promotion_candidates
                    ],
                },
            }

        # 5b. Idempotency guard: the cycle is graph-driven and re-derives
        # candidates every run. Without this it re-proposes work already in the
        # queue, piling up duplicates (the original 'duplicate demotion batch').
        # Skip candidates that already have an open proposal — pending /
        # approved / executing. Terminal proposals do not block re-proposal, so
        # the cycle still self-heals when an ontology is later deleted.
        open_promotions, open_demotions = self._get_open_proposal_targets()
        if open_promotions or open_demotions:
            before = (len(demotion_candidates), len(promotion_candidates))
            demotion_candidates = [
                c for c in demotion_candidates
                if c.get("ontology") not in open_demotions
            ]
            promotion_candidates = [
                c for c in promotion_candidates
                if c.get("concept_id") not in open_promotions
            ]
            logger.info(
                f"Queue dedup: demotion {before[0]}→{len(demotion_candidates)}, "
                f"promotion {before[1]}→{len(promotion_candidates)} "
                f"(skipped candidates with open proposals)"
            )

        # 5c. Queue-aware veto (#402, Defect A): annealing must not propose a
        # mutation against an ontology that still has in-flight ingestion work
        # queued for it. Without this guard the worker dissolves X, the
        # ingestion job dequeues with target=X, and the operator-submitted
        # content silently never lands. Promotions are not vetoed — they create
        # a new ontology and do not modify the existing one in a way that
        # invalidates queued ingest jobs against the source ontology.
        vetoed_inflight: List[Dict[str, Any]] = []
        if demotion_candidates:
            candidate_names = {c.get("ontology") for c in demotion_candidates}
            candidate_names.discard(None)
            inflight = self._get_inflight_ingestion_targets(candidate_names)
            if inflight:
                kept: List[Dict] = []
                for c in demotion_candidates:
                    name = c.get("ontology")
                    blocking = inflight.get(name) if name else None
                    if blocking:
                        vetoed_inflight.append({
                            "ontology": name,
                            "blocking_job_count": len(blocking),
                            "blocking_job_ids": blocking,
                        })
                        logger.info(
                            "Annealing veto: skipping demotion candidate "
                            f"'{name}' — {len(blocking)} in-flight ingestion "
                            f"job(s) target this ontology "
                            f"(job_ids={blocking})"
                        )
                    else:
                        kept.append(c)
                demotion_candidates = kept

        # 6. Build the per-cycle decision context, then decide + store
        inventory = [
            OntologySummary(
                name=s.get("ontology", ""),
                concept_count=s.get("concept_count", 0),
                lifecycle_state=(
                    self.client.get_ontology_node(s.get("ontology", "")) or {}
                ).get("lifecycle_state", "active"),
            )
            for s in all_scores
        ]
        context = AnnealingContext(
            ontology_inventory=inventory, primordial_pool_name="primordial"
        )
        decision_service = (
            AnnealingDecisionService(self.ai_provider) if self.ai_provider else None
        )

        proposal_ids = []
        remaining = max_proposals

        # Demotions first (more impactful)
        for candidate in demotion_candidates[:remaining]:
            proposal_id = await self._decide_and_store_demotion(
                candidate, decision_service, context, global_epoch
            )
            if proposal_id:
                proposal_ids.append(proposal_id)
                remaining -= 1
                if remaining <= 0:
                    break

        # Then promotions
        for candidate in promotion_candidates[:remaining]:
            proposal_id = await self._decide_and_store_promotion(
                candidate, decision_service, context, global_epoch
            )
            if proposal_id:
                proposal_ids.append(proposal_id)
                remaining -= 1
                if remaining <= 0:
                    break

        # 7. Emit ADJUST_CONTROL proposals for any pressure recommendation
        #    whose |delta| exceeds the deadband (#249 Part 2, ADR-206 §Phase 3).
        #    Bezier-derived; no LLM judgment needed — defense is the snapshot.
        control_proposals = self._emit_control_proposals(
            recommendation=ecological["pressure_recommendation"],
            pressure_score=ecological["pressure_score"],
            pressure_zone=ecological["pressure_zone"],
            epoch=global_epoch,
        )
        proposal_ids.extend(control_proposals)

        # 8. Persist the snapshot to kg_api.annealing_pressure_history so the
        #    admin UI can render current state and trend over time (#249).
        self._record_pressure_snapshot(ecological, global_epoch)

        logger.info(
            f"Annealing cycle complete: {len(proposal_ids)} proposals "
            f"({len(control_proposals)} control), "
            f"{len(all_scores)} scored, {centroids_updated} centroids, "
            f"{edge_result.get('edges_created', 0)} edges, "
            f"{len(vetoed_inflight)} vetoed (in-flight ingestion)"
        )

        return {
            "proposals_generated": len(proposal_ids),
            "proposal_ids": proposal_ids,
            "demotion_candidates": len(demotion_candidates),
            "promotion_candidates": len(promotion_candidates),
            "scores_updated": len(all_scores),
            "centroids_updated": centroids_updated,
            "edges_created": edge_result.get("edges_created", 0),
            "edges_deleted": edge_result.get("edges_deleted", 0),
            "cycle_epoch": global_epoch,
            "vetoed_for_inflight_ingestion": vetoed_inflight,
            "dry_run": False,
        }

    # =========================================================================
    # Candidate Identification
    # =========================================================================

    def _find_demotion_candidates(
        self,
        all_scores: List[Dict],
        threshold: float,
        current_epoch: int = 0,
        min_age_epochs: int = 0,
        min_concept_count: int = 0,
    ) -> List[Dict]:
        """Find ontologies with protection below threshold, excluding pinned/frozen.

        Per-ontology cadence floors (#402 Defect C) gate eligibility:
        ontologies younger than min_age_epochs or holding fewer than
        min_concept_count concepts are skipped — their scores are dominated
        by per-concept noise rather than ontology structure, so evaluating
        them wastes LLM calls and widens the ingestion race window.
        """
        candidates = []
        for scores in all_scores:
            name = scores.get("ontology", "")
            protection = scores.get("protection_score", 1.0)

            if protection >= threshold:
                continue

            # Activity floor — ontology must have enough mass to be judged.
            if scores.get("concept_count", 0) < min_concept_count:
                logger.debug(
                    f"Skipping demotion candidate '{name}': concept_count "
                    f"{scores.get('concept_count', 0)} < floor {min_concept_count}"
                )
                continue

            # Check lifecycle — skip pinned/frozen
            node = self.client.get_ontology_node(name)
            if not node:
                continue
            lifecycle = node.get("lifecycle_state", "active")
            if lifecycle in ("pinned", "frozen"):
                continue

            # Age floor — ontology must have existed for ≥ min_age_epochs.
            # creation_epoch missing on legacy nodes is treated as 0 (oldest),
            # so the floor never blocks pre-existing ontologies.
            creation_epoch = node.get("creation_epoch", 0) or 0
            age = current_epoch - creation_epoch
            if min_age_epochs > 0 and age < min_age_epochs:
                logger.debug(
                    f"Skipping demotion candidate '{name}': age {age} "
                    f"< floor {min_age_epochs} epochs"
                )
                continue

            candidates.append({
                **scores,
                "lifecycle_state": lifecycle,
            })

        # Sort by protection ascending (worst first)
        candidates.sort(key=lambda c: c.get("protection_score", 0))
        return candidates

    def _find_promotion_candidates(
        self,
        all_scores: List[Dict],
        min_degree: int,
        current_epoch: int = 0,
        min_age_epochs: int = 0,
        min_concept_count: int = 0,
    ) -> List[Dict]:
        """Find high-degree concepts that could become ontologies.

        The cadence floors that gate demotion (#402 Defect C) also gate
        promotion: a brand-new or near-empty source ontology has not
        accumulated enough signal for its high-degree concepts to be
        judged as natural new nuclei.
        """
        candidates = []
        existing_ontology_names = {
            s["ontology"].lower() for s in all_scores
        }
        # Concepts that already anchor an ontology have been promoted already —
        # exclude them so the graph-driven cycle does not keep re-proposing them.
        anchored_concept_ids = self._get_anchored_concept_ids()

        for scores in all_scores:
            name = scores.get("ontology", "")

            # Apply the same activity / age floors as demotion: a sparse or
            # very young source ontology hasn't earned an evaluation yet.
            if scores.get("concept_count", 0) < min_concept_count:
                continue
            if min_age_epochs > 0:
                node = self.client.get_ontology_node(name)
                creation_epoch = (node or {}).get("creation_epoch", 0) or 0
                if current_epoch - creation_epoch < min_age_epochs:
                    continue

            try:
                ranking = self.client.get_concept_degree_ranking(name, limit=10)
            except Exception:
                continue

            for concept in ranking:
                degree = concept.get("degree", 0)
                if degree < min_degree:
                    continue

                # Skip concepts that already anchor an ontology
                if concept.get("concept_id") in anchored_concept_ids:
                    continue

                # Skip if a concept with this label is already an ontology
                label = concept.get("label", "")
                if label.lower() in existing_ontology_names:
                    continue

                candidates.append({
                    "concept_id": concept["concept_id"],
                    "label": label,
                    "degree": degree,
                    "ontology": name,
                    "description": concept.get("description", ""),
                })

        # Sort by degree descending (strongest first)
        candidates.sort(key=lambda c: c.get("degree", 0), reverse=True)
        return candidates

    def _get_open_proposal_targets(self) -> Tuple[Set[str], Set[str]]:
        """Targets that already have an open (non-terminal) proposal.

        The annealing cycle is graph-driven — it re-derives candidates from the
        graph every run. Without this guard it re-proposes work already queued,
        piling up duplicates. 'Open' means pending / approved / executing;
        terminal proposals (executed / failed / rejected / expired) do not
        block re-proposal, so the cycle still self-heals if an ontology is
        later deleted.

        ADR-206 routing: CLEAVE proposals key on the anchor concept id (the
        promotion analogue); DISSOLVE / MERGE / RENAME proposals key on the
        ontology name(s) they touch (the demotion analogue). Deprecated
        'promotion' / 'demotion' rows preserve the pre-ADR-206 routing on
        the typed columns. Newer rows carry the relevant identifiers inside
        the `params` JSONB.

        Returns:
            (open_promotion_anchor_ids, open_demotion_ontology_names)
        """
        open_promotions: Set[str] = set()
        open_demotions: Set[str] = set()
        try:
            conn = self.client.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT proposal_type, ontology_name, anchor_concept_id,
                               params
                        FROM kg_api.annealing_proposals
                        WHERE proposal_type IN (
                                'promotion', 'CLEAVE',
                                'demotion', 'DISSOLVE',
                                'MERGE', 'RENAME'
                              )
                          AND status IN ('pending', 'approved', 'executing')
                    """)
                    rows = cur.fetchall()
                conn.commit()
            finally:
                self.client.pool.putconn(conn)
            for proposal_type, ontology_name, anchor_concept_id, params in rows:
                params = params or {}
                if proposal_type == "promotion":
                    if anchor_concept_id:
                        open_promotions.add(anchor_concept_id)
                elif proposal_type == "CLEAVE":
                    anchor = params.get("anchor_concept_id") or anchor_concept_id
                    if anchor:
                        open_promotions.add(anchor)
                elif proposal_type == "demotion":
                    if ontology_name:
                        open_demotions.add(ontology_name)
                elif proposal_type == "DISSOLVE":
                    source = params.get("source_ontology") or ontology_name
                    if source:
                        open_demotions.add(source)
                elif proposal_type == "MERGE":
                    for donor in params.get("donor_ontologies", []) or []:
                        if donor:
                            open_demotions.add(donor)
                elif proposal_type == "RENAME":
                    target_name = params.get("ontology") or ontology_name
                    if target_name:
                        open_demotions.add(target_name)
        except Exception as e:
            logger.error(f"Failed to read open proposals for dedup: {e}")
        return open_promotions, open_demotions

    # Non-terminal job statuses on kg_api.jobs. An ingestion job in any of
    # these states still intends to write to its target ontology — annealing
    # must not dissolve / merge / decompose that ontology out from under it
    # (#402, Defect A). Terminal statuses (completed / failed / cancelled /
    # expired) do not block.
    _NON_TERMINAL_JOB_STATUSES: Tuple[str, ...] = (
        "pending",
        "awaiting_approval",
        "approved",
        "queued",
        "running",
        "processing",
    )

    # Job types that target an ontology with intent to write. Keep in sync
    # with WORKER_REGISTRY in api/app/services/worker_registry.py.
    _INGESTION_JOB_TYPES: Tuple[str, ...] = ("ingestion", "ingest_image")

    def _get_inflight_ingestion_targets(
        self, ontology_names: Set[str]
    ) -> Dict[str, List[str]]:
        """In-flight ingestion jobs grouped by target ontology name.

        Returns a mapping `{ontology_name: [job_id, ...]}` covering only the
        supplied names — empty for an ontology with no non-terminal ingestion
        work, omitted entirely if nothing matches. Used by the queue-aware
        veto in the annealing cycle (#402).

        Reads from kg_api.jobs directly via the AGE client's pool, mirroring
        how _get_open_proposal_targets reads kg_api.annealing_proposals — the
        manager stays a self-contained consumer of the shared connection pool.
        """
        if not ontology_names:
            return {}
        targets: Dict[str, List[str]] = {}
        try:
            conn = self.client.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT ontology, job_id
                        FROM kg_api.jobs
                        WHERE job_type = ANY(%s)
                          AND status = ANY(%s)
                          AND ontology = ANY(%s)
                        """,
                        (
                            list(self._INGESTION_JOB_TYPES),
                            list(self._NON_TERMINAL_JOB_STATUSES),
                            list(ontology_names),
                        ),
                    )
                    rows = cur.fetchall()
                conn.commit()
            finally:
                self.client.pool.putconn(conn)
            for ontology, job_id in rows:
                if not ontology:
                    continue
                targets.setdefault(ontology, []).append(job_id)
        except Exception as e:
            logger.error(
                f"Failed to read in-flight ingestion targets for veto: {e}"
            )
        return targets

    def _get_anchored_concept_ids(self) -> Set[str]:
        """Concept IDs that already anchor an ontology (have an ANCHORED_BY edge).

        Such concepts have already been promoted; the graph-driven cycle would
        otherwise keep re-proposing them for promotion. Deleting an ontology
        removes its ANCHORED_BY edge, making the concept eligible again — so the
        cycle self-heals.
        """
        try:
            rows = self.client._execute_cypher(
                "MATCH (:Ontology)-[:ANCHORED_BY]->(c:Concept) "
                "RETURN c.concept_id AS concept_id"
            )
            return {
                r["concept_id"] for r in (rows or []) if r.get("concept_id")
            }
        except Exception as e:
            logger.error(f"Failed to read anchored concepts: {e}")
            return set()

    # =========================================================================
    # LLM Decision + Proposal Storage (ADR-206 6-verb vocabulary)
    # =========================================================================

    async def _decide_and_store_demotion(
        self,
        candidate: Dict,
        decision_service: Optional[AnnealingDecisionService],
        context: AnnealingContext,
        epoch: int,
    ) -> Optional[int]:
        """Decide an action for a low-protection ontology and store the proposal."""
        name = candidate["ontology"]

        try:
            affinity_rows = self.client.get_cross_ontology_affinity(name, limit=5)
        except Exception:
            affinity_rows = []
        affinity_targets = [
            AffinityTarget(
                other_ontology=row.get("other_ontology", ""),
                shared_concept_count=row.get("shared_concept_count", 0),
                affinity_score=row.get("affinity_score", 0.0),
            )
            for row in (affinity_rows or [])
        ]

        stats = self.client.get_ontology_stats(name)
        concept_count = stats.get("concept_count", 0) if stats else 0

        ann_candidate = AnnealingCandidate(
            signal_kind="low_protection_low_coherence",
            primary_ontology=name,
            mass_score=candidate.get("mass_score", 0),
            coherence_score=candidate.get("coherence_score", 0),
            protection_score=candidate.get("protection_score", 0),
            concept_count=concept_count,
            affinity_targets=affinity_targets,
        )

        if decision_service is None:
            best_target = (
                affinity_rows[0].get("other_ontology") if affinity_rows else None
            )
            reasoning = (
                f"Protection score {candidate.get('protection_score', 0):.3f} "
                f"below threshold (no LLM available for evaluation)"
            )
            return self._store_proposal(
                proposal_type="DISSOLVE",
                ontology_name=name,
                target_ontology=best_target,
                reasoning=reasoning,
                proposal_kind="ontology",
                params={"source_ontology": name, "rationale": reasoning},
                mass_score=candidate.get("mass_score"),
                coherence_score=candidate.get("coherence_score"),
                protection_score=candidate.get("protection_score"),
                epoch=epoch,
            )

        decision = await decision_service.decide_async(context, ann_candidate)

        # UI hint: DISSOLVE / MERGE / RENAME all touch an ontology; surface the
        # best-affinity neighbor (if any) on target_ontology so the queue view
        # can render a destination without parsing params. The executor reads
        # params for actual routing.
        ui_hint_target = (
            affinity_rows[0].get("other_ontology") if affinity_rows else None
        )

        return self._store_proposal(
            proposal_type=decision.proposal_type,
            ontology_name=name,
            target_ontology=ui_hint_target,
            reasoning=decision.reasoning,
            proposal_kind=decision.proposal_kind,
            params=decision.params,
            mass_score=candidate.get("mass_score"),
            coherence_score=candidate.get("coherence_score"),
            protection_score=candidate.get("protection_score"),
            epoch=epoch,
        )

    async def _decide_and_store_promotion(
        self,
        candidate: Dict,
        decision_service: Optional[AnnealingDecisionService],
        context: AnnealingContext,
        epoch: int,
    ) -> Optional[int]:
        """Decide an action for a high-degree concept and store the proposal."""
        ontology_name = candidate["ontology"]
        concept_id = candidate["concept_id"]
        label = candidate["label"]

        try:
            affinity_rows = self.client.get_cross_ontology_affinity(
                ontology_name, limit=5
            )
        except Exception:
            affinity_rows = []
        affinity_targets = [
            AffinityTarget(
                other_ontology=row.get("other_ontology", ""),
                shared_concept_count=row.get("shared_concept_count", 0),
                affinity_score=row.get("affinity_score", 0.0),
            )
            for row in (affinity_rows or [])
        ]

        try:
            neighbor_rows = self.client._execute_cypher(
                """
                MATCH (c:Concept {concept_id: $cid})-[r]-(n:Concept)
                RETURN DISTINCT n.label as label, count(r) as rel_count
                ORDER BY rel_count DESC
                LIMIT 10
                """,
                params={"cid": concept_id},
            )
            top_neighbors = [row["label"] for row in (neighbor_rows or [])]
        except Exception:
            top_neighbors = []

        anchor = AnchorConcept(
            concept_id=concept_id,
            label=label,
            description=candidate.get("description", "") or "",
            degree=candidate.get("degree", 0),
            top_neighbors=top_neighbors,
        )

        ann_candidate = AnnealingCandidate(
            signal_kind="high_degree_concept",
            primary_ontology=ontology_name,
            anchor_concept=anchor,
            affinity_targets=affinity_targets,
        )

        if decision_service is None:
            reasoning = (
                f"Degree {candidate.get('degree', 0)} exceeds threshold "
                f"(no LLM available for evaluation)"
            )
            params = {
                "source_ontology": ontology_name,
                "anchor_concept_id": concept_id,
                "cluster_selection": "first_order",
                "cluster_params": {},
                "target": {
                    "kind": "new",
                    "new_name": label,
                    "new_description": f"Domain anchored by concept '{label}'",
                },
                "reasoning": reasoning,
            }
            return self._store_proposal(
                proposal_type="CLEAVE",
                ontology_name=ontology_name,
                anchor_concept_id=concept_id,
                reasoning=reasoning,
                proposal_kind="ontology",
                params=params,
                suggested_name=label,
                suggested_description=f"Domain anchored by concept '{label}'",
                epoch=epoch,
            )

        decision = await decision_service.decide_async(context, ann_candidate)

        # Surface the CLEAVE target name on suggested_name (UI hint) so the
        # queue view can render a destination without parsing params.
        target = (decision.params or {}).get("target") or {}
        suggested_name = target.get("new_name")
        suggested_description = target.get("new_description")

        return self._store_proposal(
            proposal_type=decision.proposal_type,
            ontology_name=ontology_name,
            anchor_concept_id=concept_id,
            reasoning=decision.reasoning,
            proposal_kind=decision.proposal_kind,
            params=decision.params,
            suggested_name=suggested_name,
            suggested_description=suggested_description,
            epoch=epoch,
        )

    def _store_proposal(
        self,
        proposal_type: str,
        ontology_name: str,
        reasoning: str,
        epoch: int,
        proposal_kind: str = "ontology",
        params: Optional[Dict[str, Any]] = None,
        anchor_concept_id: Optional[str] = None,
        target_ontology: Optional[str] = None,
        mass_score: Optional[float] = None,
        coherence_score: Optional[float] = None,
        protection_score: Optional[float] = None,
        suggested_name: Optional[str] = None,
        suggested_description: Optional[str] = None,
    ) -> Optional[int]:
        """Insert a proposal into kg_api.annealing_proposals; return its id."""
        # Autonomous mode: born 'approved' (no human-raceable pending window).
        # hitl mode: born 'pending', awaiting human review.
        autonomous = self.automation_level == "autonomous"
        status = "approved" if autonomous else "pending"
        reviewed_by = "annealing_worker" if autonomous else None
        reviewed_at = datetime.now(timezone.utc) if autonomous else None
        reviewer_notes = "auto-approved (autonomous mode)" if autonomous else None

        try:
            conn = self.client.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO kg_api.annealing_proposals
                        (proposal_type, proposal_kind, params,
                         ontology_name, anchor_concept_id,
                         target_ontology, reasoning, mass_score, coherence_score,
                         protection_score, created_at_epoch,
                         suggested_name, suggested_description,
                         status, reviewed_by, reviewed_at, reviewer_notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        proposal_type, proposal_kind, Json(params or {}),
                        ontology_name, anchor_concept_id,
                        target_ontology, reasoning, mass_score, coherence_score,
                        protection_score, epoch,
                        suggested_name, suggested_description,
                        status, reviewed_by, reviewed_at, reviewer_notes,
                    ))
                    row = cur.fetchone()
                    conn.commit()
                    proposal_id = row[0] if row else None
                    logger.info(
                        f"Stored {proposal_type} proposal #{proposal_id} "
                        f"for '{ontology_name}' (status={status})"
                    )
                    return proposal_id
            finally:
                self.client.pool.putconn(conn)
        except Exception as e:
            logger.error(f"Failed to store proposal: {e}")
            return None

    # =========================================================================
    # Ecological Snapshot (ADR-200 Phase 4)
    # =========================================================================

    def _get_ecological_snapshot(
        self, all_scores: List[Dict]
    ) -> Dict[str, Any]:
        """
        Compute ecological ratio metrics + Bezier-derived control
        recommendations for the annealing cycle (#249 Part 1, ADR-206 §Phase 3).

        Observational only — the `pressure_recommendation` block is logged
        and returned so operators can eyeball calibration. Part 2 (#249,
        commit 9 of this PR) turns recommendations into ADJUST_CONTROL
        proposals when they diverge from current settings beyond a deadband.

        Returns:
            {
              total_ontologies, total_concepts, avg_concepts_per_ontology,
              pressure_score, pressure_zone,
              pressure_recommendation: {control_key: {current, recommended, zone}}
            }
        """
        total_ontologies = len(all_scores)
        total_concepts = sum(s.get("concept_count", 0) for s in all_scores)
        avg = total_concepts / total_ontologies if total_ontologies > 0 else 0

        pressure_score, pressure_zone = _ecological_pressure(avg)
        pressure_recommendation = _build_pressure_recommendation(
            pressure_score=pressure_score,
            current_options=self._load_phase3_controls(),
        )

        return {
            "total_ontologies": total_ontologies,
            "total_concepts": total_concepts,
            "avg_concepts_per_ontology": avg,
            "pressure_score": pressure_score,
            "pressure_zone": pressure_zone,
            "pressure_recommendation": pressure_recommendation,
        }

    # Below this absolute delta the recommendation is treated as noise —
    # emitting an ADJUST_CONTROL proposal for ±1 epoch every cycle would
    # spam the queue and burn human review attention. Operators tuning by
    # hand are already in the same ballpark as Bezier; only diverge when
    # the curve has something meaningful to say.
    _ADJUST_CONTROL_DEADBAND = 2

    def _emit_control_proposals(
        self,
        recommendation: Dict[str, Dict[str, Any]],
        pressure_score: float,
        pressure_zone: str,
        epoch: int,
    ) -> List[int]:
        """
        Synthesize ADJUST_CONTROL proposals when pressure recommendations
        exceed the deadband AND no open ADJUST_CONTROL proposal already
        targets the same control_key.

        Returns the list of stored proposal IDs (empty list when nothing
        crosses the deadband).
        """
        if not recommendation:
            return []

        open_keys = self._get_open_control_keys()
        emitted: List[int] = []

        for control_key, block in recommendation.items():
            delta = block.get("delta", 0)
            if abs(delta) < self._ADJUST_CONTROL_DEADBAND:
                continue
            if control_key in open_keys:
                logger.debug(
                    f"Skipping ADJUST_CONTROL for '{control_key}': open proposal exists"
                )
                continue

            defense = (
                f"Pressure score {pressure_score:.2f} ({pressure_zone}); "
                f"Bezier-derived recommendation diverges from current "
                f"{block['current']} by {delta:+d}."
            )
            params = {
                "control_key": control_key,
                "current_value": str(block["current"]),
                "recommended_value": str(block["recommended"]),
                "defense": defense,
            }
            proposal_id = self._store_proposal(
                proposal_type="ADJUST_CONTROL",
                ontology_name="(control)",
                reasoning=defense,
                epoch=epoch,
                proposal_kind="control",
                params=params,
            )
            if proposal_id:
                emitted.append(proposal_id)
                logger.info(
                    f"Emitted ADJUST_CONTROL proposal #{proposal_id} for "
                    f"'{control_key}' ({block['current']} → {block['recommended']})"
                )

        return emitted

    def _get_open_control_keys(self) -> Set[str]:
        """Return control_keys with an in-flight ADJUST_CONTROL proposal."""
        keys: Set[str] = set()
        try:
            conn = self.client.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT params->>'control_key'
                        FROM kg_api.annealing_proposals
                        WHERE proposal_kind = 'control'
                          AND proposal_type = 'ADJUST_CONTROL'
                          AND status IN ('pending', 'approved', 'executing')
                        """
                    )
                    for (control_key,) in cur.fetchall():
                        if control_key:
                            keys.add(control_key)
            finally:
                self.client.pool.putconn(conn)
        except Exception as exc:
            logger.warning(f"Could not load open control proposals: {exc}")
        return keys

    def _load_phase3_controls(self) -> Dict[str, str]:
        """Snapshot the tuneable Phase-3 options keyed in the recommendation."""
        keys = (
            "failure_cooldown_epochs",
            "max_proposals_per_cycle",
            "min_activity_for_cycle",
        )
        out: Dict[str, str] = {}
        try:
            conn = self.client.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT key, value FROM kg_api.annealing_options WHERE key = ANY(%s)",
                        (list(keys),),
                    )
                    for key, value in cur.fetchall():
                        out[key] = value
            finally:
                self.client.pool.putconn(conn)
        except Exception as exc:
            logger.warning(f"Could not load Phase-3 controls for snapshot: {exc}")
        return out

    def _record_pressure_snapshot(
        self,
        ecological: Dict[str, Any],
        epoch: int,
    ) -> None:
        """
        Append one row to kg_api.annealing_pressure_history (#249).

        Captures the post-cycle ecological state plus the Bezier-derived
        recommendations so the admin UI can render current state and the
        trend chart can read history. Failures are logged and swallowed —
        a snapshot-write hiccup must never wedge the annealing cycle.
        """
        try:
            conn = self.client.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO kg_api.annealing_pressure_history
                            (epoch, total_ontologies, total_concepts,
                             avg_concepts_per_ontology, pressure_score,
                             pressure_zone, pressure_recommendation)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            epoch,
                            ecological["total_ontologies"],
                            ecological["total_concepts"],
                            ecological["avg_concepts_per_ontology"],
                            ecological["pressure_score"],
                            ecological["pressure_zone"],
                            Json(ecological["pressure_recommendation"]),
                        ),
                    )
                    conn.commit()
            finally:
                self.client.pool.putconn(conn)
        except Exception as exc:
            logger.warning(f"Could not persist pressure snapshot: {exc}")


def _ecological_pressure(avg_concepts_per_ontology: float) -> Tuple[float, str]:
    """
    Map current ecological ratio to a pressure score in [0,1] + zone label.

    Pressure rises monotonically as the average drifts from the comfort
    band toward emergency. Below `_PRESSURE_COMFORT_MIN` the ratio also
    contributes pressure (over-fragmented graphs need cycle-throttling
    too), but the recommended *direction* of adjustment differs from
    over-pressure — see `_build_pressure_recommendation`.

    Returns:
        (pressure_score in [0,1], zone in {"comfort", "watch", "tight",
        "over", "emergency"})
    """
    if avg_concepts_per_ontology <= 0:
        return (0.0, "comfort")

    if _PRESSURE_COMFORT_MIN <= avg_concepts_per_ontology <= _PRESSURE_COMFORT_MAX:
        return (0.0, "comfort")

    if avg_concepts_per_ontology < _PRESSURE_COMFORT_MIN:
        position = (_PRESSURE_COMFORT_MIN - avg_concepts_per_ontology) / _PRESSURE_COMFORT_MIN
        score = _PRESSURE_CURVE.get_y_for_x(max(0.0, min(1.0, position)))
        zone = "tight" if score < 0.5 else "over"
        return (score, zone)

    if avg_concepts_per_ontology >= _PRESSURE_EMERGENCY:
        return (1.0, "emergency")

    position = (avg_concepts_per_ontology - _PRESSURE_COMFORT_MAX) / (
        _PRESSURE_EMERGENCY - _PRESSURE_COMFORT_MAX
    )
    score = _PRESSURE_CURVE.get_y_for_x(max(0.0, min(1.0, position)))
    if score < 0.3:
        zone = "watch"
    elif score < 0.7:
        zone = "tight"
    elif score < 0.9:
        zone = "over"
    else:
        zone = "emergency"
    return (score, zone)


def _build_pressure_recommendation(
    pressure_score: float,
    current_options: Dict[str, str],
) -> Dict[str, Dict[str, Any]]:
    """
    Derive recommended values for each Phase-3 tuneable knob.

    Heuristics:
      - failure_cooldown_epochs scales UP with pressure — back off harder
        on the same (anchor, action, target) triple when the graph is
        already in distress.
      - max_proposals_per_cycle scales DOWN with pressure — throttle
        decision volume when too much is happening.
      - min_activity_for_cycle scales UP modestly with pressure — raise
        the no-op floor so quiet cycles do not run when the graph is
        already churning.

    Per-control deadband logic is *not* applied here; commit 9
    (ADJUST_CONTROL) gates emission of proposals against the deadband.
    """
    def _parse(key: str, default: int) -> int:
        raw = current_options.get(key)
        try:
            return int(raw) if raw is not None else default
        except (TypeError, ValueError):
            return default

    cur_cooldown = _parse("failure_cooldown_epochs", 5)
    cur_max_prop = _parse("max_proposals_per_cycle", 10)
    cur_min_act = _parse("min_activity_for_cycle", 1)

    recommended_cooldown = round(5 + pressure_score * 10)
    recommended_max_prop = max(2, round(10 - pressure_score * 6))
    recommended_min_act = round(1 + pressure_score * 2)

    return {
        "failure_cooldown_epochs": {
            "current": cur_cooldown,
            "recommended": recommended_cooldown,
            "delta": recommended_cooldown - cur_cooldown,
        },
        "max_proposals_per_cycle": {
            "current": cur_max_prop,
            "recommended": recommended_max_prop,
            "delta": recommended_max_prop - cur_max_prop,
        },
        "min_activity_for_cycle": {
            "current": cur_min_act,
            "recommended": recommended_min_act,
            "delta": recommended_min_act - cur_min_act,
        },
    }
