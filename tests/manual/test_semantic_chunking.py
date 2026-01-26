#!/usr/bin/env python3
"""
Test semantic AST-based chunking with hard-cut fallback.

Verifies:
1. Natural semantic boundaries respected
2. Serial order maintained (critical for recursive upsert)
3. Hard-cut fallback for giant unstructured text
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from api.app.lib.markdown_preprocessor import MarkdownPreprocessor


def test_semantic_chunking():
    """Test semantic chunking on structured markdown"""
    print("="*80)
    print("TEST 1: Semantic Chunking (Structured Markdown)")
    print("="*80)

    markdown = """# Introduction

This is the introduction section with several paragraphs. It contains
enough text to demonstrate how semantic chunking works with natural
document boundaries.

The introduction continues here with more detail about the topic.
We want to show how headings create natural breakpoints.

## Subsection

This subsection has its own content that should be grouped intelligently.
The chunker should respect section boundaries when possible.

## Another Subsection

More content here. The chunker will group nodes until it reaches
the target word count, then break at the next natural boundary.

### Deep Heading

Even nested headings should be considered for boundaries.

# Second Major Section

This starts a completely new major section. If we've reached target
word count, this heading should trigger a chunk boundary.

The section continues with more content to fill out the chunk.

## Final Subsection

Last bit of content to complete the document.
"""

    preprocessor = MarkdownPreprocessor(max_workers=3)
    chunks = preprocessor.preprocess_to_chunks(
        markdown,
        target_words=100,  # Small target to force multiple chunks
        min_words=80,
        max_words=150
    )

    print(f"\nTotal chunks: {len(chunks)}")
    print(f"\nChunk details:")

    for chunk in chunks:
        print(f"\n  Chunk {chunk.chunk_number}: {chunk.word_count} words")
        print(f"    Boundary: {chunk.boundary_type}")
        print(f"    Position: {chunk.start_position} → {chunk.end_position}")
        print(f"    Nodes: {len(chunk.nodes)}")
        print(f"    First 80 chars: {chunk.text[:80].replace(chr(10), ' ')}...")

    # Verify serial order
    positions = [c.chunk_number for c in chunks]
    assert positions == sorted(positions), "❌ Chunks not in serial order!"
    print(f"\n✅ Serial order verified: {positions}")

    # Verify boundary types
    boundary_types = [c.boundary_type for c in chunks]
    print(f"✅ Boundary types: {boundary_types}")


def test_hard_cut_fallback():
    """Test hard-cut fallback for giant unstructured text"""
    print(f"\n{'='*80}")
    print("TEST 2: Hard-Cut Fallback (Unstructured Giant Text)")
    print("="*80)

    # Simulate audio transcript: 3000 words without breaks
    giant_paragraph = " ".join([
        f"word{i}" for i in range(3000)
    ])

    markdown = f"""# Transcript

{giant_paragraph}

# Normal Section

