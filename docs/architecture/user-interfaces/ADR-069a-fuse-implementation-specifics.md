# FUSE Driver Implementation Specifics

**Status:** Implementation Plan
**Date:** 2026-01-06
**Related:** ADR-069 (Semantic FUSE Filesystem)

## Overview

This document captures specific implementation details for the kg-fuse driver, building on the conceptual design in ADR-069.

## Core Philosophy

- **"Everything is a file"** - Unix philosophy applied to knowledge graphs
- **"Everything is a query"** - Directories represent queries, files represent results
- **"Hologram & Black Hole"** - Read path shows graph projections, write path ingests into graph
- **"Hierarchy is filtering"** - Each directory level narrows results (AND), symlinks widen sources (OR)

## Root Resources

| Resource | Description | Location |
|----------|-------------|----------|
| **Ontologies** | Knowledge domains/collections | `/ontology/{name}/` |
| **Documents** | Source files in graph | `/ontology/{name}/documents/` |
| **Concepts** | Query results | `*.concept.md` files |

## Filesystem Structure

### Hierarchy

```
/mnt/kg/
├── ontology/                              # System-managed (read-only structure)
│   ├── Strategy-As-Code/                  # Ontology (from graph)
│   │   ├── documents/                     # Source documents (read-only)
│   │   │   └── whitepaper.md              # Document content from graph
│   │   └── leadership/                    # User query scoped to ontology
│   │       ├── Concept-A.concept.md       # Results matching "leadership"
│   │       └── governance/                # Nested: "leadership" AND "governance"
│   │           └── Concept-B.concept.md
│   └── test-concepts/
│       └── documents/
│           └── notes.md
│
├── my-research/                           # User workspace (global query)
│   ├── Strategy-As-Code -> ../ontology/Strategy-As-Code    # Include
│   ├── test-concepts -> ../ontology/test-concepts          # Include
│   ├── _!old-archive -> ../ontology/old-archive            # Exclude
│   └── agents/                            # Query across linked ontologies
│       ├── _|governance,compliance/       # OR: governance OR compliance
│       │   └── Result.concept.md
│       └── _!deprecated/                  # NOT: exclude deprecated
│           └── Result.concept.md
│
└── quick-search/                          # Simple global query
    └── Concept.concept.md                 # Results from all ontologies
```

### Path Semantics

```
/ontology/{name}/documents/{file}    → Source document (read-only)
/ontology/{name}/{query}/            → Query scoped to ontology
/{user-dir}/                         → Global query (all ontologies)
/{user-dir}/{ontology-symlink}/      → Explicit source inclusion
/{user-dir}/{query}/                 → Query across linked ontologies
```

### Node Types

| Path Pattern | Type | Source | Writable |
|--------------|------|--------|----------|
| `/ontology/` | dir | Fixed | No |
| `/ontology/{name}/` | dir | Graph (ontologies) | No |
| `/ontology/{name}/documents/` | dir | Fixed | No |
| `/ontology/{name}/documents/{doc}.md` | file | Graph (documents) | No |
| `/ontology/{name}/{query}/` | dir | Client-side | Yes (mkdir/rmdir) |
| `/{user-query}/` | dir | Client-side | Yes (mkdir/rmdir) |
| `/{path}/{concept}.concept.md` | file | Graph (query results) | No |
| `/{path}/{ontology-symlink}` | symlink | Client-side | Yes (ln -s/rm) |

## Boolean Query Logic

### Filtering Model

| Mechanism | Operator | Effect |
|-----------|----------|--------|
| Nesting directories | implicit AND | Narrows results (intersection) |
| Symlinks to ontologies | implicit OR | Widens sources (union) |
| `_!` prefix | NOT | Excludes matches |
| `_\|a,b` prefix | OR | Union of terms at same level |

### Query Operators (`_` prefix)

The underscore prefix reserves a "control plane" namespace for query modifiers:

