#!/usr/bin/env python3
"""
Test script for AITL vocabulary consolidation.

Usage:
    python test_aitl_consolidation.py [--dry-run] [--target SIZE] [--batch SIZE]

Examples:
    python test_aitl_consolidation.py --dry-run
    python test_aitl_consolidation.py --target 85 --batch 10
    python test_aitl_consolidation.py  # Run with defaults (target=90, batch=15)
"""

import asyncio
import sys
import os
import argparse

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.api.lib.ai_providers import get_provider
from src.api.lib.age_client import AGEClient
from src.api.services.vocabulary_manager import VocabularyManager


async def main():
    parser = argparse.ArgumentParser(description="Test AITL vocabulary consolidation")
    parser.add_argument("--dry-run", action="store_true", help="Don't execute merges, just show what would happen")
    parser.add_argument("--target", type=int, default=90, help="Target vocabulary size (default: 90)")
    parser.add_argument("--batch", type=int, default=15, help="Batch size per iteration (default: 15)")
    parser.add_argument("--threshold", type=float, default=0.90, help="Auto-execute threshold (default: 0.90)")

    args = parser.parse_args()

    print("=" * 70)
    print("AITL Vocabulary Consolidation Test")
    print("=" * 70)
    print(f"\nMode: {'DRY RUN' if args.dry_run else 'LIVE EXECUTION'}")
    print(f"Target size: {args.target}")
    print(f"Batch size: {args.batch}")
    print(f"Auto-execute threshold: {args.threshold:.0%}")
    print()

    # Initialize clients
    print("Initializing database and AI provider...")
    db = AGEClient()
    provider = get_provider()
    print(f"  Database: Connected")
    print(f"  AI Provider: {provider.get_provider_name()}")
    print()

    # Create vocabulary manager in AITL mode
    manager = VocabularyManager(
        db_client=db,
        ai_provider=provider,
        mode="aitl"
    )

    # Get initial state
    print("Checking current vocabulary state...")
    vocab_size = db.get_vocabulary_size()
    print(f"  Current vocabulary size: {vocab_size}")
    print()

    if vocab_size <= args.target:
        print(f"✓ Vocabulary is already at or below target ({vocab_size} ≤ {args.target})")
        print("No consolidation needed.")
        db.close()
        return

    print(f"Starting AITL consolidation (target: {args.target})...")
    print("-" * 70)
    print()

    # Run consolidation
    results = await manager.aitl_consolidate_vocabulary(
        target_size=args.target,
        batch_size=args.batch,
        auto_execute_threshold=args.threshold,
        dry_run=args.dry_run
    )

    # Print summary
    print()
    print("=" * 70)
    print("CONSOLIDATION SUMMARY")
    print("=" * 70)
    print()

    final_size = db.get_vocabulary_size()
    print(f"Final vocabulary size: {final_size}")
    print(f"Size reduction: {vocab_size} → {final_size} (-{vocab_size - final_size})")
    print()

    print(f"Auto-executed merges: {len(results['auto_executed'])}")
    print(f"Needs review: {len(results['needs_review'])}")
    print(f"Rejected: {len(results['rejected'])}")
    if 'iterations' in results:
        print(f"Iterations: {len(results['iterations'])}")
    print()

    if results['auto_executed']:
        print("-" * 70)
        print("AUTO-EXECUTED MERGES")
        print("-" * 70)
        for merge in results['auto_executed']:
            status = "✓" if 'error' not in merge else "✗"
            print(f"{status} {merge['deprecated']} → {merge['target']}")
            print(f"   Similarity: {merge['similarity']:.1%}")
            print(f"   Reasoning: {merge['reasoning']}")
            if 'edges_updated' in merge:
                print(f"   Edges updated: {merge['edges_updated']}")
            if 'error' in merge:
                print(f"   ERROR: {merge['error']}")
            print()

    if results['needs_review']:
        print("-" * 70)
        print("NEEDS HUMAN REVIEW")
        print("-" * 70)
        for review in results['needs_review'][:10]:  # Show first 10
            print(f"? {review['type1']} + {review['type2']}")
            print(f"   Suggested: {review['suggested_term']}")
            print(f"   Similarity: {review['similarity']:.1%}")
            print(f"   Reasoning: {review['reasoning']}")
            print()

    if results['rejected']:
        print("-" * 70)
        print(f"REJECTED MERGES (showing first 10 of {len(results['rejected'])})")
        print("-" * 70)
        for reject in results['rejected'][:10]:
            print(f"✗ {reject['type1']} + {reject['type2']}")
            print(f"   Reasoning: {reject['reasoning']}")
            print()

    # Iteration details (only for live mode)
    if 'iterations' in results and results['iterations']:
        print("-" * 70)
        print("ITERATION DETAILS")
        print("-" * 70)
        for iter_info in results['iterations']:
            print(f"Iteration {iter_info['iteration']}:")
            print(f"  Vocab size before: {iter_info['vocab_size_before']}")
            print(f"  Auto-executed: {iter_info['auto_executed']}")
            print(f"  Needs review: {iter_info['needs_review']}")
            print(f"  Rejected: {iter_info['rejected']}")
            print()

    # Cleanup
    db.close()

    print("=" * 70)
    print("Test complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
