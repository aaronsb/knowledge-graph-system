# Product Review: State of the System

**Date:** 2026-02-07
**Version:** 0.9.3 (74 commits since v0.9.0 tag)
**Goal:** Assess readiness for public adoption and define roadmap

---

## Review Summary

Four-role assessment: Product Owner (adoption), Tech Lead (quality), Doc Lead (documentation), Architect (stability). Each independently researched the codebase and reported findings.

**Overall assessment:** The system has genuine technical differentiation (epistemic scoring, contradiction detection, FUSE filesystem, 13-tool MCP server) and a polished installation story. The core graph engine is well-tested and architecturally sound. The blockers to public adoption are not features — they're **documentation accuracy, onboarding gaps, and a few security hygiene issues** that would undermine credibility on first contact.

**Features the review initially underweighted:**
- TLS certificate flow: self-signed, domain/API-signed, and bring-your-own with custom domain support for remote deployments (not just localhost)
- Local embedding via Nomic — runs on any reasonable hardware without GPU requirements
- Multi-provider reasoning: Anthropic, OpenAI, and Ollama-compatible endpoints
- Known issues exist in subsystems (e.g., graph annealing job execution) that need tracking alongside the roadmap work

---

## Scorecard

| Area | Rating | Key Finding |
|------|--------|-------------|
| Core engine | Strong | 1164 tests pass, 0 fail. GraphProgram DSL has 109 validation tests. |
| Installation | Strong | Three clean entry points (platform, client, npm). Headless mode works. |
| API surface | Large, stable | 163 endpoints across 25 route files. Core routes well-tested. |
| Python code quality | Strong | 93.2% docstring coverage, clean Cypher linting, no slop. |
| TypeScript code quality | Weak | 40.8% docstring coverage. Web frontend largely undocumented. |
| Documentation accuracy | Poor | 8+ broken links, stale counts, wrong tool names in CLI README. |
| Documentation completeness | Mixed | Good for architecture/ADRs, gaps in user guides and API reference. |
| Security posture | Needs work | CORS wildcard with credentials, default passwords in 7 locations. |
| Onboarding | Gap | No "first ingest" tutorial, no sample data, empty graph cold start. |
| ADR discipline | Excellent | 96 ADRs, but 45 still "Proposed" despite being implemented. |
| Build/publish pipeline | Solid | Version-consistent (0.9.3), multi-target, dry-run support. |
| Test coverage (statement) | Moderate | 46% overall. Core logic high, workers/services low. |

---

## Roadmap: What Blocks Adoption

Tasks are marked with who should do them:
- **`[agent]`** — Claude can handle autonomously
- **`[human]`** — Requires human judgment, access, or testing on separate machines
- **`[pair]`** — Best done together (human decides, agent executes)

### Credibility Fixes (Do Before Telling Anyone)

Things that would undermine trust on first contact. Small effort, high signal.

- [ ] `[agent]` **Fix CORS** — replace `allow_origins=["*"]` with env-gated `ALLOWED_ORIGINS`, default to `localhost:3000` in dev
- [ ] `[agent]` **Remove default password fallbacks** — 7 locations hardcode `"password"` as fallback; fail-closed if `POSTGRES_PASSWORD` unset
- [ ] `[agent]` **Fix broken links and stale counts** — 8 broken links in docs/README.md, 1 in root README, wrong ADR counts (88→96, 67→96), wrong MCP tool names/counts in CLI README, stale CLI command table
- [ ] `[agent]` **Pipeline cleanup** — delete always-failing `publish-docs.yml`, remove `docs/.venv/` from repo
- [ ] `[pair]` **Stub honesty** — vocabulary manager has 4 functions that silently return success without doing anything; pruning has 2 fake AI call stubs. Decide: implement or `NotImplementedError`.
- [ ] `[human]` **Triage known bugs** — graph annealing job failures, any other broken subsystems

### Onboarding (Make Evaluation Possible)

Four personas, four paths. Not all need to be done simultaneously — prioritize by expected traffic.

| Persona | Entry Point | What They Need |
|---------|-------------|----------------|
| **Agent-assisted** | Points Claude Code at repo | Machine-readable guide: orient → install → first use → connect clients → verify. Conversation script, not just commands. |
| **Developer/tinkerer** | `git clone` → `operator.sh init` | 5-minute path to first ingest with sample docs and an API key (OpenAI/Anthropic — lowest friction) |
| **Standalone deployer** | `curl \| bash` installer | Clean install without repo clone; client-manager.sh for CLI/FUSE on other machines |
| **Production operator** | Dedicated server setup | TLS certs, multi-machine, user management, RBAC, embedding config |

- [ ] `[pair]` **Agent onboarding guide** — dedicated file linked from README. Sections: understand, pre-flight, install (with "ask the user" callouts), first use, connect clients, verify, troubleshoot.
- [ ] `[pair]` **Developer quick-start with sample docs** — bundle 3-5 docs, walkthrough from init to seeing results in web UI
- [ ] `[human]` **Test standalone install** on a fresh machine — note friction points
- [ ] `[human]` **Document production deployment** — TLS flow, multi-machine setup, user management, Nomic embedding (no GPU needed)
- [ ] `[human]` **License FAQ** — explain ELv2 (platform) + MIT (CLI, FUSE) split

### README & API Reference

- [ ] `[agent]` **Feature showcase** — add screenshots of polarity explorer, block builder, embedding landscape, vocab chord diagram. Add cost guidance and minimum requirements.
- [ ] `[agent]` **Regenerate OpenAPI spec** from running FastAPI — current spec covers 64 of 163 endpoints

### Backlog

Remaining findings from this review are tracked in `.claude/backlog-product-review.md` for future sessions.

---

## Key Metrics Snapshot

```
Tests:           1164 passed, 23 skipped, 0 failed
Statement cov:   46% (11,370 / 21,193 statements missed)
Docstrings:      Python 93.2% | TypeScript 40.8% | Rust 80.0%
Tech debt:       45 markers (41 TODO, 1 HACK, 3 XXX), avg age 79 days
ADRs:            96 total (33 Accepted, 45 Proposed, 16 Draft, 2 Superseded)
API endpoints:   163 across 25 route files
Version:         0.9.3 (all components aligned)
OpenAPI spec:    64 of 163 endpoints documented (39%)
```

---

## Competitive Differentiators (What to Lead With)

1. **Grounding scores** — continuous -1.0 to +1.0 reliability scoring, not binary
2. **Contradiction detection** — native, mathematical, per-relationship
3. **FUSE filesystem** — `mkdir` as semantic query, Obsidian integration (unique — no competitor has this)
4. **13-tool MCP server** — uncommonly complete agent integration
5. **Air-gapped operation** — full functionality with local Ollama reasoning + Nomic local embeddings
6. **Epistemic status classification** — per-relationship-type knowledge validation
7. **GraphProgram DSL** — composable server-side graph queries with set algebra
8. **TLS certificate management** — self-signed, domain/API-signed, BYO with custom domain support for remote deployments
9. **Multi-provider flexibility** — Anthropic, OpenAI, Ollama-compatible reasoning; local Nomic embedding runs on any reasonable hardware

---

*Review conducted by: Product Owner, Tech Lead, Doc Lead, Architect (Claude team agents)*
*Synthesized by: Team Lead*
