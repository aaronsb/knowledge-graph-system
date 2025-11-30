"""
Example usage of semantic gradient analysis on knowledge graph paths

Run these examples against a live knowledge graph to test gradient-based analysis.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
from path_analysis import SemanticPathAnalyzer, Concept, PathMetrics


# Example 1: Analyze a simple reasoning path
def example_1_basic_path_analysis():
    """Analyze gradient properties of a simple 4-concept path"""
    print("=" * 60)
    print("Example 1: Basic Path Analysis")
    print("=" * 60)

    # Simulate concepts with embeddings
    # In real usage, these would come from the database
    concepts = [
        Concept(
            concept_id="c1",
            label="Machine Learning",
            embedding=np.random.randn(768).astype(np.float32),
        ),
        Concept(
            concept_id="c2",
            label="Neural Networks",
            embedding=np.random.randn(768).astype(np.float32),
        ),
        Concept(
            concept_id="c3",
            label="Deep Learning",
            embedding=np.random.randn(768).astype(np.float32),
        ),
        Concept(
            concept_id="c4",
            label="Transformers",
            embedding=np.random.randn(768).astype(np.float32),
        ),
    ]

    analyzer = SemanticPathAnalyzer()
    metrics = analyzer.analyze_path(concepts)

    print(f"\nPath: {' → '.join(c.label for c in concepts)}")
    print(f"\nMetrics:")
    print(f"  Total Distance: {metrics.total_distance:.4f}")
    print(f"  Avg Step Size: {metrics.avg_step_size:.4f}")
    print(f"  Coherence Score: {metrics.coherence_score:.4f}")
    print(f"  Avg Curvature: {metrics.avg_curvature:.4f} radians")
    print(f"  Quality Rating: {metrics.quality_rating}")

    if metrics.weak_links:
        print(f"\n⚠️  Weak Links Detected:")
        for link in metrics.weak_links:
            print(
                f"    {link['source']} → {link['target']}: "
                f"{link['distance']:.4f} ({link['severity_sigma']:.2f}σ)"
            )
    else:
        print(f"\n✓ No weak links detected (path is coherent)")

    print()


# Example 2: Find missing intermediate concepts
def example_2_missing_links():
    """Detect and suggest bridging concepts for large semantic gaps"""
    print("=" * 60)
    print("Example 2: Missing Link Detection")
    print("=" * 60)

    # Source and target with large semantic gap
    source = Concept(
        concept_id="c1",
        label="Variables",
        embedding=np.random.randn(768).astype(np.float32),
    )

    target = Concept(
        concept_id="c2",
        label="Dynamic Programming",
        embedding=np.random.randn(768).astype(np.float32),
    )

    # Candidate bridging concepts
    candidates = [
        Concept(
            concept_id="c3",
            label="Loops",
            embedding=np.random.randn(768).astype(np.float32),
        ),
        Concept(
            concept_id="c4",
            label="Functions",
            embedding=np.random.randn(768).astype(np.float32),
        ),
        Concept(
            concept_id="c5",
            label="Recursion",
            embedding=np.random.randn(768).astype(np.float32),
        ),
        Concept(
            concept_id="c6",
            label="Memoization",
            embedding=np.random.randn(768).astype(np.float32),
        ),
    ]

    analyzer = SemanticPathAnalyzer()

    # Calculate direct gap
    direct_gap = analyzer.gradient_magnitude(
        analyzer.semantic_gradient(source.embedding, target.embedding)
    )

    print(f"\nDirect path: {source.label} → {target.label}")
    print(f"Semantic gap: {direct_gap:.4f}")

    # Find bridges
    bridges = analyzer.find_missing_links(
        source, target, candidates, gap_threshold=0.3, improvement_threshold=1.2
    )

    if bridges:
        print(f"\n✓ Found {len(bridges)} bridging concept(s):")
        for concept, improvement in bridges[:3]:  # Top 3
            print(f"  • {concept.label}: {improvement*100:.1f}% improvement")
    else:
        print("\n✗ No suitable bridging concepts found")

    print()


# Example 3: Compare learning paths
def example_3_learning_path_comparison():
    """Compare two different learning paths for the same topic"""
    print("=" * 60)
    print("Example 3: Learning Path Comparison")
    print("=" * 60)

    # Path A: Direct but large jumps
    path_a = [
        Concept(
            concept_id="a1",
            label="Variables",
            embedding=np.random.randn(768).astype(np.float32),
        ),
        Concept(
            concept_id="a2",
            label="Functions",
            embedding=np.random.randn(768).astype(np.float32),
        ),
        Concept(
            concept_id="a3",
            label="Recursion",
            embedding=np.random.randn(768).astype(np.float32),
        ),
        Concept(
            concept_id="a4",
            label="Dynamic Programming",
            embedding=np.random.randn(768).astype(np.float32),
        ),
    ]

    # Path B: More gradual progression
    path_b = [
        Concept(
            concept_id="b1",
            label="Variables",
            embedding=np.random.randn(768).astype(np.float32),
        ),
        Concept(
            concept_id="b2",
            label="Loops",
            embedding=np.random.randn(768).astype(np.float32),
        ),
        Concept(
            concept_id="b3",
            label="Functions",
            embedding=np.random.randn(768).astype(np.float32),
        ),
        Concept(
            concept_id="b4",
            label="Recursion",
            embedding=np.random.randn(768).astype(np.float32),
        ),
        Concept(
            concept_id="b5",
            label="Memoization",
            embedding=np.random.randn(768).astype(np.float32),
        ),
        Concept(
            concept_id="b6",
            label="Dynamic Programming",
            embedding=np.random.randn(768).astype(np.float32),
        ),
    ]

    analyzer = SemanticPathAnalyzer()

    metrics_a = analyzer.analyze_path(path_a)
    metrics_b = analyzer.analyze_path(path_b)

    print(f"\nPath A: {' → '.join(c.label for c in path_a)}")
    print(f"  Coherence: {metrics_a.coherence_score:.4f}")
    print(f"  Avg Curvature: {metrics_a.avg_curvature:.4f}")
    print(f"  Quality: {metrics_a.quality_rating}")

    print(f"\nPath B: {' → '.join(c.label for c in path_b)}")
    print(f"  Coherence: {metrics_b.coherence_score:.4f}")
    print(f"  Avg Curvature: {metrics_b.avg_curvature:.4f}")
    print(f"  Quality: {metrics_b.quality_rating}")

    if metrics_b.coherence_score > metrics_a.coherence_score:
        print(f"\n✓ Recommendation: Path B (smoother progression)")
    else:
        print(f"\n✓ Recommendation: Path A (more direct)")

    print()


# Example 4: Semantic momentum prediction
def example_4_momentum_prediction():
    """Use semantic momentum to predict next likely concept"""
    print("=" * 60)
    print("Example 4: Semantic Momentum Prediction")
    print("=" * 60)

    # Established path
    path = [
        Concept(
            concept_id="c1",
            label="Variables",
            embedding=np.random.randn(768).astype(np.float32),
        ),
        Concept(
            concept_id="c2",
            label="Data Types",
            embedding=np.random.randn(768).astype(np.float32),
        ),
        Concept(
            concept_id="c3",
            label="Operators",
            embedding=np.random.randn(768).astype(np.float32),
        ),
    ]

    # Candidate next concepts
    candidates = [
        Concept(
            concept_id="c4",
            label="Control Flow",
            embedding=np.random.randn(768).astype(np.float32),
        ),
        Concept(
            concept_id="c5",
            label="Quantum Computing",
            embedding=np.random.randn(768).astype(np.float32),
        ),
        Concept(
            concept_id="c6",
            label="Expressions",
            embedding=np.random.randn(768).astype(np.float32),
        ),
    ]

    analyzer = SemanticPathAnalyzer()

    print(f"\nEstablished path: {' → '.join(c.label for c in path)}")
    print(f"\nChecking alignment with semantic momentum:")

    alignments = []
    for candidate in candidates:
        momentum, alignment = analyzer.calculate_semantic_momentum(path, candidate)
        alignments.append((candidate.label, alignment))
        print(f"  {candidate.label}: {alignment:.4f}")

    # Find best alignment
    best = max(alignments, key=lambda x: x[1])
    print(f"\n✓ Most aligned with path momentum: {best[0]} ({best[1]:.4f})")

    print()


# Example 5: Concept evolution over time
def example_5_concept_drift():
    """Track how concept meaning evolves as new evidence is added"""
    print("=" * 60)
    print("Example 5: Concept Drift Tracking")
    print("=" * 60)

    # Simulate concept embedding at different timestamps
    # In real usage, this would come from recalculating embeddings
    # using only evidence up to each timestamp
    embeddings_timeline = [
        ("2024-01-01", np.random.randn(768).astype(np.float32)),
        ("2024-03-15", np.random.randn(768).astype(np.float32)),
        ("2024-06-20", np.random.randn(768).astype(np.float32)),
        ("2024-09-10", np.random.randn(768).astype(np.float32)),
        ("2024-11-29", np.random.randn(768).astype(np.float32)),
    ]

    analyzer = SemanticPathAnalyzer()
    drift_history = analyzer.track_concept_drift(embeddings_timeline)

    print(f"\nConcept: 'Transformer Architecture'")
    print(f"\nEvolution timeline:")

    for i, drift in enumerate(drift_history):
        print(
            f"  {drift['timestamp']}: "
            f"drift={drift['drift_from_previous']:.4f}, "
            f"cumulative={drift['cumulative_drift']:.4f}"
        )

    # Assess stability
    avg_drift = np.mean([d["drift_from_previous"] for d in drift_history])
    if avg_drift < 0.1:
        stability = "Highly Stable"
    elif avg_drift < 0.3:
        stability = "Moderately Stable"
    else:
        stability = "Volatile"

    print(f"\nStability assessment: {stability} (avg drift: {avg_drift:.4f})")
    print()


# Real-world example: Query actual knowledge graph
async def example_6_real_graph_analysis():
    """
    Example of analyzing a real path from the knowledge graph

    NOTE: Requires running knowledge graph system with data
    """
    print("=" * 60)
    print("Example 6: Real Graph Analysis")
    print("=" * 60)

    try:
        # This would use the actual API client
        # from src.api.lib.age_client import AGEClient
        # client = AGEClient()

        print("\n⚠️  This example requires a running knowledge graph system")
        print("    with ingested data. Skipping for now.")
        print(
            "\n    To run this example:"
            "\n    1. Ensure API server is running (docker-compose up)"
            "\n    2. Ingest some test data (kg ingest file ...)"
            "\n    3. Uncomment the implementation below"
        )

        """
        # Example implementation:

        # 1. Find a concept
        search_results = client.search_concepts("embedding models", threshold=0.7)
        start_concept_id = search_results[0]['concept_id']

        # 2. Get concept details with relationships
        concept_details = client.get_concept_details(start_concept_id)

        # 3. Traverse to build a path
        path = []
        current = concept_details
        for _ in range(5):  # 5-hop path
            path.append(Concept(
                concept_id=current['concept_id'],
                label=current['label'],
                embedding=np.array(current['embedding'])
            ))

            # Follow a relationship to next concept
            if current['relationships']:
                next_id = current['relationships'][0]['target_concept_id']
                current = client.get_concept_details(next_id)
            else:
                break

        # 4. Analyze the path
        analyzer = SemanticPathAnalyzer()
        metrics = analyzer.analyze_path(path)

        print(f"\nAnalyzed path from knowledge graph:")
        print(f"  {' → '.join(c.label for c in path)}")
        print(f"\n  Coherence: {metrics.coherence_score:.4f}")
        print(f"  Quality: {metrics.quality_rating}")

        if metrics.weak_links:
            print(f"\n  Weak links:")
            for link in metrics.weak_links:
                print(f"    • {link['source']} → {link['target']}: {link['severity_sigma']:.2f}σ")
        """

    except Exception as e:
        print(f"\n✗ Error: {e}")

    print()


def main():
    """Run all examples"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "Semantic Path Gradient Analysis" + " " * 16 + "║")
    print("║" + " " * 20 + "Examples" + " " * 28 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    example_1_basic_path_analysis()
    example_2_missing_links()
    example_3_learning_path_comparison()
    example_4_momentum_prediction()
    example_5_concept_drift()

    # Uncomment to run real graph example (requires running system)
    # asyncio.run(example_6_real_graph_analysis())


if __name__ == "__main__":
    main()
