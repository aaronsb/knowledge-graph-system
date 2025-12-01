"""
Polarity Axis Analysis - Direct Query (ADR-070).

Analyzes bidirectional semantic dimensions by projecting concepts onto
polarity axes formed by opposing concept poles.

This is a direct query function (not a background job) for fast analysis.
For large-scale analysis, use the job queue variant (future).
"""

import logging
import numpy as np
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from scipy.stats import pearsonr

logger = logging.getLogger(__name__)


@dataclass
class Concept:
    """Represents a concept with embedding and metadata"""
    concept_id: str
    label: str
    embedding: np.ndarray
    grounding: float
    description: Optional[str] = None


@dataclass
class PolarityAxis:
    """Represents a bidirectional semantic dimension"""
    positive_pole: Concept  # The "positive" direction (e.g., Modern)
    negative_pole: Concept  # The "negative" direction (e.g., Traditional)
    axis_vector: np.ndarray  # Unit vector from negative → positive
    axis_magnitude: float  # Total semantic distance

    def __post_init__(self):
        """Calculate axis properties"""
        # Gradient from negative to positive pole
        gradient = self.positive_pole.embedding - self.negative_pole.embedding
        self.axis_magnitude = float(np.linalg.norm(gradient))

        # Avoid division by zero
        if self.axis_magnitude < 1e-8:
            raise ValueError("Poles are too similar (magnitude near zero)")

        self.axis_vector = gradient / self.axis_magnitude

    def project_concept(self, concept: Concept) -> Dict[str, Any]:
        """
        Project concept onto polarity axis.

        Returns:
            position: Scalar position on axis (-1 to +1, 0 = midpoint)
            axis_distance: Distance from axis (orthogonal component)
            direction: "positive", "negative", or "neutral"
        """
        # Vector from negative pole to concept
        concept_vector = concept.embedding - self.negative_pole.embedding

        # Project onto axis (scalar projection)
        projection_scalar = float(np.dot(concept_vector, self.axis_vector))

        # Normalize to [-1, 1] range (0 = midpoint between poles)
        normalized_position = (projection_scalar / self.axis_magnitude) * 2 - 1

        # Calculate distance from axis (orthogonal component)
        projection_vector = projection_scalar * self.axis_vector
        orthogonal_vector = concept_vector - projection_vector
        axis_distance = float(np.linalg.norm(orthogonal_vector))

        # Determine direction
        if normalized_position > 0.3:
            direction = "positive"
        elif normalized_position < -0.3:
            direction = "negative"
        else:
            direction = "neutral"

        # Calculate similarities to poles
        positive_similarity = float(np.dot(
            concept.embedding / np.linalg.norm(concept.embedding),
            self.positive_pole.embedding / np.linalg.norm(self.positive_pole.embedding)
        ))
        negative_similarity = float(np.dot(
            concept.embedding / np.linalg.norm(concept.embedding),
            self.negative_pole.embedding / np.linalg.norm(self.negative_pole.embedding)
        ))

        return {
            "position": normalized_position,
            "raw_projection": projection_scalar,
            "axis_distance": axis_distance,
            "direction": direction,
            "similarity_to_positive": positive_similarity,
            "similarity_to_negative": negative_similarity
        }


def fetch_concept_with_embedding(
    concept_id: str,
    age_client
) -> Concept:
    """
    Fetch concept metadata and embedding from graph.

    Args:
        concept_id: Concept ID to fetch
        age_client: AGEClient instance

    Returns:
        Concept with embedding and metadata

    Raises:
        ValueError: If concept not found or missing embedding
    """
    # Query concept details using facade (ADR-048 namespace safety)
    # Return individual properties to get flattened dict (not vertex structure)
    results = age_client.facade.match_concepts(
        where="c.concept_id = $concept_id",
        params={"concept_id": concept_id},
        return_clause="c.concept_id AS concept_id, c.label AS label, c.description AS description, c.embedding AS embedding"
    )

    if not results or len(results) == 0:
        raise ValueError(f"Concept not found: {concept_id}")

    concept_data = results[0]

    # Extract embedding
    embedding = concept_data.get('embedding')
    if embedding is None:
        raise ValueError(f"Concept {concept_id} has no embedding")

    # Convert to numpy array
    if isinstance(embedding, list):
        embedding_array = np.array(embedding, dtype=np.float32)
    else:
        raise ValueError(f"Unexpected embedding format: {type(embedding)}")

    # Calculate grounding (ADR-058)
    try:
        grounding = age_client.calculate_grounding_strength_semantic(concept_id)
    except Exception as e:
        logger.warning(f"Failed to calculate grounding for {concept_id}: {e}")
        grounding = 0.0

    return Concept(
        concept_id=concept_data['concept_id'],
        label=concept_data['label'],
        embedding=embedding_array,
        grounding=grounding,
        description=concept_data.get('description')
    )