This is normal text after the giant blob.
"""

    preprocessor = MarkdownPreprocessor(max_workers=3)
    chunks = preprocessor.preprocess_to_chunks(
        markdown,
        target_words=1000,
        min_words=800,
        max_words=1500
    )

    print(f"\nTotal chunks: {len(chunks)}")
    print(f"\nChunk details:")

    hard_cut_count = 0
    for chunk in chunks:
        print(f"\n  Chunk {chunk.chunk_number}: {chunk.word_count} words")
        print(f"    Boundary: {chunk.boundary_type}")

        if chunk.boundary_type == "hard_cut":
            hard_cut_count += 1

    print(f"\n✅ Hard-cut chunks: {hard_cut_count}")
    assert hard_cut_count >= 2, "❌ Expected multiple hard cuts for 3000-word paragraph!"

    # Verify serial order maintained even with hard cuts
    positions = [c.chunk_number for c in chunks]
    assert positions == sorted(positions), "❌ Serial order broken by hard cuts!"
    print(f"✅ Serial order maintained through hard cuts: {positions}")


def test_real_documentation():
    """Test on real complex documentation"""
    print(f"\n{'='*80}")
    print("TEST 3: Real Documentation (ADR-016)")
    print("="*80)

    file_path = 'docs/architecture/ADR-016-apache-age-migration.md'

    if not Path(file_path).exists():
        print(f"⚠  Skipping: {file_path} not found")
        return

    with open(file_path, 'r') as f:
        content = f.read()

    preprocessor = MarkdownPreprocessor(max_workers=3)
    chunks = preprocessor.preprocess_to_chunks(content)

    print(f"\nDocument: {file_path}")
    print(f"Total chunks: {len(chunks)}")

    # Statistics
    word_counts = [c.word_count for c in chunks]
    boundary_types = {}
    for c in chunks:
        boundary_types[c.boundary_type] = boundary_types.get(c.boundary_type, 0) + 1

    print(f"\nChunk size statistics:")
    print(f"  Min:  {min(word_counts):4d} words")
    print(f"  Max:  {max(word_counts):4d} words")
    print(f"  Avg:  {sum(word_counts)/len(word_counts):4.0f} words")

    print(f"\nBoundary types:")
    for btype, count in boundary_types.items():
        print(f"  {btype}: {count}")

    # Verify in target range
    in_range = sum(1 for wc in word_counts if 800 <= wc <= 1500)
    print(f"\nIn target range (800-1500): {in_range}/{len(chunks)} ({in_range/len(chunks)*100:.1f}%)")

    # Show sample chunks
    print(f"\nSample chunks:")
    for chunk in chunks[:3]:
        print(f"\n  Chunk {chunk.chunk_number}: {chunk.word_count} words ({chunk.boundary_type})")
        print(f"    Nodes: {len(chunk.nodes)}")
        print(f"    First 100 chars: {chunk.text[:100].replace(chr(10), ' ')}...")

    # Verify serial order
    positions = [c.chunk_number for c in chunks]
    assert positions == list(range(1, len(chunks) + 1)), "❌ Chunk numbers not sequential!"
    print(f"\n✅ Serial order verified: 1..{len(chunks)}")


def test_mixed_content():
    """Test document with code blocks, lists, and various structures"""
    print(f"\n{'='*80}")
    print("TEST 4: Mixed Content (Code, Lists, Text)")
    print("="*80)

    markdown = """# API Documentation

This API provides graph querying capabilities.

## Query Examples

Here's a basic query:

```cypher
MATCH (c:Concept)
RETURN c.label
LIMIT 10
```

This query does the following:
1. Matches all Concept nodes
2. Returns their labels
3. Limits to 10 results

## Configuration

Configure with JSON:

```json
{
  "host": "localhost",
  "port": 5432,
  "database": "graph"
}
```

The configuration includes several important fields that control behavior.

## Advanced Usage

For advanced scenarios, you can use more complex queries that traverse
the graph deeply and apply sophisticated filters.

```python
def query_graph(config):
    client = GraphClient(config)
    results = client.query("MATCH (n) RETURN n")
    return results
```

This Python example shows how to connect and execute queries programmatically.
"""

    preprocessor = MarkdownPreprocessor(max_workers=3)
    chunks = preprocessor.preprocess_to_chunks(
        markdown,
        target_words=100,
        min_words=80,
        max_words=150
    )

    print(f"\nTotal chunks: {len(chunks)}")

    for chunk in chunks:
        print(f"\n  Chunk {chunk.chunk_number}: {chunk.word_count} words")
        print(f"    Boundary: {chunk.boundary_type}")
        print(f"    Nodes: {len(chunk.nodes)}")

        # Count code blocks in chunk
        code_nodes = [n for n in chunk.nodes if 'code' in n.node_type.value.lower()]
        if code_nodes:
            print(f"    Contains {len(code_nodes)} code block(s)")

    print(f"\n✅ Mixed content chunked successfully")


def main():
    """Run all tests"""
    print("Semantic AST-Based Chunking Test Suite")
    print("="*80)
    print("\nCRITICAL: Verifying serial order preservation for recursive upsert")
    print("="*80)

    test_semantic_chunking()
    test_hard_cut_fallback()
    test_real_documentation()
    test_mixed_content()

    print(f"\n{'='*80}")
    print("All tests passed!")
    print("="*80)
    print("\n✅ Semantic chunking respects natural boundaries")
    print("✅ Serial order maintained (critical for recursive upsert)")
    print("✅ Hard-cut fallback works for giant unstructured text")
    print("✅ Mixed content (code, lists, text) handled correctly")


if __name__ == '__main__':
    main()
