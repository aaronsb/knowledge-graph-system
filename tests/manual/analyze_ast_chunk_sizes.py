#!/usr/bin/env python3
"""
Analyze AST node sizes to determine if they fall within chunking parameters.

Compares AST-based semantic chunks vs traditional word-based chunks.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from api.app.lib.markdown_preprocessor import MarkdownPreprocessor
from api.app.lib.chunker import ChunkingConfig


def count_words(text: str) -> int:
    """Count words in text"""
    return len(text.split())


def analyze_ast_nodes_as_chunks(file_path: str):
    """Analyze AST nodes as potential semantic chunks"""
    print(f"\n{'='*80}")
    print(f"Analyzing: {file_path}")
    print('='*80)

    with open(file_path, 'r') as f:
        content = f.read()

    # Parse to AST
    preprocessor = MarkdownPreprocessor(max_workers=3)
    ast = preprocessor._parse_to_ast(content)

    # Chunking config for comparison
    config = ChunkingConfig()
    print(f"\nTarget chunking parameters:")
    print(f"  Min:    {config.min_words} words")
    print(f"  Target: {config.target_words} words")
    print(f"  Max:    {config.max_words} words")

    # Analyze node sizes
    print(f"\nAST Node Analysis:")
    print(f"  Total nodes: {len(ast)}")

    # Group nodes by type and size
    node_stats = {
        'too_small': [],  # < 800 words
        'ideal': [],      # 800-1500 words
        'too_large': [],  # > 1500 words
    }

    for node in ast:
        word_count = count_words(node.content)

        if word_count < config.min_words:
            node_stats['too_small'].append((node, word_count))
        elif word_count <= config.max_words:
            node_stats['ideal'].append((node, word_count))
        else:
            node_stats['too_large'].append((node, word_count))

    # Print statistics
    total = len(ast)
    print(f"\n  Too small (<{config.min_words}w): {len(node_stats['too_small'])} ({len(node_stats['too_small'])/total*100:.1f}%)")
    print(f"  Ideal range: {len(node_stats['ideal'])} ({len(node_stats['ideal'])/total*100:.1f}%)")
    print(f"  Too large (>{config.max_words}w): {len(node_stats['too_large'])} ({len(node_stats['too_large'])/total*100:.1f}%)")

    # Sample nodes from each category
    print(f"\n  Sample 'too small' nodes:")
    for node, wc in node_stats['too_small'][:5]:
        preview = node.content[:60].replace('\n', ' ')
        print(f"    [{node.node_type.value:10s}] {wc:4d}w: {preview}...")

    if node_stats['ideal']:
        print(f"\n  Sample 'ideal' nodes:")
        for node, wc in node_stats['ideal'][:5]:
            preview = node.content[:60].replace('\n', ' ')
            print(f"    [{node.node_type.value:10s}] {wc:4d}w: {preview}...")

    if node_stats['too_large']:
        print(f"\n  Sample 'too large' nodes:")
        for node, wc in node_stats['too_large'][:5]:
            preview = node.content[:60].replace('\n', ' ')
            print(f"    [{node.node_type.value:10s}] {wc:4d}w: {preview}...")

    # Simulate semantic grouping strategy
    print(f"\n{'='*80}")
    print("SEMANTIC GROUPING SIMULATION")
    print('='*80)

    semantic_chunks = []
    current_chunk = []
    current_words = 0

    for node in ast:
        node_words = count_words(node.content)

        # Skip blank lines and very small nodes
        if node_words < 5:
            continue

        # Check if adding this node would exceed max
        if current_words + node_words > config.max_words and current_chunk:
            # Finalize current chunk
            semantic_chunks.append({
                'nodes': current_chunk.copy(),
                'word_count': current_words,
                'node_types': [n.node_type.value for n in current_chunk]
            })
            current_chunk = []
            current_words = 0

        # Add node to current chunk
        current_chunk.append(node)
        current_words += node_words

        # If we've reached target, consider finishing chunk at next heading
        if current_words >= config.target_words:
            # Look ahead for natural boundary
            # For now, just finish chunk
            semantic_chunks.append({
                'nodes': current_chunk.copy(),
                'word_count': current_words,
                'node_types': [n.node_type.value for n in current_chunk]
            })
            current_chunk = []
            current_words = 0

    # Add final chunk
    if current_chunk:
        semantic_chunks.append({
            'nodes': current_chunk.copy(),
            'word_count': current_words,
            'node_types': [n.node_type.value for n in current_chunk]
        })

    print(f"\nSemantic chunks created: {len(semantic_chunks)}")

    chunk_sizes = [c['word_count'] for c in semantic_chunks]
    if chunk_sizes:
        print(f"  Min size:  {min(chunk_sizes):4d} words")
        print(f"  Max size:  {max(chunk_sizes):4d} words")
        print(f"  Avg size:  {sum(chunk_sizes)/len(chunk_sizes):4.0f} words")

        in_range = sum(1 for s in chunk_sizes if config.min_words <= s <= config.max_words)
        print(f"  In range:  {in_range}/{len(chunk_sizes)} ({in_range/len(chunk_sizes)*100:.1f}%)")

    # Show sample chunks
    print(f"\n  Sample chunks:")
    for i, chunk in enumerate(semantic_chunks[:3]):
        print(f"\n  Chunk {i+1}: {chunk['word_count']} words, {len(chunk['nodes'])} nodes")
        print(f"    Node types: {', '.join(set(chunk['node_types']))}")
        first_node = chunk['nodes'][0]
        preview = first_node.content[:80].replace('\n', ' ')
        print(f"    Starts: {preview}...")

    return {
        'ast_nodes': len(ast),
        'semantic_chunks': len(semantic_chunks),
        'avg_chunk_size': sum(chunk_sizes)/len(chunk_sizes) if chunk_sizes else 0,
        'in_range_pct': in_range/len(chunk_sizes)*100 if chunk_sizes else 0
    }


def main():
    """Analyze multiple documents"""
    print("AST-Based Semantic Chunking Analysis")
    print("="*80)

    test_files = [
        'docs/api/OPENCYPHER_QUERIES.md',
        'docs/architecture/ADR-016-apache-age-migration.md',
        'docs/guides/QUICKSTART.md',
    ]

    results = []
    for file_path in test_files:
        if Path(file_path).exists():
            result = analyze_ast_nodes_as_chunks(file_path)
            results.append((file_path, result))
        else:
            print(f"⚠ File not found: {file_path}")

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print('='*80)

    for file_path, result in results:
        filename = Path(file_path).name
        print(f"\n{filename}:")
        print(f"  AST nodes: {result['ast_nodes']}")
        print(f"  Semantic chunks: {result['semantic_chunks']}")
        print(f"  Avg chunk size: {result['avg_chunk_size']:.0f} words")
        print(f"  In target range: {result['in_range_pct']:.1f}%")

    print(f"\n{'='*80}")
    print("CONCLUSION")
    print('='*80)

    avg_in_range = sum(r['in_range_pct'] for _, r in results) / len(results) if results else 0
    print(f"\nAverage chunks in target range: {avg_in_range:.1f}%")

    if avg_in_range > 70:
        print("✅ AST-based chunking is VIABLE - most chunks fall in target range")
        print("   Recommendation: Use AST nodes as semantic chunks, skip serialization")
    elif avg_in_range > 40:
        print("⚠️  AST-based chunking is PARTIAL - needs grouping strategy")
        print("   Recommendation: Group small nodes, split large nodes")
    else:
        print("❌ AST-based chunking is NOT VIABLE - fall back to word-based")
        print("   Recommendation: Serialize to markdown, use traditional chunker")


if __name__ == '__main__':
    main()
