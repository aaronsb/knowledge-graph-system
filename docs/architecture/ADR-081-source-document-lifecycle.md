# ADR-081: Source Document Lifecycle

**Status:** Proposed
**Date:** 2025-12-14
**Deciders:** @aaronsb, @claude
**Related ADRs:** ADR-080 (Garage Service Architecture), ADR-057 (Multimodal Image Ingestion)
**Closes:** #172 (partially)

## Context

When documents are ingested into the knowledge graph, the original source material is currently discarded after extraction. We retain:
- Chunked text in Source nodes (`full_text` property)
- Evidence quotes in Instance nodes
- Extracted concepts and relationships

But we lose:
- The original document as a cohesive unit
- Precise position information (line/character offsets)
- The ability to re-process with improved extraction
- Version history when documents are updated

### The Redundancy Question

Storing source documents in Garage while also keeping chunked evidence in the graph creates apparent duplication. However, this **intentional redundancy** enables critical capabilities:

| Scenario | Primary Source | Recovery From |
|----------|---------------|---------------|
| Garage unavailable | Graph evidence | Concatenate chunks to recreate source |
| Graph corrupted | Garage sources | Re-ingest to rebuild graph |
| Backup/restore | Either | Database backup OR Garage backup |
| Strategy change | Garage sources | Re-ingest with new matching mode |

This bidirectional relationship means the system can recover from either storage layer failing.

## Decision

### 1. Pre-Ingestion Storage

Store documents in Garage **before** ingestion begins:

```
┌─────────────────────────────────────────────────────────────────┐
│  Document Ingestion Flow                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Document ──► [Compute Hash] ──► [Dedup Check] ──► Decision     │
│                     │                  │              │         │
│                     ▼                  ▼              ▼         │
│              content_hash        Exact match?    Similarity?    │
│                                       │              │          │
│                     ┌─────────────────┴──────────────┘          │
│                     ▼                                           │
│              [Store in Garage] ◄─── garage_key assigned         │
│                     │                                           │
│                     ▼                                           │
│              [Chunk Document] ──► AST with offsets              │
│                     │                                           │
│                     ▼                                           │
│              [Extract Concepts] ──► Graph with positions        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Why pre-ingestion:**
- `garage_key` is known before Source nodes are created
- Deduplication check can reference stored content
- Even refused documents are archived (audit trail)
- Failure at any later step doesn't lose the original

### 2. Content-Based Identity

Documents are identified by content hash, not filename:

```python
def compute_document_identity(content: bytes, ontology: str) -> DocumentIdentity:
    """
    Compute content-based identity for a document.

    Returns:
        DocumentIdentity with hash, garage_key, and metadata
    """
    content_hash = hashlib.sha256(content).hexdigest()

    # Garage key uses hash prefix (12 chars = 48 bits = collision-resistant)
    # Extension preserved for content-type inference
    garage_key = f"sources/{sanitize(ontology)}/{content_hash[:12]}.txt"

    return DocumentIdentity(
        content_hash=content_hash,
        garage_key=garage_key,
        size_bytes=len(content)
    )
```

**Benefits:**
- Same content always gets same key (idempotent)
- Different content never collides
- Filename changes don't create duplicates
- Natural deduplication

### 3. Deduplication Tiers

| Match Level | Detection | Behavior | Rationale |
|-------------|-----------|----------|-----------|
| **Exact** (100%) | SHA-256 hash match | Refuse | Already ingested, no new information |
| **High similarity** (80-95%) | Cosine similarity of chunk embeddings | Warn + refuse | Likely same document with minor edits |
| **Forced similar** | User overrides warning | Ingest as version | Explicit acknowledgment of near-duplicate |
| **Novel** (<80%) | Below threshold | Normal ingest | Sufficiently different content |

The **80% threshold** aligns with existing concept deduplication - consistency across the system.

```python
class DeduplicationResult:
    status: Literal["exact_match", "high_similarity", "novel"]
    similarity_score: Optional[float]  # 0.0-1.0 for similar matches
    matching_document: Optional[str]   # garage_key of match
    can_force: bool                    # True if force=True would proceed

async def check_deduplication(
    content: bytes,
    ontology: str,
    force: bool = False
) -> DeduplicationResult:
    """
    Check if document is duplicate or near-duplicate.

    1. Compute hash, check for exact match
    2. If no exact match, chunk and embed
    3. Compare embeddings against existing sources
    4. Return result with similarity info
    """