def discover_candidate_concepts(
    positive_pole_id: str,
    negative_pole_id: str,
    age_client,
    max_candidates: int = 20,
    max_hops: int = 1
) -> List[str]:
    """
    Auto-discover concepts related to the poles.

    Uses graph traversal to find concepts connected to either pole.

    Args:
        positive_pole_id: Positive pole concept ID
        negative_pole_id: Negative pole concept ID
        age_client: AGEClient instance
        max_candidates: Maximum concepts to return
        max_hops: Maximum hops from poles

    Returns:
        List of concept IDs (excludes the poles themselves)
    """
    # Find concepts connected to either pole within max_hops
    # Filter for concepts with embeddings (required for projection)
    # Using facade.execute_raw for variable-length path (ADR-048 namespace safety)
    # Format pole IDs as Cypher list manually (json.dumps uses double quotes which Cypher rejects)
    # Performance optimization: Limit per-pole results to avoid expensive DISTINCT on large sets
    pole_ids_cypher = "[" + ", ".join(f"'{pid}'" for pid in [positive_pole_id, negative_pole_id]) + "]"

    results = age_client.facade.execute_raw(
        query=f"""
            MATCH (pole:Concept)
            WHERE pole.concept_id IN {pole_ids_cypher}
            MATCH (pole)-[*1..$max_hops]-(candidate:Concept)
            WHERE NOT (candidate.concept_id IN {pole_ids_cypher})
              AND candidate.embedding IS NOT NULL
            WITH DISTINCT candidate
            LIMIT $limit
            RETURN candidate.concept_id as concept_id
        """,
        params={
            "max_hops": max_hops,
            "limit": max_candidates * 2  # Increase to account for potential overlap
        },
        namespace="concept"
    )

    if not results:
        logger.warning("No candidate concepts discovered")
        return []

    return [r['concept_id'] for r in results]


