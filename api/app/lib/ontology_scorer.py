"""
Ontology Scoring Service (ADR-200 Phase 3a).

Computes mass, coherence, exposure, and protection scores for ontologies.
Pure computation — takes AGE client, returns scores.

Scoring algorithms:
- Mass: Michaelis-Menten saturation of ontology statistics (reuses ADR-044 pattern)
- Coherence: mean pairwise cosine similarity of concept embeddings
- Exposure: epoch delta with adjacency weighting
- Protection: mass × coherence minus exposure pressure

References:
    - ADR-200: Breathing Ontologies
    - ADR-044: Dynamic Grounding (Michaelis-Menten saturation)
    - ADR-063: Semantic Diversity (Gini-Simpson index)
"""

import logging
import math
from typing import Dict, Any, List, Optional
from itertools import combinations

import numpy as np

logger = logging.getLogger(__name__)


class OntologyScorer:
    """
    Computes breathing scores for ontologies.

    All scoring methods are deterministic given the same inputs.
    The AGE client is used only for data retrieval, not mutation.
    """

    def __init__(self, age_client):
        self.client = age_client

    # =========================================================================
    # Individual Score Calculations
    # =========================================================================

    def calculate_mass(self, stats: Dict[str, Any]) -> float:
        """
        Calculate mass score using Michaelis-Menten saturation.

        Reuses the pattern from ConfidenceAnalyzer._calculate_score() (ADR-044).
        Each component normalized to roughly 0-1 range, then saturated.

        Composite = concept_count/50 + source_count/20 + internal_rels/50
        Mass = composite / (composite + k), k=2.0

        Args:
            stats: Dictionary from get_ontology_stats()

        Returns:
            float 0.0-1.0 (mass score)
        """
        concept_count = stats.get("concept_count", 0)
        source_count = stats.get("source_count", 0)
        internal_rels = stats.get("internal_relationship_count", 0)

        # Composite with normalization factors tuned for typical ontology sizes
        composite = (
            concept_count / 50.0 +    # 50 concepts → 1.0 contribution
            source_count / 20.0 +     # 20 sources → 1.0 contribution
            internal_rels / 50.0      # 50 internal relationships → 1.0
        )

        # Half-saturation constant: when composite = k, score = 0.5
        k = 2.0

        # Michaelis-Menten saturation with diminishing returns
        if composite <= 0:
            return 0.0
        return composite / (composite + k)

    def calculate_coherence(self, ontology_name: str) -> float:
        """
        Calculate coherence as mean pairwise cosine similarity.

        High coherence = concepts are semantically similar (tight domain).
        Low coherence = concepts are diverse (broad/unfocused domain).

        Samples up to 100 concept embeddings and computes the average pairwise
        cosine similarity. Inspired by the diversity patterns in ADR-063.

        Args:
            ontology_name: Ontology name

        Returns:
            float 0.0-1.0 (coherence score). Returns 0.0 if < 2 concepts.
        """
        concepts = self.client.get_ontology_concept_embeddings(
            ontology_name, limit=100
        )

        if len(concepts) < 2:
            return 0.0

        embeddings = []
        for c in concepts:
            emb = c.get("embedding")
            if emb is not None:
                embeddings.append(np.array(emb, dtype=np.float64))

        if len(embeddings) < 2:
            return 0.0

        # Pairwise cosine similarity
        similarities = []
        for emb1, emb2 in combinations(embeddings, 2):
            sim = self._cosine_similarity(emb1, emb2)
            similarities.append(sim)

        if not similarities:
            return 0.0

        # Coherence = mean similarity (not 1-diversity, since we want
        # high coherence = high similarity = tight domain)
        avg_similarity = float(np.mean(similarities))
        return max(0.0, min(1.0, avg_similarity))

    def calculate_exposure(self, ontology_name: str) -> Dict[str, Any]:
        """
        Calculate exposure as epoch delta with adjacency weighting.

        raw_exposure = global_epoch - creation_epoch (normalized)
        weighted_exposure = raw_exposure adjusted by adjacent ontology activity

        Args:
            ontology_name: Ontology name

        Returns:
            {raw_exposure, weighted_exposure, adjacent_ontologies}
        """
        node = self.client.get_ontology_node(ontology_name)
        if not node:
            return {
                "raw_exposure": 0.0,
                "weighted_exposure": 0.0,
                "adjacent_ontologies": [],
            }

        creation_epoch = node.get("creation_epoch", 0) or 0
        global_epoch = self.client.get_current_epoch()

        # Raw exposure: normalized epoch delta
        # Uses sigmoid-like normalization: exposure approaches 1.0 as age increases
        epoch_delta = max(0, global_epoch - creation_epoch)
        # Half-life at 50 epochs — after 50 ingestion events, exposure = 0.5
        raw_exposure = epoch_delta / (epoch_delta + 50.0) if epoch_delta > 0 else 0.0

        # Adjacency weighting from cross-ontology affinity
        affinities = self.client.get_cross_ontology_affinity(ontology_name, limit=5)
        adjacent_ontologies = []
        weighted_sum = 0.0

        for aff in affinities:
            other_name = aff.get("other_ontology", "")
            affinity_score = aff.get("affinity_score", 0.0)

            # Get other ontology's epoch to measure its activity
            other_node = self.client.get_ontology_node(other_name)
            if other_node:
                other_epoch = other_node.get("creation_epoch", 0) or 0
                other_delta = max(0, global_epoch - other_epoch)
                # Weight: affinity × other's activity level
                other_activity = other_delta / (other_delta + 50.0) if other_delta > 0 else 0.0
                weighted_sum += affinity_score * other_activity
                adjacent_ontologies.append(other_name)

        # Weighted exposure blends raw age with neighbor activity
        # Adjacent active ontologies with high affinity increase pressure
        weighted_exposure = raw_exposure + (weighted_sum * 0.3)
        weighted_exposure = min(1.0, weighted_exposure)

        return {
            "raw_exposure": round(raw_exposure, 4),
            "weighted_exposure": round(weighted_exposure, 4),
            "adjacent_ontologies": adjacent_ontologies,
        }

    def calculate_protection(
        self,
        mass: float,
        coherence: float,
        weighted_exposure: float,
    ) -> float:
        """
        Calculate protection score as mass × coherence minus exposure pressure.

        protection = sigmoid(mass × coherence) - exposure_pressure(weighted_exposure)

        Ontologies with high mass and coherence are well-protected.
        Exposure erodes protection over time.
        Protection can go negative for severely failing ontologies.

        Args:
            mass: Mass score 0.0-1.0
            coherence: Coherence score 0.0-1.0
            weighted_exposure: Weighted exposure 0.0-1.0

        Returns:
            float (can be negative for severely failed ontologies)
        """
        # Combined strength from mass and coherence
        # Using sigmoid: maps product [0,1] to [0.5,~0.73] range
        strength = mass * coherence
        # Rescale sigmoid to 0-1 range: sigmoid(x*4-2) maps [0,1] → [0.12, 0.88]
        sigmoid_input = strength * 4.0 - 2.0
        strength_score = 1.0 / (1.0 + math.exp(-sigmoid_input))

        # Exposure pressure: increases with weighted exposure
        # Lower pressure initially, ramps up above 0.5
        exposure_pressure = weighted_exposure * 0.6

        protection = strength_score - exposure_pressure
        return round(protection, 4)

    # =========================================================================
    # Composite Scoring
    # =========================================================================

    def score_ontology(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Run full scoring pipeline for a single ontology and cache results.

        Args:
            name: Ontology name

        Returns:
            Dictionary with all scores, or None if ontology not found
        """
        stats = self.client.get_ontology_stats(name)
        if stats is None:
            return None

        mass = self.calculate_mass(stats)
        coherence = self.calculate_coherence(name)
        exposure = self.calculate_exposure(name)
        protection = self.calculate_protection(
            mass, coherence, exposure["weighted_exposure"]
        )

        global_epoch = self.client.get_current_epoch()

        scores = {
            "ontology": name,
            "mass_score": round(mass, 4),
            "coherence_score": round(coherence, 4),
            "raw_exposure": exposure["raw_exposure"],
            "weighted_exposure": exposure["weighted_exposure"],
            "protection_score": protection,
            "last_evaluated_epoch": global_epoch,
            "concept_count": stats.get("concept_count", 0),
        }

        # Cache scores on the Ontology node
        self.client.update_ontology_scores(
            name=name,
            mass=scores["mass_score"],
            coherence=scores["coherence_score"],
            protection=scores["protection_score"],
            raw_exposure=scores["raw_exposure"],
            weighted_exposure=scores["weighted_exposure"],
            epoch=global_epoch,
        )

        return scores

    def score_all_ontologies(self) -> List[Dict[str, Any]]:
        """
        Run full scoring pipeline for all ontologies.

        Returns:
            List of score dictionaries for each ontology
        """
        nodes = self.client.list_ontology_nodes()
        all_scores = []

        for node in nodes:
            name = node.get("name")
            if not name:
                continue
            try:
                scores = self.score_ontology(name)
                if scores:
                    all_scores.append(scores)
            except Exception as e:
                logger.error(f"Failed to score ontology {name}: {e}")

        return all_scores

    # =========================================================================
    # Centroid Recomputation
    # See ADR-200 §Phase 3 "Centroid Recomputation (Weighted Top-K)"
    # =========================================================================

    def recompute_centroid(
        self,
        ontology_name: str,
        top_k: int = 30,
        drift_threshold: float = 0.99,
    ) -> bool:
        """
        Recompute ontology embedding as mass-weighted centroid of top-K concepts.

        Replaces the initial name-based embedding with one reflecting the
        ontology's actual semantic position. Only writes if the centroid has
        drifted beyond the threshold (hysteresis check).

        Args:
            ontology_name: Ontology to recompute
            top_k: Number of top concepts by degree to use
            drift_threshold: Cosine similarity threshold — skip write if above

        Returns:
            True if embedding was updated, False if skipped or insufficient data
        """
        # 1. Get top concepts by degree (Elder selection)
        ranking = self.client.get_concept_degree_ranking(ontology_name, limit=top_k)
        if not ranking or len(ranking) < 2:
            logger.debug(f"Centroid skip for {ontology_name}: insufficient concepts")
            return False

        # 2. Get their embeddings
        elder_ids = {r["concept_id"] for r in ranking}
        all_embeddings = self.client.get_ontology_concept_embeddings(
            ontology_name, limit=top_k * 2  # fetch extra in case of filter
        )

        # Match embeddings to ranked concepts
        elders = []
        for emb_data in all_embeddings:
            if emb_data["concept_id"] in elder_ids:
                embedding = emb_data.get("embedding")
                if embedding is not None:
                    # Find the degree for weighting
                    degree = next(
                        (r["degree"] for r in ranking
                         if r["concept_id"] == emb_data["concept_id"]),
                        1
                    )
                    elders.append((np.array(embedding, dtype=np.float64), degree))

        if len(elders) < 2:
            logger.debug(f"Centroid skip for {ontology_name}: insufficient embeddings")
            return False

        # 3. Weighted average by degree
        weighted_sum = np.zeros(len(elders[0][0]), dtype=np.float64)
        total_weight = 0.0

        for embedding, degree in elders:
            weight = float(max(degree, 1))
            weighted_sum += embedding * weight
            total_weight += weight

        new_centroid = weighted_sum / total_weight
        norm = np.linalg.norm(new_centroid)
        if norm > 0:
            new_centroid = new_centroid / norm

        # 4. Hysteresis: check drift from current embedding
        current_node = self.client.get_ontology_node(ontology_name)
        if current_node:
            current_emb = current_node.get("embedding")
            if current_emb is not None:
                current_vec = np.array(current_emb, dtype=np.float64)
                similarity = float(np.dot(current_vec, new_centroid))
                if similarity > drift_threshold:
                    logger.debug(
                        f"Centroid skip for {ontology_name}: "
                        f"drift {1-similarity:.6f} below threshold"
                    )
                    return False

        # 5. Update
        self.client.update_ontology_embedding(ontology_name, new_centroid.tolist())
        logger.info(f"Centroid updated for '{ontology_name}' from {len(elders)} concepts")
        return True

    def recompute_all_centroids(self, top_k: int = 30) -> int:
        """
        Recompute centroids for all active ontologies.

        Returns:
            Number of ontologies whose centroids were updated
        """
        nodes = self.client.list_ontology_nodes()
        updated = 0
        for node in nodes:
            name = node.get("name")
            if not name:
                continue
            try:
                if self.recompute_centroid(name, top_k=top_k):
                    updated += 1
            except Exception as e:
                logger.error(f"Centroid recomputation failed for {name}: {e}")
        return updated

    # =========================================================================
    # Ontology-to-Ontology Edge Derivation (ADR-200 Phase 5)
    # =========================================================================

    def derive_ontology_edges(
        self,
        overlap_threshold: float = 0.1,
        specializes_threshold: float = 0.3,
    ) -> Dict[str, int]:
        """
        Derive OVERLAPS / SPECIALIZES / GENERALIZES edges between ontologies.

        Algorithm:
          1. For each active ontology, compute affinity to all others
          2. Build bidirectional affinity pairs: (A→B score, B→A score)
          3. Classify each pair:
             - OVERLAPS: both directions >= overlap_threshold
             - SPECIALIZES: A→B high, B→A low (A is a subset of B)
             - GENERALIZES: inverse of SPECIALIZES
          4. Upsert edges, using the higher of the two scores

        Args:
            overlap_threshold: Minimum affinity score for OVERLAPS (default: 0.1)
            specializes_threshold: Minimum asymmetry ratio for
                SPECIALIZES/GENERALIZES — ratio of (high/low) must exceed
                this factor above 1.0 (default: 0.3, meaning 30% asymmetry)

        Returns:
            {edges_created, edges_deleted, overlaps, specializes, generalizes}
        """
        epoch = self.client.get_current_epoch()

        # 1. Get all active ontologies
        nodes = self.client.list_ontology_nodes()
        active = [
            n["name"] for n in nodes
            if n.get("name") and n.get("lifecycle_state", "active") != "frozen"
        ]

        if len(active) < 2:
            return {
                "edges_created": 0, "edges_deleted": 0,
                "overlaps": 0, "specializes": 0, "generalizes": 0,
            }

        # 2. Collect bidirectional affinities: {(A, B): score_A_to_B}
        pair_scores = {}
        for name in active:
            try:
                affinities = self.client.get_cross_ontology_affinity(
                    name, limit=len(active)
                )
                for aff in affinities:
                    other = aff["other_ontology"]
                    pair_scores[(name, other)] = {
                        "score": aff["affinity_score"],
                        "shared": aff["shared_concept_count"],
                        "total": aff["total_concepts"],
                    }
            except Exception as e:
                logger.warning(f"Affinity query failed for {name}: {e}")

        # 3. Delete stale derived edges (full refresh each cycle)
        deleted = self.client.delete_all_derived_ontology_edges()

        # 4. Classify pairs and upsert edges
        processed_pairs = set()
        counts = {"overlaps": 0, "specializes": 0, "generalizes": 0}
        edges_created = 0

        for (a, b), a_to_b in pair_scores.items():
            pair_key = tuple(sorted([a, b]))
            if pair_key in processed_pairs:
                continue
            processed_pairs.add(pair_key)

            b_to_a = pair_scores.get((b, a), {"score": 0.0, "shared": 0, "total": 0})

            score_ab = a_to_b["score"]
            score_ba = b_to_a["score"]

            # Skip if neither direction meets minimum threshold
            if score_ab < overlap_threshold and score_ba < overlap_threshold:
                continue

            # Determine edge type based on asymmetry
            high_score = max(score_ab, score_ba)
            low_score = min(score_ab, score_ba)
            shared = max(a_to_b["shared"], b_to_a["shared"])

            if low_score >= overlap_threshold:
                # Both directions significant — mutual overlap
                # Asymmetry check: is one direction much stronger?
                asymmetry = (high_score - low_score) / high_score if high_score > 0 else 0

                if asymmetry > specializes_threshold:
                    # Asymmetric: the one with higher score is the subset
                    if score_ab > score_ba:
                        # A's concepts are mostly in B → A specializes B
                        self._upsert_edge(a, b, "SPECIALIZES", score_ab, shared, epoch)
                        self._upsert_edge(b, a, "GENERALIZES", score_ba, shared, epoch)
                        counts["specializes"] += 1
                        counts["generalizes"] += 1
                        edges_created += 2
                    else:
                        self._upsert_edge(b, a, "SPECIALIZES", score_ba, shared, epoch)
                        self._upsert_edge(a, b, "GENERALIZES", score_ab, shared, epoch)
                        counts["specializes"] += 1
                        counts["generalizes"] += 1
                        edges_created += 2
                else:
                    # Symmetric enough — bidirectional OVERLAPS
                    self._upsert_edge(a, b, "OVERLAPS", score_ab, shared, epoch)
                    self._upsert_edge(b, a, "OVERLAPS", score_ba, shared, epoch)
                    counts["overlaps"] += 2
                    edges_created += 2
            else:
                # Only one direction significant — the higher side specializes
                if score_ab >= overlap_threshold:
                    self._upsert_edge(a, b, "SPECIALIZES", score_ab, shared, epoch)
                    self._upsert_edge(b, a, "GENERALIZES", score_ba, shared, epoch)
                else:
                    self._upsert_edge(b, a, "SPECIALIZES", score_ba, shared, epoch)
                    self._upsert_edge(a, b, "GENERALIZES", score_ab, shared, epoch)
                counts["specializes"] += 1
                counts["generalizes"] += 1
                edges_created += 2

        logger.info(
            f"Ontology edges derived: {edges_created} created, {deleted} deleted "
            f"(overlaps={counts['overlaps']}, specializes={counts['specializes']}, "
            f"generalizes={counts['generalizes']})"
        )

        return {
            "edges_created": edges_created,
            "edges_deleted": deleted,
            **counts,
        }

    def _upsert_edge(
        self, from_name: str, to_name: str, edge_type: str,
        score: float, shared: int, epoch: int,
    ) -> None:
        """Helper: upsert a single ontology edge, log failures without raising."""
        try:
            self.client.upsert_ontology_edge(
                from_name=from_name,
                to_name=to_name,
                edge_type=edge_type,
                score=score,
                shared_concept_count=shared,
                epoch=epoch,
            )
        except Exception as e:
            logger.error(f"Failed to upsert {edge_type} {from_name}->{to_name}: {e}")

    # =========================================================================
    # Helpers
    # =========================================================================

    @staticmethod
    def _cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Returns:
            float in range [0, 1]
        """
        dot_product = np.dot(emb1, emb2)
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)
        # Clamp to [0, 1] — negative cosine similarity treated as 0 for coherence
        return max(0.0, min(1.0, float(similarity)))
