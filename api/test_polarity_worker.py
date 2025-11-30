#!/usr/bin/env python3
"""
Quick test script for PolarityAxisWorker.

Tests the worker by submitting a job and checking results.
"""

import sys
import time
import json

# Add API to path
sys.path.insert(0, '/workspace/api')

from api.services.job_queue import init_job_queue, get_job_queue
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


def test_polarity_axis_worker():
    """Test the polarity axis worker with real concepts"""

    print("=" * 70)
    print("Testing PolarityAxisWorker")
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

    # Initialize job queue
    print("🔧 Initializing job queue...")
    queue = init_job_queue(queue_type="postgresql")

    # Register the worker
    from api.workers.polarity_axis_worker import run_polarity_axis_worker
    queue.register_worker("polarity_axis_analysis", run_polarity_axis_worker)
    print("✓ Worker registered")
    print()

    # Submit job
    print("📝 Submitting polarity axis analysis job...")

    job_data = {
        "positive_pole_id": positive_pole['concept_id'],
        "negative_pole_id": negative_pole['concept_id'],
        "candidate_discovery": {
            "enabled": True,
            "max_candidates": 10,
            "relationship_types": ["SUPPORTS", "ENABLES", "PREVENTS"],
            "max_hops": 2
        },
        "user_id": 1  # Admin user (id=1 per migration 020)
    }

    queue = get_job_queue()
    job_id = queue.enqueue(
        job_type="polarity_axis_analysis",
        job_data=job_data
    )
    print(f"✓ Job submitted: {job_id}")
    print()

    # Wait for job to complete
    print("⏳ Waiting for job to complete...")
    max_wait = 30  # seconds
    start_time = time.time()

    while time.time() - start_time < max_wait:
        job_status = queue.get_job(job_id)
        status = job_status.get('status', 'unknown')
        progress = job_status.get('progress', '')

        if status == 'completed':
            print(f"✅ Job completed!")
            print()
            break
        elif status == 'failed':
            error = job_status.get('error', 'Unknown error')
            print(f"❌ Job failed: {error}")
            return False
        else:
            print(f"   Status: {status} - {progress}")
            time.sleep(1)
    else:
        print(f"⏰ Timeout waiting for job to complete")
        return False

    # Get results
    print("📊 Results:")
    print("-" * 70)

    result = job_status.get('result', {})

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


if __name__ == "__main__":
    try:
        success = test_polarity_axis_worker()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
