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

### The Knowledge Keeper Model

Think of the system as a knowledge keeper with a warehouse:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        THE KNOWLEDGE KEEPER                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  WAREHOUSE (Garage)              MIND (Graph)                       │
│  ═══════════════════             ══════════════                     │
│                                                                     │
│    Books                           WHY I kept them                  │
│    Documents                       HOW they connect                 │
│    Pictures                        WHAT they mean together          │
│    Artifacts                       The project context              │
│                                    The relationships I see          │
│    (storage)                       (understanding)                  │
│                                                                     │
│         │            FILING SYSTEM              │                   │
│         │            ══════════════             │                   │
│         └───────►    Document nodes    ◄────────┘                   │
│                      Source nodes                                   │
│                      (where things are)                             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

- **Garage** = The warehouse (physical artifacts, content storage)
- **Document/Source nodes** = The filing system (organization, location, offsets)
- **Concepts + Relationships** = The mind (meaning, context, the "why")

The graph isn't just an index - it's the **understanding layer**. Concepts and relationships capture what a filing system never could: *"I collected these systems architecture docs because of that project, which connects to these project management behaviors..."*

### The Redundancy Question

Storing source documents in Garage while also keeping chunked evidence in the graph creates apparent duplication. However, this **intentional redundancy** enables resilience:

| Scenario | What Happens | Recovery |
|----------|--------------|----------|
| **Warehouse disaster** | Garage storage lost | Mind rebuilds warehouse from last backup |
| **New keeper** | Graph cleared or strategy change | New keeper re-reads all documents, builds fresh understanding |
| **Routine backup** | Either layer backed up | Database backup OR Garage backup sufficient |

The "new keeper" scenario is particularly valuable: re-ingesting the same documents with a different extraction strategy (random sampling → popularity-weighted → hybrid) produces different interpretations of the same source material.

### Model Evolution Insurance

In traditional software, storing both source documents and parsed data might be overbuilding. However, in LLM-based knowledge graphs, the "parser" (the LLM + prompts) is **non-deterministic and rapidly evolving**.

Consider: today we extract concepts using a 2024-era model. When next-generation models arrive with superior reasoning, documents ingested today would be locked to 2024 extraction quality - unless we kept the sources.

| Without Source Storage | With Source Storage |
|------------------------|---------------------|
| Locked to extraction model at ingestion time | Re-extract with future models |
| Graph quality is frozen | Graph intelligence grows with model improvements |
| No way to benefit from prompt improvements | Re-run with better prompts |

**ADR-081 is an insurance policy against model obsolescence.** It allows replaying history with smarter agents later.

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

    # Garage key uses hash prefix (32 chars = 128 bits = UUID-equivalent)
    # This provides collision resistance for a future sharded universe
    # where billions of documents may exist across many shards.
    # Extension preserved for content-type inference.
    garage_key = f"sources/{sanitize(ontology)}/{content_hash[:32]}.txt"

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

**Why 32 characters (128 bits)?**

| Hash Length | Bits | 50% Collision At | Suitability |
|-------------|------|------------------|-------------|
| 12 chars | 48 | ~17 million | Single instance only |
| 16 chars | 64 | ~4 billion | Tight for universe |
| 32 chars | 128 | ~18 quintillion | UUID-equivalent ✓ |

The 128-bit namespace provides collision resistance for a future sharded universe where billions of documents may exist across many shards. This follows the well-understood UUID pattern with extensive library support.

### 3. Deduplication Strategy

**Implemented: Hash-Based Exact Match**

| Match Level | Detection | Behavior | Rationale |
|-------------|-----------|----------|-----------|
| **Exact** (100%) | SHA-256 hash match | Refuse (unless `force=true`) | Already ingested, no new information |
| **In progress** | Job status check | Refuse | Already processing or queued |
| **Recent** (<30 days) | Timestamp check | Refuse (unless `force=true`) | Recently ingested |
| **Novel** | No match | Normal ingest | New content |

This is implemented via `ContentHasher` → `DocumentMeta` lookup (ADR-051).

**Deferred: Similarity-Based Detection**

Document-level embedding similarity was considered but **intentionally not implemented**:

1. **Concept-level dedup is the unique strength** — The graph already deduplicates
   semantically at the concept level during ingestion. Each concept is matched against
   existing concepts via embedding similarity. This is where semantic understanding happens.

2. **Wrong layer for intelligence** — Document-level similarity tries to be smart at
   the file level instead of the knowledge level. We're not building a document
   similarity engine.

3. **Hash exact-match is sufficient** — True duplicates (same bytes) are caught by hash.
   Near-duplicates (formatting changes, typo fixes) are rare edge cases. If they occur,
   concept-level matching handles semantic overlap anyway.

4. **Latency concern** — Similarity check requires embedding the document before
   making the dedup decision, adding ~100-500ms latency per document.

If similarity-based detection becomes necessary in the future, the infrastructure
exists (embeddings, similarity functions) but should be an optional admin tool
rather than a blocking gate.

### 4. Schema Changes

#### Source Node Enhancement

