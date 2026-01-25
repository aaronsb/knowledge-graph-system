#!/usr/bin/env python3
"""
Performance comparison: Sequential vs Parallel polarity candidate discovery.

Tests ADR-071 parallel implementation against sequential baseline.
Measures speedup and validates result consistency.
"""

import sys
import time
import argparse

# Add API to path
sys.path.insert(0, '/workspace/api')

from api.app.lib.age_client import AGEClient
from api.app.lib.polarity_axis import (
    discover_candidate_concepts,
    discover_candidate_concepts_parallel
)


def find_concept_by_search(query: str, limit: int = 5):
    """Search for concepts to use as test poles"""
    client = AGEClient()
    try:
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


def test_performance_comparison(max_hops: int = 2, max_candidates: int = 20):
    """
    Compare sequential vs parallel performance.

    Args:
        max_hops: Number of graph hops (1 or 2)
        max_candidates: Maximum candidates to discover

    Returns:
        Dict with timing results and speedup
    """
    print("=" * 80)
    print(f"Performance Comparison: Sequential vs Parallel (max_hops={max_hops})")
    print("=" * 80)
    print()

    # Search for test concepts
    print("🔍 Searching for test concepts...")
    modern_concepts = find_concept_by_search("Modern")
    traditional_concepts = find_concept_by_search("Traditional")

    if not modern_concepts:
        modern_concepts = find_concept_by_search("Digital")

    if not traditional_concepts:
        traditional_concepts = find_concept_by_search("Legacy")

    if not modern_concepts or not traditional_concepts:
        print("❌ Could not find suitable test concepts")
        print("   Please run on a database with concepts containing 'Modern' or 'Traditional'")
        return None

    positive_pole = modern_concepts[0]
    negative_pole = traditional_concepts[0]

    print(f"✓ Positive pole: {positive_pole['label']} ({positive_pole['concept_id']})")
    print(f"✓ Negative pole: {negative_pole['label']} ({negative_pole['concept_id']})")
    print()

    # Test Sequential Implementation
    print("-" * 80)
    print("TEST 1: Sequential Discovery")
    print("-" * 80)

    client1 = AGEClient()
    try:
        start_time = time.time()

        sequential_results = discover_candidate_concepts(
            positive_pole_id=positive_pole['concept_id'],
            negative_pole_id=negative_pole['concept_id'],
            age_client=client1,
            max_candidates=max_candidates,
            max_hops=max_hops
        )

        sequential_time = time.time() - start_time

        print(f"✅ Sequential: {len(sequential_results)} concepts in {sequential_time:.2f}s")
        print(f"   Sample IDs: {sequential_results[:3]}")
        print()

    except Exception as e:
        print(f"❌ Sequential test failed: {e}")
        return None
    finally:
        client1.close()

    # Test Parallel Implementation
    print("-" * 80)
    print("TEST 2: Parallel Discovery (ADR-071)")
    print("-" * 80)

    client2 = AGEClient()
    try:
        start_time = time.time()

        parallel_results = discover_candidate_concepts_parallel(
            positive_pole_id=positive_pole['concept_id'],
            negative_pole_id=negative_pole['concept_id'],
            age_client=client2,
            max_candidates=max_candidates,
            max_hops=max_hops
        )

        parallel_time = time.time() - start_time

        print(f"✅ Parallel: {len(parallel_results)} concepts in {parallel_time:.2f}s")
        print(f"   Sample IDs: {parallel_results[:3]}")
        print()

    except Exception as e:
        print(f"❌ Parallel test failed: {e}")
        return None
    finally:
        client2.close()

    # Calculate Performance Metrics
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)

    speedup = sequential_time / parallel_time if parallel_time > 0 else 0
    time_saved = sequential_time - parallel_time

    print(f"\n📊 Performance:")
    print(f"   Sequential: {sequential_time:.3f}s")
    print(f"   Parallel:   {parallel_time:.3f}s")
    print(f"   Speedup:    {speedup:.1f}x")
    print(f"   Time saved: {time_saved:.3f}s")

    # Validate Results Consistency
    print(f"\n🔍 Result Consistency:")
    print(f"   Sequential found: {len(sequential_results)} concepts")
    print(f"   Parallel found:   {len(parallel_results)} concepts")

    # Check overlap
    seq_set = set(sequential_results)
    par_set = set(parallel_results)
    overlap = seq_set.intersection(par_set)
    overlap_pct = (len(overlap) / max(len(seq_set), len(par_set)) * 100) if max(len(seq_set), len(par_set)) > 0 else 0

    print(f"   Overlap:          {len(overlap)} concepts ({overlap_pct:.1f}%)")

    if overlap_pct < 80:
        print(f"   ⚠️  Warning: Low overlap ({overlap_pct:.1f}%), results may differ significantly")
    else:
        print(f"   ✓ Good overlap ({overlap_pct:.1f}%), results are consistent")

    # Success Criteria
    print(f"\n✨ Success Criteria:")

    success = True

    # Criterion 1: Speedup (for max_hops=2, should be significant)
    if max_hops == 2:
        if speedup >= 2.0:
            print(f"   ✅ Speedup: {speedup:.1f}x (target: ≥2x)")
        else:
            print(f"   ⚠️  Speedup: {speedup:.1f}x (target: ≥2x) - may indicate small graph")
            success = False
    else:
        print(f"   ℹ️  Speedup: {speedup:.1f}x (max_hops=1, modest speedup expected)")

    # Criterion 2: Result consistency
    if overlap_pct >= 80:
        print(f"   ✅ Consistency: {overlap_pct:.1f}% overlap (target: ≥80%)")
    else:
        print(f"   ❌ Consistency: {overlap_pct:.1f}% overlap (target: ≥80%)")
        success = False

    # Criterion 3: Both succeeded
    print(f"   ✅ Both implementations completed successfully")

    print()
    print("=" * 80)
    if success:
        print("✅ All criteria passed!")
    else:
        print("⚠️  Some criteria did not pass (see above)")
    print("=" * 80)

    return {
        'sequential_time': sequential_time,
        'parallel_time': parallel_time,
        'speedup': speedup,
        'sequential_count': len(sequential_results),
        'parallel_count': len(parallel_results),
        'overlap_pct': overlap_pct,
        'success': success
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test parallel query performance')
    parser.add_argument(
        '--max-hops',
        type=int,
        default=2,
        choices=[1, 2],
        help='Maximum graph hops (1 or 2, default: 2)'
    )
    parser.add_argument(
        '--max-candidates',
        type=int,
        default=20,
        help='Maximum candidates to discover (default: 20)'
    )

    args = parser.parse_args()

    try:
        result = test_performance_comparison(
            max_hops=args.max_hops,
            max_candidates=args.max_candidates
        )

        if result is None:
            sys.exit(1)

        sys.exit(0 if result['success'] else 1)

    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
