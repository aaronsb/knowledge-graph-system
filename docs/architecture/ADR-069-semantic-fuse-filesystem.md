# ADR-069: Semantic FUSE Filesystem

**Status:** Proposed
**Date:** 2025-11-28
**Related ADRs:** ADR-055 (Sharding), ADR-048 (GraphQueryFacade)

> "Everything is a file" - Traditional Unix Philosophy
> "Everything is a file, but which file depends on what you're thinking about" - Semantic Unix Philosophy

## Abstract

This ADR proposes exposing the knowledge graph as a FUSE (Filesystem in Userspace) mount point, enabling semantic navigation and querying through standard Unix tools (`ls`, `cd`, `cat`, `grep`, `find`). Like `/sys/` or `/proc/`, this is a **partial filesystem** that implements only operations that make semantic sense, providing a familiar interface to knowledge graph exploration.

## Context

### The Problem: Hierarchies Don't Fit Knowledge

Traditional filesystems organize knowledge through rigid hierarchies:
```
/docs/
  /architecture/
    /decisions/
      adr-068.md
  /guides/
    embedding-guide.md
```

But knowledge doesn't fit in trees. ADR-068 is simultaneously:
- An architecture decision
- A guide for operators
- An embedding system reference
- A bug fix chronicle
- A compatibility management strategy

Why force it into one directory when it semantically belongs in multiple conceptual spaces?

### The Opportunity: FUSE as Semantic Interface

The knowledge graph already provides:
- Semantic search (vector similarity)
- Relationship traversal (graph navigation)
- Multi-ontology federation (shard/facet architecture from ADR-055)
- Cross-domain linking (automatic concept merging)

FUSE could expose these capabilities through filesystem metaphors that users already understand.

### Architectural Validation

This proposal underwent external peer review to validate feasibility against the existing codebase. Key findings:

- **Architectural Fit:** The FUSE operations map directly to existing services without requiring new core logic
  - `ls` (semantic query) → `QueryService.build_search_query`
  - `cd relationships/` (graph traversal) → `QueryService.build_concept_details_query`
  - Write operations → existing async ingestion pipeline

- **Implementation Feasibility:** High - essentially re-skinning existing services into FUSE protocol

- **Discovery Value:** Solves the "I don't know what to search for" problem by allowing users to browse valid semantic pathways

- **Standard Tool Integration:** Turns every Unix utility (`grep`, `diff`, `tar`) into a knowledge graph tool for free

The review validated this is a "rigorous application of the 'everything is a file' philosophy to high-dimensional data," not a cursed hack.

### Related Work: Other Semantic File Systems

This proposal builds on a rich history of semantic filesystems, though none have applied the "Directory = Query" metaphor to vector embeddings and probabilistic similarity.

#### 1. Logic & Query-Based Systems (Direct Ancestors)

**Semantic File System (SFS)** - MIT, 1991
- **Concept:** Original implementation of "transducers" extracting attributes from files
- **Innovation:** Virtual directories interpreted as queries (`/sfs/author/jdoe` dynamically generated)
- **Limitation:** Attribute-based (key-value pairs), not semantic
- **Our Extension:** Replace discrete attributes with continuous similarity scores

**Tagsistant** - Linux/FUSE
- **Concept:** Directory nesting for boolean logic operations
- **Innovation:** Path as query language (`/tags/music/+/rock/` for AND operations)
- **Similarity:** The `/+/` operator is conceptually similar to our relationship traversal
- **Our Extension:** Replace boolean logic with semantic similarity thresholds

**JOINFS**
- **Concept:** Dynamic directories populated by metadata query matching
- **Innovation:** `mkdir "format=mp3"` creates persistent searches
- **Similarity:** Query definition via directory creation (like our approach)
- **Our Extension:** Semantic queries vs. exact metadata matching

#### 2. Tag-Based Systems (Modern Implementations)

**TMSU** (Tag My Sh*t Up)
- **Concept:** SQLite-backed FUSE mount with explicit tagging
- **Architecture:** Standard "FUSE + Database" pattern we follow
- **Similarity:** Files exist in multiple paths (`/mnt/tmsu/tags/music/mp3/`)
- **Difference:** Deterministic (file is tagged or not), no similarity threshold
- **Our Extension:** Probabilistic membership based on semantic similarity

**TagFS / SemFS**
- **Concept:** RDF triples for tag storage (graph-like structure)
- **Similarity:** Graph backend architecture (closer to our Knowledge Graph than SQL)
- **Difference:** Explicit RDF relationships vs. emergent semantic relationships
- **Our Extension:** Vector embeddings replace RDF triples

#### 3. Partial POSIX Precedents

**Google Cloud FUSE / rclone**
- **Precedent:** Explicitly documents "Limitations and differences from POSIX"
- **Validation:** Large-scale ML workloads accept non-compliance for utility
- **Similar Violations:** Directories disappear, non-deterministic caching, eventual consistency
- **Our Justification:** If users accept this for cloud storage, they'll accept it for semantic navigation

#### Comparison Table

| Feature | Tagsistant | TMSU | MIT SFS (1991) | **ADR-069 (This Proposal)** |
|---------|------------|------|----------------|----------------------------|
| **Organization** | Boolean Logic | Explicit Tags | Key-Value Attributes | **Vector Embeddings** |
| **Navigation** | `/tag1/+/tag2/` | `/tag1/tag2/` | `/author/name/` | **`/query/threshold/`** |
| **Determinism** | Deterministic | Deterministic | Deterministic | **Probabilistic** |
| **Backend** | SQL/Dedup | SQLite | Transducers | **Vector DB + LLM** |
| **Write Behavior** | Tags file | Tags file | Indexing | **Ingest & Grounding** |
| **Membership Model** | Binary (tagged/not) | Binary | Binary | **Continuous (similarity score)** |

#### The Key Innovation

**Existing systems:** Map **discrete values** (tags, attributes) → directories
- File either has tag "music" or it doesn't
- Boolean membership: true/false
- Deterministic listings