```

### 4. Schema Changes

#### Source Node Enhancement

```cypher
(:Source {
    source_id: "src-abc123",
    document: "Philosophy",                    // Ontology name

    // Existing fields
    full_text: "The chunk text content...",   // Still needed for graph queries
    paragraph: 3,                              // Legacy paragraph number

    // NEW: Garage reference
    garage_key: "sources/Philosophy/a1b2c3d4e5f6.txt",
    content_hash: "a1b2c3d4e5f6789...",       // Full SHA-256

    // NEW: Position in original document
    char_offset_start: 4521,                  // Character position
    char_offset_end: 5847,
    line_start: 142,                          // Line numbers
    line_end: 189,
    chunk_index: 3,                           // Sequential chunk number

    // NEW: Chunking metadata
    chunk_method: "ast_semantic",             // How it was chunked
    overlap_chars: 200                        // Overlap with adjacent chunks
})
```

#### Document Node (New)

Track document-level metadata separately from chunks:

```cypher
(:Document {
    garage_key: "sources/Philosophy/a1b2c3d4e5f6.txt",
    content_hash: "a1b2c3d4e5f6789...",
    ontology: "Philosophy",

    // Metadata
    original_filename: "watts_zen.txt",       // For display only
    size_bytes: 45230,
    chunk_count: 12,
    ingested_at: datetime(),

    // Versioning
    version: 1,
    supersedes: null,                         // Previous version's garage_key
    superseded_by: null                       // Newer version's garage_key
})

// Relationship to chunks
(:Document)-[:HAS_CHUNK {index: 0}]->(:Source)
(:Document)-[:HAS_CHUNK {index: 1}]->(:Source)
```

### 5. Bidirectional Regeneration

#### Graph → Garage (Source Recovery)

When Garage is unavailable or corrupted, reconstruct from graph:

```python
async def regenerate_source_from_graph(garage_key: str) -> bytes:
    """
    Reconstruct original document from graph evidence.

    Chunks are stored with offset information, enabling
    precise reconstruction of the original document.
    """
    # Get all chunks for this document, ordered by offset
    chunks = await graph.query("""
        MATCH (s:Source {garage_key: $key})
        RETURN s.full_text, s.char_offset_start, s.chunk_index
        ORDER BY s.chunk_index
    """, key=garage_key)

    # Handle overlaps - chunks may have 200 char overlap
    # Use char_offset_start to deduplicate overlapping regions
    content = reconstruct_with_overlaps(chunks)

    return content.encode('utf-8')


async def restore_garage_from_graph(ontology: str = None):
    """
    Bulk restore Garage sources from graph evidence.

    Use cases:
    - Garage failure recovery
    - Migration to new Garage instance
    - Disaster recovery
    """
    documents = await graph.query("""
        MATCH (d:Document)
        WHERE $ontology IS NULL OR d.ontology = $ontology
        RETURN d.garage_key
    """, ontology=ontology)

    for doc in documents:
        content = await regenerate_source_from_graph(doc.garage_key)
        await garage.store(doc.garage_key, content)

    return {"restored": len(documents)}
```

#### Garage → Graph (Graph Regeneration)

When the graph is corrupted or needs re-processing:

```python
async def regenerate_graph_from_garage(
    ontology: str,
    strategy: ConceptMatchingStrategy = "hybrid",
    dry_run: bool = True
) -> RegenerationPlan:
    """
    Re-ingest all documents for an ontology from Garage.

    Use cases:
    - Graph corruption recovery
    - Strategy experimentation (random vs popularity vs hybrid)
    - Schema migration requiring full re-extraction
    - Testing extraction improvements

    Args:
        ontology: Which ontology to regenerate
        strategy: Concept matching strategy to use
            - "random": Full random sampling for matches
            - "popularity": Max popularity by edge count
            - "hybrid": Popularity with random tail
        dry_run: If True, return plan without executing

    Returns:
        RegenerationPlan with estimated cost and changes
    """
    # List all source documents for ontology
    documents = await garage.list(prefix=f"sources/{ontology}/")

    if dry_run:
        return RegenerationPlan(
            document_count=len(documents),
            estimated_chunks=estimate_chunks(documents),
            estimated_cost=estimate_llm_cost(documents),
            strategy=strategy
        )

    # Clear existing graph data for ontology
    await graph.execute("""
        MATCH (s:Source {document: $ontology})
        DETACH DELETE s
    """, ontology=ontology)

    await graph.execute("""
        MATCH (c:Concept)-[:APPEARS_IN]->(:Source {document: $ontology})
        WHERE NOT EXISTS((c)-[:APPEARS_IN]->(:Source))
        DETACH DELETE c
    """, ontology=ontology)

    # Re-ingest each document
    for doc in documents:
        content = await garage.get(doc.key)
        await ingest_document(
            content=content,
            ontology=ontology,
            strategy=strategy,
            skip_dedup=True  # We know these are unique
        )

    return RegenerationResult(
        documents_processed=len(documents),
        concepts_created=...,
        strategy=strategy
    )
