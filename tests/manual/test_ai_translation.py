#!/usr/bin/env python3
"""
Test AI translation of code blocks to prose.

Tests the complete pipeline with real AI provider.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from api.app.lib.markdown_preprocessor import MarkdownPreprocessor
from api.app.lib.ai_providers import get_provider


def test_code_translation():
    """Test translation of various code block types"""
    print("="*80)
    print("TEST: AI Code Block Translation")
    print("="*80)

    markdown = """# API Documentation

This document explains graph querying.

## Cypher Query Example

```cypher
MATCH (c:Concept)-[:EVIDENCED_BY]->(i:Instance)
WHERE c.label CONTAINS "graph"
RETURN c.label, count(i) as evidence_count
ORDER BY evidence_count DESC
LIMIT 10
```

The query finds concepts related to graphs.

## Python Example

```python
def calculate_similarity(embedding_a, embedding_b):
    \"\"\"Calculate cosine similarity between two embeddings\"\"\"
    import numpy as np
    dot_product = np.dot(embedding_a, embedding_b)
    norm_a = np.linalg.norm(embedding_a)
    norm_b = np.linalg.norm(embedding_b)
    return dot_product / (norm_a * norm_b)
```

This function computes vector similarity.

## Mermaid Diagram

```mermaid
graph TD
    A[Document] --> B[Parse to AST]
    B --> C[Translate Code]
    C --> D[Semantic Chunks]
    D --> E[Extract Concepts]
    E --> F[Upsert to Graph]
```

This diagram shows the preprocessing pipeline.
"""

    print(f"\nTest document: {len(markdown)} characters")
    print("\nUsing AI provider for translation...")

    try:
        # Get configured AI provider
        provider = get_provider()
        print(f"Provider: {provider.get_provider_name()}")

        # Create preprocessor with AI
        preprocessor = MarkdownPreprocessor(
            max_workers=3,
            code_min_lines=3,
            ai_provider=provider
        )

        # Preprocess to chunks (triggers translation)
        chunks = preprocessor.preprocess_to_chunks(markdown)

        # Check stats
        stats = preprocessor.get_stats()
        print(f"\n{'='*80}")
        print("TRANSLATION STATISTICS")
        print('='*80)
        print(f"Blocks detected:    {stats['blocks_detected']}")
        print(f"Blocks translated:  {stats['blocks_translated']}")
        print(f"Blocks stripped:    {stats['blocks_stripped']}")
        print(f"Translation tokens: {stats['translation_tokens']:,}")

        # Estimate cost (gpt-4o-mini: $0.15/1M input, $0.60/1M output)
        # Approximate 50/50 split
        cost = (stats['translation_tokens'] / 1_000_000) * 0.375  # Average rate
        print(f"Estimated cost:     ${cost:.4f}")

        # Show chunks with translations
        print(f"\n{'='*80}")
        print(f"CHUNKS CREATED: {len(chunks)}")
        print('='*80)

        for chunk in chunks:
            print(f"\nChunk {chunk.chunk_number}: {chunk.word_count} words ({chunk.boundary_type})")
            print(f"First 200 chars:")
            print(f"  {chunk.text[:200].replace(chr(10), ' ')}...")

        # Verify translations actually happened
        if stats['blocks_translated'] > 0:
            print(f"\n✅ SUCCESS: {stats['blocks_translated']} code blocks translated to prose!")
            print(f"✅ Cost: ${cost:.4f} (very reasonable)")
        else:
            print(f"\n⚠️  WARNING: No blocks were translated (all too short or errors?)")

        return chunks, stats

    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None


def test_individual_block():
    """Test translation of a single code block"""
    print(f"\n{'='*80}")
    print("TEST: Individual Code Block Translation")
    print('='*80)

    code = """MATCH (c:Concept {concept_id: $id})
RETURN c.label, c.search_terms"""

    prompt = """Explain this Cypher code in plain English prose.
Describe what the code does, how it works, and its purpose.
Use simple paragraphs and lists. Focus on WHAT it does and WHY."""

    try:
        provider = get_provider()
        print(f"Provider: {provider.get_provider_name()}")
        print(f"\nOriginal code ({len(code)} chars):")
        print(code)

        result = provider.translate_to_prose(prompt, code)

        print(f"\nTranslated prose ({len(result['text'])} chars):")
        print(result['text'])
        print(f"\nTokens used: {result['tokens']}")

        print("\n✅ Individual translation successful!")

    except Exception as e:
        print(f"\n❌ Individual translation failed: {str(e)}")
        import traceback
        traceback.print_exc()


def main():
    """Run translation tests"""
    print("AI Code Translation Test Suite")
    print("="*80)
    print("\nNOTE: This requires a valid AI_PROVIDER and API key")
    print("      Set AI_PROVIDER=openai or AI_PROVIDER=anthropic")
    print("="*80)

    # Test 1: Individual block
    test_individual_block()

    # Test 2: Full document
    test_code_translation()

    print(f"\n{'='*80}")
    print("Tests complete!")
    print('='*80)


if __name__ == '__main__':
    main()
