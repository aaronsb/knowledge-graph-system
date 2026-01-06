# FUSE Driver Implementation Tracking

**ADR:** ADR-069, ADR-069a
**Branch:** feature/fuse-driver
**Started:** 2026-01-05

## Phase 1: Core Infrastructure (Complete)
- [x] Basic FUSE mount/unmount with pyfuse3
- [x] OAuth authentication from config file
- [x] List ontologies at `/ontology/` root
- [x] `kg oauth create --for fuse` setup command

## Phase 2: Query System (Current)
- [ ] QueryStore class with TOML persistence (`~/.local/share/kg-fuse/queries.toml`)
- [ ] `mkdir` creates query directory (stores in QueryStore)
- [ ] `rmdir` removes query directory (removes from QueryStore)
- [ ] `readdir` on query dir executes semantic search
- [ ] Results appear as `.concept` files

## Phase 3: Content Reading
- [ ] Document content reading (`.md` files from graph)
- [ ] Concept file rendering (`.concept` files with evidence/relationships)
- [ ] Nested query resolution (intersection of parent queries)

## Phase 4: Caching
- [ ] Userspace LRU cache with TTL
- [ ] Cache invalidation on mkdir/rmdir
- [ ] FUSE kernel cache options (entry_timeout, attr_timeout)

## Phase 5: Write Support (Future)
- [ ] Write to ontology triggers ingestion
- [ ] Buffer to temp file, POST on release
- [ ] `.processing` ghost files for job tracking

## Notes

### Key Files
- `fuse/kg_fuse/filesystem.py` - Core FUSE operations
- `fuse/kg_fuse/main.py` - Entry point, config loading
- `fuse/kg_fuse/config.py` - XDG config file handling

### API Endpoints
- `POST /auth/oauth/token` - Auth
- `GET /ontology/` - List ontologies
- `GET /documents/?ontology=X` - List documents
- `POST /query/search` - Semantic search
- `GET /concepts/{id}` - Concept details

### Design Decisions
- TOML over SQLite for query persistence (simpler, sufficient)
- Two-tier caching (kernel + userspace)
- Directory name = search term (no special syntax)
- `.query` file can override search term
