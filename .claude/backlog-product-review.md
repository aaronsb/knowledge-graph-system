# Product Review Backlog (2026-02-07)

Findings from the product review that aren't blocking adoption but should be
investigated when working in these areas. Source: `docs/PRODUCT_REVIEW_2026-02-07.md`

## Documentation Depth

- TypeScript docstring coverage at 40.8% — web/ stores, types, API client mostly undocumented
- @verified docstring tags not adopted at scale (97% unverified)
- Missing user guides: web UI workspaces, FUSE reference, graph editing, projection/embedding landscape, artifact system, batch operations
- Config path discrepancy: `~/.config/kg/` vs `~/.kg/` — which is correct?

## Test Coverage

- `oauth.py` — 2K lines, 9% coverage, security-critical
- Workers (ingestion, embedding, projection, restore) — all under 35%
- `queries.py` — 22% coverage, most-used API surface
- Security tests: 6/6 skipped in auth audit suite
- Integration test infrastructure has stubs but no database fixtures (`conftest.py` TODOs)

## Architecture & Tech Debt

- 45 Proposed ADRs that are actually implemented — should be promoted to Accepted (start with ADR-016, 024, 028, 040, 060)
- Schema README claims version 001, actual is 052
- Forward-only migrations — no rollback path, should document explicitly
- Migration numbering gaps (002, 010 missing)
- Restore worker has no post-restore integrity check
- `graph_facade.py` module-level pinned connection pattern — no ADR coverage
- MCP server architecture (2000+ lines of tool definitions) — no dedicated ADR

## Security Hardening

- Dev compose exposes Postgres 5432 and Garage 3900/3903 to host — verify production compose doesn't
- Docker socket mounted into operator container (accepted tradeoff per ADR-061, but worth documenting for security reviewers)
- CORS TODO at `api/app/main.py:62` — tracked in roadmap Phase 0

## CI/CD

- Tests only run locally — no CI test pipeline (lint.yml only)
- OpenAPI spec generation should be automated
- Docs pipeline should have link-checking (mkdocs linkcheck plugin)

## Competitive & Positioning

- Comparison table missing: LangGraph, LlamaIndex KG, Microsoft GraphRAG
- No hosted demo instance or video walkthrough
- macOS FUSE support unclear — may need explicit "Linux only" statement
