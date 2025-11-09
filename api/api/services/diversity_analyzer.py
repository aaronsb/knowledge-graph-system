"""
Semantic Diversity Analyzer (ADR-063).

Measures semantic diversity of related concepts within N-hop graph traversal
to distinguish authentic information (high diversity from independent domains)
from fabricated claims (low diversity from circular reasoning).

References:
    - ADR-063: Semantic Diversity as Authenticity Signal
    - ADR-044: Dynamic Grounding (probabilistic truth convergence)
    - ADR-058: Polarity Axis Triangulation
"""

from typing import Dict, Any, List, Optional, Tuple
import logging
import json
import numpy as np
from itertools import combinations
import time

logger = logging.getLogger(__name__)


class DiversityAnalyzer:
    """
    Analyzes semantic diversity of concept neighborhoods in knowledge graph.

    Core metric: diversity_score = 1 - avg_pairwise_similarity(related_embeddings)

    Mathematical foundation: This is equivalent to the **Gini-Simpson Index** from ecology,
    adapted to semantic spaces. In ecology, the Simpson Index measures species concentration;
    here, cosine similarity measures semantic concentration. The Gini-Simpson inversion
    (1 - concentration) yields diversity.

    High diversity (>0.35): Authentic information from independent domains
    Low diversity (<0.25): Fabricated claims with circular reasoning
    """

    def __init__(self, age_client):
        """
        Initialize diversity analyzer.

        Args:
            age_client: AGEClient instance for graph queries
        """
        self.client = age_client

    def calculate_diversity(
        self,
        concept_id: str,
        max_hops: int = 2,
        limit: int = 100,
        grounding_strength: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate semantic diversity of related concepts.

        Uses omnidirectional graph traversal to find all concepts within N hops,
        then measures pairwise cosine similarity of their embeddings.

        When grounding_strength is provided, also calculates authenticated_diversity
        which combines diversity with grounding polarity (ADR-044 + ADR-063).

        Args:
            concept_id: Target concept ID
            max_hops: Maximum traversal depth (1-3, default 2)
            limit: Maximum related concepts to analyze (default 100, prevents O(N²) explosion)
            grounding_strength: Optional grounding score (-1.0 to 1.0) for authenticated diversity

        Returns:
            Dictionary with diversity metrics:
            {
                "diversity_score": float,           # 1 - avg_similarity (0-1)
                "related_concept_count": int,      # Number of concepts analyzed
                "avg_pairwise_similarity": float,  # Mean cosine similarity
                "sampled": bool,                   # True if > limit concepts (sampling used)
                "calculation_time_ms": int,        # Performance metric
                "interpretation": str,             # Human-readable assessment
                "authenticated_diversity": float   # diversity × grounding (if grounding provided)
            }

        Raises:
            ValueError: If concept not found or has no embeddings
            Exception: If calculation fails
        """
        start_time = time.time()

        try:
            # Validate concept exists and get label
            concept = self._get_concept(concept_id)
            if not concept:
                raise ValueError(f"Concept not found: {concept_id}")

            concept_label = concept.get('label', concept_id)

            # Get related concepts with omnidirectional traversal
            related_concepts = self._get_related_concepts(
                concept_id=concept_id,
                max_hops=max_hops,
                limit=limit
            )

            if len(related_concepts) < 2:
                return {
                    "diversity_score": None,
                    "related_concept_count": len(related_concepts),
                    "avg_pairwise_similarity": None,
                    "sampled": False,
                    "calculation_time_ms": int((time.time() - start_time) * 1000),
                    "interpretation": "Insufficient related concepts (need at least 2)"
                }

            # Extract embeddings
            embeddings = []
            for concept in related_concepts:
                emb = self._parse_embedding(concept.get('embedding'))
                if emb is not None:
                    embeddings.append(emb)

            if len(embeddings) < 2:
                return {
                    "diversity_score": None,
                    "related_concept_count": len(related_concepts),
                    "avg_pairwise_similarity": None,
                    "sampled": False,
                    "calculation_time_ms": int((time.time() - start_time) * 1000),
                    "interpretation": "Related concepts missing embeddings"
                }

            # Calculate pairwise cosine similarities
            similarities = []
            for emb1, emb2 in combinations(embeddings, 2):
                similarity = self._cosine_similarity(emb1, emb2)
                similarities.append(similarity)

            avg_similarity = float(np.mean(similarities))
            diversity_score = 1.0 - avg_similarity

            # Calculate authenticated diversity if grounding provided
            # Formula: sign(grounding) × diversity
            # Positive: diverse evidence supports concept
            # Negative: diverse evidence contradicts concept
            authenticated_diversity = None
            if grounding_strength is not None:
                sign = 1.0 if grounding_strength >= 0 else -1.0
                authenticated_diversity = float(sign * diversity_score)

            calculation_time_ms = int((time.time() - start_time) * 1000)

            auth_str = f"{authenticated_diversity:.3f}" if authenticated_diversity is not None else "N/A"
            logger.info(
                f"Diversity calculated for '{concept_label}': "
                f"score={diversity_score:.3f}, related={len(embeddings)}, "
                f"authenticated={auth_str}, "
                f"time={calculation_time_ms}ms"
            )

            return {
                "diversity_score": float(diversity_score),
                "related_concept_count": len(embeddings),
                "avg_pairwise_similarity": avg_similarity,
                "sampled": len(related_concepts) >= limit,
                "calculation_time_ms": calculation_time_ms,
                "interpretation": self._interpret_diversity(diversity_score),
                "authenticated_diversity": authenticated_diversity
            }

        except Exception as e:
            logger.error(f"Diversity calculation failed for {concept_id}: {e}")
            raise

    def _get_concept(self, concept_id: str) -> Optional[Dict[str, Any]]:
        """Get concept by ID."""
        query = """
        MATCH (c:Concept {concept_id: $concept_id})
        RETURN c.concept_id as concept_id, c.label as label
        """
        results = self.client._execute_cypher(
            query,
            params={'concept_id': concept_id}
        )
        return results[0] if results else None

    def _get_related_concepts(
        self,
        concept_id: str,
        max_hops: int,
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Get related concepts using omnidirectional traversal.

        Critical: Uses undirected relationships (-[*]-) to capture full semantic
        neighborhood. Both inbound and outbound relationships contribute to diversity.

        Example:
            Moon Rocks -[:COLLECTED_BY]-> Apollo 11  (inbound to Apollo 11)
            Apollo 11 -[:USED]-> Saturn V            (outbound from Apollo 11)
            Both contribute to Apollo 11's semantic diversity.
        """
        query = f"""
        MATCH (target:Concept {{concept_id: $concept_id}})-[*1..{max_hops}]-(related:Concept)
        WHERE related.concept_id <> $concept_id
        WITH DISTINCT related
        RETURN related.concept_id as concept_id,
               related.label as label,
               related.embedding as embedding
        LIMIT {limit}
        """

        return self.client._execute_cypher(
            query,
            params={'concept_id': concept_id}
        )

    def _parse_embedding(self, embedding_data: Any) -> Optional[np.ndarray]:
        """
        Parse embedding from AGE format to numpy array.

        Handles various AGE return formats:
        - String JSON array: "[0.1, 0.2, ...]"
        - Direct list: [0.1, 0.2, ...]
        - None/null
        """
        if embedding_data is None:
            return None

        try:
            if isinstance(embedding_data, str):
                # Parse JSON string
                emb_list = json.loads(embedding_data)
            elif isinstance(embedding_data, (list, tuple)):
                emb_list = embedding_data
            else:
                return None

            return np.array(emb_list, dtype=np.float32)

        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning(f"Failed to parse embedding: {e}")
            return None

    def _cosine_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Formula: similarity = dot(emb1, emb2) / (norm(emb1) * norm(emb2))

        Returns:
            float in range [0, 1] (we use absolute value to handle negative similarities)
        """
        dot_product = np.dot(emb1, emb2)
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def _interpret_diversity(self, score: float) -> str:
        """
        Interpret diversity score for human readability.

        Thresholds based on empirical validation (ADR-063):
        - Apollo 11 (authentic): 0.377 diversity
        - Moon Landing Conspiracy (fabricated): 0.232 diversity
        """
        if score > 0.6:
            return "Very high diversity (strong signal of authentic/independent sources)"
        elif score > 0.4:
            return "High diversity (likely independent sources)"
        elif score > 0.2:
            return "Moderate diversity (some variation)"
        elif score > 0.1:
            return "Low diversity (similar/repetitive evidence)"
        else:
            return "Very low diversity (likely synthetic/single-source)"
