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
