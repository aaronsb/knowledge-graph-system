"""
Annealing Manager — orchestrates ontology annealing cycles (ADR-200).

Follows the vocabulary consolidation pattern:
score all → identify candidates → LLM judgment → store proposals.

In autonomous mode (default), proposals are auto-approved and executed
by the annealing worker. In hitl mode, proposals wait for human review.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Tuple

from api.app.lib.ontology_scorer import OntologyScorer
from api.app.lib.annealing_evaluator import (
    llm_evaluate_promotion,
    llm_evaluate_demotion,
    PromotionDecision,
    DemotionDecision,
)

logger = logging.getLogger(__name__)


class AnnealingManager:
    """
    Runs annealing cycles: score, identify candidates, evaluate, propose.

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
    ) -> Dict[str, Any]:
        """
        Run a full annealing cycle.

        1. Score all ontologies
        2. Recompute centroids
        3. Derive ontology-to-ontology edges (Phase 5)
        4. Identify demotion candidates (low protection)
        5. Identify promotion candidates (high-degree concepts)
        6. LLM evaluation (unless dry_run)
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
            f"~{ecological['avg_concepts_per_ontology']:.0f} concepts/ontology"
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
            all_scores, demotion_threshold
        )
        logger.info(f"Found {len(demotion_candidates)} demotion candidates")

        # 5. Identify promotion candidates
        promotion_candidates = self._find_promotion_candidates(
            all_scores, promotion_min_degree
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

        # 6. Evaluate and store proposals
        proposal_ids = []
        remaining = max_proposals

        # Demotions first (more impactful)
        for candidate in demotion_candidates[:remaining]:
            proposal_id = await self._evaluate_and_store_demotion(candidate, global_epoch)
            if proposal_id:
                proposal_ids.append(proposal_id)
                remaining -= 1
                if remaining <= 0:
                    break

        # Then promotions
        for candidate in promotion_candidates[:remaining]:
            proposal_id = await self._evaluate_and_store_promotion(candidate, global_epoch)
            if proposal_id:
                proposal_ids.append(proposal_id)
                remaining -= 1
                if remaining <= 0:
                    break

        logger.info(
            f"Annealing cycle complete: {len(proposal_ids)} proposals, "
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
        self, all_scores: List[Dict], threshold: float
    ) -> List[Dict]:
        """Find ontologies with protection below threshold, excluding pinned/frozen."""
        candidates = []
        for scores in all_scores:
            name = scores.get("ontology", "")
            protection = scores.get("protection_score", 1.0)

            if protection >= threshold:
                continue

            # Check lifecycle — skip pinned/frozen
            node = self.client.get_ontology_node(name)
            if not node:
                continue
            lifecycle = node.get("lifecycle_state", "active")
            if lifecycle in ("pinned", "frozen"):
                continue

            candidates.append({
                **scores,
                "lifecycle_state": lifecycle,
            })

        # Sort by protection ascending (worst first)
        candidates.sort(key=lambda c: c.get("protection_score", 0))
        return candidates

    def _find_promotion_candidates(
        self, all_scores: List[Dict], min_degree: int
    ) -> List[Dict]:
        """Find high-degree concepts that could become ontologies."""
        candidates = []
        existing_ontology_names = {
            s["ontology"].lower() for s in all_scores
        }
        # Concepts that already anchor an ontology have been promoted already —
        # exclude them so the graph-driven cycle does not keep re-proposing them.
        anchored_concept_ids = self._get_anchored_concept_ids()

        for scores in all_scores:
            name = scores.get("ontology", "")
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
                        SELECT proposal_type, ontology_name, anchor_concept_id
                        FROM kg_api.annealing_proposals
                        WHERE status IN ('pending', 'approved', 'executing')
                    """)
                    rows = cur.fetchall()
                conn.commit()
            finally:
                self.client.pool.putconn(conn)
            for proposal_type, ontology_name, anchor_concept_id in rows:
                if proposal_type == "promotion" and anchor_concept_id:
                    open_promotions.add(anchor_concept_id)
                elif proposal_type == "demotion" and ontology_name:
                    open_demotions.add(ontology_name)
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
    # LLM Evaluation + Proposal Storage
    # =========================================================================

    async def _evaluate_and_store_demotion(
        self, candidate: Dict, epoch: int
    ) -> Optional[int]:
        """Evaluate a demotion candidate with LLM and store proposal if confirmed."""
        name = candidate["ontology"]

        # Get affinity targets for the LLM
        try:
            affinities = self.client.get_cross_ontology_affinity(name, limit=5)
        except Exception:
            affinities = []

        stats = self.client.get_ontology_stats(name)
        concept_count = stats.get("concept_count", 0) if stats else 0

        if self.ai_provider:
            decision = await llm_evaluate_demotion(
                ontology_name=name,
                mass_score=candidate.get("mass_score", 0),
                coherence_score=candidate.get("coherence_score", 0),
                protection_score=candidate.get("protection_score", 0),
                concept_count=concept_count,
                affinity_targets=affinities,
                ai_provider=self.ai_provider,
            )
        else:
            # No AI provider — propose based on scores alone
            best_target = affinities[0].get("other_ontology") if affinities else None
            decision = DemotionDecision(
                should_demote=True,
                reasoning=f"Protection score {candidate.get('protection_score', 0):.3f} "
                          f"below threshold (no LLM available for evaluation)",
                absorption_target=best_target,
            )

        if not decision.should_demote:
            logger.info(f"Demotion rejected for '{name}': {decision.reasoning}")
            return None

        return self._store_proposal(
            proposal_type="demotion",
            ontology_name=name,
            target_ontology=decision.absorption_target,
            reasoning=decision.reasoning,
            mass_score=candidate.get("mass_score"),
            coherence_score=candidate.get("coherence_score"),
            protection_score=candidate.get("protection_score"),
            epoch=epoch,
        )

    async def _evaluate_and_store_promotion(
        self, candidate: Dict, epoch: int
    ) -> Optional[int]:
        """Evaluate a promotion candidate with LLM and store proposal if confirmed."""
        ontology_name = candidate["ontology"]

        try:
            affinities = self.client.get_cross_ontology_affinity(ontology_name, limit=5)
        except Exception:
            affinities = []

        # Get neighbor labels for context
        try:
            # Use the concept's ontology stats for count
            stats = self.client.get_ontology_stats(ontology_name)
            ontology_concept_count = stats.get("concept_count", 0) if stats else 0
        except Exception:
            ontology_concept_count = 0

        # Get neighbor labels so the LLM can assess coherence
        try:
            neighbor_rows = self.client._execute_cypher(
                """
                MATCH (c:Concept {concept_id: $cid})-[r]-(n:Concept)
                RETURN DISTINCT n.label as label, count(r) as rel_count
                ORDER BY rel_count DESC
                LIMIT 10
                """,
                params={"cid": candidate["concept_id"]},
            )
            top_neighbors = [row["label"] for row in (neighbor_rows or [])]
        except Exception:
            top_neighbors = []

        if self.ai_provider:
            decision = await llm_evaluate_promotion(
                concept_label=candidate["label"],
                concept_description=candidate.get("description", ""),
                degree=candidate["degree"],
                ontology_name=ontology_name,
                ontology_concept_count=ontology_concept_count,
                top_neighbors=top_neighbors,
                affinity_targets=affinities,
                ai_provider=self.ai_provider,
            )
        else:
            decision = PromotionDecision(
                should_promote=True,
                reasoning=f"Degree {candidate['degree']} exceeds threshold "
                          f"(no LLM available for evaluation)",
                suggested_name=candidate["label"],
                suggested_description=f"Domain anchored by concept '{candidate['label']}'",
            )

        if not decision.should_promote:
            logger.info(f"Promotion rejected for '{candidate['label']}': {decision.reasoning}")
            return None

        return self._store_proposal(
            proposal_type="promotion",
            ontology_name=ontology_name,
            anchor_concept_id=candidate["concept_id"],
            reasoning=decision.reasoning,
            epoch=epoch,
            suggested_name=decision.suggested_name,
            suggested_description=decision.suggested_description,
        )

    def _store_proposal(
        self,
        proposal_type: str,
        ontology_name: str,
        reasoning: str,
        epoch: int,
        anchor_concept_id: Optional[str] = None,
        target_ontology: Optional[str] = None,
        mass_score: Optional[float] = None,
        coherence_score: Optional[float] = None,
        protection_score: Optional[float] = None,
        suggested_name: Optional[str] = None,
        suggested_description: Optional[str] = None,
    ) -> Optional[int]:
        """Store a proposal in the annealing_proposals table. Returns proposal ID."""
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
                        (proposal_type, ontology_name, anchor_concept_id,
                         target_ontology, reasoning, mass_score, coherence_score,
                         protection_score, created_at_epoch,
                         suggested_name, suggested_description,
                         status, reviewed_by, reviewed_at, reviewer_notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        proposal_type, ontology_name, anchor_concept_id,
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
        Compute ecological ratio metrics for the annealing cycle.

        Observational only — logged and returned but does not yet adjust
        promotion/demotion thresholds. Threshold feedback is deferred (#249).

        Returns:
            {total_ontologies, total_concepts, avg_concepts_per_ontology}
        """
        total_ontologies = len(all_scores)

        # Sum concept counts already carried in scores (from scorer's stats fetch)
        total_concepts = sum(s.get("concept_count", 0) for s in all_scores)

        avg = total_concepts / total_ontologies if total_ontologies > 0 else 0

        return {
            "total_ontologies": total_ontologies,
            "total_concepts": total_concepts,
            "avg_concepts_per_ontology": avg,
        }
