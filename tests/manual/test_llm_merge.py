#!/usr/bin/env python3
"""
Test script for LLM merge evaluation.

Usage:
    python test_llm_merge.py TYPE1 TYPE2 [similarity]

Examples:
    python test_llm_merge.py STATUS HAS_STATUS 0.934
    python test_llm_merge.py PART_OF HAS_PART 0.862
    python test_llm_merge.py REFERS_TO IMPLIES 0.808
"""

import asyncio
import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.app.lib.pruning_strategies import llm_evaluate_merge
from api.app.lib.ai_providers import get_provider


async def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    type1 = sys.argv[1]
    type2 = sys.argv[2]
    similarity = float(sys.argv[3]) if len(sys.argv) > 3 else 0.85

    # Default edge counts (can be made into args if needed)
    type1_count = 5
    type2_count = 12

    print("=" * 70)
    print("LLM Merge Evaluation Test")
    print("=" * 70)
    print(f"\nType 1: {type1} ({type1_count} edges)")
    print(f"Type 2: {type2} ({type2_count} edges)")
    print(f"Similarity: {similarity:.1%}")
    print()

    # Get AI provider
    print("Initializing AI provider...")
    provider = get_provider()
    print(f"Using provider: {provider.__class__.__name__}")
    print()

    # Evaluate merge
    print("Calling LLM for merge decision...")
    decision = await llm_evaluate_merge(
        type1=type1,
        type2=type2,
        type1_edge_count=type1_count,
        type2_edge_count=type2_count,
        similarity=similarity,
        ai_provider=provider
    )

    # Display result
    print()
    print("=" * 70)
    print("DECISION")
    print("=" * 70)
    print(f"\nShould Merge: {decision.should_merge}")
    print(f"Reasoning: {decision.reasoning}")

    if decision.should_merge:
        print(f"\n✓ Blended Term: {decision.blended_term}")
        print(f"  Description: {decision.blended_description}")
    else:
        print(f"\n✗ Merge rejected")

    print(f"\nConfidence: {decision.confidence:.1%}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
