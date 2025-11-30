"""
Semantic Path Gradient Analysis
Experimental implementation for analyzing reasoning chains in embedding space

Based on Large Concept Models (Meta, 2024) and path-constrained retrieval research.
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from numpy.typing import NDArray


@dataclass
class Concept:
    """Concept with embedding vector"""
    concept_id: str
    label: str
    embedding: NDArray[np.float32]
    grounding: float = 0.0


@dataclass
class PathMetrics:
    """Gradient-based metrics for a reasoning path"""
    total_distance: float
    avg_step_size: float
    step_variance: float
    coherence_score: float
    curvature_angles: List[float]
    avg_curvature: float
    weak_links: List[Dict]
    quality_rating: str


class SemanticPathAnalyzer:
    """Analyzes semantic properties of graph paths using gradient calculations"""

    def __init__(self, weak_link_threshold: float = 2.0):
        """
        Args:
            weak_link_threshold: Standard deviations above mean to flag weak links
        """
        self.weak_link_threshold = weak_link_threshold

    def semantic_gradient(self, emb1: NDArray, emb2: NDArray) -> NDArray:
        """
        Calculate semantic gradient (directional derivative) between two embeddings

        Args:
            emb1: Source embedding vector
            emb2: Target embedding vector

        Returns:
            Gradient vector pointing from emb1 to emb2
        """
        return emb2 - emb1

    def gradient_magnitude(self, gradient: NDArray) -> float:
        """
        Calculate magnitude of semantic gradient (L2 norm)

        Args:
            gradient: Gradient vector

        Returns:
            Scalar magnitude
        """
        return float(np.linalg.norm(gradient))

    def path_curvature(self, grad1: NDArray, grad2: NDArray) -> Tuple[NDArray, float]:
        """
        Calculate curvature between two consecutive gradients

        Args:
            grad1: First gradient vector
            grad2: Second gradient vector

        Returns:
            Tuple of (curvature vector, angular change in radians)
        """
        # Curvature vector (second derivative)
        curvature_vec = grad2 - grad1

        # Angular change (cosine similarity)
        cos_sim = np.dot(grad1, grad2) / (
            np.linalg.norm(grad1) * np.linalg.norm(grad2) + 1e-8
        )
        angle = float(np.arccos(np.clip(cos_sim, -1.0, 1.0)))

        return curvature_vec, angle

    def analyze_path(self, concepts: List[Concept]) -> PathMetrics:
        """
        Comprehensive gradient analysis of a reasoning path

        Args:
            concepts: Ordered list of concepts forming a path

        Returns:
            PathMetrics with all calculated metrics
        """
        if len(concepts) < 2:
            raise ValueError("Path must contain at least 2 concepts")

        embeddings = [c.embedding for c in concepts]

        # Calculate gradients between consecutive concepts
        gradients = [
            self.semantic_gradient(embeddings[i], embeddings[i + 1])
            for i in range(len(embeddings) - 1)
        ]

        # Step sizes (gradient magnitudes)
        step_sizes = [self.gradient_magnitude(g) for g in gradients]

        # Calculate curvature (only possible with 3+ concepts)
        curvature_angles = []
        if len(gradients) >= 2:
            for i in range(len(gradients) - 1):
                _, angle = self.path_curvature(gradients[i], gradients[i + 1])
                curvature_angles.append(angle)

        # Identify weak links (outlier distances)
        mean_dist = np.mean(step_sizes)
        std_dist = np.std(step_sizes)
        weak_links = []

        for i, dist in enumerate(step_sizes):
            if dist > mean_dist + self.weak_link_threshold * std_dist:
                severity = (dist - mean_dist) / (std_dist + 1e-8)
                weak_links.append(
                    {
                        "step_index": i,
                        "source": concepts[i].label,
                        "target": concepts[i + 1].label,
                        "distance": dist,
                        "severity_sigma": severity,
                    }
                )

        # Path coherence (1 - normalized variance)
        coherence = 1.0 - (np.var(step_sizes) / (mean_dist + 1e-8))

        # Quality rating
        quality = self._rate_path_quality(coherence, curvature_angles, weak_links)

        return PathMetrics(
            total_distance=sum(step_sizes),
            avg_step_size=mean_dist,
            step_variance=np.var(step_sizes),
            coherence_score=coherence,
            curvature_angles=curvature_angles,
            avg_curvature=np.mean(curvature_angles) if curvature_angles else 0.0,
            weak_links=weak_links,
            quality_rating=quality,
        )

    def _rate_path_quality(
        self, coherence: float, curvatures: List[float], weak_links: List[Dict]
    ) -> str:
        """Rate overall path quality based on metrics"""
        if coherence > 0.8 and len(weak_links) == 0:
            avg_curv = np.mean(curvatures) if curvatures else 0
            if avg_curv < 0.5:  # Low curvature (smooth)
                return "Excellent"
            return "Good"
        elif coherence > 0.6 and len(weak_links) <= 1:
            return "Moderate"
        else:
            return "Poor"

    def find_missing_links(
        self,
        source: Concept,
        target: Concept,
        candidate_pool: List[Concept],
        gap_threshold: float = 0.5,
        improvement_threshold: float = 0.8,
    ) -> List[Tuple[Concept, float]]:
        """
        Find concepts that could bridge a large semantic gap

        Args:
            source: Starting concept
            target: Ending concept
            candidate_pool: Pool of concepts to search for bridges
            gap_threshold: Minimum gap size to trigger search
            improvement_threshold: Max ratio of detour distance to direct distance

        Returns:
            List of (bridging_concept, improvement_factor) tuples
        """
        # Calculate direct gap
        direct_gap = self.gradient_magnitude(
            self.semantic_gradient(source.embedding, target.embedding)
        )

        if direct_gap < gap_threshold:
            return []  # Gap is small enough, no bridge needed

        bridges = []

        for candidate in candidate_pool:
            # Skip if candidate is source or target
            if candidate.concept_id in (source.concept_id, target.concept_id):
                continue

            # Calculate detour distance
            dist_to_candidate = self.gradient_magnitude(
                self.semantic_gradient(source.embedding, candidate.embedding)
            )
            dist_from_candidate = self.gradient_magnitude(
                self.semantic_gradient(candidate.embedding, target.embedding)
            )
            detour_distance = dist_to_candidate + dist_from_candidate

            # Check if detour is acceptable
            if detour_distance < direct_gap * improvement_threshold:
                improvement = (direct_gap - detour_distance) / direct_gap
                bridges.append((candidate, improvement))

        # Sort by improvement (best first)
        bridges.sort(key=lambda x: x[1], reverse=True)

        return bridges

    def calculate_semantic_momentum(
        self, path: List[Concept], next_concept: Optional[Concept] = None
    ) -> Tuple[NDArray, Optional[float]]:
        """
        Calculate semantic momentum along a path and optionally check alignment with next concept

        Args:
            path: List of concepts (minimum 2)
            next_concept: Optional next concept to check alignment

        Returns:
            Tuple of (momentum_vector, alignment_score)
            alignment_score is None if next_concept not provided
        """
        if len(path) < 2:
            raise ValueError("Path must contain at least 2 concepts")

        # Calculate all gradients
        gradients = [
            self.semantic_gradient(path[i].embedding, path[i + 1].embedding)
            for i in range(len(path) - 1)
        ]

        # Momentum is the average gradient direction
        momentum = np.mean(gradients, axis=0)

        alignment = None
        if next_concept is not None:
            # Calculate gradient to next concept
            next_gradient = self.semantic_gradient(
                path[-1].embedding, next_concept.embedding
            )

            # Cosine similarity between momentum and next gradient
            cos_sim = np.dot(momentum, next_gradient) / (
                np.linalg.norm(momentum) * np.linalg.norm(next_gradient) + 1e-8
            )
            alignment = float(cos_sim)

        return momentum, alignment

    def track_concept_drift(
        self, embeddings_over_time: List[Tuple[str, NDArray]]
    ) -> List[Dict]:
        """
        Track how concept embedding changes over time

        Args:
            embeddings_over_time: List of (timestamp, embedding) tuples in chronological order

        Returns:
            List of drift measurements
        """
        if len(embeddings_over_time) < 2:
            return []

        drift_history = []
        initial_embedding = embeddings_over_time[0][1]

        for i in range(1, len(embeddings_over_time)):
            prev_timestamp, prev_emb = embeddings_over_time[i - 1]
            curr_timestamp, curr_emb = embeddings_over_time[i]

            # Calculate drift from previous state
            drift = self.semantic_gradient(prev_emb, curr_emb)
            drift_magnitude = self.gradient_magnitude(drift)

            # Calculate cumulative drift from initial state
            cumulative_drift = self.gradient_magnitude(
                self.semantic_gradient(initial_embedding, curr_emb)
            )

            drift_history.append(
                {
                    "timestamp": curr_timestamp,
                    "drift_from_previous": drift_magnitude,
                    "cumulative_drift": cumulative_drift,
                    "drift_direction": drift / (drift_magnitude + 1e-8),
                }
            )

        return drift_history


# Convenience functions for quick analysis

def quick_path_analysis(embeddings: List[NDArray]) -> Dict:
    """
    Quick analysis of embedding path without full Concept objects

    Args:
        embeddings: List of embedding vectors

    Returns:
        Dictionary with basic metrics
    """
    concepts = [
        Concept(concept_id=f"c{i}", label=f"Concept {i}", embedding=emb)
        for i, emb in enumerate(embeddings)
    ]

    analyzer = SemanticPathAnalyzer()
    metrics = analyzer.analyze_path(concepts)

    return {
        "coherence": metrics.coherence_score,
        "avg_step": metrics.avg_step_size,
        "quality": metrics.quality_rating,
        "weak_links": len(metrics.weak_links),
    }


def cosine_similarity(vec1: NDArray, vec2: NDArray) -> float:
    """Calculate cosine similarity between two vectors"""
    dot_product = np.dot(vec1, vec2)
    norm_product = np.linalg.norm(vec1) * np.linalg.norm(vec2)
    return float(dot_product / (norm_product + 1e-8))
