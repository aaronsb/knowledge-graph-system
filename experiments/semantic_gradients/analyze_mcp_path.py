"""
Analyze real paths from the knowledge graph using MCP data

This script uses concept IDs and embeddings from MCP queries to perform
gradient analysis on actual reasoning paths.
"""

import numpy as np
from path_analysis import SemanticPathAnalyzer, Concept
import json
import psycopg2
import os

# Path from MCP query results:
# Embedding Models → Model Migration → Unified Embedding Regeneration → Bug Fix

# Real concept data from the knowledge graph
concepts_data = [
    {
        "concept_id": "sha256:62dc3_chunk1_9360a498",
        "label": "Embedding Models",
        "grounding": 0.070,
        # Embedding would be fetched from API - using placeholder for now
    },
    {
        "concept_id": "sha256:62dc3_chunk1_45a7faf6",
        "label": "Model Migration",
        "grounding": 0.0,
    },
    {
        "concept_id": "sha256:95454_chunk1_76de0274",
        "label": "Unified Embedding Regeneration",
        "grounding": 0.168,
    },
    {
        "concept_id": "sha256:95454_chunk1_6a25165c",
        "label": "Bug Fix in Source Embedding Regeneration",
        "grounding": 0.0,
    },
]


def get_db_connection():
    """Get PostgreSQL database connection"""
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        database=os.getenv('POSTGRES_DB', 'knowledge_graph'),
        user=os.getenv('POSTGRES_USER', 'admin'),
        password=os.getenv('POSTGRES_PASSWORD', 'admin123')
    )