**Our proposal:** Map **continuous values** (similarity scores) → directories
- Concept has 73.5% similarity to query "embedding models"
- Probabilistic membership: threshold-dependent
- Non-deterministic listings (similarity changes as graph evolves)

This is the specific innovation that justifies the "POSIX violations" in our design - we're not just organizing files by metadata, we're navigating high-dimensional semantic space through a filesystem interface.

## Motivation

Traditional filesystems organize knowledge through rigid hierarchies:
```
/docs/
  /architecture/
    /decisions/
      adr-068.md
  /guides/
    embedding-guide.md
```

But knowledge doesn't fit in trees. ADR-068 is simultaneously:
- An architecture decision
- A guide for operators
- An embedding system reference
- A bug fix chronicle
- A compatibility management strategy

Why force it into one directory when it semantically belongs in multiple conceptual spaces?

## The Proposal

### Mount Point

```bash
mount -t fuse.knowledge-graph /dev/knowledge /mnt/knowledge
```

### Directory Structure

Directories are **semantic queries**, not static folders:

```bash
/mnt/knowledge/
├── embedding-regeneration/     # Concepts matching "embedding regeneration"
│   ├── unified-regeneration.concept (79.8% similarity)
│   ├── compatibility-checking.concept (75.2% similarity)
│   └── model-migration.concept (78.5% similarity)
├── ai-models/                  # Concepts matching "ai models"
│   ├── embedding-models.concept (89.6% similarity)
│   ├── unified-regeneration.concept (64.5% similarity)  # Same file!
│   └── ai-capabilities.concept (70.6% similarity)
└── search/
    ├── 0.7/                    # 70% similarity threshold
    │   └── embedding+models/
    ├── 0.8/                    # 80% similarity threshold
    │   └── embedding+models/   # Fewer results
    └── 0.6/                    # 60% similarity threshold
        └── embedding+models/   # More results
```

### File Format

Concept files are dynamically generated:

```bash
$ cat /mnt/knowledge/embedding-regeneration/unified-regeneration.concept
```

```markdown
# Unified Embedding Regeneration

**ID:** sha256:95454_chunk1_76de0274
**Ontologies:** ADR-068-Phase4-Implementation, AI-Applications
**Similarity:** 79.8% (to directory query: "embedding regeneration")
**Grounding:** Weak (0.168, 17%)
**Diversity:** 39.2% (10 related concepts)

## Description

A system for regenerating vector embeddings across all graph text entities,
ensuring compatibility and proper namespace organization.

## Evidence

### Source 1: ADR-068-Phase4-Implementation (para 1)
The knowledge graph system needed a unified approach to regenerating vector
embeddings across all graph text entities (concepts, sources, and vocabulary)...

### Source 2: AI-Applications (para 1)
A unified embedding regeneration system addresses this challenge by treating
all embedded entities consistently...

## Relationships

→ INCLUDES compatibility-checking.concept
→ REQUIRES embedding-management-endpoints.concept
→ VALIDATES testing-verification.concept
← SUPPORTS bug-fix-source-regeneration.concept

## Navigate

ls ../ai-models/           # See related concepts in different semantic space
cd relationships/includes/ # Traverse by relationship type
```

### Relationship Navigation

Traverse the graph via relationships:

```bash
$ cd /mnt/knowledge/embedding-regeneration/unified-regeneration/
$ ls relationships/
includes/  requires/  validates/  supported-by/

$ cd relationships/includes/
$ ls
compatibility-checking.concept

$ cat compatibility-checking.concept  # Full concept description
```

### Search Interface

```bash
$ cd /mnt/knowledge/search/0.75/
$ mkdir "embedding+migration+compatibility"  # Creates query directory!
$ cd "embedding+migration+compatibility"/
$ ls  # Results ranked by similarity
```

## POSIX Violations (Features!)

### 1. Non-Deterministic Directory Listings

```bash
$ ls /mnt/knowledge/embedding-models/
unified-regeneration.concept
compatibility-checking.concept
model-migration.concept

# New concept added to graph elsewhere...

$ ls /mnt/knowledge/embedding-models/
unified-regeneration.concept
compatibility-checking.concept
model-migration.concept
embedding-architecture.concept  # New! Without touching this directory!
```

**Why it's beautiful:** Your filesystem stays current with your knowledge, automatically.

### 2. Multiple Canonical Paths

```bash
$ pwd
/mnt/knowledge/embedding-regeneration/unified-regeneration.concept

$ cat unified-regeneration.concept
# ... reads file ...

$ pwd  # From the file's perspective
/mnt/knowledge/ai-models/unified-regeneration.concept

# Both are correct! The file exists in multiple semantic spaces!
```

**Why it's beautiful:** Concepts belong to multiple contexts simultaneously.

### 3. Read-Influenced Writes

```bash
$ cat concept-a.concept
$ cat concept-b.concept

# Graph notices correlation...

$ ls  # Now concept-c appears because semantic relatedness!
concept-a.concept
concept-b.concept
concept-c.concept  # ← Appeared based on your read pattern
```

**Why it's beautiful:** The filesystem adapts to your workflow.

### 4. Relationship-Based Symlinks That Aren't Symlinks

```bash
$ ls -l /mnt/knowledge/embedding-regeneration/
lrwxrwxrwx compatibility → [INCLUDES] ../compatibility-checking/
lrwxrwxrwx testing → [VALIDATES] ../testing-verification/

# These aren't real symlinks, they're semantic relationships!
# Different relationship types could render differently!
```

**Why it's beautiful:** Explicit relationship semantics instead of opaque links.

### 5. Threshold-Dependent Paths

```bash
$ cd /mnt/knowledge/search/0.8/ai+models/
$ ls | wc -l
12

$ cd ../0.7/ai+models/  # Same query, lower threshold
$ ls | wc -l
27

$ cd ../0.9/ai+models/  # Higher threshold
$ ls | wc -l
5
```

**Why it's beautiful:** Precision vs. recall as a filesystem operation!

### 6. Temporal Inconsistency

