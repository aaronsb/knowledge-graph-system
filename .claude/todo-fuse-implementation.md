# FUSE Driver Implementation Tracking

**ADR:** ADR-069, ADR-069a
**Branch:** feature/fuse-driver
**Started:** 2026-01-05

## Phase 1: Core Infrastructure (Complete)
- [x] Basic FUSE mount/unmount with pyfuse3
- [x] OAuth authentication from config file
- [x] List ontologies at `/ontology/` root
- [x] `kg oauth create --for fuse` setup command

## Phase 2: Query System (Complete)
- [x] QueryStore class with TOML persistence (`~/.local/share/kg-fuse/queries.toml`)
- [x] `mkdir` creates query directory (stores in QueryStore)
- [x] `rmdir` removes query directory (removes from QueryStore)
- [x] `readdir` on query dir executes semantic search
- [x] Results appear as `.concept.md` files

## Phase 3: Content Reading (Complete)
- [x] Document content reading (`.md` files from graph)
- [x] Concept file rendering (`.concept.md` files with evidence/relationships)
- [x] YAML frontmatter with relationships and source documents
- [x] Source document filename from DocumentMeta (Apache AGE workaround)

## Phase 4: Advanced Structure (Complete)
- [x] Move documents to `/ontology/{name}/documents/`
- [x] Root-level user directories (global queries)
- [x] Symlink support for multi-ontology queries
- [x] `.meta` control plane (virtual directories)
  - [x] `.meta/limit` - result count
  - [x] `.meta/threshold` - similarity filter
  - [x] `.meta/exclude` - semantic NOT (fully implemented)
  - [x] `.meta/union` - semantic OR (fully implemented)
  - [x] `.meta/query.toml` - debug view (read-only)
- [x] Nested query resolution (AND intersection)

## Phase 5: Caching (Planned)
- [ ] Userspace LRU cache with TTL
- [ ] Cache invalidation on mkdir/rmdir
- [ ] FUSE kernel cache options (entry_timeout, attr_timeout)

## Phase 6: Write Support (Complete)
- [x] `mkdir /ontology/name` creates new ontology
- [x] `cp file /ontology/name/` triggers ingestion
  - Buffer to memory, POST on release
  - Auto-approve for FUSE ingestions
  - Black hole semantics (file disappears after ingestion)
- [ ] `.processing` ghost files for job tracking (future)

## Design Notes

### `.meta` Control Plane (sysfs-style)

Instead of DSL operators in directory names, queries are configured via virtual `.meta/` directories:

| Mechanism | Effect |
|-----------|--------|
| Nesting directories | Implicit AND (narrows results) |
| Symlinks to ontologies | Implicit OR (widens sources) |
| `.meta/exclude` | Semantic NOT (removes matches) |
| `.meta/union` | Semantic OR (adds matches) |
| `.meta/threshold` | Minimum similarity filter |
| `.meta/limit` | Maximum result count |
| `.meta/query.toml` | Debug view (read-only) |

Each `.meta/` file contains a comment line explaining the setting, followed by the value:
```
# Maximum number of concepts to return. Default is 50.
50
```

### Key Files
- `fuse/kg_fuse/filesystem.py` - Core FUSE operations
- `fuse/kg_fuse/query_store.py` - Query persistence (TOML)
- `fuse/kg_fuse/main.py` - Entry point, config loading
- `fuse/kg_fuse/config.py` - XDG config file handling

### Known Issues
- Apache AGE OPTIONAL MATCH bug requires separate query for DocumentMeta filename
  See: https://www.mail-archive.com/dev@age.apache.org/msg05690.html
