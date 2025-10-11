# Knowledge Graph System - TODO

## High Priority

### Modular Schema Architecture (ADR-024 Enhancement)

**Issue:** Current `schema/multi_schema.sql` is monolithic - creates all schemas in one file.

**Problem:**
- Reset is "all or nothing" - can't preserve users while clearing jobs/graph
- No granular control for selective resets
- Production scenarios need different reset combinations

**Proposed Structure:**
```
schema/
├── init_age.sql              # Graph (ag_catalog) - AGE initialization
├── 02_schema_api.sql         # kg_api (jobs, vocabulary, performance)
├── 03_schema_auth.sql        # kg_auth (users, API keys, permissions)
├── 04_schema_logs.sql        # kg_logs (audit, metrics, health)
└── multi_schema.sql          # Orchestrator (sources all above for backward compat)
```

**Selective Reset Scenarios:**
1. **Dev reset** - Nuke everything (current behavior)
2. **Job queue reset** - Keep users/logs, clear kg_api + ag_catalog
3. **Graph reset** - Keep users/jobs/logs, clear only ag_catalog
4. **Production reset** - Keep kg_auth, clear everything else

**Implementation Tasks:**
- [ ] Split `multi_schema.sql` into modular files (one per schema)
- [ ] Update `docker-compose.yml` to mount all schema files
- [ ] Add `--preserve-users`, `--preserve-jobs`, `--preserve-logs` flags to reset CLI
- [ ] Update `src/admin/reset.py` to support selective reset modes
- [ ] Document reset scenarios in `docs/guides/DATABASE_RESET.md`

**Benefits:**
- Production-safe resets (preserve user accounts)
- Faster development (reset graph without losing local config)
- Granular maintenance (clear old jobs without touching graph)
- Better testing (reset specific subsystems)

**Related Files:**
- `schema/multi_schema.sql`
- `src/admin/reset.py`
- `docker-compose.yml`

**Priority:** Medium (works fine as-is, but important for production)

---

## Future Enhancements

### LLM-Assisted Vocabulary Curation (ADR-026)
- [ ] Implement `vocabulary_suggestions` table population
- [ ] Add `kg vocabulary review --with-suggestions` command
- [ ] LLM synonym detection batch process

### Vocabulary Analytics Dashboard (ADR-026)
- [ ] Trending relationship types over time
- [ ] Co-occurrence network visualization
- [ ] Vocabulary growth forecasting

### Performance Optimization
- [ ] Implement `refresh_hot_edges()` scheduled job
- [ ] Add query result caching layer
- [ ] pgvector extension for faster vector search

### Authentication & Authorization
- [ ] Implement real user authentication (replace placeholder)
- [ ] JWT token support
- [ ] OAuth integration (ADR-024: kg_auth.oauth_tokens)

---

**Last Updated:** 2025-10-10