```bash
$ stat unified-regeneration.concept
Modified: 2025-11-29 03:59:57  # When concept was created

$ cat unified-regeneration.concept  # Read it

$ stat unified-regeneration.concept
Modified: 2025-11-29 04:15:32  # NOW! Because grounding updated!
```

**Why it's beautiful:** Living knowledge, not static files.

## Use Cases Where This Is Actually Useful

### 1. Exploratory Research

```bash
# Start with a concept
cd /mnt/knowledge/embedding-models/

# Navigate by relationships
cd unified-regeneration/relationships/requires/

# Follow to related concepts
cd compatibility-checking/relationships/includes/

# Emerge somewhere totally different but semantically connected!
pwd
# /mnt/knowledge/ai-models/compatibility-checking/relationships/includes/
```

### 2. Context-Aware Documentation

```bash
# You're working on AI models
cd /workspace/ai-stuff/

# Mount context-aware knowledge
ln -s /mnt/knowledge/ai-models/ ./docs

# Everything in ./docs is semantically relevant to AI!
```

### 3. Semantic Grep

```bash
# Traditional grep
grep -r "embedding" /docs/
# Returns every file mentioning "embedding" (thousands of false positives)

# Semantic filesystem
ls /mnt/knowledge/search/0.8/embedding/
# Returns only concepts semantically related to embedding at 80% threshold
```

### 4. AI-Assisted Workflows

```bash
# What concepts relate to what I'm working on?
git log --oneline -1
# fix: compatibility checking for embeddings

ls /mnt/knowledge/compatibility+checking/relationships/
requires/  includes/  supports/  related-to/

# Oh, it requires these other concepts!
cd requires/
ls
embedding-models.concept
model-migration.concept
```

## Practical Applications That Sound Insane But Actually Work

### TAR as Temporal Snapshots

```bash
# Capture your research state RIGHT NOW
tar czf research-$(date +%s).tar.gz /mnt/knowledge/embedding-models/

# Three months later: graph has evolved, new concepts exist
tar czf research-$(date +%s).tar.gz /mnt/knowledge/embedding-models/

# DIFFERENT tar contents!
# Same "directory", different semantic space!
# Each tarball is a temporal snapshot of the knowledge graph
```

**Why this works:** The filesystem is a *view* of the knowledge graph at a point in time. TAR captures that view. Different views = different archives. Version your knowledge semantically!

**Practical use:**
- Archive research findings before pivoting
- Create snapshots before major refactoring
- Share "knowledge packs" with collaborators
- Restore previous understanding states

### Living Documentation in Development Workspaces

```bash
# Your project workspace
cd /workspace/my-ai-project/

# Symlink semantic knowledge as documentation
ln -s /mnt/knowledge/my-project/ ./docs

# Claude Code (or any IDE) can now:
cat docs/architecture/api-design.concept          # Read current architecture
ls docs/relationships/SUPPORTS/                    # See what supports this design
grep -r "performance" docs/                        # Semantic search in docs!

# As you work and ingest commit messages:
git commit -m "feat: add caching layer"
kg ingest commit HEAD -o my-project

# Moments later:
ls ./docs/
# NEW concepts appear automatically!
# caching-layer.concept
# performance-optimization.concept
```

**Why this works:** The symlink points to a semantic query. The query results update as the graph evolves. Your documentation becomes a living, self-organizing entity.

**Claude Code integration:**
```bash
# Claude can literally read your knowledge graph
<Read file="docs/api-design.concept">
# Gets: full concept, relationships, evidence, grounding metrics
# Not just static markdown

# Claude can explore relationships
cd docs/api-design/relationships/REQUIRES/
# Discovers dependencies automatically
```

### Bidirectional Ingestion

```bash
# Write support makes this a full knowledge management system
echo "# New Architecture Decision

We're adopting GraphQL for the API layer because..." > /mnt/knowledge/my-project/adr-070.md

# File write triggers:
# 1. Document chunking
# 2. LLM concept extraction
# 3. Semantic matching against existing concepts
# 4. Relationship discovery
# 5. Graph integration

# Seconds later:
ls /mnt/knowledge/api-design/
# adr-070-graphql-adoption.concept appears!

# Batch ingestion:
cp docs/*.md /mnt/knowledge/my-project/
# Processes all files, discovers cross-document relationships automatically
```

**Why this works:** Every write is an ingestion trigger. The filesystem becomes a natural interface for knowledge capture.

**Anti-pattern prevention:**
```bash
# Only accept markdown/text
cp binary-file.exe /mnt/knowledge/
# Error: unsupported file type

# Prevent knowledge pollution
cp spam.txt /mnt/knowledge/my-project/
# Ingests but low grounding, won't pollute semantic queries
```

### Build System Integration

```bash
# Makefile that depends on semantic queries
API_DOCS := $(shell ls /mnt/knowledge/api-endpoints/*.concept)

docs/api.html: $(API_DOCS)
	kg export --format html /mnt/knowledge/api-endpoints/ > $@

# When new API concepts appear (from code ingestion):
# - Build automatically detects new .concept files
# - Regenerates documentation
# - No manual tracking needed
```

**Why this works:** The filesystem exposes semantic queries as file paths. Build tools already know how to depend on file paths.

**CI/CD integration:**
```yaml
# GitHub Actions
- name: Check documentation coverage
  run: |
    concept_count=$(ls /mnt/knowledge/my-project/*.concept | wc -l)
    if [ $concept_count -lt 50 ]; then
      echo "Warning: Only $concept_count concepts documented"
    fi
```

### Event-Driven Workflows

```bash
# Watch for knowledge graph changes
fswatch /mnt/knowledge/my-project/ | while read event; do
    echo "Knowledge updated: $event"
    kg admin embedding regenerate --type concept --only-missing
done

# Trigger notifications when concepts appear
inotifywait -m /mnt/knowledge/security-vulnerabilities/ -e create |
while read dir action file; do
    notify-send "Security Alert" "New vulnerability concept: $file"
done
```

