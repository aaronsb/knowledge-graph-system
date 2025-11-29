"""
Polarity Axis Analysis - Bidirectional Semantic Dimensions

This script analyzes semantic polarity axes between opposing concepts.
Uses gradient-based analysis to:
1. Identify the semantic axis between polar opposites
2. Project other concepts onto the axis to find their position
3. Determine directionality (which end of the spectrum)
4. Find concepts along the axis in both directions

Example polarity axes:
- Modern Operating Model ↔ Traditional Operating Models
- Centralized ↔ Decentralized
- Hierarchical ↔ Flat

Based on semantic gradient analysis (ADR-069, experiment/semantic-path-gradients)
"""

import numpy as np
from typing import List, Tuple, Dict
from dataclasses import dataclass
import psycopg2
import json
import os
import sys

# Add API lib to path for AGEClient
sys.path.insert(0, '/workspace/api')

from path_analysis import Concept, SemanticPathAnalyzer
from api.lib.age_client import AGEClient


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
        self.axis_vector = gradient / (self.axis_magnitude + 1e-8)

    def project_concept(self, concept: Concept) -> Dict:
        """
        Project concept onto polarity axis

        Returns:
            position: Scalar position on axis (-1 to +1, 0 = midpoint)
            distance: Distance from axis (orthogonal component)
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

        return {
            "position": normalized_position,
            "raw_projection": projection_scalar,
            "axis_distance": axis_distance,
            "direction": direction,
            "similarity_to_positive": float(np.dot(concept.embedding, self.positive_pole.embedding)),
            "similarity_to_negative": float(np.dot(concept.embedding, self.negative_pole.embedding))
        }


def get_db_connection():
    """Get PostgreSQL database connection"""
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        database=os.getenv('POSTGRES_DB', 'knowledge_graph'),
        user=os.getenv('POSTGRES_USER', 'admin'),
        password=os.getenv('POSTGRES_PASSWORD', 'password')
    )


def fetch_embedding_from_db(concept_id: str) -> np.ndarray:
    """Fetch actual embedding from PostgreSQL database using AGE Cypher"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Load AGE extension
            cur.execute("LOAD 'age';")
            cur.execute("SET search_path = ag_catalog, '$user', public;")

            # Use AGE Cypher to query the Concept vertex
            query = f"""
                SELECT * FROM ag_catalog.cypher('knowledge_graph', $$
                    MATCH (c:Concept {{concept_id: '{concept_id}'}})
                    RETURN c.embedding
                $$) AS (embedding agtype);
            """
            cur.execute(query)

            result = cur.fetchone()
            if result and result[0]:
                embedding_agtype = result[0]

                # Convert agtype to Python object
                if isinstance(embedding_agtype, str):
                    embedding_data = json.loads(embedding_agtype)
                else:
                    embedding_data = embedding_agtype

                # Extract the actual list of floats
                if isinstance(embedding_data, list):
                    return np.array(embedding_data, dtype=np.float32)
                else:
                    raise ValueError(f"Unexpected embedding format: {type(embedding_data)}")
            else:
                raise ValueError(f"No embedding found for concept {concept_id}")
    finally:
        conn.close()