| Operator | Meaning | Example |
|----------|---------|---------|
| `_!` | NOT / exclude | `_!deprecated/` |
| `_\|` | OR terms | `_\|agents,operators/` |
| `_>N` | Min similarity | `_>0.8/` |
| `_#N` | Limit results | `_#10/` |
| `_@name` | Scope to ontology | `_@Strategy-As-Code/` |
| `_$name` | Saved query ref | `_$my-saved-query/` |

### Example Query

```
/research/
  Strategy-As-Code -> ../ontology/Strategy-As-Code    # Include
  test-concepts -> ../ontology/test-concepts          # Include
  _!old-archive -> ../ontology/old-archive            # Exclude
  agents/                                             # AND "agents"
    _|governance,compliance/                          # AND (governance OR compliance)
      _>0.7/                                          # WHERE similarity > 0.7
        _#20/                                         # LIMIT 20
          Result.concept.md
```

Equivalent query:
```
(Strategy-As-Code OR test-concepts) NOT old-archive
AND agents
AND (governance OR compliance)
WHERE similarity > 0.7
LIMIT 20
```

## Rules

1. **`/ontology/` is reserved** - System-managed, lists ontologies from graph
2. **`/ontology/{name}/documents/` is read-only** - Contains source files, no user dirs inside
3. **Root-level dirs are user workspaces** - Search all ontologies by default
4. **Symlinks scope sources** - Only ontologies can be symlinked, only into user dirs
5. **Ontologies cannot be symlinked into other ontologies** - Only user dirs can have symlinks
6. **Depth = specificity** - Each nested level ANDs another constraint
7. **Operators modify behavior** - Underscore prefix reserved for query control
8. **Concepts are always leaves** - `.concept.md` files are read-only results
9. **Simple queries need no operators** - Just `mkdir "my search term"` works

## Query System

### How Queries Work

1. User runs `mkdir /mnt/kg/ontology/Strategy-As-Code/leadership`
2. FUSE driver stores query definition client-side
3. Directory name becomes the search term ("leadership")
4. When user runs `ls`, driver executes semantic search scoped to ontology
5. Results appear as `.concept.md` files

### Nested Query Resolution

Each level refines the previous results:

```python
def resolve_query(ontology: str, path: str) -> SearchParams:
    """
    Build search params by walking the path hierarchy.
    Each level adds a filter that refines previous results.
    """
    parts = path.split('/') if path else []

    # Start with ontology scope
    params = SearchParams(ontology=ontology, filters=[])

    # Each path component adds a semantic filter
    current_path = ""
    for part in parts:
        current_path = f"{current_path}/{part}".lstrip('/')

        query = query_store.get_query(ontology, current_path)
        if query:
            params.filters.append(SemanticFilter(
                text=query.query_text,
                threshold=query.threshold
            ))

    return params
```

Example:
- `ls /ontology/Strategy-As-Code/` → all documents in ontology
- `ls /ontology/Strategy-As-Code/leadership/` → concepts matching "leadership" in that ontology
- `ls /ontology/Strategy-As-Code/leadership/communication/` → concepts matching "communication" AND "leadership"

### Query Override

Users can customize query text by creating a `.query` file:

```bash
# Default: directory name is the query
mkdir leadership/
ls leadership/  # searches for "leadership"

# Override: custom query text
echo "executive leadership strategy" > leadership/.query
ls leadership/  # now searches for "executive leadership strategy"
```

## Client-Side Storage

### Query Persistence

Location: `~/.local/share/kg-fuse/queries.toml`

```toml
# Query definitions (user-created directories)

[queries."Strategy-As-Code"."leadership"]
query_text = "leadership"
threshold = 0.7
created_at = "2025-01-06T04:00:00Z"

[queries."Strategy-As-Code"."leadership/communication"]
query_text = "communication"
threshold = 0.7
created_at = "2025-01-06T04:01:00Z"

[queries."Strategy-As-Code"."strategy-for-executives"]
query_text = "strategy for executives"
threshold = 0.7
created_at = "2025-01-06T04:02:00Z"
```

### Query Store Implementation