**Why this works:** Filesystem events map to knowledge graph updates. Standard Linux tools (inotify, fswatch) become knowledge graph event listeners.

**Knowledge-driven automation:**
```bash
# When AI research concepts appear, trigger model retraining
ls /mnt/knowledge/ai-research/*.concept | entr make train-model

# When architecture concepts change, validate against constraints
ls /mnt/knowledge/architecture/*.concept | entr ./validate-architecture.sh
```

### Diff-Based Knowledge Evolution Tracking

```bash
# Semantic diff across time
tar czf snapshot-before.tar.gz /mnt/knowledge/my-research/

# ... three months of work ...

tar czf snapshot-after.tar.gz /mnt/knowledge/my-research/
tar xzf snapshot-before.tar.gz -C /tmp/before/
tar xzf snapshot-after.tar.gz -C /tmp/after/

diff -r /tmp/before/ /tmp/after/
# Shows concept evolution:
# - New concepts (+ files)
# - Strengthened concepts (modified files with higher grounding)
# - Abandoned concepts (- files, fell below similarity threshold)
```

**Why this works:** Concepts are files. Files can be diffed. Knowledge evolution becomes visible through standard Unix tools.

## Architecture and Hierarchy

### Important: This Is NOT a Full Filesystem

Like `/sys/` or `/proc/`, this is a **partial filesystem** that exposes a specific interface (knowledge graphs) through filesystem semantics. It only implements operations that make semantic sense.

**What works:**
- `ls` (semantic query)
- `cd` (navigate semantic space)
- `cat` (read concept)
- `find` / `grep` (search)
- `echo >` / `cp` (ingest)
- `tar` (snapshot)
- `stat` (metadata)

