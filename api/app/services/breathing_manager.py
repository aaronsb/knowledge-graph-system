"""
Breathing Manager — orchestrates ontology breathing cycles (ADR-200 Phase 3b).

Follows the vocabulary consolidation pattern:
score all → identify candidates → LLM judgment → store proposals.

Phase 3b is proposal-only (HITL). Phase 4 adds execution.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from api.app.lib.ontology_scorer import OntologyScorer
from api.app.lib.breathing_evaluator import (
    llm_evaluate_promotion,
    llm_evaluate_demotion,
    PromotionDecision,
    DemotionDecision,
)

logger = logging.getLogger(__name__)


class BreathingManager:
    """
    Runs breathing cycles: score, identify candidates, evaluate, propose.

    Does NOT execute proposals — that's Phase 4.
    """

    def __init__(self, age_client, scorer: OntologyScorer, ai_provider=None):
        self.client = age_client
        self.scorer = scorer
        self.ai_provider = ai_provider

    async def run_breathing_cycle(
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
        Run a full breathing cycle.

        1. Score all ontologies
        2. Recompute centroids
        3. Derive ontology-to-ontology edges (Phase 5)
        4. Identify demotion candidates (low protection)
        5. Identify promotion candidates (high-degree concepts)
        5. LLM evaluation (unless dry_run)
        6. Store proposals

        Args:
            demotion_threshold: Protection score below which to consider demotion
            promotion_min_degree: Minimum concept degree for promotion candidacy
            max_proposals: Cap on proposals per cycle
            dry_run: If True, identify candidates but don't call LLM or store

        Returns:
            Cycle result summary
        """
        global_epoch = self.client.get_current_epoch()
        logger.info(f"Breathing cycle starting at epoch {global_epoch}")

        # 1. Score all ontologies
        all_scores = self.scorer.score_all_ontologies()
        logger.info(f"Scored {len(all_scores)} ontologies")

        # 2. Recompute centroids
        centroids_updated = self.scorer.recompute_all_centroids()
        logger.info(f"Updated {centroids_updated} ontology centroids")

        # 3. Derive ontology-to-ontology edges (ADR-200 Phase 5)
        edge_result = {"edges_created": 0, "edges_deleted": 0}
        if derive_edges:
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

        # 5. Evaluate and store proposals
        proposals_generated = 0
        remaining = max_proposals

        # Demotions first (more impactful)
        for candidate in demotion_candidates[:remaining]:
            proposal = await self._evaluate_and_store_demotion(candidate, global_epoch)
            if proposal:
                proposals_generated += 1
                remaining -= 1
                if remaining <= 0:
                    break

        # Then promotions
        for candidate in promotion_candidates[:remaining]:
            proposal = await self._evaluate_and_store_promotion(candidate, global_epoch)
            if proposal:
                proposals_generated += 1
                remaining -= 1
                if remaining <= 0:
                    break

        logger.info(
            f"Breathing cycle complete: {proposals_generated} proposals, "
            f"{len(all_scores)} scored, {centroids_updated} centroids, "
            f"{edge_result.get('edges_created', 0)} edges"
        )

        return {
            "proposals_generated": proposals_generated,
            "demotion_candidates": len(demotion_candidates),
            "promotion_candidates": len(promotion_candidates),
            "scores_updated": len(all_scores),
            "centroids_updated": centroids_updated,
            "edges_created": edge_result.get("edges_created", 0),
            "edges_deleted": edge_result.get("edges_deleted", 0),
            "cycle_epoch": global_epoch,
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
    ) -> Optional[int]:
        """Store a proposal in the breathing_proposals table. Returns proposal ID."""
        try:
            conn = self.client.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO kg_api.breathing_proposals
                        (proposal_type, ontology_name, anchor_concept_id,
                         target_ontology, reasoning, mass_score, coherence_score,
                         protection_score, created_at_epoch)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        proposal_type, ontology_name, anchor_concept_id,
                        target_ontology, reasoning, mass_score, coherence_score,
                        protection_score, epoch,
                    ))
                    row = cur.fetchone()
                    conn.commit()
                    proposal_id = row[0] if row else None
                    logger.info(
                        f"Stored {proposal_type} proposal #{proposal_id} "
                        f"for '{ontology_name}'"
                    )
                    return proposal_id
            finally:
                self.client.pool.putconn(conn)
        except Exception as e:
            logger.error(f"Failed to store proposal: {e}")
            return None
