---
status: Accepted
date: 2025-11-28
deciders:
  - aaronsb
  - claude
related:
  - ADR-055
  - ADR-048
  - ADR-054
---

# ADR-069: Semantic FUSE Filesystem

> "Everything is a file" - Traditional Unix Philosophy
> "Everything is a file, but which file depends on what you're thinking about" - Semantic Unix Philosophy

## Overview

Traditional filesystems force you to organize knowledge in rigid hierarchies — one directory, one path, one canonical location. But knowledge doesn't work that way. A document about embedding models is simultaneously about AI architecture, operational procedures, and bug fixes. Why should it live in only one folder?

The knowledge graph already solves this by letting concepts exist in multiple semantic contexts. But accessing it requires custom tools: CLI commands, web interfaces, MCP integration. Unix users already have powerful tools — grep, find, diff, tar — that they know intimately, but these tools can't touch the graph.

This ADR describes exposing the knowledge graph as a FUSE (Filesystem in Userspace) mount point, turning standard Unix tools into knowledge graph explorers. Type `cd /mnt/knowledge/embedding-models/` and you're executing a semantic query. Run `ls` and you see concepts with similarity scores. The filesystem adapts to your exploration patterns, making knowledge navigation feel like browsing files — except the files organize themselves based on what they mean.

## Implementation Status

