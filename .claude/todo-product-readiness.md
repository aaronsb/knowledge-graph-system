# Product Readiness Roadmap

Source: `docs/PRODUCT_REVIEW_2026-02-07.md`
Backlog: `.claude/backlog-product-review.md`

## Credibility Fixes

- [ ] `[agent]` Fix CORS — replace `allow_origins=["*"]` with env-gated `ALLOWED_ORIGINS`, default to `localhost:3000` in dev
- [ ] `[agent]` Remove default password fallbacks — 7 locations hardcode `"password"`; fail-closed if `POSTGRES_PASSWORD` unset
- [ ] `[agent]` Fix broken links and stale counts — 8 broken links in docs/README.md, 1 in root README, wrong ADR counts, wrong MCP tool names/counts in CLI README, stale CLI command table
- [ ] `[agent]` Pipeline cleanup — delete always-failing `publish-docs.yml`, remove `docs/.venv/` from repo
- [ ] `[pair]` Stub honesty — vocab manager 4 silent no-ops, pruning 2 fake AI stubs. Decide: implement or `NotImplementedError`.
- [ ] `[human]` Triage known bugs — graph annealing job failures, any other broken subsystems

## Onboarding

- [ ] `[pair]` Agent onboarding guide — dedicated file linked from README. Sections: understand, pre-flight, install (with "ask the user" callouts), first use, connect clients, verify, troubleshoot.
- [ ] `[pair]` Developer quick-start with sample docs — bundle 3-5 docs, walkthrough from init to seeing results in web UI
- [ ] `[human]` Test standalone install on a fresh machine — note friction points
- [ ] `[human]` Document production deployment — TLS flow, multi-machine setup, user management, Nomic embedding (no GPU needed)
- [ ] `[human]` License FAQ — explain ELv2 (platform) + MIT (CLI, FUSE) split

## README & API Reference

- [ ] `[agent]` Feature showcase — add screenshots of polarity explorer, block builder, embedding landscape, vocab chord diagram. Add cost guidance and minimum requirements.
- [ ] `[agent]` Regenerate OpenAPI spec from running FastAPI — current spec covers 64 of 163 endpoints
