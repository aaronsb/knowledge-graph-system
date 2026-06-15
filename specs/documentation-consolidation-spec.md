# Documentation Consolidation Spec

Status: approved intermediary spec — not an ADR. Owner ratified 2026-06-15.

**Ratified decisions (§7):** cut depth 69.5% approved (Q0); "Knowledge Graph System" → "Kappa Graph" rename folded into this pass, kg-* identifiers unchanged (Q1, closes task #8); schema-reference generator built this pass (Q4); tracked `endpoint-security-audit-2026-05-28.md` is cut (untracked 06-09 audit untouched). Defaults for the rest: accuracy bugs fixed during the merge (Q5); `ARCHITECTURE_OVERVIEW`/`OPERATOR_ARCHITECTURE` dropped from docs/ nav (Q3); no URL redirects (Q2); unreferenced media pruned in-pass (Q6); research sources deleted only after confirming ADR rationale exists (Q7).

Scope: all 154 tracked markdown files under `docs/` except `docs/architecture/`, plus the three repo-root community files. Untracked paths are out of scope.
Branch: `docs/refactor-spec-and-rewrite`. Produced by a 21-agent audit (14 section readers + 5 cross-cutting sweeps), synthesized, then adversarially reviewed; the P0/P1 corrections from that review are folded in here.

---

## §1 Intent model & taxonomy

The project carries five parallel documentation hierarchies — `docs/features/`, `docs/manual/`, `docs/guides/`, `docs/operating/`, `docs/reference/` — and most topics appear in three or four of them at different depths. "How do I configure Ollama" lives in the manual, in a guide, and in two reference dumps. That duplication is the root of the bloat. The remedy is structural: collapse all five into one taxonomy organized by what the reader is doing when they open a page.

The organizing principle is Diátaxis, held to one rule: **one page, one mode, one reader job.** A page either teaches a beginner by doing (tutorial), walks a competent user through a goal (how-to), states a fact to look up (reference), or explains why a design is the way it is (explanation). A page that does two of these gets split or cut.

Diátaxis defines four modes. This project adds a fifth top-level section because self-hosting is a first-class concern for an installable platform, not a how-to sub-task — the same choice Supabase makes. The taxonomy is five sections mapped to four personas:

- **Get Started** (tutorial) — the new-user persona, learning by doing.
- **How-To** (how-to) — any persona with a specific goal; mostly integrator and new-user.
- **Self-Host** (how-to, operator register) — the operator-deployer persona.
- **Explanation** (explanation) — any persona who needs the "why"; mostly contributor and evaluator.
- **Reference** (reference, mostly generated) — the integrator and contributor looking up a fact.

Two cross-cutting decisions follow. Reference whose ground truth lives in code is generated, not hand-written: CLI flags, MCP tool schemas, REST endpoints, the FUSE Python API. Content whose ground truth is a point in time leaves the published docs: audit snapshots, completed migration checklists, research dumps, session journals. Those belong in an ADR, a GitHub issue, or commit history, where the friction of writing them is the point. A docs page that absorbs that pressure stops being documentation.

The test for whether a page belongs on the published site: a user opens it during active work or active learning. A page only its developers would open is not documentation.

---

## §2 Target structure + mkdocs nav skeleton

The tree collapses to five content sections plus a home page and a contributor voice guide. The nav becomes **explicit** (the `awesome-pages` plugin is removed) because the structure now carries meaning that directory order should not override.

```yaml
nav:
  - Home: index.md

  - Get Started:
      - "What and Why": get-started/what-and-why.md
      - "Your First Graph": get-started/first-graph.md
      - "Your First Query": get-started/first-query.md
      - "Connect via MCP": get-started/mcp-quickstart.md
      - "Mining a Git Repo": get-started/github-history.md

  - How-To:
      - "Ingest Documents": how-to/ingest.md
      - "Explore and Query": how-to/query.md
      - "Filter by Epistemic Status": how-to/epistemic-status.md
      - "Analyze a Polarity Axis": how-to/polarity-axis.md
      - "Use the FUSE Drive": how-to/fuse.md
      - "Configure AI Providers": how-to/ai-providers.md
      - "Configure Embeddings": how-to/embeddings.md
      - "Compare Extraction Quality": how-to/extraction-quality.md
      - "Consolidate Vocabulary": how-to/vocabulary.md

  - Self-Host:
      - "Quick Start": self-host/quick-start.md
      - "Production Deployment": self-host/production.md
      - "Configuration Reference": self-host/configuration.md
      - "Dedicated IP (macvlan)": self-host/macvlan.md
      - "TLS and Certificates": self-host/tls.md
      - "Security and Access": self-host/security.md
      - "Backup and Restore": self-host/backup-restore.md
      - "Scheduled Jobs": self-host/scheduled-jobs.md
      - "Upgrading": self-host/upgrading.md
      - "Troubleshooting": self-host/troubleshooting.md

  - Explanation:
      - "How It Works": explanation/how-it-works.md
      - "Computed Evidence over Asserted Truth": explanation/computed-evidence.md
      - "Grounding and Epistemic Confidence": explanation/grounding.md
      - "Recursive Upsert": explanation/recursive-upsert.md
      - "Vocabulary Lifecycle": explanation/vocabulary-lifecycle.md
      - "Storage and Freshness": explanation/storage-and-freshness.md
      - "Worker Lanes and Concurrency": explanation/worker-lanes.md
      - "Embedding Landscape": explanation/embedding-landscape.md
      - "GraphProgram DSL": explanation/graph-program.md

  - Reference:
      - "REST API": reference/api.md                  # Swagger UI over openapi.json (committed snapshot)
      - CLI: reference/cli.md                          # GENERATED (wireable today)
      - MCP Tools: reference/mcp.md                    # GENERATED (wireable today)
      - "MCP Session Context": reference/mcp-session-context.md
      - FUSE Driver: reference/fuse.md                 # GENERATED (generator exists, unwired in CI)
      - "Database Schema": reference/schema.md         # GENERATED — generator built this pass (§7 Q4)
      - "Cypher Patterns": reference/cypher.md
      - "GraphProgram Specification": reference/graph-program-spec.md
      - "GraphProgram Validation": reference/graph-program-validation.md
      - "GraphProgram Security": reference/graph-program-security.md
      - "Backup Object Format": reference/backup-object-spec.md

  - Contributing:
      - "Prose & Voice Guide": contributing/voice.md
      - "Docstring Coverage": contributing/docstring-coverage.md
      - "Test Suite": contributing/test-suite.md
```

Repo-root community files (`README.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`) stay at root as GitHub community-health files, outside the mkdocs nav. The `docs/media/` image tree and `docs/research/` non-markdown assets stay out of nav; their markdown is dispositioned in §3.

Target: **47 published markdown pages** (excluding `reference/schema.md` until its generator exists — §7 Q4), against 154 today.

### mkdocs migration steps (required for the explicit nav)

1. Remove the `awesome-pages` plugin from `mkdocs.yml` `plugins:` and from the `pip install` in `.github/workflows/docs.yml`.
2. Delete both tracked `.pages` files: `docs/.pages` and `docs/features/.pages`.
3. Add the explicit `nav:` block above to `mkdocs.yml`.
4. Keep `docs/media/` link integrity build-blocking: a surviving page that references a pruned image fails the mkdocs build (§7 Q6).

---

## §3 Disposition table

Every tracked markdown file under `docs/` (excluding `docs/architecture/`) plus the three root community files. Disposition is one of **keep** (move/rename only), **merge** (fold into a target, then delete source), **cut** (delete, no surviving content), **generate** (replace with build-time generation).

### Repo-root + docs landing

| Current path | Disp | Target |
|---|---|---|
| README.md | keep | README.md (root; fix stale ADR count + name sweep) |
| CONTRIBUTING.md | keep | CONTRIBUTING.md (root; name sweep) |
| CODE_OF_CONDUCT.md | keep | CODE_OF_CONDUCT.md (root) |
| docs/README.md | merge | index.md (becomes the mkdocs Home page) |
| docs/PRODUCT_REVIEW_2026-02-07.md | cut | point-in-time review snapshot |
| docs/.pages | cut | explicit nav replaces awesome-pages |

### docs/concepts/

| Current path | Disp | Target |
|---|---|---|
| docs/concepts/README.md | merge | explanation/how-it-works.md |
| docs/concepts/how-it-works.md | keep | explanation/how-it-works.md |
| docs/concepts/computed-evidence-over-asserted-truth.md | keep | explanation/computed-evidence.md |
| docs/concepts/glossary.md | merge | explanation/how-it-works.md (Key Terms) |

### docs/features/

| Current path | Disp | Target |
|---|---|---|
| docs/features/.pages | cut | explicit nav replaces it |
| docs/features/README.md | merge | get-started/what-and-why.md (interface-choice table) |
| docs/features/cli.md | cut | superseded by generated reference/cli.md |
| docs/features/mcp-server.md | merge | reference/mcp.md (patterns) + get-started/mcp-quickstart.md |
| docs/features/fuse-driver.md | merge | how-to/fuse.md |
| docs/features/rest-api.md | cut | superseded by reference/api.md |
| docs/features/web-workstation.md | merge | get-started/what-and-why.md (tour) + how-to/query.md |

### docs/language/

| Current path | Disp | Target |
|---|---|---|
| docs/language/README.md | merge | reference/graph-program-spec.md (intro) |
| docs/language/specification.md | keep | reference/graph-program-spec.md |
| docs/language/validation.md | keep | reference/graph-program-validation.md |
| docs/language/security.md | keep | reference/graph-program-security.md |
| docs/language/lifecycle.md | merge | explanation/graph-program.md (client matrix) |

### docs/guides/

| Current path | Disp | Target |
|---|---|---|
| docs/guides/README.md | cut | explicit nav replaces it |
| docs/guides/exploring.md | merge | how-to/query.md |
| docs/guides/querying.md | merge | how-to/query.md |
| docs/guides/SAVED_QUERIES.md | merge | how-to/query.md (Saving and Replaying) |
| docs/guides/understanding-grounding.md | merge | explanation/grounding.md |
| docs/guides/DEPLOYMENT.md | cut | stale pre-operator.sh; **salvage** Swarm/K8s note → self-host/production.md |
| docs/guides/CONTAINER_IMAGES.md | merge | self-host/production.md (image tags, release) |
| docs/guides/ASYNC-ARCHITECTURE.md | keep | explanation/worker-lanes.md |
| docs/guides/CLI_DEVELOPMENT.md | cut | narrow auth-internal; covered by ADR-054/029 + docstrings |
| docs/guides/CROSS_ONTOLOGY_LINKING.md | cut | experiment log; **salvage** best-practices → how-to/query.md |
| docs/guides/EPISTEMIC-STATUS-FILTERING.md | merge | how-to/epistemic-status.md (trim; generate param table) |
| docs/guides/FUSE_FILESYSTEM.md | keep | how-to/fuse.md |
| docs/guides/POLARITY_AXIS_ANALYSIS.md | merge | how-to/polarity-axis.md (trim) |
| docs/guides/QUERY_SAFETY_BASELINE.md | cut | resolved tech-debt ticket |
| docs/guides/SCHEDULED-JOBS.md | keep | self-host/scheduled-jobs.md |
| docs/guides/SEMANTIC_PATH_GRADIENTS.md | cut | never implemented (results TBD) |
| docs/guides/VOCABULARY_LIFECYCLE.md | keep | explanation/vocabulary-lifecycle.md |
| docs/guides/DOCSTRING_COVERAGE.md | keep | contributing/docstring-coverage.md |
| docs/guides/adr-045-046-migration-plan.md | cut | completed migration plan |
| docs/guides/adr-068-implementation-plan.md | cut | completed migration plan |
| docs/guides/adr-074-implementation-checklist.md | cut | completed checklist |

### docs/manual/

| Current path | Disp | Target |
|---|---|---|
| docs/manual/README.md | cut | explicit nav replaces it |
| docs/manual/00-introduction/01-WHAT_AND_WHY.md | merge | get-started/what-and-why.md |
| docs/manual/01-getting-started/02-CLI_USAGE.md | generate | reference/cli.md |
| docs/manual/01-getting-started/03-INGESTION.md | keep | how-to/ingest.md |
| docs/manual/02-configuration/01-AI_PROVIDERS.md | merge | how-to/ai-providers.md |
| docs/manual/02-configuration/02-EXTRACTION_CONFIGURATION.md | keep | how-to/ai-providers.md (fix restart contradiction) |
| docs/manual/02-configuration/03-EMBEDDING_CONFIGURATION.md | keep | how-to/embeddings.md |
| docs/manual/02-configuration/04-SWITCHING_EXTRACTION_PROVIDERS.md | merge | how-to/ai-providers.md |
| docs/manual/02-configuration/05-LOCAL_INFERENCE_IMPLEMENTATION.md | cut | internal roadmap, unbuilt |
| docs/manual/02-configuration/06-EXTRACTION_QUALITY_COMPARISON.md | keep | how-to/extraction-quality.md |
| docs/manual/03-integration/01-MCP_SETUP.md | keep | get-started/mcp-quickstart.md (regen tool table) |
| docs/manual/03-integration/02-VOCABULARY_CONSOLIDATION.md | merge | how-to/vocabulary.md (fix non-existent --auto flag) |
| docs/manual/04-security-and-access/01-AUTHENTICATION.md | keep | self-host/security.md (fix /users + config path) |
| docs/manual/04-security-and-access/02-RBAC.md | merge | self-host/security.md |
| docs/manual/04-security-and-access/03-SECURITY.md | merge | self-host/security.md |
| docs/manual/04-security-and-access/04-PASSWORD_RECOVERY.md | merge | self-host/security.md (Recovery) |
| docs/manual/05-maintenance/01-BACKUP_RESTORE.md | merge | self-host/backup-restore.md |
| docs/manual/05-maintenance/02-DATABASE_MIGRATIONS.md | merge | self-host/backup-restore.md (fix stale "version 001") |
| docs/manual/06-reference/01-SCHEMA_REFERENCE.md | generate | reference/schema.md (conditional — §7 Q4) |
| docs/manual/06-reference/02-USE_CASES.md | cut | stub: 1 real entry, 7 "Planned" placeholders |
| docs/manual/06-reference/03-EXAMPLES.md | keep | get-started/first-query.md |
| docs/manual/06-reference/04-github_project_history.md | keep | get-started/github-history.md |
| docs/manual/06-reference/05-CONCEPTS_AND_TERMINOLOGY.md | merge | explanation/how-it-works.md (fix `python cli.py`) |
| docs/manual/06-reference/06-CONCEPT.md | merge | explanation/how-it-works.md |
| docs/manual/06-reference/07-ENRICHMENT_JOURNEY.md | cut | blog-style experiment journal |
| docs/manual/06-reference/08-DISTRIBUTED_SHARDING_RESEARCH.md | cut | research note, single-shard system |
| docs/manual/06-reference/09-CYPHER_PATTERNS.md | merge | reference/cypher.md |
| docs/manual/06-reference/10-OPENCYPHER_QUERIES.md | merge | reference/cypher.md |
| docs/manual/06-reference/11-LLM_EDGE_DISCOVERY_FLOW.md | merge | explanation/recursive-upsert.md |

### docs/operating/ + docs/deployment/

| Current path | Disp | Target |
|---|---|---|
| docs/operating/README.md | cut | explicit nav replaces it |
| docs/operating/quick-start.md | keep | self-host/quick-start.md |
| docs/operating/production.md | keep | self-host/production.md (acme.sh → Traefik) |
| docs/operating/configuration.md | keep | self-host/configuration.md (Compose-selection for Traefik) |
| docs/operating/backup-restore.md | keep | self-host/backup-restore.md |
| docs/operating/client-tools.md | merge | self-host/quick-start.md + self-host/troubleshooting.md |
| docs/operating/macvlan-headless-install.md | keep | self-host/macvlan.md (align to Traefik TLS) |
| docs/operating/troubleshooting.md | keep | self-host/troubleshooting.md |
| docs/operating/upgrading.md | keep | self-host/upgrading.md |
| docs/deployment/macvlan-dedicated-ip.md | merge | self-host/macvlan.md |

### docs/reference/ (top-level + api + fuse)

| Current path | Disp | Target |
|---|---|---|
| docs/reference/README.md | cut | explicit nav replaces it |
| docs/reference/api/README.md | keep | reference/api.md (Swagger UI wrapper) |
| docs/reference/api/ADMIN-ENDPOINTS.md | cut | hand-keyed subset of openapi.json; drifts |
| docs/reference/openapi.json | keep | reference/openapi.json (committed snapshot; §7 Q4) |
| docs/reference/fuse/README.md | generate | reference/fuse.md (regen from `fuse/kg_fuse/` docstrings) |
| docs/reference/ARCHITECTURE_OVERVIEW.md | cut | overlaps architecture tree; remove from docs/ nav (§7 Q3) |
| docs/reference/BACKUP_OBJECT_SPEC.md | keep | reference/backup-object-spec.md |
| docs/reference/FRESHNESS-ARCHITECTURE.md | merge | explanation/storage-and-freshness.md |
| docs/reference/OPERATOR_ARCHITECTURE.md | cut | belongs in architecture tree (§7 Q3) |
| docs/reference/RECURSIVE_UPSERT_ARCHITECTURE.md | merge | explanation/recursive-upsert.md |
| docs/reference/STORAGE-ARCHITECTURE.md | merge | explanation/storage-and-freshness.md (fix graph_change_counter claim) |

### docs/reference/cli/ — generated cluster

| Current path | Disp | Target |
|---|---|---|
| docs/reference/cli/README.md | generate | reference/cli.md (`simple-doc-gen.mjs`) |
| docs/reference/cli/commands/*.md (26 files) | cut | strict subsets of generated output |
| docs/reference/cli/media/README.md | cut | empty placeholder |

### docs/reference/mcp/ — generated cluster

| Current path | Disp | Target |
|---|---|---|
| docs/reference/mcp/README.md | generate | reference/mcp.md (`generate-mcp-docs.mjs`) |
| docs/reference/mcp/tools/session_context.md | keep | reference/mcp-session-context.md (hand-written; relocate out of tools/) |
| docs/reference/mcp/tools/*.md (14 generated stubs) | cut | strict subsets of generated output |
| docs/reference/mcp/media/README.md | cut | empty placeholder |

### docs/research/

| Current path | Disp | Target |
|---|---|---|
| docs/research/epistemic-confidence.md | keep | explanation/grounding.md (merge w/ understanding-grounding) |
| docs/research/t-sne-viz.md | keep | explanation/embedding-landscape.md (trim library section) |
| docs/research/code-intelligence-platforms-comparison.md | cut | positioning essay |
| docs/research/emergent-visual-relationships.md | cut | finding in ADR-046 |
| docs/research/graph-object-platform-exploration.md | cut | design memo → ADR (§7 Q7) |
| docs/research/headless-install-analysis.md | cut | superseded by shipped install.sh |
| docs/research/llm-knowledge-extraction-research-2024-2025.md | cut | dated literature survey |
| docs/research/polarity-axis-findings.md | cut | unimplemented experiment |
| docs/research/polarity-axis-visualization.md | cut | proposal; feature shipped |
| docs/research/vision-testing/README.md | cut | pre-implementation scratch |
| docs/research/vision-testing/FINDINGS.md | cut | decision in ADR-057 (§7 Q7) |
| docs/research/vision-testing/EMBEDDING_COMPARISON_REPORT.md | cut | decision in ADR-057 (§7 Q7) |
| docs/research/vision-testing/RESEARCH_SUMMARY.md | cut | decision in ADR-057 (§7 Q7) |

### docs/testing/

| Current path | Disp | Target |
|---|---|---|
| docs/testing/TEST_COVERAGE.md | keep | contributing/test-suite.md (prune stale snapshot) |
| docs/testing/ADR-200-PHASE-3A-EXERCISE-REPORT.md | cut | session artifact |
| docs/testing/API_AUTH_AUDIT_RESULTS.md | cut | stale audit snapshot |
| docs/testing/API_AUTH_AUDIT_SUMMARY.md | cut | remediation complete |
| docs/testing/API_AUTH_TESTING_RESEARCH.md | cut | patterns now in test suite |
| docs/testing/INTEGRATION_TEST_NOTES.md | cut | session log |
| docs/testing/INTEGRATION_TEST_PLAN.md | cut | completed plan |
| docs/testing/SCHEMA_MIGRATION_TEST_REPORT.md | cut | merge-approval artifact |

### docs/security/ — owner sign-off required

| Current path | Disp | Target |
|---|---|---|
| docs/security/endpoint-security-audit-2026-05-28.md | **cut (pending owner sign-off)** | point-in-time audit snapshot, same class as testing/ audits. TRACKED, so in scope — but it sits beside the owner's separate security thread. Do not delete without confirmation. |
| docs/security/security-consistency-audit-2026-06-09.md | **out of scope** | UNTRACKED — belongs to the active security thread. Not touched by this effort. |

---

## §4 Consolidation metrics

| Measure | Before | After | Reduction |
|---|---|---|---|
| Tracked markdown under docs/ (excl. architecture) | 154 | 47 | 69.5% |
| Published nav pages | ~110 (awesome-pages auto) | 47 | ~57% |
| Parallel hierarchies for the same audience | 5 | 1 (five Diátaxis sections) | — |

The 107-file reduction breaks down as:

- **Generated-cluster collapse (~46):** 26 CLI command stubs + 14 MCP tool stubs + 2 media placeholders + 4 nav `README`/`.pages` indexes. These are generator output or replaced by explicit nav.
- **Historical artifacts (~31):** 7 testing files + 11 research markdown + 4 ADR implementation checklists + 1 product review + several stub/roadmap/never-built files. Zero ongoing reader value; rationale lives in ADRs and commit history.
- **Topic merges (~30):** concepts (4→1), features (6→0 standalone), AI-provider config (5→3), querying/exploring (4→1), security manual (4→1), backup (3→2), Cypher (2→1), GraphProgram (5→4), plus the storage/recursive-upsert/grounding explanation merges.

The owner's stated target was a 40–50% cut (land at 77–92 files). This spec lands at 47 — a 69.5% cut, deeper than asked. The depth is driven by the two structural facts above: nearly a third of the corpus is generator output or dead historical artifact. **This deeper cut is a scope decision for the owner to ratify (§7 Q0), not a settled number.**

---

## §5 Generated reference

Five reference clusters have their ground truth in code. The honest status of each generator differs, and the spec states it plainly rather than crediting work that does not exist yet.

| Reference page | Source of truth | Generator status | mkdocs slot |
|---|---|---|---|
| `reference/cli.md` | `cli/src/cli/commands.ts` (Commander registry) | **Exists, wireable today** (`cli/scripts/simple-doc-gen.mjs`) | `Reference > CLI` |
| `reference/mcp.md` | `cli/src/mcp-server.ts` tool array | **Exists, wireable today** (`cli/scripts/generate-mcp-docs.mjs`) | `Reference > MCP Tools` |
| `reference/fuse.md` | docstrings in `fuse/kg_fuse/*.py` | **Generator exists, unwired in CI** (`fuse/scripts/generate-fuse-docs.py`, `make docs-fuse`). Output quality depends on FUSE docstring coverage. | `Reference > FUSE Driver` |
| `reference/api.md` + `openapi.json` | FastAPI app | **Committed snapshot, manually refreshed.** CI cannot export without a running API; no build step today. | `Reference > REST API` (Swagger UI via `swagger-ui-tag`) |
| `reference/schema.md` | `schema/00_baseline.sql` + `schema/migrations/` | **Net-new — no generator exists.** Conditional on §7 Q4. | `Reference > Database Schema` (omit until built) |

So of the reference surface: **2 generators are wireable today (CLI, MCP), 1 exists but is unwired (FUSE), 1 is a committed snapshot (OpenAPI), and 1 is net-new work (schema).**

Required generator changes:

- The CLI/MCP/FUSE generators currently emit `…/README.md`. The target nav uses flat paths (`reference/cli.md`, `reference/mcp.md`, `reference/fuse.md`). **Retarget the generators' output filenames**, or the nav will not resolve.
- `reference/mcp-session-context.md` is the one hand-written file in the MCP cluster (cross-session memory, with a diagram the schema cannot produce). Relocate it out of `tools/` so the generator cannot clobber it.
- `ADMIN-ENDPOINTS.md` is deleted, not generated. Permission strings live in FastAPI route definitions and flow into `openapi.json`; a hand-keyed tier table drifts. If a permission-tiered view is wanted later, generate it by parsing `require_permission(...)` against the spec.

CI gap (`.github/workflows/docs.yml` runs `mkdocs gh-deploy` only — no generators). Add before the mkdocs step:

```yaml
- uses: actions/setup-node@v4
  with: { node-version: 22 }
- name: Generate CLI + MCP reference
  working-directory: cli
  run: npm install && npm run build
- name: Generate FUSE reference
  run: python3 fuse/scripts/generate-fuse-docs.py
```

`openapi.json` stays a committed snapshot until a `get_openapi()` export step is added. The schema generator is net-new (§7 Q4).

---

## §6 Prose & voice guide

Normative for the rewrite. Every surviving and merged page follows it. It ships as `contributing/voice.md`.

### Voice in one sentence

Plain, direct, declarative. State what the system does and what the reader should do. Stop there.

### Defaults

- **Declarative first.** State the fact, then the evidence or command.
- **Second person for how-to.** "Run `./operator.sh status`," not "the user should run."
- **Commands and real output over abstraction.** Show the command, show what it produces, trust the reader to extrapolate.
- **Depth is earned.** Go deep only where the reader needs it to act correctly or avoid a mistake. Otherwise link out.
- **Name gaps honestly.** "This is not implemented yet" is correct prose. Optimistic silence is not.

### Ban-list

**1. The antithesis cliché ("it's not X, it's Y").** Sounds like a manifesto, not documentation.

> Bad: "Unlike traditional retrieval systems that find similar text chunks, this system understands and preserves the *relationships* between ideas."
> Good: "The system stores concepts and the typed relationships between them — IMPLIES, CONTRADICTS, ENABLES. Queries traverse these edges; similarity search finds where to start."

The comparison earns one appearance, in the system introduction, where positioning is a real reader job. In a feature or reference page it is filler — cut it.

**2. Marketing superlatives.** Words that carry no information: powerful, seamless, robust, revolutionary, cutting-edge, simply, just, unique, innovative, game-changing.

> Bad: "Simply run `./operator.sh init` to get started."
> Good: "Run `./operator.sh init` to start."

If removing the adjective loses no meaning, remove it.

**3. Rhetorical-question setups and anthropomorphism.**

> Bad: "Think of them as smart maintenance workers that check if there's work to do."
> Good: "Scheduled jobs run on a timer and skip execution when there is no work to do."

**4. Hollow openers and transitions.** "In today's world," "It's important to note that," "Let's dive in," "At its heart is."

> Bad: "It's important to note that grounding is not the same as truth."
> Good: "Grounding measures evidence in your corpus, not universal truth."

**5. Exhaustive dumps.** A reference page that lists every option at equal weight, or an explanation that makes the same point from six angles, wastes the reader's time. One page, one reader job. To explain why a decision was made, link the ADR — do not reproduce its reasoning in a guide.

### Two registers, kept separate

- **Explanatory** (`explanation/`): longer sentences acceptable; first-person plural acceptable when the author's reasoning is the subject ("we do not encode truth"). The computed-evidence note is the model.
- **Operational** (`how-to/`, `self-host/`, `reference/`): imperative, short paragraphs, command first and explanation after. The async-architecture and querying guides are the models.

Do not mix the two registers in one page.

### Structure conventions

- Headers name what the section delivers ("How the lane manager claims jobs"), not the topic ("Overview," "Background").
- Code blocks are the primary vehicle for how-to; prose says what the code accomplishes and what to watch for, not a line-by-line narration.
- Tables for comparisons, flags, status codes — not for prose that happens to have two columns.
- The first sentence of a page names what the page covers, declaratively. Not a question, not a promise, not the title restated.

### Pre-commit checklist

- [ ] Does the first sentence name what this page covers?
- [ ] Is every adjective that survives removal-without-meaning-loss gone?
- [ ] Any "it's not X, it's Y" that should be one sentence or cut?
- [ ] Does every section serve one reader job?
- [ ] Could a section be replaced by a link to an ADR or research note?
- [ ] Is depth proportional to what the reader needs to act?
- [ ] Does each code block show a real command with real or representative output?

---

## §7 Open questions for the owner

**Q0 — Cut depth.** The spec lands at 47 files (69.5%), beyond the stated 40–50% target. Most of the extra depth is generator stubs and dead historical artifacts. Ratify the deeper cut, or name files to restore.

**Q1 — Project name.** README calls it "Kappa Graph — κ(G)"; CONTRIBUTING and most docs still say "Knowledge Graph System." The rewrite touches nearly every file. Confirm the target name and whether the rename lands in this pass or stays pending (task #8).

**Q2 — `docs/manual/` numeric-prefix URLs.** The target nav drops the `00-`/`01-` prefixes. Confirm no external links depend on the `docs/manual/.../NN-NAME.md` paths; if they do, add the mkdocs `redirects` plugin.

**Q3 — Explanation vs architecture.** `ARCHITECTURE_OVERVIEW.md` and `OPERATOR_ARCHITECTURE.md` are explanation-mode but reference ADRs heavily, and this effort's scope excludes `docs/architecture/`. The table cuts them from `docs/` nav on the assumption their home is the architecture tree. Confirm, or route them to `explanation/` instead.

**Q4 — Schema reference generator is net-new.** CLI/MCP/FUSE generators exist; a `reference/schema.md` generator parsing `schema/00_baseline.sql` + migrations does not. Decide: build it now (in scope), keep a hand-written page with a staleness warning, or drop schema reference from the public site. Until decided, the nav entry is omitted.

**Q5 — Accuracy fixes during the merge.** The audit found concrete bugs to fix while merging, not carry forward: `/admin/users` should be `/users`; CLI config path is `~/.config/kg/config.json` not `~/.kg/`; `operator.sh models list` does not exist; Node minimum is 20.12.0 not 18; `POST /auth/login` was removed (ADR-054); Postgres is 18 / AGE 1.7.0 not 16 / 1.5.0; the `--auto` vocab flag does not exist; the extraction-config restart contradiction. Confirm these are in-scope for the rewrite rather than separate issues.

**Q6 — `docs/media/` retention.** 30+ screenshots are referenced mainly by pages being cut or merged. A surviving page that links a pruned image fails the mkdocs build. Confirm which screenshots survive into `get-started/what-and-why.md` so unused assets prune safely in the same pass.

**Q7 — Research artifacts being cut.** The graph-object-platform exploration and vision-testing reports informed shipped decisions. The disposition assumes ADR-046/ADR-057 capture the rationale. Per the project's "verify feature state in code, not ADR prose" guidance, confirm those ADRs are sufficient before the sources are deleted.
