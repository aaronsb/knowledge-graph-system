# Concepts and Terminology

A comprehensive guide to understanding the knowledge graph system's terminology, conceptual model, and how we protect your LLM token investment.

---

## Table of Contents

- [Core Concepts](#core-concepts)
- [Ontology in This System](#ontology-in-this-system)
- [Graph Integrity](#graph-integrity)
- [Stitching and Pruning](#stitching-and-pruning)
- [Apache AGE Graph Database](#apache-age-graph-database)
- [Token Investment Protection](#token-investment-protection)
- [Workflow Scenarios](#workflow-scenarios)

---

## Core Concepts

### Knowledge Graph

A **knowledge graph** represents information as an interconnected network of concepts and their relationships, rather than linear text. This enables:

- **Semantic exploration**: Navigate by meaning, not sequential reading
- **Multi-dimensional understanding**: See how ideas connect across documents
- **Relationship discovery**: Find implied connections the LLM identified

### Concept Extraction

When you ingest a document, the LLM (GPT-4 or Claude) extracts:

1. **Concepts**: Core ideas, entities, or principles (e.g., "Linear Thinking", "Emergence")
2. **Relationships**: How concepts connect (IMPLIES, SUPPORTS, CONTRADICTS, etc.)
3. **Evidence**: Specific quotes from the source text supporting each concept
4. **Embeddings**: 1536-dimensional vector representations for semantic similarity

This extraction process costs tokens ($0.10-0.50 per document depending on size and complexity).

---

## Ontology in This System

### What is an Ontology Here?

In traditional philosophy/computer science, an **ontology** is a formal specification of a conceptualization - a structured framework defining entities and relationships in a domain.

**In this system**, we use "ontology" more loosely to mean:

> **A collection of concepts extracted from a related set of source documents that form a coherent knowledge domain.**

Think of it as a **thematic knowledge cluster** or **conceptual domain**.

### Examples

- **Ontology**: "Alan Watts Lectures"
  - Sources: watts_lecture_1.txt, watts_lecture_2.txt, watts_lecture_3.txt
  - Concepts: "Linear Thinking", "Eastern Philosophy", "Paradox", etc.

- **Ontology**: "Agile Methodology"
  - Sources: agile_manifesto.pdf, scrum_guide.md, kanban_principles.txt
  - Concepts: "Iterative Development", "User Stories", "Retrospectives", etc.

### Ontology as Document Grouping

When you ingest a document, you specify an ontology name:

```bash
python cli.py ingest watts_lecture_1.txt --ontology "Alan Watts Lectures"
```

This creates a boundary in the graph:
- All concepts from this document are tagged with this ontology
- Relationships to concepts in OTHER ontologies are tracked
- You can backup/restore by ontology (domain isolation)

### Cross-Ontology Relationships

The LLM may identify that a concept in one ontology relates to a concept in another:

```
[Ontology: Alan Watts]
  Concept: "Linear Thinking"
    |
    | CONTRADICTS
    |
    v
  Concept: "Agile Mindset"  [Ontology: Agile Methodology]
```

This is a **cross-ontology relationship** - it connects different knowledge domains.

---

## Graph Integrity

### What is Graph Integrity?

Graph integrity means:

> **Every relationship in the graph points to concepts that actually exist, ensuring traversal queries work correctly.**

### The Integrity Problem

Graph database relationships are like pointers - they reference nodes by their properties. A **dangling relationship** occurs when:

1. A relationship exists: `(ConceptA)-[:IMPLIES]->(ConceptB)`
2. But `ConceptB` doesn't exist in the database
3. Traversal queries break or return incomplete results

### How Dangling Relationships Happen

**Scenario**: You backup "Alan Watts Lectures" ontology, which has relationships to concepts in "Agile Methodology" ontology.

1. **Backup**: Only saves "Alan Watts" concepts, but remembers the relationships to "Agile" concepts
2. **Restore to new database**: "Alan Watts" concepts are imported
3. **Problem**: Relationships point to "Agile" concepts that don't exist in new database
4. **Result**: Dangling references, broken graph integrity

### Why This Matters

```cypher
// This query will break with dangling relationships
MATCH (c:Concept {label: "Linear Thinking"})-[:IMPLIES*1..3]->(related)
RETURN related
```

If `IMPLIES` relationships point to non-existent concepts, traversal fails or returns incomplete paths.

---

## Stitching and Pruning

Two strategies for handling dangling relationships after a partial ontology restore.

### The Problem: Torn Ontological Fabric

When you restore a partial backup, external concept references create "tears" in the conceptual fabric:

```
[Restored Ontology]              [Missing Ontology]

Concept A ──IMPLIES──> ??? Concept X (doesn't exist)
Concept B ──SUPPORTS─> ??? Concept Y (doesn't exist)
```

These dangling pointers break graph integrity. You **MUST** choose how to handle them:

### Option 1: Pruning (Isolation)

**Prune** = Cut away the torn edges, keep ontology isolated

```
[Restored Ontology - Isolated]

Concept A                (relationship removed)
Concept B                (relationship removed)
```

**When to use:**
- You want strict ontology boundaries
- Cross-domain connections aren't needed
- You're restoring into a clean database (auto-selected)

**Command:**
```bash
python -m src.admin.prune --ontology "Alan Watts Lectures"
```

**Result:**
- ✓ Clean, self-contained ontology
- ✓ All queries work within this domain
- ✗ Cross-domain insights lost

### Option 2: Stitching (Semantic Reconnection)

**Stitch** = Reconnect torn edges to similar concepts in the target database

```
[Restored Ontology]              [Target Database]

Concept A ──IMPLIES──> ??? ──similarity──> Concept X' (85% similar)
Concept B ──SUPPORTS─> ??? ──similarity──> Concept Y' (92% similar)
```

**How it works:**
1. Identifies external concept references
2. Uses vector similarity to find similar concepts in target database
3. Reconnects relationships to the best matches (above threshold)
4. Auto-prunes unmatched references (100% edge handling)

**When to use:**
- Restoring into a database with related ontologies
- You want to preserve cross-domain connections
- Semantic merging of knowledge domains

**Command:**
```bash
python -m src.admin.stitch --backup backups/alan_watts.json --threshold 0.85
```

**Result:**
- ✓ Cross-domain connections preserved (where similar concepts exist)
- ✓ Semantic integration across knowledge bases
- ⚠ Requires careful threshold tuning (too low = false connections, too high = nothing matches)

### Auto-Pruning in Stitcher

The stitcher **always** ensures 100% edge handling:

1. **Match**: Find similar concepts above threshold
2. **Stitch**: Reconnect relationships to matches
3. **Auto-prune**: Remove relationships to unmatched concepts

This guarantees graph integrity - no dangling edges remain.

### Clean Database Scenario

**Special case**: Restoring partial ontology into an empty database

```
[Empty Database]  +  [Partial Backup with external refs]
```

**Behavior**:
- System detects 0 existing concepts
- Auto-selects **prune** mode (stitching is impossible)
- User sees: *"✓ Target database is empty - will auto-prune to keep ontology isolated"*
- No prompts, automatic handling

---

## Apache AGE Graph Database

### Why Apache AGE?

Apache AGE (A Graph Extension) is a PostgreSQL extension that provides graph database capabilities:

1. **Nodes**: Represent entities (Concepts, Sources, Instances)
2. **Relationships**: First-class citizens with properties
3. **Traversal**: Fast path queries across connected data using openCypher
4. **openCypher**: Open-source declarative query language for graph patterns
5. **PostgreSQL Integration**: Combines graph and relational data in a single database
6. **Cost-Effective**: Open-source alternative to proprietary graph databases

### Data Model

```
(:Concept)                  Core idea extracted by LLM
  ├─ concept_id            Unique identifier
  ├─ label                 Human-readable name
  ├─ search_terms          Synonyms/related terms
  └─ embedding            1536-dim vector (OpenAI)

(:Source)                   Paragraph from source document
  ├─ source_id            Unique identifier
  ├─ document             Ontology name
  ├─ file_path            Source file
  ├─ paragraph_number     Position in document
  └─ full_text           Complete paragraph text

(:Instance)                 Specific evidence for concept
  ├─ instance_id          Unique identifier
  └─ quote                Exact quote from source

Relationships:
  (:Concept)-[:APPEARS_IN]->(:Source)        Concept found in source
  (:Concept)-[:EVIDENCED_BY]->(:Instance)    Evidence for concept
  (:Instance)-[:FROM_SOURCE]->(:Source)      Instance from source
  (:Concept)-[:IMPLIES|SUPPORTS|CONTRADICTS|...]->(:Concept)
```

### Vector Embeddings

Every concept has a 1536-dimensional embedding from OpenAI's `text-embedding-3-small`:

- **Semantic similarity**: Find related concepts by vector distance
- **Matching**: Used in stitching to find similar concepts
- **Search**: Power semantic search beyond keyword matching

**Critical**: Embeddings MUST be preserved in backups - they're expensive to regenerate.

### Ontology Boundaries

Concepts are tagged with their ontology via the `APPEARS_IN` relationship:

```cypher
(:Concept)-[:APPEARS_IN]->(:Source {document: "Alan Watts Lectures"})
```

This enables:
- Filtering queries by ontology
- Selective backup/restore
- Cross-ontology relationship tracking

---

## Token Investment Protection

### The Cost Problem

LLM-powered knowledge extraction is expensive:

- **Small document** (5 pages): ~10,000 tokens = $0.10
- **Medium document** (50 pages): ~100,000 tokens = $1.00
- **Large corpus** (500 pages): ~1,000,000 tokens = $10.00
- **Academic library** (5,000 pages): ~10,000,000 tokens = $100.00

Losing this data means re-ingesting and re-paying.

### Backup as Investment Protection

Backups preserve the entire value chain:

```
Source Document ($0.10-10 in tokens to extract)
    ↓
Concepts + Relationships + Evidence
    ↓
Embeddings (1536-dim vectors)
    ↓
Queryable Knowledge Graph
```

**What backups include:**

1. ✅ All concepts with labels and search terms
2. ✅ Full 1536-dimensional embeddings (no regeneration needed)
3. ✅ All relationships with types and properties
4. ✅ Source text and evidence quotes
5. ✅ Metadata (ontology names, file paths, positions)

### Portability

Backups are portable JSON files:

```json
{
  "version": "1.0",
  "type": "ontology_backup",
  "ontology": "Alan Watts Lectures",
  "timestamp": "2025-10-06T12:30:00Z",
  "statistics": {
    "concepts": 47,
    "sources": 12,
    "instances": 89,
    "relationships": 73
  },
  "data": {
    "concepts": [...],
    "sources": [...],
    "instances": [...],
    "relationships": [...]
  }
}
```

**Benefits:**

- Share knowledge graphs across teams
- Move between databases (dev → staging → prod)
- Archive expensive extractions
- Mix-and-match ontologies across systems

### Cost Recovery Scenarios

**Scenario 1: Database Corruption**
- Database crashes, all data lost
- Restore from backup → 0 additional LLM costs
- Minutes to restore vs. hours/days to re-ingest

**Scenario 2: Selective Knowledge Sharing**
- Team member needs "Agile Methodology" ontology
- Send them the 2MB JSON backup
- They restore → instant access to $5 worth of extractions

**Scenario 3: Environment Migration**
- Development database has 20 ontologies
- Production needs only 3 high-value ones
- Selective restore → precise control, no waste

**Scenario 4: Knowledge Merging**
- Two teams built related knowledge graphs
- Stitch them together with semantic matching
- Combined value > sum of parts, no re-ingestion

---

## Workflow Scenarios

### Scenario 1: Single Ontology Development

**Context**: Building a knowledge base from one document set

```bash
# Ingest documents
python cli.py ingest watts_1.txt --ontology "Alan Watts"
python cli.py ingest watts_2.txt --ontology "Alan Watts"

# Backup
python -m src.admin.backup --ontology "Alan Watts"

# Later: Restore to new database
python -m src.admin.restore --file backups/alan_watts.json
```

**Integrity**: No external dependencies, no stitching/pruning needed

---

### Scenario 2: Multi-Ontology System

**Context**: Building interconnected knowledge domains

```bash
# Ingest multiple ontologies
python cli.py ingest watts_*.txt --ontology "Alan Watts"
python cli.py ingest agile_*.md --ontology "Agile Methodology"
python cli.py ingest systems_*.pdf --ontology "Systems Thinking"

# Full backup
python -m src.admin.backup --auto-full
```

**Integrity**: Cross-ontology relationships exist, full backup captures everything

---

### Scenario 3: Partial Restore with Stitching

**Context**: Restore one ontology into database with related ontologies

```bash
# Backup single ontology (has external refs to other ontologies)
python -m src.admin.backup --ontology "Alan Watts"

# Restore to database that has "Systems Thinking" ontology
python -m src.admin.restore --file backups/alan_watts.json
# Choose: "Stitch later (defer)"

# Stitch using semantic similarity
python -m src.admin.stitch --backup backups/alan_watts.json --threshold 0.85
# System matches + auto-prunes unmatched → 100% edge handling
```

**Result**: "Linear Thinking" from Watts might stitch to "Reductionism" from Systems Thinking

---

### Scenario 4: Clean Database Restore

**Context**: Restore partial ontology into empty database

```bash
# Empty database
python -m src.admin.restore --file backups/alan_watts.json
# Auto-detects clean database
# Auto-selects prune mode
# Message: "✓ Target database is empty - will auto-prune to keep ontology isolated"
```

**Result**: Ontology restored in isolation, clean graph, no user prompts

---

### Scenario 5: Strict Isolation

**Context**: Keep ontologies completely separate

```bash
# Restore but maintain boundaries
python -m src.admin.restore --file backups/alan_watts.json
# Choose: "Auto-prune after restore (keep isolated)"

# Or prune existing dangling relationships
python -m src.admin.prune --ontology "Alan Watts"
```

**Result**: Clean ontology boundaries, no cross-domain connections

---

### Scenario 6: Integrity Validation

**Context**: Check graph health before/after operations

```bash
# Before restore: Assess backup
python -m src.admin.backup --ontology "Alan Watts"
# Console shows: "⚠ 7 relationships to external concepts"

# After restore: Validate
python -m src.admin.check_integrity --ontology "Alan Watts"
# Reports orphaned concepts, dangling relationships, missing embeddings

# Repair if needed
python -m src.admin.check_integrity --ontology "Alan Watts" --repair
```

---

## Summary

### Key Principles

1. **Ontology** = Thematic knowledge cluster from related documents
2. **Graph Integrity** = All relationships point to existing concepts
3. **Stitching** = Semantic reconnection using vector similarity
4. **Pruning** = Removing dangling relationships for isolation
5. **Backups** = Portable JSON preserving $$ token investment
6. **100% Edge Handling** = All external refs are either stitched or pruned (zero tolerance for dangling edges)

### Decision Framework

**When to Prune:**
- Clean database (auto-selected)
- Want strict ontology boundaries
- No related ontologies in target database

**When to Stitch:**
- Target database has related ontologies
- Want cross-domain insights
- Willing to tune similarity threshold

**Always Remember:**
- Backups protect token investment (embeddings + extractions)
- Partial restores create integrity challenges
- System enforces 100% edge handling (no broken graphs)
- Stitcher auto-prunes unmatched refs (guaranteed clean state)

---

## Further Reading

- [Architecture Decisions](../../architecture/ARCHITECTURE_DECISIONS.md) - ADR-011 on backup/restore design
- [Backup & Restore Guide](../05-maintenance/01-BACKUP_RESTORE.md) - Detailed operational guide
- [openCypher Language Reference](https://s3.amazonaws.com/artifacts.opencypher.org/openCypher9.pdf) - Query language reference
- [Apache AGE Documentation](https://age.apache.org/age-manual/master/intro/overview.html) - AGE implementation details
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings) - Vector representation details

---

*This document explains the conceptual model and terminology. For operational procedures, see [../05-maintenance/01-BACKUP_RESTORE.md](../05-maintenance/01-BACKUP_RESTORE.md).*