**Published:** `pipx install kg-fuse` ([PyPI](https://pypi.org/project/kg-fuse/))

| Feature | Status |
|---------|--------|
| FUSE mount/unmount (pyfuse3) | Shipped |
| OAuth authentication | Shipped |
| Ontology listing at `/ontology/` | Shipped |
| `mkdir` creates semantic query | Shipped |
| Query results as `.concept.md` files | Shipped |
| Document content reading | Shipped |
| Concept rendering with evidence | Shipped |
| `kg oauth create --for fuse` setup | Shipped |
| Desktop integration (Dolphin, GNOME) | Shipped |
| Obsidian graph view compatibility | Shipped |
| `.meta/` control plane | Planned |
| Nested query resolution (AND) | Planned |
| Multi-ontology symlinks | Planned |
| Write-to-ingest | Planned |
| Userspace LRU caching | Planned |

See ADR-069.1 for detailed implementation specifics (phases, caching, query store).

---

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
- Multi-ontology organization
- Cross-domain linking (automatic concept merging)

FUSE exposes these capabilities through filesystem metaphors that users already understand.

### Architectural Validation

This proposal underwent external peer review to validate feasibility against the existing codebase. Key findings:

- **Architectural Fit:** The FUSE operations map directly to existing services without requiring new core logic
  - `ls` (semantic query) -> `QueryService.build_search_query`
  - `cd relationships/` (graph traversal) -> `QueryService.build_concept_details_query`
  - Write operations -> existing async ingestion pipeline

- **Implementation Feasibility:** High - essentially re-skinning existing services into FUSE protocol

- **Discovery Value:** Solves the "I don't know what to search for" problem by allowing users to browse valid semantic pathways

- **Standard Tool Integration:** Turns every Unix utility (`grep`, `diff`, `tar`) into a knowledge graph tool for free

The review validated this is a "rigorous application of the 'everything is a file' philosophy to high-dimensional data," not a cursed hack.

### Performance and Consistency Engineering

External research on high-dimensional semantic file systems identified critical engineering considerations that our architecture already addresses:

**1. The Write Latency Trap (Mitigated)**
- **Risk:** Synchronous embedding generation (15-50ms+) and graph linking (seconds) would block write() syscalls, hanging applications
- **Our Solution:** Asynchronous worker pattern (ADR-014) with job queue

**2. The Read (ls) Bottleneck (Mitigated)**
- **Risk:** Fresh vector searches on every readdir would cause sluggish directory listings
- **Our Solution:** Query-time retrieval with caching, 100-200ms retrieval target, PostgreSQL connection pooling

**3. POSIX Stability via Deterministic Structure (Addressed)**
- **Risk:** Purely emergent clustering causes "cluster jitter" - files randomly moving between folders
- **Our Solution:** Stable hierarchy based on ontology assignment. Concepts appear in multiple semantic query directories (intentional), but underlying storage location is stable.

**4. Eventual Consistency Gap (Acknowledged)**
- **Risk:** Async processing creates delay between write and appearance in semantic directories
- **Mitigation:** Virtual README.md in empty query results explaining why (future)

**Verdict:** The architecture decouples high-latency "thinking" (AI processing) from low-latency "acting" (filesystem I/O), which research validates as the primary requirement for functional semantic filesystems.

---

## The Design

### Mount Point

```bash
# Create OAuth credentials
kg oauth create --for fuse

# Mount the filesystem
kg-fuse /mnt/knowledge

# Explore
ls /mnt/knowledge/ontology/
```

### Directory Structure

Directories are **semantic queries**, not static folders:

```bash
/mnt/knowledge/
├── ontology/                           # All knowledge domains
│   ├── economics/                      # An ontology
│   │   ├── documents/                  # Source files (read-only)
│   │   │   └── research-paper.pdf
│   │   ├── inflation/                  # Your query (mkdir)
│   │   │   ├── Monetary-Policy.concept.md
│   │   │   └── Supply-Chain.concept.md
│   │   └── market-dynamics/            # Another query
│   └── architecture/                   # Another ontology
```

### File Format

Concept files are dynamically generated markdown:

```bash
$ cat /mnt/knowledge/ontology/economics/inflation/Monetary-Policy.concept.md
```

```markdown
# Monetary Policy

Central bank actions to control money supply and interest rates.

## Evidence

> "The Federal Reserve uses open market operations..."
> -- research-paper.pdf (chunk 3)

> "Interest rate adjustments affect borrowing costs..."
> -- economics-textbook.pdf (chunk 12)

## Relationships

- INFLUENCES -> Inflation (0.92)
- CONTROLLED_BY -> Central Bank (0.88)
- AFFECTS -> Employment (0.75)

## Grounding

Strength: 0.85 (well-supported)
Sources: 3 documents
```

### Query System

Creating a directory defines a semantic query. Listing it executes the query:

```bash
# Create a query
mkdir /mnt/knowledge/ontology/economics/inflation
# List results (executes semantic search)
ls /mnt/knowledge/ontology/economics/inflation/
# Monetary-Policy.concept.md
# Supply-Chain.concept.md
# Consumer-Price-Index.concept.md

# Remove the query (not the concepts)
rmdir /mnt/knowledge/ontology/economics/inflation/
```

---

## POSIX Violations (Features!)

### 1. Non-Deterministic Directory Listings

```bash
$ ls /mnt/knowledge/ontology/ai-research/embedding-models/
unified-regeneration.concept.md
compatibility-checking.concept.md

# New concept ingested elsewhere...

$ ls /mnt/knowledge/ontology/ai-research/embedding-models/
unified-regeneration.concept.md
compatibility-checking.concept.md
embedding-architecture.concept.md  # New! Without touching this directory!
```

**Why it's beautiful:** Your filesystem stays current with your knowledge, automatically.

### 2. Multiple Canonical Paths

The same concept can appear in multiple query directories. It "exists" everywhere it's semantically relevant.

**Why it's beautiful:** Concepts belong to multiple contexts simultaneously.

### 3. Temporal Inconsistency

```bash
$ stat unified-regeneration.concept.md
Modified: 2025-11-29 03:59:57  # When concept was created

$ cat unified-regeneration.concept.md  # Read it

$ stat unified-regeneration.concept.md
Modified: 2025-11-29 04:15:32  # NOW! Because grounding updated!
```

**Why it's beautiful:** Living knowledge, not static files.

### Important: This Is NOT a Full Filesystem

Like `/sys/` or `/proc/`, this is a **partial filesystem** that exposes a specific interface through filesystem semantics. It only implements operations that make semantic sense.

**What works:**
- `ls` (semantic query)
- `cd` (navigate semantic space)
- `cat` (read concept)
- `find` / `grep` (search)
- `tar` (snapshot)
- `stat` (metadata)
- `mkdir` / `rmdir` (create/remove queries)

**What doesn't work (and won't):**
- `mv` (concepts don't "move" in semantic space)
- `chmod` / `chown` (use OAuth scoping instead)
- `touch` (timestamps are semantic, not file-based)
- `dd` (nonsensical for semantic content)

**This is a feature, not a limitation.** Don't pretend to be a full filesystem. Be an excellent semantic interface.

---

## Use Cases

### Unix Tool Integration

```bash
# Find all concepts mentioning "distributed"
grep -r "distributed" /mnt/knowledge/ontology/architecture/

# Open concept in your editor
vim /mnt/knowledge/ontology/economics/inflation/Monetary-Policy.concept.md

# Snapshot your research
tar czf research-$(date +%s).tar.gz /mnt/knowledge/ontology/my-research/
# Same path, different contents over time -- temporal knowledge snapshots

# Copy a snapshot of query results
cp -r /mnt/knowledge/ontology/economics/inflation/ ./local-backup/
```

### Obsidian as a Graph Viewer

The FUSE filesystem presents concepts as markdown files with relationship references. Point Obsidian at the mount point and its built-in graph view renders your knowledge graph natively -- no plugin required. Obsidian is essentially fooled into being a graph introspection interface and document viewer.

### Remote Access

Since it's a real filesystem, remote access is free:

```bash
# SSH into your server and browse the graph
ssh server "ls /mnt/knowledge/ontology/"

# Mount remotely via SSHFS
sshfs server:/mnt/knowledge /mnt/remote-knowledge

# Copy a snapshot of query results
scp -r server:/mnt/knowledge/ontology/economics/inflation/ ./local-copy/
```

### Semantic Grep

```bash
# Traditional grep
grep -r "embedding" /docs/
# Returns every file mentioning "embedding" (thousands of false positives)

# Semantic filesystem
ls /mnt/knowledge/ontology/ai-research/embedding/
# Returns only concepts semantically related to embedding
```

---

## Decision

**Implement knowledge graph access as a FUSE filesystem** with the following design choices:

1. **Partial Filesystem Model** - Like `/sys/` or `/proc/`, implement only semantically meaningful operations
2. **Ontology-Based Hierarchy** - Ontologies are directories, queries are subdirectories created by the user
3. **Directory Creation = Semantic Query** - `mkdir "embedding models"` defines a query, `ls` executes it
4. **Python FUSE (pyfuse3)** - Direct integration with the API backend, shared auth model
5. **OAuth Client Authentication** - Same auth as CLI and MCP (ADR-054)

## Consequences

### Benefits

1. **Familiar Interface** - Users already understand `cd`, `ls`, `cat`, `grep`. No new query language needed.
2. **Standard Tool Integration** - Every Unix utility becomes a knowledge graph tool for free.
3. **Desktop Integration** - File managers (Dolphin, GNOME Files) browse the graph natively.
4. **Editor Compatibility** - Obsidian, VS Code, vim all read concept files without plugins.
5. **Remote Access** - SSH and SSHFS provide remote graph browsing with zero extra infrastructure.

### Drawbacks

1. **Non-Determinism Can Be Confusing** - `ls` results change as graph evolves. Mitigation: document as feature, provide caching.
2. **POSIX Violations Require Education** - Many standard file operations won't work. Mitigation: follow rclone precedent, document limitations.
3. **Performance Considerations** - Semantic queries slower than filesystem metadata operations. Mitigation: caching layer, configurable similarity thresholds.

---

## Future Vision

The following ideas informed the design but are not yet implemented. They represent the natural evolution of a semantic filesystem.

### `.meta` Control Plane

Every query directory would contain a hidden `.meta/` folder with virtual files for tuning:

```bash
echo 0.85 > .meta/threshold     # High precision
echo 20 > .meta/limit           # Fewer results
echo "deprecated" >> .meta/exclude  # Filter out
cat .meta/query.toml            # Debug view
```

### Nested Query Resolution

Each directory level narrows results (implicit AND):

```bash
ls /ontology/economics/leadership/                  # "leadership" in economics
ls /ontology/economics/leadership/communication/     # "leadership" AND "communication"
```

### Multi-Ontology Queries via Symlinks

```bash
mkdir my-research
ln -s ../ontology/economics my-research/
ln -s ../ontology/sociology my-research/
ls my-research/inequality/   # Searches across both ontologies
```

### Write-to-Ingest

```bash
cp report.pdf /mnt/knowledge/ontology/economics/
# File "disappears" into the ingestion pipeline
# After extraction, concepts appear in query results
```

### Multi-Tenant Hierarchy (Shards and Facets)

The ADR originally proposed a four-level hierarchy:

```
Shard (infrastructure: database + API)
  -> Facet (logical grouping: RBAC + resource isolation)
    -> Ontology (knowledge domain)
      -> Concepts (semantic content)
```

This would enable per-team access control, resource isolation, and organizational clarity. The current implementation uses the flat ontology model. Shards and facets remain a future consideration for multi-tenant deployments.

### Relationship Navigation as Filesystem

```bash
cd /mnt/knowledge/ontology/ai/embedding-models/unified-regeneration/
ls relationships/
# includes/  requires/  validates/  supported-by/
cd relationships/includes/
ls
# compatibility-checking.concept.md
```

### rclone Backend (Alternative Implementation)

Instead of a custom FUSE driver, the knowledge graph could be exposed as an rclone backend. This would provide instant interoperability with cloud storage:

```bash
rclone sync kg:research s3:backup/
rclone copy gdrive:Papers/ kg:research/papers/
```

The Python FUSE approach was chosen for tighter integration, but rclone remains viable for remote access and cross-backend sync scenarios.

### Distributed Queries Across Mount Boundaries

```bash
# Mount local and remote shards
mount -t fuse.knowledge-graph -o shard=research /dev/knowledge /mnt/local
sshfs partner@remote:/mnt/knowledge/shared /mnt/remote

# grep across ALL of them
grep -r "API compatibility" /mnt/{local,remote}/
# Standard Unix tools become distributed knowledge graph query engines
```

### Event-Driven Workflows

```bash
# Watch for knowledge graph changes
inotifywait -m /mnt/knowledge/ontology/security/ -e create |
while read dir action file; do
    notify-send "New vulnerability concept: $file"
done
```

### Build System Integration

```bash
# Makefile that depends on semantic queries
API_DOCS := $(shell ls /mnt/knowledge/ontology/api-endpoints/*.concept.md)

docs/api.html: $(API_DOCS)
    kg export --format html /mnt/knowledge/ontology/api-endpoints/ > $@
```

### Diff-Based Knowledge Evolution

```bash
# Capture semantic state at two points
tar czf snapshot-before.tar.gz /mnt/knowledge/ontology/my-research/
# ... months of work ...
tar czf snapshot-after.tar.gz /mnt/knowledge/ontology/my-research/

diff -r /tmp/before/ /tmp/after/
# New concepts (+), strengthened concepts (modified), abandoned concepts (-)
```

---

## Appendix: Related Work

This proposal builds on a rich history of semantic filesystems, though none have applied the "Directory = Query" metaphor to vector embeddings and probabilistic similarity.

| Feature | Tagsistant | TMSU | MIT SFS (1991) | **This System** |
|---------|------------|------|----------------|-----------------|
| **Organization** | Boolean Logic | Explicit Tags | Key-Value Attributes | **Vector Embeddings** |
| **Determinism** | Deterministic | Deterministic | Deterministic | **Probabilistic** |
| **Backend** | SQL/Dedup | SQLite | Transducers | **Vector DB + LLM** |
| **Membership Model** | Binary (tagged/not) | Binary | Binary | **Continuous (similarity score)** |

**The key innovation:** Existing systems map **discrete values** (tags, attributes) to directories. This system maps **continuous values** (similarity scores) to directories. That's the specific innovation that justifies the POSIX violations -- we're navigating high-dimensional semantic space through a filesystem interface.

## Appendix: Why This Will Make Unix Admins Angry

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

Have you considered that maybe `rsync` should understand semantic similarity?

### The rclone Defense

Google Cloud Storage FUSE and rclone for Google Drive exhibit the same violations:
- Non-deterministic listings (files appear/disappear as others edit)
- Multiple canonical paths (same file via `/MyDrive/` and `/SharedDrives/`)
- Eventually consistent (write then read might return old content)
- Partial POSIX (no symlinks, fake permissions)

**People accept this because the abstraction is useful.**

rclone documentation literally says:
> "Note that many operations are not fully POSIX compliant. This is an inherent limitation of cloud storage systems."

If you accept rclone's weirdness for the convenience of `grep`-ing Google Drive, you'll accept semantic FUSE's weirdness for the convenience of `grep`-ing knowledge graphs.

## Appendix: Alternatives Considered

### WebDAV/HTTP Filesystem
**Pros:** Cross-platform, no FUSE required. **Cons:** Poorer Unix integration.
**Decision:** FUSE provides better Unix integration, can add WebDAV later.

### Git-Like Interface
**Pros:** Familiar to developers. **Cons:** Concepts aren't commits, poor semantic fit.
**Decision:** Git is for version control, not semantic navigation.

### Custom CLI Only
**Pros:** Full control. **Cons:** Can't use standard Unix tools.
**Decision:** CLI exists (`kg` command), FUSE adds complementary interface.

### Database-as-Filesystem (Direct PostgreSQL Mount)
**Pros:** Tools exist (pgfuse). **Cons:** Exposes tables/rows, wrong abstraction level.
**Decision:** Need semantic layer, not raw database access.

## References

- [FUSE Documentation](https://github.com/libfuse/libfuse)
- [pyfuse3 Documentation](https://pyfuse3.readthedocs.io/)
- [Semantic File System (SFS)](https://dl.acm.org/doi/10.1145/121132.121138) - Gifford et al., MIT, 1991
- [Tagsistant](http://www.tagsistant.net/) - Linux FUSE semantic filesystem
- [TMSU](https://tmsu.org/) - Tag My Sh*t Up - Modern SQLite-backed tagging filesystem
- [Google Cloud Storage FUSE](https://cloud.google.com/storage/docs/gcs-fuse) - Partial POSIX compliance precedent
- ADR-069.1: FUSE Implementation Specifics
- ADR-054: OAuth 2.0 Authentication
- ADR-055: Sharding and facet architecture

---

*Knowledge doesn't fit in trees. It forms graphs. Your filesystem should too.*