def calculate_grounding_correlation(
    projections: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calculate correlation between axis position and grounding strength.

    Strong correlation (r > 0.7) indicates value-laden axis.
    Weak correlation (r < 0.3) indicates descriptive axis.

    Args:
        projections: List of projection dicts with 'position' and 'grounding'

    Returns:
        Dict with pearson_r, p_value, and interpretation
    """
    if len(projections) < 3:
        return {
            "pearson_r": 0.0,
            "p_value": 1.0,
            "interpretation": "Insufficient data for correlation (need ≥3 concepts)"
        }

    positions = [p['position'] for p in projections]
    groundings = [p['grounding'] for p in projections]

    try:
        r, p_value = pearsonr(positions, groundings)

        # Interpret correlation strength
        if abs(r) > 0.7:
            strength = "Strong"
        elif abs(r) > 0.4:
            strength = "Moderate"
        else:
            strength = "Weak"

        if r > 0:
            direction = "positive"
            interpretation = f"{strength} positive correlation: concepts toward positive pole have higher grounding"
        elif r < 0:
            direction = "negative"
            interpretation = f"{strength} negative correlation: concepts toward negative pole have higher grounding"
        else:
            direction = "none"
            interpretation = "No correlation between axis position and grounding"

        return {
            "pearson_r": float(r),
            "p_value": float(p_value),
            "interpretation": interpretation,
            "strength": strength.lower(),
            "direction": direction
        }
    except Exception as e:
        logger.error(f"Failed to calculate correlation: {e}")
        return {
            "pearson_r": 0.0,
            "p_value": 1.0,
            "interpretation": f"Correlation calculation failed: {str(e)}"
        }


def analyze_polarity_axis(
    positive_pole_id: str,
    negative_pole_id: str,
    age_client,
    candidate_ids: Optional[List[str]] = None,
    auto_discover: bool = True,
    max_candidates: int = 20,
    max_hops: int = 1
) -> Dict[str, Any]:
    """
    Analyze polarity axis between two concept poles (direct query).

    Args:
        positive_pole_id: Concept ID for positive pole
        negative_pole_id: Concept ID for negative pole
        age_client: AGEClient instance
        candidate_ids: Specific concepts to project (optional)
        auto_discover: Auto-discover candidates if not provided
        max_candidates: Max candidates for auto-discovery
        max_hops: Max hops for auto-discovery

    Returns:
        Dict with axis analysis, projections, and statistics

    Raises:
        ValueError: If poles are invalid or too similar
    """
    logger.info(f"Polarity axis analysis: {positive_pole_id} ↔ {negative_pole_id}")

    # Fetch pole concepts
    positive_pole = fetch_concept_with_embedding(positive_pole_id, age_client)
    negative_pole = fetch_concept_with_embedding(negative_pole_id, age_client)

    logger.info(
        f"Poles loaded: {positive_pole.label} (grounding: {positive_pole.grounding:.3f}) ↔ "
        f"{negative_pole.label} (grounding: {negative_pole.grounding:.3f})"
    )

    # Create polarity axis
    axis = PolarityAxis(
        positive_pole=positive_pole,
        negative_pole=negative_pole,
        axis_vector=np.zeros_like(positive_pole.embedding),  # Calculated in __post_init__
        axis_magnitude=0.0
    )

    logger.info(f"Axis magnitude: {axis.axis_magnitude:.4f}")

    # Determine candidate concepts
    if candidate_ids is None and auto_discover:
        candidate_ids = discover_candidate_concepts(
            positive_pole_id=positive_pole_id,
            negative_pole_id=negative_pole_id,
            age_client=age_client,
            max_candidates=max_candidates,
            max_hops=max_hops
        )
        logger.info(f"Discovered {len(candidate_ids)} candidate concepts")
    elif candidate_ids is None:
        candidate_ids = []
        logger.warning("No candidates provided and auto-discovery disabled")

    # Project candidates onto axis
    projections = []
    for concept_id in candidate_ids:
        try:
            concept = fetch_concept_with_embedding(concept_id, age_client)
            projection = axis.project_concept(concept)

            projections.append({
                "concept_id": concept.concept_id,
                "label": concept.label,
                "position": projection["position"],
                "axis_distance": projection["axis_distance"],
                "direction": projection["direction"],
                "grounding": concept.grounding,
                "alignment": {
                    "positive_pole_similarity": projection["similarity_to_positive"],
                    "negative_pole_similarity": projection["similarity_to_negative"]
                }
            })
        except Exception as e:
            logger.warning(f"Failed to project concept {concept_id}: {e}")
            continue

    logger.info(f"Successfully projected {len(projections)} concepts")

    # Calculate statistics
    if projections:
        positions = [p["position"] for p in projections]
        axis_distances = [p["axis_distance"] for p in projections]

        direction_dist = {
            "positive": sum(1 for p in projections if p["direction"] == "positive"),
            "negative": sum(1 for p in projections if p["direction"] == "negative"),
            "neutral": sum(1 for p in projections if p["direction"] == "neutral")
        }

        statistics = {
            "total_concepts": len(projections),
            "position_range": [min(positions), max(positions)],
            "mean_position": float(np.mean(positions)),
            "std_deviation": float(np.std(positions)),
            "mean_axis_distance": float(np.mean(axis_distances)),
            "direction_distribution": direction_dist
        }

        # Grounding correlation
        grounding_correlation = calculate_grounding_correlation(projections)
    else:
        statistics = {
            "total_concepts": 0,
            "position_range": [0, 0],
            "mean_position": 0.0,
            "std_deviation": 0.0,
            "mean_axis_distance": 0.0,
            "direction_distribution": {"positive": 0, "negative": 0, "neutral": 0}
        }
        grounding_correlation = {
            "pearson_r": 0.0,
            "p_value": 1.0,
            "interpretation": "No concepts projected"
        }

    # Prepare result
    result = {
        "success": True,
        "axis": {
            "positive_pole": {
                "concept_id": positive_pole.concept_id,
                "label": positive_pole.label,
                "grounding": positive_pole.grounding,
                "description": positive_pole.description
            },
            "negative_pole": {
                "concept_id": negative_pole.concept_id,
                "label": negative_pole.label,
                "grounding": negative_pole.grounding,
                "description": negative_pole.description
            },
            "magnitude": axis.axis_magnitude,
            "axis_quality": "strong" if axis.axis_magnitude > 0.8 else "weak"
        },
        "projections": projections,
        "statistics": statistics,
        "grounding_correlation": grounding_correlation
    }

    logger.info(
        f"✅ Polarity axis analysis completed: "
        f"({len(projections)} concepts projected, r={grounding_correlation['pearson_r']:.2f})"
    )

    return result
