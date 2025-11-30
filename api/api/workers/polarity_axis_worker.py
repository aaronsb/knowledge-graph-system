"""
Polarity Axis Analysis Worker (ADR-070).

Analyzes bidirectional semantic dimensions by projecting concepts onto
polarity axes formed by opposing concept poles.

Key capabilities:
- Analyze specific polarity axis (positive ↔ negative poles)
- Project candidate concepts onto axis
- Calculate grounding correlation
- Auto-discover related concepts
- Find connection paths between poles
- Source evidence grounding (ADR-068 integration)
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
    # Query concept details
    query = f"""
        MATCH (c:Concept {{concept_id: '{concept_id}'}})
        RETURN c.concept_id as concept_id,
               c.label as label,
               c.embedding as embedding,
               c.description as description
    """

    results = age_client._execute_cypher(query)

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
    relationship_types: Optional[List[str]] = None,
    max_hops: int = 2
) -> List[str]:
    """
    Auto-discover concepts related to the poles.

    Uses graph traversal to find concepts connected to either pole
    via specified relationship types.

    Args:
        positive_pole_id: Positive pole concept ID
        negative_pole_id: Negative pole concept ID
        age_client: AGEClient instance
        max_candidates: Maximum concepts to return
        relationship_types: Relationship types to traverse (currently ignored - AGE limitation)
        max_hops: Maximum hops from poles

    Returns:
        List of concept IDs (excludes the poles themselves)

    Note:
        AGE/openCypher doesn't support relationship type filtering in variable-length
        paths (e.g., [:TYPE1|TYPE2*1..2]). For now, we traverse all relationship types.
        Future: Could implement with UNION queries or path filtering.
    """
    # Note: relationship_types parameter currently ignored due to AGE syntax limitation
    # AGE doesn't support [:TYPE1|TYPE2*1..2] syntax

    # Find concepts connected to either pole within max_hops
    query = f"""
        MATCH (pole:Concept)
        WHERE pole.concept_id IN ['{positive_pole_id}', '{negative_pole_id}']
        MATCH (pole)-[*1..{max_hops}]-(candidate:Concept)
        WHERE candidate.concept_id <> '{positive_pole_id}'
          AND candidate.concept_id <> '{negative_pole_id}'
        WITH DISTINCT candidate
        RETURN candidate.concept_id as concept_id
        LIMIT {max_candidates}
    """

    results = age_client._execute_cypher(query)

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


def run_polarity_axis_worker(
    job_data: Dict[str, Any],
    job_id: str,
    job_queue
) -> Dict[str, Any]:
    """
    Execute polarity axis analysis as a background job.

    Job Data Parameters:
        positive_pole_id: str - Concept ID for positive pole
        negative_pole_id: str - Concept ID for negative pole
        candidate_ids: Optional[List[str]] - Specific concepts to project
        candidate_discovery: Optional[Dict] - Auto-discovery config
            - enabled: bool
            - max_candidates: int
            - relationship_types: List[str]
            - max_hops: int

    Args:
        job_data: Job parameters
        job_id: Job ID for progress tracking
        job_queue: Queue instance for progress updates

    Returns:
        Result dict with axis analysis, projections, and statistics

    Raises:
        ValueError: If poles are invalid or too similar
        Exception: If analysis fails
    """
    try:
        from api.lib.age_client import AGEClient

        logger.info(f"🔄 Polarity axis analysis worker started: {job_id}")

        # Update progress
        job_queue.update_job(job_id, {
            "status": "processing",
            "progress": "Polarity axis analysis worker started"
        })

        # Extract parameters
        positive_pole_id = job_data.get("positive_pole_id")
        negative_pole_id = job_data.get("negative_pole_id")

        if not positive_pole_id or not negative_pole_id:
            raise ValueError("Both positive_pole_id and negative_pole_id are required")

        candidate_ids = job_data.get("candidate_ids")
        candidate_discovery = job_data.get("candidate_discovery", {})

        logger.info(
            f"Polarity axis analysis: {positive_pole_id} ↔ {negative_pole_id}"
        )

        # Initialize AGE client
        age_client = AGEClient()

        try:
            # Fetch pole concepts
            job_queue.update_job(job_id, {
                "progress": "Fetching pole concepts and embeddings"
            })

            positive_pole = fetch_concept_with_embedding(positive_pole_id, age_client)
            negative_pole = fetch_concept_with_embedding(negative_pole_id, age_client)

            logger.info(
                f"Poles loaded: {positive_pole.label} (grounding: {positive_pole.grounding:.3f}) ↔ "
                f"{negative_pole.label} (grounding: {negative_pole.grounding:.3f})"
            )

            # Create polarity axis
            job_queue.update_job(job_id, {
                "progress": "Calculating polarity axis"
            })

            axis = PolarityAxis(
                positive_pole=positive_pole,
                negative_pole=negative_pole,
                axis_vector=np.zeros_like(positive_pole.embedding),  # Calculated in __post_init__
                axis_magnitude=0.0
            )

            logger.info(f"Axis magnitude: {axis.axis_magnitude:.4f}")

            # Determine candidate concepts
            if candidate_ids is None:
                # Auto-discover candidates
                if candidate_discovery.get("enabled", True):
                    job_queue.update_job(job_id, {
                        "progress": "Auto-discovering candidate concepts"
                    })

                    candidate_ids = discover_candidate_concepts(
                        positive_pole_id=positive_pole_id,
                        negative_pole_id=negative_pole_id,
                        age_client=age_client,
                        max_candidates=candidate_discovery.get("max_candidates", 20),
                        relationship_types=candidate_discovery.get("relationship_types"),
                        max_hops=candidate_discovery.get("max_hops", 2)
                    )

                    logger.info(f"Discovered {len(candidate_ids)} candidate concepts")
                else:
                    candidate_ids = []
                    logger.warning("No candidates provided and auto-discovery disabled")

            # Project candidates onto axis
            job_queue.update_job(job_id, {
                "progress": f"Projecting {len(candidate_ids)} concepts onto axis"
            })

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
            job_queue.update_job(job_id, {
                "progress": "Calculating axis statistics and correlations"
            })

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
                f"✅ Polarity axis analysis completed: {job_id} "
                f"({len(projections)} concepts projected, r={grounding_correlation['pearson_r']:.2f})"
            )
            return result

        except Exception as e:
            error_msg = f"Polarity axis analysis failed: {str(e)}"
            logger.error(error_msg, exc_info=True)

            job_queue.update_job(job_id, {
                "status": "failed",
                "error": error_msg,
                "progress": "Polarity axis analysis failed"
            })

            raise Exception(error_msg) from e
        finally:
            if age_client:
                age_client.close()

    except Exception as e:
        logger.error(f"❌ Polarity axis analysis worker failed: {job_id} - {e}")
        raise
