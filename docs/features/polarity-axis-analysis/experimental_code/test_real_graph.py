"""
Test semantic gradient analysis on real knowledge graph data

Fetches actual concept paths from the database and analyzes them.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
import requests
import numpy as np
from path_analysis import SemanticPathAnalyzer, Concept


API_URL = "http://localhost:8000"


def fetch_concept_details(concept_id: str) -> dict:
    """Fetch concept details from API"""
    response = requests.get(f"{API_URL}/queries/concepts/{concept_id}")
    response.raise_for_status()
    return response.json()


def search_concepts(query: str, threshold: float = 0.7, limit: int = 10) -> list:
    """Search for concepts"""
    response = requests.post(
        f"{API_URL}/queries/concepts/search",
        json={"query": query, "threshold": threshold, "limit": limit}
    )
    response.raise_for_status()
    return response.json().get('results', [])


def build_path_from_relationships(start_concept_id: str, max_depth: int = 5) -> list:
    """
    Build a path by following relationships from starting concept

    Returns list of concept dictionaries with embeddings
    """
    path = []
    visited = set()
    current_id = start_concept_id

    for _ in range(max_depth):
        if current_id in visited:
            break

        visited.add(current_id)

        # Fetch concept details
        concept = fetch_concept_details(current_id)
        path.append(concept)

        # Find next concept via relationship
        if concept.get('relationships'):
            # Pick first unvisited relationship
            for rel in concept['relationships']:
                next_id = rel['target_concept_id']
                if next_id not in visited:
                    current_id = next_id
                    break
            else:
                break  # No unvisited relationships
        else:
            break  # No relationships

    return path


def analyze_real_path(start_query: str):
    """Analyze a real path from the knowledge graph"""

    print("=" * 70)
    print(f"Analyzing path starting from: '{start_query}'")
    print("=" * 70)

    # 1. Search for starting concept
    print(f"\n🔍 Searching for '{start_query}'...")
    results = search_concepts(start_query, threshold=0.7, limit=5)

    if not results:
        print(f"✗ No concepts found matching '{start_query}'")
        return

    print(f"✓ Found {len(results)} matching concepts:")
    for i, r in enumerate(results):
        print(f"  [{i+1}] {r['label']} (similarity: {r.get('similarity', 0):.2%})")

    # Use first result
    start_concept_id = results[0]['concept_id']
    print(f"\n📍 Starting from: {results[0]['label']}")

    # 2. Build path by following relationships
    print(f"\n🔗 Building path by following relationships...")
    path_data = build_path_from_relationships(start_concept_id, max_depth=6)

    print(f"✓ Built path with {len(path_data)} concepts:")
    for i, c in enumerate(path_data):
        print(f"  {i+1}. {c['label']}")

    if len(path_data) < 2:
        print("✗ Path too short for analysis (need at least 2 concepts)")
        return

    # 3. Convert to Concept objects with embeddings
    print(f"\n📊 Converting to gradient analysis format...")
    concepts = []
    for c in path_data:
        if 'embedding' not in c or not c['embedding']:
            print(f"⚠️  Skipping {c['label']} (no embedding)")
            continue

        concepts.append(Concept(
            concept_id=c['concept_id'],
            label=c['label'],
            embedding=np.array(c['embedding'], dtype=np.float32),
            grounding=c.get('grounding', 0.0)
        ))

    if len(concepts) < 2:
        print("✗ Not enough concepts with embeddings for analysis")
        return

    print(f"✓ Analyzing {len(concepts)} concepts with embeddings")

    # 4. Run gradient analysis
    print(f"\n📈 Running gradient analysis...")
    analyzer = SemanticPathAnalyzer(weak_link_threshold=2.0)
    metrics = analyzer.analyze_path(concepts)

    # 5. Display results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    print(f"\n🛤️  Path:")
    print(f"  {' → '.join(c.label for c in concepts)}")

    print(f"\n📏 Distance Metrics:")
    print(f"  Total Distance: {metrics.total_distance:.4f}")
    print(f"  Avg Step Size: {metrics.avg_step_size:.4f}")
    print(f"  Step Variance: {metrics.step_variance:.4f}")

    print(f"\n🎯 Coherence:")
    print(f"  Coherence Score: {metrics.coherence_score:.4f}")
    print(f"  Quality Rating: {metrics.quality_rating}")

    print(f"\n🌀 Curvature:")
    print(f"  Avg Curvature: {metrics.avg_curvature:.4f} radians ({np.degrees(metrics.avg_curvature):.1f}°)")
    if metrics.curvature_angles:
        print(f"  Curvature range: {min(metrics.curvature_angles):.4f} - {max(metrics.curvature_angles):.4f}")

    if metrics.weak_links:
        print(f"\n⚠️  Weak Links Detected ({len(metrics.weak_links)}):")
        for link in metrics.weak_links:
            print(f"\n  Step {link['step_index']}: {link['source']} → {link['target']}")
            print(f"    Distance: {link['distance']:.4f}")
            print(f"    Severity: {link['severity_sigma']:.2f}σ above mean")
    else:
        print(f"\n✓ No weak links detected")

    print("\n" + "=" * 70)
    print()


def compare_relationship_types():
    """Compare semantic gaps across different relationship types"""

    print("=" * 70)
    print("Relationship Type Analysis")
    print("=" * 70)

    print("\n🔍 Fetching relationship data from API...")

    # This would require a new API endpoint to fetch relationships with embeddings
    # For now, show the concept
    print("\n⚠️  This requires an API endpoint to fetch relationships with embeddings")
    print("    Example endpoint: GET /queries/relationships/with-embeddings")
    print()


def test_missing_link_detection(source_query: str, target_query: str):
    """Test missing link detection between two concepts"""

    print("=" * 70)
    print(f"Missing Link Detection: '{source_query}' → '{target_query}'")
    print("=" * 70)

    # Search for source and target
    print(f"\n🔍 Searching for source: '{source_query}'...")
    source_results = search_concepts(source_query, limit=1)

    print(f"🔍 Searching for target: '{target_query}'...")
    target_results = search_concepts(target_query, limit=1)

    if not source_results or not target_results:
        print("✗ Could not find both concepts")
        return

    source_data = fetch_concept_details(source_results[0]['concept_id'])
    target_data = fetch_concept_details(target_results[0]['concept_id'])

    source = Concept(
        concept_id=source_data['concept_id'],
        label=source_data['label'],
        embedding=np.array(source_data['embedding'], dtype=np.float32)
    )

    target = Concept(
        concept_id=target_data['concept_id'],
        label=target_data['label'],
        embedding=np.array(target_data['embedding'], dtype=np.float32)
    )

    # Calculate direct gap
    analyzer = SemanticPathAnalyzer()
    direct_gap = analyzer.gradient_magnitude(
        analyzer.semantic_gradient(source.embedding, target.embedding)
    )

    print(f"\n📏 Direct semantic gap: {direct_gap:.4f}")

    # Search for potential bridges
    print(f"\n🔍 Searching for bridging concepts...")
    # Get 50 random concepts as candidates
    all_concepts_search = search_concepts("", threshold=0.0, limit=50)

    candidates = []
    for c_data in all_concepts_search:
        concept_details = fetch_concept_details(c_data['concept_id'])
        if 'embedding' in concept_details and concept_details['embedding']:
            candidates.append(Concept(
                concept_id=concept_details['concept_id'],
                label=concept_details['label'],
                embedding=np.array(concept_details['embedding'], dtype=np.float32)
            ))

    bridges = analyzer.find_missing_links(
        source, target, candidates,
        gap_threshold=0.3,
        improvement_threshold=1.2
    )

    if bridges:
        print(f"\n✓ Found {len(bridges)} potential bridging concepts:")
        for concept, improvement in bridges[:5]:
            print(f"  • {concept.label}: {improvement*100:.1f}% improvement")
    else:
        print("\n✗ No suitable bridging concepts found")

    print()


def main():
    """Run tests on real knowledge graph data"""

    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "Semantic Path Gradient Analysis" + " " * 22 + "║")
    print("║" + " " * 23 + "Real Graph Testing" + " " * 27 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    try:
        # Test 1: Analyze a path starting from "embedding"
        analyze_real_path("embedding")

        # Test 2: Analyze a path starting from "API"
        analyze_real_path("API")

        # Test 3: Missing link detection (if you want to test this)
        # test_missing_link_detection("vector", "database")

    except requests.exceptions.ConnectionError:
        print("✗ Error: Could not connect to API at http://localhost:8000")
        print("  Make sure the API server is running:")
        print("  cd docker && docker-compose up api")
        print()
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