**What doesn't work (and won't):**
- `mv` (concepts don't "move" in semantic space)
- `chmod` / `chown` (use facet-level RBAC instead)
- `ln -s` (maybe future: create relationships)
- `touch` (timestamps are semantic, not file-based)
- `dd` (nonsensical for semantic content)
- Most other file operations that assume static files

**This is a feature, not a limitation.** Don't pretend to be a full filesystem. Be an excellent semantic interface.

### The Four-Level Model

The semantic filesystem has a clear hierarchy that maps infrastructure to semantic content:

```
Shard (infrastructure: database + API + resources)
  └── Facet (logical grouping of related ontologies)
      └── Ontology (specific knowledge domain)
          └── Concepts (semantic content)
```

**Why this hierarchy matters:**

| Level | Purpose | Example | Isolation |
|-------|---------|---------|-----------|
| **Shard** | Physical deployment instance | `shard-research`, `shard-production` | Infrastructure (separate databases) |
| **Facet** | Logical grouping for organization/RBAC | `academic`, `industrial`, `engineering` | Access control & resource limits |
| **Ontology** | Knowledge domain namespace | `ai-research`, `api-docs`, `patents` | Semantic namespace |
| **Concepts** | Individual semantic units | `embedding-models.concept` | Content |

### Directory Structure

```bash
/mnt/knowledge/
├── shard-research/              # Shard: research infrastructure
│   ├── academic/                # Facet: academic research group
│   │   ├── ai-research/         # Ontology: AI papers
│   │   │   └── embedding-models.concept
│   │   ├── neuroscience/        # Ontology: neuroscience papers
│   │   └── ml-papers/           # Ontology: ML literature
│   │
│   └── industrial/              # Facet: industrial R&D group
│       ├── patents/             # Ontology: patent filings
│       └── prototypes/          # Ontology: prototype docs
│
├── shard-production/            # Shard: production infrastructure
│   ├── engineering/             # Facet: engineering team
│   │   ├── api-docs/            # Ontology: API documentation
│   │   ├── architecture/        # Ontology: architecture decisions
│   │   └── runbooks/            # Ontology: operational runbooks
│   │
│   └── compliance/              # Facet: compliance team
│       ├── gdpr/                # Ontology: GDPR documentation
│       └── soc2/                # Ontology: SOC2 compliance
│
└── shard-partners/              # Shard: partner infrastructure (remote)
    └── shared/                  # Facet: shared knowledge
        └── api-integration/     # Ontology: integration docs
```

### Why Facets?

**Facets** provide logical organization within a shard without requiring separate infrastructure:

1. **Access Control Boundaries:**
   ```bash
   # Academic team: read/write to academic/ facet
   # Industrial team: read/write to industrial/ facet
   # Same database, different permissions
   ```

2. **Resource Isolation:**
   ```bash
   # Academic facet: high ingestion rate, low query rate
   # Industrial facet: low ingestion rate, high query rate
   # Same infrastructure, different resource profiles
   ```

3. **Namespace Management:**
   ```bash
   # Both facets can have "documentation" ontology:
   /mnt/knowledge/shard-research/academic/documentation/
   /mnt/knowledge/shard-research/industrial/documentation/
   # No collision!
   ```

4. **Organizational Clarity:**
   ```bash
   ls /mnt/knowledge/shard-research/
   academic/      # University research
   industrial/    # Corporate R&D
   # Clear logical separation
   ```

### Mount Options at Different Levels

```bash
# Mount entire shard (all facets, all ontologies)
mount -t fuse.knowledge-graph \
  -o shard=research \
  /dev/knowledge /mnt/knowledge/research

ls /mnt/knowledge/research/
academic/  industrial/

# Mount specific facet (all ontologies in facet)
mount -t fuse.knowledge-graph \
  -o shard=research,facet=academic \
  /dev/knowledge /mnt/knowledge/academic

ls /mnt/knowledge/academic/
ai-research/  neuroscience/  ml-papers/

# Mount specific ontology (direct semantic access)
mount -t fuse.knowledge-graph \
  -o shard=research,facet=academic,ontology=ai-research \
  /dev/knowledge /mnt/knowledge/ai-research

ls /mnt/knowledge/ai-research/
# Shows semantic query space directly
embedding-models/  neural-networks/  transformers/
```

### Cross-Shard, Cross-Facet Queries

Standard Unix tools traverse the hierarchy automatically:

```bash
# Search across all mounted shards, facets, and ontologies
find /mnt/knowledge/ -name "*.concept" | grep "embedding"

# Traverses:
# 1. Shards (local + remote)
#    ├── shard-research (local FUSE → local PostgreSQL)
#    └── shard-partners (SSHFS → remote FUSE → remote PostgreSQL)
#
# 2. Facets within each shard
#    ├── academic
#    ├── industrial
#    └── shared
#
# 3. Ontologies within each facet
#    ├── ai-research
#    ├── patents
#    └── api-integration
#
# 4. Semantic queries within each ontology
#    └── embedding-models.concept (found!)

# All through standard Unix tooling!
```

**The magic:** `find` and `grep` don't know about:
- Knowledge graphs
- Semantic queries
- Shard boundaries
- Local vs. remote mounts

They just traverse directories and read files. **The abstraction is perfect.**

### Distributed Queries Across Mount Boundaries

```bash
# Mount local shards
mount -t fuse.knowledge-graph -o shard=research /dev/knowledge /mnt/local/research
mount -t fuse.knowledge-graph -o shard=production /dev/knowledge /mnt/local/production

# Mount remote shards via SSH
sshfs partner-a@remote:/mnt/knowledge/shared /mnt/remote/partner-a
sshfs partner-b@remote:/mnt/knowledge/public /mnt/remote/partner-b

# Now grep across ALL of them:
grep -r "API compatibility" /mnt/{local,remote}/*/

# What actually happens:
# 1. grep traverses /mnt/local/research/
#    → FUSE reads local database
#    → Returns concept files as text
#
# 2. grep traverses /mnt/local/production/
#    → FUSE reads local database
#    → Returns concept files as text
#
# 3. grep traverses /mnt/remote/partner-a/
#    → SSHFS sends reads over SSH
#    → Remote FUSE reads remote database
#    → SSH returns concept files as text
#
# 4. grep traverses /mnt/remote/partner-b/
#    → Same: SSHFS → SSH → remote FUSE → remote database

# Result: distributed semantic search across multiple knowledge graphs
# Using only: grep, mount, and sshfs
# No special distributed query protocol needed
```

**This is profound:** Standard Unix tools become distributed knowledge graph query engines simply by mounting semantic filesystems at different paths.

### Write Operations Respect Hierarchy

```bash
cd /mnt/knowledge/research/academic/ai-research/embedding-models/

# Write here → ingests into:
# - Shard: research
# - Facet: academic
# - Ontology: ai-research
# - Context: embedding-models (semantic query)
echo "# Quantization Techniques..." > quantization.md

# Concept appears in:
# ✓ /mnt/knowledge/research/academic/ai-research/
# ✗ NOT in /mnt/knowledge/research/industrial/patents/
# Same shard, different facet = isolated
```

### Federation and Discovery

```bash
# Local shard (FUSE → local knowledge graph)
mount -t fuse.knowledge-graph -o shard=research /dev/knowledge /mnt/local

# Remote shard (SSHFS → remote FUSE → remote knowledge graph)
sshfs partner@partner.com:/mnt/knowledge/shared \
      /mnt/remote

# Now find operates across BOTH:
find /mnt/{local,remote}/ -name "*.concept" | grep "api"

# Returns concepts from:
# - Local research shard (all facets)
# - Remote partner shard (shared facet)
# Distributed knowledge graph queries via standard Unix tools!
```

### Path Semantics

Every path encodes the full context:

```
/mnt/knowledge/shard-research/academic/ai-research/embedding-models/quantization.concept
│              │              │        │            │                │
│              │              │        │            │                └─ Concept (semantic entity)
│              │              │        │            └─────────────────── Semantic query context
│              │              │        └──────────────────────────────── Ontology (knowledge domain)
│              │              └───────────────────────────────────────── Facet (logical group)
│              └──────────────────────────────────────────────────────── Shard (infrastructure)
└─────────────────────────────────────────────────────────────────────── Mount point
```

**Deterministic structure, semantic content.**

## Implementation Sketch

### Technology Stack

- **FUSE:** Filesystem in Userspace (client interface)
- **Backend:** FastAPI REST API server
- **Query Engine:** Semantic search API (part of backend)
- **Cache:** TTL-based concept cache (fights non-determinism slightly)

**Note:** The FUSE filesystem is a client interface, just like the MCP server, CLI, and web interface. All clients communicate with the same FastAPI backend.

### Basic Operations

```python
class SemanticFS(Operations):
    def readdir(self, path, fh):
        """List directory = semantic query"""
        query = path_to_query(path)
        concepts = kg.search(query, threshold=0.7)
        return [f"{c.id}.concept" for c in concepts]

    def read(self, path, size, offset, fh):
        """Read file = get concept details"""
        concept_id = path_to_concept_id(path)
        concept = kg.get_concept(concept_id)
        return format_concept_markdown(concept)

    def getattr(self, path, fh=None):
        """Stat file = concept metadata"""
        concept = kg.get_concept(path_to_concept_id(path))
        return {
            'st_mode': S_IFREG | 0o444,  # Read-only
            'st_size': len(concept.description),
            'st_mtime': concept.last_updated,  # Changes with grounding!
        }
```

### Mount Options

```bash
mount -t fuse.knowledge-graph \
  -o threshold=0.75 \           # Default similarity threshold
  -o cache_ttl=60 \              # Cache concepts for 60s
  -o relationship_links=true \   # Show relationship symlinks
  -o dynamic_discovery=true \    # Concepts appear based on access patterns
  /dev/knowledge /mnt/knowledge
```

### Alternative: rclone Backend Implementation

Instead of writing a custom FUSE driver, implement as an **rclone backend**.

**Why rclone?**
- rclone already handles FUSE mounting, caching, config management
- Implement knowledge graph as "just another backend" (like S3, Google Drive)
- Get interop between knowledge graphs and cloud storage for free
- Users already understand rclone's model

**Implementation:**

```go
// rclone backend for knowledge graphs
package kg

import (
    "context"
    "github.com/rclone/rclone/fs"
)

func init() {
    fs.Register(&fs.RegInfo{
        Name:        "kg",
        Description: "Knowledge Graph Backend",
        NewFs:       NewFs,
        Options: []fs.Option{{
            Name: "api_url",
            Default: "http://localhost:8000",
        }, {
            Name: "shard",
        }, {
            Name: "auth_token",
        }},
    })
}

// List directory = semantic query
func (f *Fs) List(ctx context.Context, dir string) (entries fs.DirEntries, err error) {
    facet, ontology, query := parsePath(dir)
    concepts, err := f.client.Search(ctx, query, ontology)
    for _, concept := range concepts {
        entries = append(entries, conceptToEntry(concept))
    }
    return entries, nil
}

// Open file = read concept as markdown
func (o *Object) Open(ctx context.Context) (io.ReadCloser, error) {
    concept, err := o.fs.client.GetConcept(ctx, o.conceptID)
    markdown := formatConceptMarkdown(concept)
    return io.NopCloser(strings.NewReader(markdown)), nil
}

// Put file = ingest into knowledge graph
func (f *Fs) Put(ctx context.Context, in io.Reader, src fs.ObjectInfo) (fs.Object, error) {
    data, _ := io.ReadAll(in)
    facet, ontology, _ := parsePath(src.Remote())
    result, err := f.client.Ingest(ctx, data, ontology, facet)
    return &Object{...}, nil
}
```

**Usage:**

```bash
# Configure knowledge graph backend
rclone config create kg-research kg \
  api_url=http://localhost:8000 \
  shard=research \
  auth_token=$TOKEN

# Mount it
rclone mount kg-research:academic/ai-research /mnt/knowledge

# Works like any rclone mount
ls /mnt/knowledge/
cat /mnt/knowledge/embedding-models.concept
echo "new idea" > /mnt/knowledge/new-concept.md
```

**Bonus: Cross-Backend Operations**

```bash
# Backup knowledge graph to S3
rclone sync kg-research: s3:backup/kg-snapshot/

# Ingest Google Drive docs into knowledge graph
rclone copy gdrive:Papers/ kg-research:academic/papers/

# Sync between knowledge graph shards
rclone sync kg-shard-a: kg-shard-b:

# Export concepts to git repository
rclone sync kg-research: /tmp/kg-export/
cd /tmp/kg-export && git init && git add . && git commit

# Use rclone browser GUI to explore knowledge graph
rclone rcd --rc-web-gui
```

**Benefits:**
- Don't write FUSE layer (rclone handles it)
- Get caching, retry logic, rate limiting for free
- Instant interop with cloud storage backends
- Existing rclone user base understands the model
- rclone browser GUI works automatically

**Implementation effort:** Minimal backend (List/Read/Write) could be prototyped in a weekend.

## Why This Will Make Unix Admins Angry

### The Angry Tweets We Expect

> "This violates everything POSIX stands for. Files shouldn't magically appear and disappear."

Yes. That's the point. Knowledge isn't static.

> "How am I supposed to backup a filesystem where `tar` gives different results each time?"

You backup the knowledge graph, not the filesystem. The filesystem is a *view* of knowledge.

> "My scripts depend on deterministic `ls` output!"

Your scripts are thinking in hierarchies. Think in semantics instead.

> "`find . -name '*.concept' | wc -l` returns different numbers!"

Correct! The number of concepts matching your context changes as you explore.

> "This breaks `rsync`!"

Have you considered that maybe `rsync` should understand semantic similarity? 🤔

### The rclone Defense

> "This is just like rclone for Google Drive!"

**Yes. Exactly.** And millions of people use rclone daily despite its POSIX violations.

**rclone for Google Drive exhibits:**
- **Non-deterministic listings:** Files appear/disappear as others edit shared drives
- **Multiple canonical paths:** Same file accessible via `/MyDrive/` and `/SharedDrives/` (Google's "Add to My Drive")
- **Eventually consistent:** Write a file, read might return old content (API sync lag)
- **Weird metadata:** Fake Unix permissions from Google's ACLs, timestamps from cloud provider
- **Partial POSIX:** No symlinks, no memory mapping, fake chmod/chown

**People accept this because the abstraction is useful.**

**Semantic FUSE is actually BETTER than rclone:**

| Aspect | rclone (Google Drive) | Semantic FUSE |
|--------|----------------------|---------------|
| Non-determinism | Network sync (unpredictable) | Semantic relevance (intentional) |
| Multiple paths | Google's sharing model (confusing) | Semantic contexts (by design) |
| Performance | Network latency, API rate limits | Local database (consistent) |
| Metadata | Fake Unix perms from ACLs (awkward) | Native semantic data (grounding, similarity) |
| Consistency | Eventually consistent (network) | Immediately consistent (local) |

**rclone documentation literally says:**
> "Note that many operations are not fully POSIX compliant. This is an inherent limitation of cloud storage systems."

**Our documentation:**
> "Note that many operations are not fully POSIX compliant. This is an inherent limitation of exposing semantic graphs as filesystems."

**Same energy. Same usefulness. Same tradeoffs.**

If you accept rclone's weirdness for the convenience of `grep`-ing Google Drive, you'll accept semantic FUSE's weirdness for the convenience of `grep`-ing knowledge graphs.

### The Defenses We Don't Care About

**"But the POSIX specification says..."**

The POSIX specification doesn't account for semantic knowledge graphs. Times change.

**"This would break every tool!"**

Good! Those tools assume files are in trees. Knowledge isn't a tree.

**"What about `make`? What about `git`?"**

Don't use this for source code. Use it for *knowledge about* source code.

**"This is cursed."**

Yes. Beautifully cursed. Like all the best ideas.

## Practical Limitations

### What This Is NOT Good For

- Source code version control (use git)
- Binary file storage (use object storage)
- High-performance computing (use tmpfs)
- Traditional backups (use the graph's native backup)
- Anything requiring determinism (use a real filesystem)

### What This IS Good For

- Research and exploration
- Documentation navigation
- Semantic code search
- Learning domain knowledge
- Following conceptual trails
- AI-assisted development workflows

## Future Extensions

### Write Support

```bash
$ mkdir /mnt/knowledge/my-new-concept/
$ echo "Description: A revolutionary new idea..." > description.md
$ echo "Ontology: MyProject" > .ontology

# Automatically ingested and linked!
```

### Relationship Creation

```bash
$ ln -s ../target-concept.concept relationship/supports/
# Creates SUPPORTS relationship in the graph!
```

### Query Operators

```bash
$ cd /mnt/knowledge/search/AND/embedding+models/
$ cd /mnt/knowledge/search/OR/ai+ml/
$ cd /mnt/knowledge/search/NOT/embedding-models/
```

### Grounding Filters

```bash
$ cd /mnt/knowledge/grounding/strong/embedding-models/
# Only concepts with strong grounding (>0.5)
```

## Decision

**Implement knowledge graph access as a FUSE filesystem** with the following design choices:

1. **Partial Filesystem Model** - Like `/sys/` or `/proc/`, implement only semantically meaningful operations
   - Support: `ls` (query), `cd` (navigate), `cat` (read), `grep`/`find` (search), `echo`/`cp` (ingest), `tar` (snapshot)
   - Do not support: `mv`, `chmod`, `chown`, `touch`, `dd` (operations that don't map to semantic concepts)

2. **Four-Level Hierarchy** - Map infrastructure to semantics:
   - **Shard** (infrastructure: database + API + resources)
   - **Facet** (logical grouping: RBAC + resource isolation)
   - **Ontology** (knowledge domain namespace)
   - **Concepts** (semantic content)

3. **Directory Creation = Semantic Query** - User creates directories with query names
   - `mkdir "embedding models"` defines a semantic query
   - `cd embedding-models/` executes the query
   - `ls` shows concepts matching the query at configured similarity threshold

4. **Relationship Navigation** - Concepts expose `relationships/` subdirectory
   - `cd concept.concept/relationships/SUPPORTS/` traverses graph edges
   - Path represents traversal history (deterministic structure, semantic content)

5. **Write = Ingest** - File writes trigger automatic ingestion
   - `echo "content" > file.md` ingests into current ontology/facet context
   - File may not reappear with same name (concept extraction determines label)
   - Embraces non-determinism as feature (concepts appear based on semantic relevance)

6. **Implementation Options** - Two paths forward:
   - **Option A:** Custom FUSE driver in Python (full control, more code)
   - **Option B:** rclone backend in Go (leverage existing infrastructure, instant interop)

## Consequences

### Benefits

**1. Familiar Interface for Semantic Exploration**
- Users already understand `cd`, `ls`, `cat`, `grep`
- No need to learn custom query language or web UI
- Standard Unix tools become knowledge graph query engines

**2. Distributed Queries via Standard Tools**
```bash
# Transparently searches local + remote shards
find /mnt/knowledge/ -name "*.concept" | grep "pattern"
# - Local shards: FUSE → local PostgreSQL
# - Remote shards: SSHFS → SSH → remote FUSE → remote PostgreSQL
```

**3. Cross-Backend Interoperability** (if rclone implementation)
```bash
# Backup knowledge graph to S3
rclone sync kg:research s3:backup/

# Ingest from Google Drive
rclone copy gdrive:Papers/ kg:research/papers/

# Export to git repository
rclone sync kg:research /tmp/export/
```

**4. TAR as Temporal Snapshots**
```bash
tar czf snapshot-$(date +%s).tar.gz /mnt/knowledge/my-research/
# Same path, different contents over time
# Version your semantic space
```

**5. Living Documentation in Workspaces**
```bash
ln -s /mnt/knowledge/my-project/ ./docs
# Documentation auto-updates as concepts evolve
# Claude Code can read semantic graph directly
```

### Drawbacks

**1. Non-Determinism Can Be Confusing**
- `ls` results change as graph evolves
- Same query returns different results over time
- Mitigation: Clear documentation, caching options, embrace as feature

**2. POSIX Violations Require Education**
- Many standard file operations won't work
- Users expect traditional filesystem behavior
- Mitigation: Follow rclone precedent, document limitations clearly

**3. Performance Considerations**
- Semantic queries slower than filesystem metadata operations
- Graph traversal can be expensive for deep relationships
- Mitigation: Caching layer, configurable similarity thresholds, limit traversal depth

**4. Implementation Complexity**
- Custom FUSE: ~2000-3000 lines of Python
- rclone backend: ~500-1000 lines of Go + API wrapper
- Either requires ongoing maintenance

### Risks

**1. User Confusion** - Non-deterministic behavior violates expectations
- Mitigation: Clear "partial filesystem" designation, precedent from rclone

**2. Performance at Scale** - Large knowledge graphs may be slow
- Mitigation: Shard/facet architecture limits query scope

**3. Adoption Barrier** - Requires FUSE support, mount permissions
- Mitigation: Provide alternative interfaces (web UI, CLI, MCP)

## Alternatives Considered

### 1. WebDAV/HTTP Filesystem

**Pros:** Cross-platform, no FUSE required, browser-compatible
**Cons:** Poorer performance, limited caching, no local integration
**Decision:** FUSE provides better Unix integration, can add WebDAV later

### 2. Git-Like Interface

**Pros:** Familiar to developers, built-in versioning, distributed
**Cons:** Concepts aren't commits, relationships aren't branches, poor semantic fit
**Decision:** Git is for version control, not semantic navigation

### 3. Custom CLI Only

**Pros:** Full control, no filesystem abstraction mismatch
**Cons:** Users must learn new commands, can't use standard Unix tools
**Decision:** CLI exists (kg command), FUSE adds complementary interface

### 4. SQL/GraphQL Query Interface

**Pros:** Powerful queries, precise results, standard protocols
**Cons:** Requires learning query language, no filesystem metaphor benefits
**Decision:** APIs exist, FUSE provides filesystem convenience layer

### 5. Database-as-Filesystem (Direct PostgreSQL Mount)

**Pros:** Tools exist (pgfuse), direct database access
**Cons:** Exposes tables/rows, not semantic concepts, wrong abstraction level
**Decision:** Need semantic layer, not raw database access

## Implementation Recommendation

**Update (Post Peer Review):** After architectural review, we are **strongly leaning toward Python FUSE (Option A)** for the MVP, though not yet committed.

### Reconsidering Python FUSE (Option A)

**Advantages for our specific architecture:**

1. **Shared Logic Layer** - All core services (`QueryService`, `EmbeddingModel`, `GraphQueryFacade`) are Python
   - Can import services directly without HTTP overhead
   - Zero-latency local operations during development
   - No schema drift between FUSE layer and graph layer

2. **Complex Traversal Support** - Deep graph schema knowledge (ADR-048)
   - Relationship navigation requires VocabType awareness
   - Dynamic relationship discovery easier in Python
   - Access to full graph context without API round-trips

3. **Tight Integration** - Same runtime as API server
   - Can mount on same machine as database for testing
   - Direct access to PostgreSQL connection pool
   - Shared caching layer with existing services

**Implementation with `pyfuse3`:**
```python
import pyfuse3
from api.services.query_service import QueryService

class SemanticFS(pyfuse3.Operations):
    def __init__(self):
        self.query_service = QueryService()  # Direct import!

    async def readdir(self, inode, off, token):
        # Direct service call, no HTTP
        concepts = await self.query_service.execute_search(query, threshold=0.7)
        for concept in concepts:
            pyfuse3.readdir_reply(token, f"{concept.label}.concept", ...)
```

**When to use rclone instead (Option B):**
- Remote mounting (laptop → cloud server)
- OAuth management for remote instances
- Cross-backend sync requirements (knowledge graph ↔ S3/Google Drive)
- Deployment to users unfamiliar with Python infrastructure

**Current stance:** Prototype with Python FUSE for local/development use. Both implementations may coexist - Python for tight integration, rclone for remote access and OAuth workflows.

## Future Extensions

### Core Features

- Relationship-based symbolic links (`ln -s concept relationships/SUPPORTS/`)
- Query operators (`/search/AND/`, `/search/OR/`, `/search/NOT/`)
- Grounding filters (`/grounding/strong/`, `/grounding/weak/`)
- Write support for relationship creation
- Multi-shard federated views

### Usability Enhancements (From Peer Review)

**1. Empty Directory Problem Solution**

When semantic queries return no results, generate a virtual `README.md` explaining why:

```bash
mkdir /mnt/knowledge/research/unicorn-physics/
ls /mnt/knowledge/research/unicorn-physics/
# Empty directory - no matching concepts

cat /mnt/knowledge/research/unicorn-physics/README.md
# Query 'unicorn physics' (Threshold: 0.7) matched 0 concepts in ontology 'research'.
#
# Suggestions:
# - Lower threshold: /mnt/knowledge/search/0.5/unicorn+physics/
# - Try broader query: /mnt/knowledge/research/physics/
# - Check available ontologies: ls /mnt/knowledge/
```

**Benefits:** Users understand empty results instead of wondering if the system is broken.

**2. Tarball Snapshots with Temporal Metadata**

Include a `.manifest` file in every tarball to enable "time travel":

```bash
tar czf snapshot-$(date +%s).tar.gz /mnt/knowledge/research/

tar tzf snapshot-*.tar.gz | head -5
.manifest
embedding-models.concept
neural-networks.concept
...

cat .manifest
{
  "snapshot_timestamp": "2025-11-28T23:45:00Z",
  "graph_revision": "a3b2c1d4",
  "shard": "research",
  "facet": "academic",
  "ontology": "ai-research",
  "query_threshold": 0.7,
  "concept_count": 127,
  "embedding_model": "nomic-ai/nomic-embed-text-v1.5"
}
```

**Benefits:**
- Restore semantic state from snapshots
- Track knowledge evolution over time
- Debug "why did this concept disappear?"

**3. RBAC Integration via Filesystem Permissions**

Map filesystem permission bits to OAuth scopes from ADR-054/055:

```bash
ls -l /mnt/knowledge/shard-production/
drwxr-xr-x  engineering/     # User has write:engineering scope
drwxr-xr--  compliance/      # User has read:compliance scope (no write)
d---------  finance/         # User has no access

# Attempting to write without scope:
echo "test" > /mnt/knowledge/shard-production/compliance/test.md
# Permission denied (requires write:compliance scope)
```

**Implementation:** Check OAuth scopes during FUSE `access()` and `open()` operations.

**Benefits:**
- Familiar Unix permission model
- Natural RBAC enforcement
- Tools like `ls -l` show access levels automatically

## References

### Implementation Tools

- [FUSE Documentation](https://github.com/libfuse/libfuse)
- [pyfuse3 Documentation](https://pyfuse3.readthedocs.io/)
- [rclone Architecture](https://rclone.org/docs/)
- [rclone Backend Implementation Guide](https://rclone.org/docs/#writing-your-own-backend)

### Related Semantic File Systems

- [Semantic File System (SFS)](https://dl.acm.org/doi/10.1145/121132.121138) - Gifford et al., MIT, 1991 - Original virtual directories as queries
- [Tagsistant](http://www.tagsistant.net/) - Linux FUSE semantic filesystem with boolean logic
- [TMSU](https://tmsu.org/) - Tag My Sh*t Up - Modern SQLite-backed tagging filesystem
- [Google Cloud Storage FUSE](https://cloud.google.com/storage/docs/gcs-fuse) - Example of widely-used partial POSIX compliance

### Internal Architecture

- ADR-055: Sharding and facet architecture
- ADR-048: Query safety and namespace isolation
- ADR-054: OAuth client management

---

*Knowledge doesn't fit in trees. It forms graphs. Your filesystem should too.* 🌳→🕸️
