#!/usr/bin/env python3
"""
Test script for markdown preprocessing pipeline.

Tests AST parsing and serialization without AI translation.
Can be run standalone to verify preprocessing before API integration.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.api.lib.markdown_preprocessor import MarkdownPreprocessor


def test_single_file(file_path: str, show_output: bool = False):
    """Test preprocessing on a single markdown file"""
    print(f"\n{'='*80}")
    print(f"Testing: {file_path}")
    print('='*80)

    with open(file_path, 'r') as f:
        content = f.read()

    preprocessor = MarkdownPreprocessor(max_workers=3, code_min_lines=3)
    result = preprocessor.preprocess(content)

    stats = preprocessor.get_stats()

    print(f"\nInput:  {len(content):,} characters")
    print(f"Output: {len(result):,} characters")
    print(f"\nStatistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    if show_output:
        print(f"\n{'-'*80}")
        print("FIRST 500 CHARS:")
        print('-'*80)
        print(result[:500])
        print(f"\n{'-'*80}")
        print("LAST 500 CHARS:")
        print('-'*80)
        print(result[-500:])

    return stats


def test_docs_directory():
    """Test on multiple files from /docs"""
    docs_dir = Path('docs')

    if not docs_dir.exists():
        print("Error: docs/ directory not found")
        return

    # Find markdown files
    md_files = list(docs_dir.rglob('*.md'))

    print(f"\nFound {len(md_files)} markdown files in docs/")

    # Test a few complex ones
    test_files = [
        'docs/api/OPENCYPHER_QUERIES.md',
        'docs/architecture/ADR-016-apache-age-migration.md',
        'docs/guides/QUICKSTART.md',
    ]

    total_stats = {
        'blocks_detected': 0,
        'blocks_translated': 0,
        'blocks_stripped': 0,
        'blocks_kept': 0,
    }

    for file_path in test_files:
        if Path(file_path).exists():
            stats = test_single_file(file_path, show_output=False)
            for key in total_stats:
                total_stats[key] += stats.get(key, 0)
        else:
            print(f"⚠ File not found: {file_path}")

    print(f"\n{'='*80}")
    print("TOTAL STATISTICS")
    print('='*80)
    for key, value in total_stats.items():
        print(f"  {key}: {value}")


def test_embedded_sample():
    """Test with an embedded sample containing various edge cases"""
    sample = '''# Test Document with Edge Cases

## Regular Code Block

```python
def calculate_similarity(a, b):
    """Calculate cosine similarity"""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
```

## Cypher Query (Parser Breaker!)

```cypher
MATCH (c:Concept {concept_id: $id})
WHERE c.label CONTAINS "query"
RETURN c.label, c.search_terms
```

## Mermaid Diagram

```mermaid
graph TD
    A[Document] --> B[Chunk]
    B --> C[Extract]
    C --> D[Store]
```

## JSON Configuration

```json
{
  "model": "gpt-4o-mini",
  "temperature": 0.7,
  "max_tokens": 500
}
```

## Short Code Block (Should Strip)

```bash
ls -la
```

## Lists and Formatting

1. **Bold item** with text
2. *Italic item* with text
3. Regular item

- Bullet with `inline code`
- Bullet with [link](https://example.com)

## Inline Code

This paragraph has `inline_code` and even longer inline code like `MATCH (c:Concept) RETURN c`.

## Conclusion

This tests various edge cases from ADR-023.
'''

    print(f"\n{'='*80}")
    print("Testing Embedded Sample (Edge Cases)")
    print('='*80)

    preprocessor = MarkdownPreprocessor(max_workers=3, code_min_lines=3)
    result = preprocessor.preprocess(sample)

    stats = preprocessor.get_stats()

    print(f"\nInput:  {len(sample):,} characters")
    print(f"Output: {len(result):,} characters")
    print(f"\nStatistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print(f"\n{'-'*80}")
    print("OUTPUT:")
    print('-'*80)
    print(result)

    # Verify structure is preserved
    assert '# Test Document with Edge Cases' in result
    assert '## Regular Code Block' in result
    assert '## Lists and Formatting' in result
    assert '1. **Bold item** with text' in result
    assert '- Bullet with `inline code`' in result

    print(f"\n✅ Structure verification: PASSED")


def main():
    """Run all tests"""
    print("Markdown Preprocessing Test Suite")
    print("="*80)

    # Test 1: Embedded sample with edge cases
    test_embedded_sample()

    # Test 2: Real documentation files
    test_docs_directory()

    print(f"\n{'='*80}")
    print("All tests completed successfully!")
    print('='*80)


if __name__ == '__main__':
    main()