```

### 6. Deletion Cascade (Forgetting)

Remove a document and its associated knowledge:

```python
async def delete_document(
    garage_key: str,
    cascade: Literal["orphans", "all", "none"] = "orphans"
) -> DeletionResult:
    """
    Delete a document and optionally its derived knowledge.

    Args:
        garage_key: Document to delete
        cascade: What to delete beyond the document
            - "none": Only delete from Garage, leave graph intact
            - "orphans": Delete Sources, delete Concepts with no other evidence
            - "all": Delete Sources and ALL connected Concepts

    Use cases:
    - Removing incorrect/outdated information
    - GDPR/privacy compliance (right to be forgotten)
    - "Compressing memories" - removing low-value evidence
    """
    result = DeletionResult(garage_key=garage_key)

    if cascade in ("orphans", "all"):
        # Delete Source nodes for this document
        sources = await graph.execute("""
            MATCH (s:Source {garage_key: $key})
            DETACH DELETE s
            RETURN count(s) as deleted
        """, key=garage_key)
        result.sources_deleted = sources.deleted

        if cascade == "orphans":
            # Delete concepts with no remaining evidence
            concepts = await graph.execute("""
                MATCH (c:Concept)
                WHERE NOT EXISTS((c)-[:APPEARS_IN]->(:Source))
                  AND NOT EXISTS((c)-[:EVIDENCED_BY]->(:Instance))
                DETACH DELETE c
                RETURN count(c) as deleted
            """)
            result.concepts_deleted = concepts.deleted

        elif cascade == "all":
            # More aggressive - would need concept tracking
            # Not implemented in v1
            raise NotImplementedError("Full cascade not yet supported")

    # Delete from Garage
    await garage.delete(garage_key)
    result.garage_deleted = True

    # Delete Document node
    await graph.execute("""
        MATCH (d:Document {garage_key: $key})
        DELETE d
    """, key=garage_key)

    return result
```

### 7. Version Management

When a similar document is force-ingested:

```python
async def ingest_as_version(
    content: bytes,
    ontology: str,
    supersedes: str  # garage_key of previous version
) -> IngestResult:
    """
    Ingest document as a new version of an existing document.

    The new version:
    - Gets its own garage_key (based on new content hash)
    - Links to previous version via supersedes relationship
    - Creates new Source nodes (may deduplicate to same Concepts)
    - Novel concepts from the 5-20% difference become new nodes
    """
    # Compute identity for new content
    identity = compute_document_identity(content, ontology)

    # Store in Garage
    await garage.store(identity.garage_key, content)

    # Create Document node with version link
    await graph.execute("""
        MATCH (old:Document {garage_key: $supersedes})
        CREATE (new:Document {
            garage_key: $new_key,
            content_hash: $hash,
            ontology: $ontology,
            version: old.version + 1,
            supersedes: $supersedes,
            ingested_at: datetime()
        })
        SET old.superseded_by = $new_key
    """,
        supersedes=supersedes,
        new_key=identity.garage_key,
        hash=identity.content_hash,
        ontology=ontology
    )

    # Normal ingestion - dedup will attach to existing concepts
    # where appropriate, create new for novel content
    return await ingest_document(content, ontology, garage_key=identity.garage_key)
```

## Consequences

### Positive

1. **Bidirectional Recovery**: Either storage layer can restore the other
2. **Strategy Experimentation**: Re-generate graph with different matching modes
3. **Audit Trail**: Original documents preserved for compliance/debugging
4. **Version History**: Track document evolution over time
5. **Precise Provenance**: Line/character offsets enable source highlighting
6. **Simplified Backup**: Either database OR Garage backup is sufficient

### Negative

1. **Storage Duplication**: Same content in Garage and graph (intentional)
2. **Schema Changes**: Requires migration for new Source/Document properties
3. **Complexity**: More moving parts in ingestion pipeline
4. **Regeneration Cost**: Re-ingesting is expensive (LLM calls)

### Neutral

1. **Eventual Consistency**: Graph and Garage may briefly diverge during operations
2. **Deletion is Rare**: Most use cases are additive, not subtractive
3. **Versioning Optional**: Can ignore version management if not needed

## Implementation Plan

### Phase 1: Pre-Ingestion Storage
1. Update ingestion to compute hash first
2. Store document in Garage before chunking
3. Add `garage_key` and `content_hash` to Source nodes
4. Add offset tracking during chunking

### Phase 2: Deduplication Enhancement
1. Implement exact-match deduplication (hash)
2. Implement similarity-based deduplication (embeddings)
3. Add force override with versioning
4. Update API to return dedup warnings

### Phase 3: Document Node + Regeneration
1. Create Document node type
2. Implement graph → Garage regeneration
3. Implement Garage → graph regeneration
4. Add admin endpoints for recovery operations

### Phase 4: Deletion
1. Implement cascade deletion
2. Add orphan cleanup
3. Document the "forgetting" workflow

## Migration

```sql
-- Migration 034: Source document lifecycle

-- Add new columns to track document position
-- (Applied via AGE property updates, not ALTER TABLE)

-- New Document label
-- (Created automatically when first Document node is created)
```

Graph properties are schemaless, so new fields can be added incrementally during ingestion. Existing Source nodes without the new properties continue to work.

## References

- Issue #172: Expand Garage storage for projections and source documents
- ADR-080: Garage Service Architecture
- ADR-057: Multimodal Image Ingestion
- Concept matching modes: random sampling, popularity-weighted, hybrid
