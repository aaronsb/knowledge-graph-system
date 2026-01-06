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

## Phase 4: Advanced Structure (Planned)
- [ ] Move documents to `/ontology/{name}/documents/`
- [ ] Root-level user directories (global queries)
- [ ] Symlink support for multi-ontology queries
- [ ] Boolean operators (`_!`, `_|`, `_>`, `_#`, `_@`, `_$`)
- [ ] Nested query resolution (AND intersection)

## Phase 5: Caching (Planned)
- [ ] Userspace LRU cache with TTL
- [ ] Cache invalidation on mkdir/rmdir
- [ ] FUSE kernel cache options (entry_timeout, attr_timeout)

## Phase 6: Write Support (Future)
- [ ] Write to ontology triggers ingestion
- [ ] Buffer to temp file, POST on release
- [ ] `.processing` ghost files for job tracking

## Design Notes

### Boolean Query Model

The filesystem structure acts as a visual query builder:

| Mechanism | Operator | Effect |
|-----------|----------|--------|
| Nesting directories | implicit AND | Narrows results |
| Symlinks to ontologies | implicit OR | Widens sources |
| `_!term` | NOT | Excludes matches |
| `_\|a,b` | OR | Union of terms |
| `_>N` | threshold | Min similarity |
| `_#N` | limit | Max results |
| `_@name` | scope | Explicit ontology |
| `_$name` | reference | Saved query |

### Key Files
- `fuse/kg_fuse/filesystem.py` - Core FUSE operations
- `fuse/kg_fuse/query_store.py` - Query persistence (TOML)
- `fuse/kg_fuse/main.py` - Entry point, config loading
- `fuse/kg_fuse/config.py` - XDG config file handling

### Known Issues
- Apache AGE OPTIONAL MATCH bug requires separate query for DocumentMeta filename
  See: https://www.mail-archive.com/dev@age.apache.org/msg05690.html