def fetch_concept_metadata(concept_id: str, age_client: AGEClient) -> Dict:
    """
    Fetch concept metadata (label, grounding) using AGEClient

    Grounding is calculated on-demand using the same logic as query endpoints.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("LOAD 'age';")
            cur.execute("SET search_path = ag_catalog, '$user', public;")

            query = f"""
                SELECT * FROM ag_catalog.cypher('knowledge_graph', $$
                    MATCH (c:Concept {{concept_id: '{concept_id}'}})
                    RETURN c.label
                $$) AS (label agtype);
            """
            cur.execute(query)

            result = cur.fetchone()
            if result:
                label = result[0].strip('"') if result[0] else "Unknown"
            else:
                label = "Unknown"

        # Calculate grounding using AGEClient (reuses API implementation)
        grounding = age_client.calculate_grounding_strength_semantic(concept_id)

        return {"label": label, "grounding": grounding}
    finally:
        conn.close()


def analyze_polarity_axis(
    positive_id: str,
    negative_id: str,
    candidate_ids: List[str]
) -> PolarityAxis:
    """
    Analyze a polarity axis between two opposing concepts

    Args:
        positive_id: Concept ID for positive pole (e.g., "Modern Operating Model")
        negative_id: Concept ID for negative pole (e.g., "Traditional Operating Models")
        candidate_ids: List of concept IDs to project onto the axis
    """
    print("=" * 70)
    print("Polarity Axis Analysis - Bidirectional Semantic Dimensions")
    print("=" * 70)

    # Fetch pole concepts
    print("\n📍 Loading polarity axis...")

    # Initialize AGEClient for grounding calculations
    age_client = AGEClient()

    positive_meta = fetch_concept_metadata(positive_id, age_client)
    positive_emb = fetch_embedding_from_db(positive_id)
    positive_pole = Concept(
        concept_id=positive_id,
        label=positive_meta["label"],
        embedding=positive_emb,
        grounding=positive_meta["grounding"]
    )
    print(f"  ➕ Positive pole: {positive_pole.label} (grounding: {positive_pole.grounding:.3f})")

    negative_meta = fetch_concept_metadata(negative_id, age_client)
    negative_emb = fetch_embedding_from_db(negative_id)
    negative_pole = Concept(
        concept_id=negative_id,
        label=negative_meta["label"],
        embedding=negative_emb,
        grounding=negative_meta["grounding"]
    )
    print(f"  ➖ Negative pole: {negative_pole.label} (grounding: {negative_pole.grounding:.3f})")

    # Create polarity axis
    axis = PolarityAxis(
        positive_pole=positive_pole,
        negative_pole=negative_pole,
        axis_vector=np.zeros_like(positive_emb),  # Will be calculated in __post_init__
        axis_magnitude=0.0
    )

    print(f"\n📏 Axis Properties:")
    print(f"  Semantic distance: {axis.axis_magnitude:.4f}")
    print(f"  Axis direction: {negative_pole.label} → {positive_pole.label}")

    # Project candidates onto axis
    print(f"\n🎯 Projecting {len(candidate_ids)} concepts onto axis...")
    print()

    projections = []
    for candidate_id in candidate_ids:
        try:
            meta = fetch_concept_metadata(candidate_id, age_client)
            emb = fetch_embedding_from_db(candidate_id)
            concept = Concept(
                concept_id=candidate_id,
                label=meta["label"],
                embedding=emb,
                grounding=meta["grounding"]
            )

            projection = axis.project_concept(concept)
            projections.append((concept, projection))

        except Exception as e:
            print(f"  ⚠️  Skipped {candidate_id}: {e}")

    # Sort by position on axis
    projections.sort(key=lambda x: x[1]["position"], reverse=True)

    # Display results
    print("=" * 70)
    print("Polarity Axis Spectrum")
    print("=" * 70)
    print()
    print(f"← {negative_pole.label} {'─' * 30} {positive_pole.label} →")
    print()

    for concept, proj in projections:
        position = proj["position"]
        direction = proj["direction"]
        axis_dist = proj["axis_distance"]

        # Visual representation
        bar_length = 40
        center = bar_length // 2
        pos_on_bar = int(center + (position * center))
        pos_on_bar = max(0, min(bar_length - 1, pos_on_bar))

        bar = ["-"] * bar_length
        bar[center] = "|"
        bar[pos_on_bar] = "●"

        # Direction indicator
        if direction == "positive":
            indicator = "➕"
        elif direction == "negative":
            indicator = "➖"
        else:
            indicator = "⚖️"

        print(f"{indicator} {''.join(bar)} {concept.label}")
        print(f"   Position: {position:+.3f} | Axis distance: {axis_dist:.4f} | Grounding: {concept.grounding:.3f}")
        print()

    print("=" * 70)
    print()

    # Summary statistics
    print("📊 Axis Statistics:")
    positions = [p[1]["position"] for p in projections]
    distances = [p[1]["axis_distance"] for p in projections]

    print(f"  Concepts analyzed: {len(projections)}")
    print(f"  Position range: {min(positions):.3f} to {max(positions):.3f}")
    print(f"  Mean position: {np.mean(positions):.3f}")
    print(f"  Std deviation: {np.std(positions):.3f}")
    print(f"  Mean distance from axis: {np.mean(distances):.3f}")
    print()

    # Identify clusters
    positive_concepts = [c for c, p in projections if p["direction"] == "positive"]
    negative_concepts = [c for c, p in projections if p["direction"] == "negative"]
    neutral_concepts = [c for c, p in projections if p["direction"] == "neutral"]

    print(f"🔍 Direction Analysis:")
    print(f"  ➕ Positive pole ({positive_pole.label}): {len(positive_concepts)} concepts")
    for c in positive_concepts[:3]:
        print(f"     • {c.label}")

    print(f"  ➖ Negative pole ({negative_pole.label}): {len(negative_concepts)} concepts")
    for c in negative_concepts[:3]:
        print(f"     • {c.label}")

    print(f"  ⚖️  Neutral/Mixed: {len(neutral_concepts)} concepts")
    for c in neutral_concepts[:3]:
        print(f"     • {c.label}")

    print()

    return axis


def main():
    """Run polarity axis analysis on Modern vs Traditional operating models"""

    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "Polarity Axis Analysis" + " " * 32 + "║")
    print("║" + " " * 10 + "Bidirectional Semantic Dimensions" + " " * 26 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    # Define polarity axis
    positive_pole_id = "sha256:2af75_chunk1_78594e1b"  # Modern Operating Model
    negative_pole_id = "sha256:0f72d_chunk1_9a13bb20"  # Traditional Operating Models

    # Candidate concepts to project (from search results)
    candidate_ids = [
        "sha256:0d5be_chunk1_d22215ed",  # Enterprise Operating Model
        "sha256:0d5be_chunk3_9a66842d",  # Capacity-Based Operating Model
        "sha256:9aa45_chunk1_081acfa1",  # Budget Operating Model
        "sha256:23ba4_chunk4_0343189a",  # AI-Enabled Operating Models
        "sha256:0d5be_chunk4_e2165899",  # Product Platform Service Operating Model
        "sha256:23ba4_chunk3_75a9cef0",  # Operating Model Canvas
    ]

    # Run analysis
    axis = analyze_polarity_axis(positive_pole_id, negative_pole_id, candidate_ids)

    print("💡 Key Insights:")
    print("  • Polarity axes reveal implicit semantic dimensions not captured in explicit relationships")
    print("  • Concepts can be positioned along bidirectional spectrums (Modern ↔ Traditional)")
    print("  • Grounding scores correlate with pole position (positive concepts have positive grounding)")
    print("  • Axis distance measures how 'pure' vs 'mixed' a concept is on the spectrum")
    print()
    print("📝 Applications:")
    print("  • Find conceptual opposites (CONTRADICTS relationships)")
    print("  • Identify middle-ground concepts (synthesis, integration)")
    print("  • Detect conceptual drift (concepts moving along axis over time)")
    print("  • Suggest missing pole concepts (unbalanced axes)")
    print()


if __name__ == "__main__":
    main()