```python
from pathlib import Path
import tomllib
import tomli_w
from typing import Optional
from dataclasses import dataclass

@dataclass
class Query:
    query_text: str
    threshold: float = 0.7
    created_at: str = ""

class QueryStore:
    """Manages user-created query directories"""

    def __init__(self):
        self.path = self._get_data_path() / "queries.toml"
        self.queries: dict[str, Query] = {}
        self._load()

    def _get_data_path(self) -> Path:
        xdg_data = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        data_dir = Path(xdg_data) / "kg-fuse"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    def _load(self):
        if self.path.exists():
            with open(self.path, "rb") as f:
                data = tomllib.load(f)
            for key, value in data.get("queries", {}).items():
                self.queries[key] = Query(**value)

    def _save(self):
        data = {"queries": {k: vars(v) for k, v in self.queries.items()}}
        with open(self.path, "wb") as f:
            tomli_w.dump(data, f)

    def add_query(self, ontology: str, path: str, query_text: Optional[str] = None):
        """Add a query (called on mkdir)"""
        key = f"{ontology}/{path}"
        # Default query text is the last path component
        if query_text is None:
            query_text = path.split('/')[-1]
        self.queries[key] = Query(
            query_text=query_text,
            threshold=0.7,
            created_at=datetime.now().isoformat()
        )
        self._save()

    def remove_query(self, ontology: str, path: str):
        """Remove a query and all children (called on rmdir)"""
        prefix = f"{ontology}/{path}"
        self.queries = {k: v for k, v in self.queries.items()
                        if not k.startswith(prefix)}
        self._save()

    def get_query(self, ontology: str, path: str) -> Optional[Query]:
        """Get query definition"""
        return self.queries.get(f"{ontology}/{path}")

    def is_query_dir(self, ontology: str, path: str) -> bool:
        """Check if path is a user-created query directory"""
        return f"{ontology}/{path}" in self.queries

    def list_queries_under(self, ontology: str, path: str) -> list[str]:
        """List immediate child queries under a path"""
        prefix = f"{ontology}/{path}/" if path else f"{ontology}/"
        children = []
        for key in self.queries:
            if key.startswith(prefix):
                remainder = key[len(prefix):]
                if '/' not in remainder:  # Immediate child only
                    children.append(remainder)
        return children
```

## Caching Architecture

### Two-Tier Caching

1. **Kernel cache** (FUSE options) - Fastest, automatic
2. **Userspace cache** (our code) - Reduces API calls

### Kernel Cache Settings

```python
fuse_options.add("entry_timeout=30")   # Cache dir entries 30s
fuse_options.add("attr_timeout=30")    # Cache file attrs 30s
fuse_options.add("negative_timeout=5") # Cache "not found" 5s
```

### Userspace Cache Implementation

```python
import time
from typing import Any, Optional

class Cache:
    """LRU cache with TTL for API responses"""

    def __init__(self, ttl: float = 30.0, max_size: int = 1000):
        self.ttl = ttl
        self.max_size = max_size
        self._cache: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            timestamp, value = self._cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            del self._cache[key]
        return None

    def set(self, key: str, value: Any):
        # LRU eviction if needed
        if len(self._cache) >= self.max_size:
            oldest = min(self._cache, key=lambda k: self._cache[k][0])
            del self._cache[oldest]
        self._cache[key] = (time.time(), value)

    def invalidate(self, prefix: str = ""):
        """Invalidate all keys starting with prefix (or all if empty)"""
        if prefix:
            self._cache = {k: v for k, v in self._cache.items()
                           if not k.startswith(prefix)}
        else:
            self._cache.clear()
```

### Cache Key Schema

```python
# Ontology list
"ontologies"

# Documents in ontology
"ontology:{name}:docs"

# Query results (includes full path for uniqueness)
"query:{ontology}:{path}"

# File content (by document ID)
"file:{document_id}"

# Concept details
"concept:{concept_id}"
```

### What Gets Cached