def fetch_embedding_from_db(concept_id: str) -> np.ndarray:
    """
    Fetch actual embedding from PostgreSQL database using AGE Cypher

    Returns the embedding vector stored in the Concept vertex
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Load AGE extension
            cur.execute("LOAD 'age';")
            cur.execute("SET search_path = ag_catalog, '$user', public;")

            # Use AGE Cypher to query the Concept vertex
            # AGE requires parameters in agtype format
            query = f"""
                SELECT * FROM ag_catalog.cypher('knowledge_graph', $$
                    MATCH (c:Concept {{concept_id: '{concept_id}'}})
                    RETURN c.embedding
                $$) AS (embedding agtype);
            """
            cur.execute(query)

            result = cur.fetchone()
            if result and result[0]:
                # AGE returns agtype, need to parse it
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


def analyze_path(concepts_data: list):
    """Analyze gradient properties of a real graph path"""

    print("=" * 70)
    print("Semantic Path Gradient Analysis - Real Knowledge Graph Path")
    print("=" * 70)

    # Build Concept objects with embeddings
    print("\n📥 Fetching embeddings from database...")
    concepts = []
    for c_data in concepts_data:
        try:
            embedding = fetch_embedding_from_db(c_data['concept_id'])
            concepts.append(Concept(
                concept_id=c_data['concept_id'],
                label=c_data['label'],
                embedding=embedding,
                grounding=c_data.get('grounding', 0.0)
            ))
            print(f"  ✓ {c_data['label']} (dim: {len(embedding)})")
        except Exception as e:
            print(f"  ✗ {c_data['label']}: {e}")
            raise

    # Analyze path
    print("\n📊 Analyzing path with gradient-based metrics...")
    analyzer = SemanticPathAnalyzer(weak_link_threshold=2.0)
    metrics = analyzer.analyze_path(concepts)

    # Display results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    print(f"\n🛤️  Reasoning Path:")
    path_str = " → ".join(c.label for c in concepts)
    print(f"  {path_str}")

    print(f"\n📏 Distance Metrics:")
    print(f"  Total Distance: {metrics.total_distance:.4f}")
    print(f"  Average Step Size: {metrics.avg_step_size:.4f}")
    print(f"  Step Variance: {metrics.step_variance:.6f}")

    print(f"\n🎯 Coherence Analysis:")
    print(f"  Coherence Score: {metrics.coherence_score:.4f}")
    coherence_rating = (
        "Excellent" if metrics.coherence_score > 0.9
        else "Good" if metrics.coherence_score > 0.7
        else "Moderate" if metrics.coherence_score > 0.5
        else "Poor"
    )
    print(f"  Coherence Rating: {coherence_rating}")
    print(f"  Overall Quality: {metrics.quality_rating}")

    print(f"\n🌀 Curvature Analysis:")
    if metrics.curvature_angles:
        print(f"  Average Curvature: {metrics.avg_curvature:.4f} radians ({np.degrees(metrics.avg_curvature):.1f}°)")
        print(f"  Min Curvature: {min(metrics.curvature_angles):.4f} rad")
        print(f"  Max Curvature: {max(metrics.curvature_angles):.4f} rad")

        # Interpret curvature
        if metrics.avg_curvature < 0.5:
            print(f"  Interpretation: ✓ Smooth progression (low curvature)")
        elif metrics.avg_curvature < 1.5:
            print(f"  Interpretation: ◐ Moderate turns (medium curvature)")
        else:
            print(f"  Interpretation: ◯ Sharp pivots (high curvature)")
    else:
        print(f"  (Need 3+ concepts for curvature analysis)")

    # Individual steps
    print(f"\n📐 Individual Step Analysis:")
    for i in range(len(concepts) - 1):
        step_gradient = analyzer.semantic_gradient(
            concepts[i].embedding,
            concepts[i+1].embedding
        )
        step_size = analyzer.gradient_magnitude(step_gradient)

        deviation = abs(step_size - metrics.avg_step_size) / (metrics.avg_step_size + 1e-8)

        print(f"\n  Step {i+1}: {concepts[i].label}")
        print(f"          → {concepts[i+1].label}")
        print(f"    Distance: {step_size:.4f}", end="")

        if deviation > 0.5:
            print(f" ⚠️  ({deviation*100:.0f}% deviation from average)")
        else:
            print(f" ✓ (within normal range)")

        # Show grounding for context
        print(f"    Source grounding: {concepts[i].grounding:.3f}")
        print(f"    Target grounding: {concepts[i+1].grounding:.3f}")

    # Weak links
    if metrics.weak_links:
        print(f"\n⚠️  Weak Links Detected ({len(metrics.weak_links)}):")
        for link in metrics.weak_links:
            print(f"\n  Step {link['step_index'] + 1}: {link['source']} → {link['target']}")
            print(f"    Semantic Gap: {link['distance']:.4f}")
            print(f"    Severity: {link['severity_sigma']:.2f}σ above mean")
            print(f"    Recommendation: Consider adding intermediate concept")
    else:
        print(f"\n✅ No weak links detected - path is coherent!")

    # Correlation with grounding
    print(f"\n🔬 Grounding Correlation Analysis:")
    groundings = [c.grounding for c in concepts]
    avg_grounding = np.mean(groundings)
    print(f"  Average grounding: {avg_grounding:.3f}")

    if avg_grounding < 0.1:
        print(f"  Note: Low grounding - concepts may need more evidence")

    print("\n" + "=" * 70)
    print()

    return metrics


def analyze_semantic_momentum():
    """Demonstrate semantic momentum prediction"""

    print("\n" + "=" * 70)
    print("Semantic Momentum Analysis")
    print("=" * 70)

    # Build shorter path for momentum analysis
    path = [
        Concept(
            concept_id="sha256:62dc3_chunk1_9360a498",
            label="Embedding Models",
            embedding=fetch_embedding_from_db("sha256:62dc3_chunk1_9360a498"),
            grounding=0.070
        ),
        Concept(
            concept_id="sha256:62dc3_chunk1_45a7faf6",
            label="Model Migration",
            embedding=fetch_embedding_from_db("sha256:62dc3_chunk1_45a7faf6"),
            grounding=0.0
        ),
        Concept(
            concept_id="sha256:95454_chunk1_76de0274",
            label="Unified Embedding Regeneration",
            embedding=fetch_embedding_from_db("sha256:95454_chunk1_76de0274"),
            grounding=0.168
        ),
    ]

    # Candidate next concepts (from MCP query Distance 3)
    candidates = [
        Concept(
            concept_id="sha256:95454_chunk1_6a25165c",
            label="Bug Fix in Source Embedding Regeneration",
            embedding=fetch_embedding_from_db("sha256:95454_chunk1_6a25165c"),
        ),
        Concept(
            concept_id="sha256:95454_chunk1_6cf7348c",
            label="Testing and Verification",
            embedding=fetch_embedding_from_db("sha256:95454_chunk1_6cf7348c"),
        ),
        Concept(
            concept_id="sha256:95454_chunk1_1f44c138",
            label="GraphQueryFacade",
            embedding=fetch_embedding_from_db("sha256:95454_chunk1_1f44c138"),
        ),
    ]

    analyzer = SemanticPathAnalyzer()

    print(f"\n🛤️  Established path:")
    print(f"  {' → '.join(c.label for c in path)}")

    print(f"\n🎯 Checking alignment with semantic momentum:")

    alignments = []
    for candidate in candidates:
        momentum, alignment = analyzer.calculate_semantic_momentum(path, candidate)
        alignments.append((candidate.label, alignment))

        status = "✓" if alignment > 0 else "◯"
        print(f"  {status} {candidate.label}: {alignment:.4f}")

    # Find best alignment
    best = max(alignments, key=lambda x: x[1])
    print(f"\n✨ Most aligned with path momentum: {best[0]} ({best[1]:.4f})")
    print()


def main():
    """Run gradient analysis on real knowledge graph path"""

    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 10 + "Semantic Path Gradient Analysis" + " " * 27 + "║")
    print("║" + " " * 15 + "Real Knowledge Graph Data" + " " * 28 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    # Analyze main path
    metrics = analyze_path(concepts_data)

    # Analyze semantic momentum
    analyze_semantic_momentum()

    print("\n💡 Key Insights:")
    print("  • Gradient-based analysis reveals semantic coherence of reasoning paths")
    print("  • Weak links indicate where intermediate concepts may be needed")
    print("  • Curvature shows how sharply concepts pivot in semantic space")
    print("  • Momentum prediction helps identify logically-aligned next concepts")
    print()
    print("📝 Next Steps:")
    print("  • Test correlation between semantic gap and grounding scores")
    print("  • Analyze multiple paths to establish baseline metrics")
    print("  • Integrate weak link detection into relationship extraction")
    print()


if __name__ == "__main__":
    main()
