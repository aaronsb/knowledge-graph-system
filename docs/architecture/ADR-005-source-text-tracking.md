# ADR-005: Source Text Tracking and Retrieval

**Status:** Proposed
**Date:** 2025-10-08
**Deciders:** System Architecture
**Related:** ADR-004 (Pure Graph Design)

## Context

Concepts in a knowledge graph need traceability back to their original source text for verification, context, and citation purposes. Storing full document text in graph nodes creates storage overhead and versioning challenges. A clear strategy is needed for linking concepts to source material while keeping the graph focused on relationships.

## Decision

Use markdown as the canonical source format with paragraph/sentence indexing. The graph stores references and metadata, not full document text. Actual source text remains in version-controlled markdown files on the filesystem.

### Source Storage Model

**Document Store (File System):**
```
documents/
  governed-agility.md           # Source markdown
  watts-lecture-1.md
  safe-framework.md

.document-index/
  governed-agility.json         # Paragraph/sentence offsets
  {
    "paragraphs": [
      {"id": 1, "start": 0, "end": 245, "sentences": 3},
      {"id": 2, "start": 246, "end": 512, "sentences": 2}
    ]
  }
```

**Graph References:**
```cypher
(:Source {
  source_id: "governed-agility_p42",
  document: "governed-agility",
  document_path: "documents/governed-agility.md",
  paragraph: 42,
  paragraph_start_char: 5234,
  paragraph_end_char: 5687,
  full_text: "..."  // The paragraph text (optional, for quick access)
})

(:Instance {
  instance_id: "...",
  quote: "exact verbatim quote from text",
  char_offset_start: 5341,  // Offset within document
  char_offset_end: 5423,
  sentence_index: 2          // Which sentence in paragraph
})
```

### Retrieval Pattern

**Query: Get concept with full context**
```cypher
MATCH (concept:Concept {concept_id: $id})
MATCH (concept)-[:EVIDENCED_BY]->(instance:Instance)
MATCH (instance)-[:FROM_SOURCE]->(source:Source)
RETURN
  concept.label as concept,
  instance.quote as evidence,
  source.document as document,
  source.paragraph as paragraph,
  source.document_path as file_path,
  source.full_text as context
ORDER BY source.paragraph
```

**Retrieval Service:**
```python
def get_concept_with_context(concept_id: str):
    # Query graph for references
    result = neo4j.run(query, concept_id=concept_id)

    for record in result:
        # Option 1: Use cached paragraph text from Source node
        context = record["context"]

        # Option 2: Retrieve from markdown file (if not cached)
        if not context:
            context = retrieve_paragraph(
                file_path=record["file_path"],
                paragraph_num=record["paragraph"]
            )

        yield {
            "concept": record["concept"],
            "evidence": record["evidence"],
            "source_document": record["document"],
            "source_paragraph": record["paragraph"],
            "source_context": context
        }
```

### Markdown as Canonical Format

**Ingestion converts all formats to markdown:**
- PDF → markdown (via pandoc or similar)
- DOCX → markdown
- HTML → markdown
- Plain text → markdown (trivial)

**Benefits:**
- Simple, git-friendly format
- Easy to version control
- Human readable
- Preserves structure (headers, lists, emphasis)
- Can embed metadata in frontmatter

### Text Retrieval Modes

**1. Quote Only (Fast):**
```python
instance.quote  # Just the extracted quote
```

**2. Paragraph Context (Medium):**
```python
source.full_text  # Entire paragraph containing quote
```

**3. Document Section (Slower):**
```python
retrieve_markdown_section(
    document="governed-agility.md",
    start_paragraph=40,
    end_paragraph=45
)
```

**4. Full Document (Rare):**
```python
retrieve_full_document("governed-agility.md")
```

## Consequences

### Positive
- Graph stores compact references, not bulky text
- Source text remains in version-controlled markdown files
- Flexible retrieval based on context needs (quote → paragraph → section → document)
- Can reconstruct full context when needed
- Supports incremental loading strategies
- Markdown files can be edited/versioned independently

### Negative
- Requires file system access in addition to graph database
- Paragraph indexing adds preprocessing overhead during ingestion
- Changes to source files can break references if not managed carefully
- Need strategy for handling moved/renamed source files

### Neutral
- Optional caching of paragraph text in Source nodes (space/speed tradeoff)
- May need garbage collection for orphaned source files
- Version control strategy needed for source documents