| Data | Cache Key | TTL | Invalidation |
|------|-----------|-----|--------------|
| Ontology list | `ontologies` | 30s | Manual refresh |
| Documents in ontology | `ontology:X:docs` | 30s | On write to ontology |
| Query results | `query:X:path` | 30s | On mkdir/rmdir in path |
| File content | `file:doc_id` | 30s | Rarely changes |
| Concept details | `concept:id` | 30s | Rarely changes |

### Invalidation Strategy

```python
def mkdir(self, ontology: str, path: str):
    """Handle mkdir - create query"""
    self.query_store.add_query(ontology, path)
    # Invalidate parent listing so new dir appears
    parent = '/'.join(path.split('/')[:-1])
    self.cache.invalidate(f"query:{ontology}:{parent}")

def rmdir(self, ontology: str, path: str):
    """Handle rmdir - remove query"""
    self.query_store.remove_query(ontology, path)
    # Invalidate parent listing
    parent = '/'.join(path.split('/')[:-1])
    self.cache.invalidate(f"query:{ontology}:{parent}")
```

## FUSE Operations Mapping

### Read Operations

| FUSE Op | Path | Action |
|---------|------|--------|
| `readdir /ontology/` | Root | List ontologies from API |
| `readdir /ontology/X/` | Ontology | List docs + user queries |
| `readdir /ontology/X/q/` | Query | Execute query, list results |
| `read /ontology/X/doc.md` | Document | Fetch document content |
| `read /ontology/X/q/c.concept.md` | Concept | Fetch concept details |
| `getattr` | Any | Return cached attrs or fetch |

### Write Operations

| FUSE Op | Path | Action |
|---------|------|--------|
| `mkdir /ontology/X/q/` | Query | Store query in QueryStore |
| `rmdir /ontology/X/q/` | Query | Remove from QueryStore |
| `write /ontology/X/doc.md` | Document | Trigger ingestion (future) |
| `unlink` | Any | Not supported (read-only hologram) |

### Operation Implementation Sketch

```python
async def readdir(self, fh: int, start_id: int, token) -> None:
    path_info = self._parse_path(fh)

    if path_info.is_root:
        # Fixed: just "ontology"
        entries = [("ontology", DIR)]

    elif path_info.is_ontology_root:
        # List all ontologies from API
        entries = await self._list_ontologies()

    elif path_info.is_ontology:
        # List documents + user query dirs
        docs = await self._list_documents(path_info.ontology)
        queries = self.query_store.list_queries_under(path_info.ontology, "")
        entries = docs + [(q, DIR) for q in queries]

    elif path_info.is_query:
        # Execute query, list results + child queries
        results = await self._execute_query(path_info.ontology, path_info.query_path)
        child_queries = self.query_store.list_queries_under(
            path_info.ontology, path_info.query_path)
        entries = results + [(q, DIR) for q in child_queries]

    # Emit entries...
```

## File Formats

### Document Files (`.md`)

Documents from the graph rendered as markdown:

```markdown
# Document Title

**Ontology:** Strategy-As-Code
**Document ID:** sha256:abc123
**Chunks:** 8

## Content

[Full document text from chunks...]
```

### Concept Files (`.concept.md`)

Concept details rendered as markdown:

```markdown
# Concept Name

**ID:** sha256:concept123
**Grounding:** 0.75 (Strong)
**Diversity:** 42%

## Description

[Concept description...]

## Evidence

### Source 1: document.md (para 3)
> Quoted evidence text...

### Source 2: other-doc.md (para 7)
> More evidence...

## Relationships

- SUPPORTS → other-concept
- CONTRADICTS → another-concept
- IMPLIES → yet-another
```

## Authentication

### OAuth Client Flow

The FUSE driver is an OAuth client, same as CLI and MCP:

```
┌─────────────────────────────────────────────────────┐
│                    API Server                        │
└─────────────────────────────────────────────────────┘
        ▲           ▲           ▲           ▲
     OAuth       OAuth       OAuth       OAuth
        │           │           │           │
   ┌────┴───┐  ┌────┴───┐  ┌────┴───┐  ┌────┴───┐
   │  CLI   │  │  MCP   │  │  Web   │  │  FUSE  │
   └────────┘  └────────┘  └────────┘  └────────┘
```