```cypher
(:Source {
    source_id: "src-abc123",
    document: "Philosophy",                    // Ontology name

    // Existing fields
    full_text: "The chunk text content...",   // Still needed for graph queries
    paragraph: 3,                              // Legacy paragraph number

    // NEW: Garage reference (32-char hash = 128 bits)
    garage_key: "sources/Philosophy/a1b2c3d4e5f6789012345678abcdef01.txt",
    content_hash: "a1b2c3d4e5f6789012345678abcdef01...",  // Full SHA-256

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
    garage_key: "sources/Philosophy/a1b2c3d4e5f6789012345678abcdef01.txt",
    content_hash: "a1b2c3d4e5f6789012345678abcdef01...",  // Full SHA-256
    ontology: "Philosophy",

    // Metadata
    original_filename: "watts_zen.txt",       // For display only
    size_bytes: 45230,
    chunk_count: 12,
    ingested_at: datetime(),

    // Versioning
    version: 1,
    supersedes: null,                         // Previous version's garage_key
    superseded_by: null,                      // Newer version's garage_key

    // Shard provenance (for future universe of shards)
    shard_origin: null                        // Shard ID if received via trade
})

// Relationship to chunks
(:Document)-[:HAS_CHUNK {index: 0}]->(:Source)
(:Document)-[:HAS_CHUNK {index: 1}]->(:Source)
```

### 5. Graph Regeneration (New Keeper Scenario)

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

1. **Model Evolution Insurance**: Re-extract with future LLMs as they improve
2. **New Keeper Recovery**: Re-ingest from Garage with different extraction strategy
3. **Strategy Experimentation**: Re-generate graph with different matching modes
4. **Audit Trail**: Original documents preserved for compliance/debugging
5. **Version History**: Track document evolution over time
6. **Precise Provenance**: Line/character offsets enable source highlighting
7. **Backup Flexibility**: Garage backup preserves source truth; graph is rebuildable

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

### Phase 1: Pre-Ingestion Storage ✓
1. ✓ Update ingestion to compute hash first
2. ✓ Store document in Garage before chunking
3. ✓ Add `garage_key` and `content_hash` to Source nodes
4. ✓ Add offset tracking during chunking (`char_offset_start`, `char_offset_end`, `chunk_index`)
5. ✓ Add `garage_key` to DocumentMeta node

### Phase 2: Deduplication
1. ✓ Exact-match deduplication (hash) — Already implemented via ContentHasher + DocumentMeta
2. ✗ Similarity-based deduplication — **Deferred** (see "Deduplication Strategy" section)
3. Force override with versioning — Optional future enhancement
4. Update API to return dedup warnings — Optional future enhancement

### Phase 3: Regeneration (Optional)
1. Implement Garage → graph regeneration ("new keeper" scenario)
2. Add admin endpoints for recovery operations

### Phase 4: Deletion (Optional)
1. Implement cascade deletion
2. Add orphan cleanup
3. Document the "forgetting" workflow

Note: DocumentMeta (ADR-051) serves as the Document node type. No separate :Document label needed.

## Migration

```sql
-- Migration 034: Source document lifecycle

-- Add new columns to track document position
-- (Applied via AGE property updates, not ALTER TABLE)

-- New Document label
-- (Created automatically when first Document node is created)
```

Graph properties are schemaless, so new fields can be added incrementally during ingestion. Existing Source nodes without the new properties continue to work.

## Enables: Semantic FUSE Filesystem (ADR-069)

This ADR provides the final foundational piece for the Semantic FUSE Filesystem (ADR-069):

```
ADR-057 (Images in Garage)
    ↓
ADR-079 (Projections in Garage)
    ↓
ADR-081 (Source Documents in Garage) ← THIS ADR
    ↓
ADR-069 (Semantic FUSE Filesystem)
```

**Why source document storage enables FUSE:**

1. **Document Retrieval**: FUSE can serve original documents via `cat /mnt/knowledge/ontology/source.txt`
2. **Position Highlighting**: Offset information (`char_offset_start/end`, `line_start/end`) enables displaying exact evidence locations within source documents
3. **Bidirectional Navigation**: From concept → evidence → source chunk → original document (all resolvable)
4. **Backup/Restore Symmetry**: FUSE can operate on either graph or Garage as authoritative source

**Future FUSE operations enabled:**

```bash
# Navigate to source document from concept
cat /mnt/knowledge/embedding-models/unified-regeneration.concept/evidence/1/source.txt

# The source.txt is fetched from Garage using garage_key
# Offset metadata enables highlighting the exact quote

# Regenerate graph from FUSE-mounted Garage sources
find /mnt/garage/sources/Philosophy/*.txt | xargs kg ingest --strategy hybrid
```

Without source documents in Garage (this ADR), FUSE would only expose graph-derived content. With this ADR, FUSE can expose the complete document lifecycle - original sources, extracted concepts, and their relationships.

## Future Considerations

### Graph → Garage Reconstruction (YAGNI)

The offset information stored in Source nodes (`char_offset_start`, `char_offset_end`, `chunk_index`) theoretically enables reconstructing original documents from graph chunks. This would allow recovery if Garage is lost but the graph is intact.

**Not implemented because:**
- Rare scenario (Garage lost, graph intact, no Garage backup)
- Garage backups are simpler and more reliable
- Adds complexity without clear near-term value

**If needed later**, the implementation would:
1. Query all Source nodes for a `garage_key`, ordered by `chunk_index`
2. Handle chunk overlaps using `char_offset_start` to deduplicate
3. Concatenate to reconstruct original document

A TODO comment in the code will document this possibility without implementing it.

## References

- Issue #172: Expand Garage storage for projections and source documents
- ADR-069: Semantic FUSE Filesystem (enabled by this ADR)
- ADR-080: Garage Service Architecture
- ADR-057: Multimodal Image Ingestion
- Concept matching modes: random sampling, popularity-weighted, hybrid
