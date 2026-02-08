# Product Readiness Roadmap

Source: `docs/PRODUCT_REVIEW_2026-02-07.md`
Backlog: `.claude/backlog-product-review.md`

## Credibility Fixes

- [x] `[agent]` Fix CORS — env-gated `ALLOWED_ORIGINS`, defaults to `localhost:3000`
- [x] `[agent]` Remove default password fallbacks — 8 app code locations + 3 docker-compose + OAUTH_SIGNING_KEY through SecretManager
- [x] `[agent]` Fix broken links and stale counts — 8+ links, ADR counts, CLI README tools (5→12) and commands (9→30)
- [x] `[agent]` Pipeline cleanup — deleted `publish-docs.yml`, `.venv/` already gitignored
- [x] `[agent]` Pin dev AGE image to PG17 (upstream :latest advanced to PG18)
- [x] `[agent]` Add migration runner retry loop for postgres startup race
- [ ] `[pair]` Stub honesty — vocab manager 4 silent no-ops, pruning 2 fake AI stubs. Decide: implement or `NotImplementedError`.
- [ ] `[human]` Triage known bugs — graph annealing job failures, FUSE truncation (#307)

## Onboarding

- [ ] `[pair]` Agent onboarding guide — dedicated file linked from README. Sections: understand, pre-flight, install (with "ask the user" callouts), first use, connect clients, verify, troubleshoot.
- [ ] `[pair]` Developer quick-start with sample docs — bundle 3-5 docs, walkthrough from init to seeing results in web UI
- [ ] `[human]` Test standalone install on a fresh machine — note friction points
- [ ] `[human]` Document production deployment — TLS flow, multi-machine setup, user management, Nomic embedding (no GPU needed)
- [ ] `[human]` License FAQ — explain ELv2 (platform) + MIT (CLI, FUSE) split

## README & API Reference

- [ ] `[agent]` Feature showcase — add screenshots of polarity explorer, block builder, embedding landscape, vocab chord diagram. Add cost guidance and minimum requirements.
- [ ] `[agent]` Regenerate OpenAPI spec from running FastAPI — current spec covers 64 of 163 endpoints