### Setup Flow

```bash
# Create OAuth client for FUSE (one-time)
kg oauth create --for fuse

# This writes to ~/.config/kg-fuse/config.toml:
# [auth]
# client_id = "kg-fuse-admin-abc123"
# client_secret = "secret..."
#
# [api]
# url = "http://localhost:8000"

# Mount (reads config automatically)
kg-fuse /mnt/kg
```

### Config File Location

- Credentials: `~/.config/kg-fuse/config.toml` (XDG config)
- Query data: `~/.local/share/kg-fuse/queries.toml` (XDG data)

## API Endpoints Used

| Operation | Endpoint | Notes |
|-----------|----------|-------|
| Auth | `POST /auth/oauth/token` | Client credentials grant |
| List ontologies | `GET /ontology/` | Returns ontology names |
| List documents | `GET /documents/?ontology=X` | Documents in ontology |
| Get document | `GET /documents/{id}` | Document content |
| Search concepts | `POST /query/search` | Semantic search |
| Get concept | `GET /concepts/{id}` | Concept details |

## Future Extensions

### Write Support (Ingestion)

```bash
# Copy file to ontology → triggers ingestion
cp report.pdf /mnt/kg/ontology/Strategy-As-Code/

# File "disappears" into ingestion pipeline
# After processing, concepts appear in query results
```

Implementation:
- `write()` buffers to temp file
- `release()` triggers POST to `/ingest/file`
- Optional: create `.processing` ghost file with job ID

### Query Parameters in Path

Could support threshold in directory name:

```bash
mkdir "leadership@0.8"    # 80% threshold
mkdir "leadership@0.5"    # 50% threshold (broader)
```

### Symlinks as Relationships

```bash
# Create relationship between concepts
ln -s ../other-concept.concept.md relationships/SUPPORTS/
```

### Watch for Changes

```bash
# inotify-based monitoring
inotifywait -m /mnt/kg/ontology/Strategy-As-Code/ -e create |
while read dir action file; do
    echo "New concept: $file"
done
```

## Implementation Status

### Phase 1: Core Infrastructure (Complete)
- [x] Basic FUSE mount/unmount with pyfuse3
- [x] OAuth authentication from config file
- [x] List ontologies at `/ontology/` root
- [x] `kg oauth create --for fuse` setup command

### Phase 2: Query System (Complete)
- [x] QueryStore class with TOML persistence (`~/.local/share/kg-fuse/queries.toml`)
- [x] `mkdir` creates query directory (stores in QueryStore)
- [x] `rmdir` removes query directory (removes from QueryStore)
- [x] `readdir` on query dir executes semantic search
- [x] Results appear as `.concept.md` files

### Phase 3: Content Reading (Complete)
- [x] Document content reading (`.md` files from graph)
- [x] Concept file rendering with YAML frontmatter
- [x] Source document filename in evidence (Apache AGE workaround)

### Phase 4: Advanced Structure (Planned)
- [ ] Move documents to `/ontology/{name}/documents/`
- [ ] Root-level user directories (global queries)
- [ ] Symlink support for multi-ontology queries
- [ ] Boolean operators (`_!`, `_|`, `_>`, `_#`, `_@`, `_$`)
- [ ] Nested query resolution (AND intersection)

### Phase 5: Caching (Planned)
- [ ] Userspace LRU cache with TTL
- [ ] Cache invalidation on mkdir/rmdir
- [ ] FUSE kernel cache options (entry_timeout, attr_timeout)

### Phase 6: Write Support (Future)
- [ ] Write to ontology triggers ingestion
- [ ] Buffer to temp file, POST on release
- [ ] `.processing` ghost files for job tracking

## References

- ADR-069: Semantic FUSE Filesystem (conceptual design)
- ADR-054: OAuth 2.0 Authentication
- pyfuse3 documentation: https://pyfuse3.readthedocs.io/
- XDG Base Directory Spec: https://specifications.freedesktop.org/basedir-spec/
