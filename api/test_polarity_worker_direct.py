#!/usr/bin/env python3
"""
Direct test of PolarityAxisWorker - bypasses job queue for faster testing.

Tests the worker by calling it directly with mock job queue.
"""

import sys
import time

# Add API to path
sys.path.insert(0, '/workspace/api')

from api.lib.age_client import AGEClient


def find_concept_by_search(query: str, limit: int = 5):
    """Search for concepts to use as test poles"""
    client = AGEClient()
    try:
        # Simple search for concepts with matching labels
        cypher = f"""
            MATCH (c:Concept)
            WHERE c.label =~ '(?i).*{query}.*'
            RETURN c.concept_id as concept_id, c.label as label
            LIMIT {limit}
        """
        results = client._execute_cypher(cypher)
        return results if results else []
    finally:
        client.close()


class MockJobQueue:
    """Minimal mock for job queue update_job calls"""
    def __init__(self, job_id):
        self.job_id = job_id
        self.updates = []

    def update_job(self, job_id, updates):
        """Track updates for debugging"""
        self.updates.append(updates)
        if 'progress' in updates:
            print(f"  Progress: {updates['progress']}")


def test_polarity_axis_worker_direct():
    """Test the polarity axis worker by calling it directly"""

    print("=" * 70)
    print("Testing PolarityAxisWorker (Direct Call)")
    print("=" * 70)
    print()

    # Search for concepts to use as poles
    print("🔍 Searching for test concepts...")

    # Look for "Modern" and "Traditional" concepts
    modern_concepts = find_concept_by_search("Modern")
    traditional_concepts = find_concept_by_search("Traditional")

    if not modern_concepts:
        print("❌ No 'Modern' concepts found. Trying alternative...")
        modern_concepts = find_concept_by_search("Digital")

    if not traditional_concepts:
        print("❌ No 'Traditional' concepts found. Trying alternative...")
        traditional_concepts = find_concept_by_search("Legacy")

    if not modern_concepts or not traditional_concepts:
        print("❌ Could not find suitable test concepts")
        print("   Please run on a database with concepts containing 'Modern' or 'Traditional'")
        return False

    positive_pole = modern_concepts[0]
    negative_pole = traditional_concepts[0]

    print(f"✓ Positive pole: {positive_pole['label']} ({positive_pole['concept_id']})")
    print(f"✓ Negative pole: {negative_pole['label']} ({negative_pole['concept_id']})")
    print()

    # Prepare job data
    job_data = {
        "positive_pole_id": positive_pole['concept_id'],
        "negative_pole_id": negative_pole['concept_id'],
        "candidate_discovery": {
            "enabled": True,
            "max_candidates": 10,
            "relationship_types": ["SUPPORTS", "ENABLES", "PREVENTS"],
            "max_hops": 2
        },
        "user_id": 1  # Admin user
    }

    job_id = "test_job_polarity"
    mock_queue = MockJobQueue(job_id)

    # Call worker directly
    print("🔄 Running polarity axis analysis...")
    print()

    start_time = time.time()

    try:
        from api.workers.polarity_axis_worker import run_polarity_axis_worker

        result = run_polarity_axis_worker(
            job_data=job_data,
            job_id=job_id,
            job_queue=mock_queue
        )

        duration = time.time() - start_time

        print()
        print(f"✅ Analysis completed in {duration:.2f} seconds")
        print()

        # Display results
        print("📊 Results:")
        print("-" * 70)

        # Axis info
        axis = result.get('axis', {})
        print(f"\nPolarity Axis:")
        print(f"  Positive: {axis.get('positive_pole', {}).get('label')} (grounding: {axis.get('positive_pole', {}).get('grounding', 0):.3f})")
        print(f"  Negative: {axis.get('negative_pole', {}).get('label')} (grounding: {axis.get('negative_pole', {}).get('grounding', 0):.3f})")
        print(f"  Magnitude: {axis.get('magnitude', 0):.4f}")
        print(f"  Quality: {axis.get('axis_quality', 'unknown')}")

        # Statistics
        stats = result.get('statistics', {})
        print(f"\nStatistics:")
        print(f"  Total concepts: {stats.get('total_concepts', 0)}")
        print(f"  Position range: {stats.get('position_range', [0, 0])}")
        print(f"  Mean position: {stats.get('mean_position', 0):.3f}")
        print(f"  Mean axis distance: {stats.get('mean_axis_distance', 0):.3f}")

        # Direction distribution
        dist = stats.get('direction_distribution', {})
        print(f"\nDirection Distribution:")
        print(f"  Positive: {dist.get('positive', 0)}")
        print(f"  Neutral: {dist.get('neutral', 0)}")
        print(f"  Negative: {dist.get('negative', 0)}")

        # Grounding correlation
        corr = result.get('grounding_correlation', {})
        print(f"\nGrounding Correlation:")
        print(f"  Pearson r: {corr.get('pearson_r', 0):.3f}")
        print(f"  p-value: {corr.get('p_value', 1):.4f}")
        print(f"  {corr.get('interpretation', 'N/A')}")

        # Sample projections
        projections = result.get('projections', [])
        if projections:
            print(f"\nSample Projections (top 5):")
            for i, proj in enumerate(projections[:5], 1):
                print(f"  {i}. {proj['label']}")
                print(f"     Position: {proj['position']:+.3f} | Direction: {proj['direction']} | Grounding: {proj['grounding']:.3f}")

        print()
        print("=" * 70)
        print("✅ Test completed successfully!")
        print("=" * 70)

        return True

    except Exception as e:
        duration = time.time() - start_time
        print(f"\n❌ Test failed after {duration:.2f} seconds: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = test_polarity_axis_worker_direct()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
