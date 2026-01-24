# Documentation Overhaul - Cross-Session Tracking

**ADR-087 Implementation**

After months of architectural work, we have a functional platform. Time to consolidate.

---

## Audiences (from ADR-087)

| Audience | Needs | Format |
|----------|-------|--------|
| Builder pair (us) | Shared state, coherency | ADRs, .claude/, ways |
| Operators | Deploy, configure, maintain | Runbooks, config reference |
| Users | Work with knowledge system | Task-oriented guides |
| Developers | Extend, integrate | Architecture, API reference |
| AI agents | Autonomous operation | Structured, self-describing |
| Non-technical | Conceptual understanding | Plain language, no jargon |

---

## Phase 1: Concepts (Non-Technical Foundation) ✅

Create `docs/concepts/`

- [x] README.md - The 30-second explanation
  - "You give it documents. It finds the ideas, connects them, and remembers what contradicts what."
- [x] how-it-works.md - Conceptual model without code
  - Ingestion → Extraction → Connection → Grounding
  - No mention of embeddings, vectors, LLMs as implementation
- [x] glossary.md - Terms in plain language
  - Concept, Relationship, Source, Grounding, Ontology, Provenance

### Feature Inventory (plain language)

What you can **do**:
- Feed it documents (text, PDFs, markdown)
- It extracts the ideas automatically
- It connects ideas that relate
- It finds where sources disagree
- Search by meaning, not keywords
- Trace any idea back to its source
- See confidence levels (well-supported vs contested)
- Explore visually in the browser
- Query through AI assistants (MCP)

What it **remembers**:
- Concepts (the ideas themselves)
- Relationships (implies, supports, contradicts)
- Sources (where ideas came from)
- Grounding (how well-supported)
- Provenance (the chain of evidence)

---

## Phase 2: Operating (Unblock Operators) ✅

Create `docs/operating/`

- [x] README.md - Deployment overview (which path for which situation)
- [x] quick-start.md - Minimal path to running system
  - Clone, init, start - 3 commands to working system
- [x] production.md - Full production deployment
  - Headless init parameters
  - GHCR vs local builds
  - GPU modes
  - SSL/HTTPS with Let's Encrypt
- [x] configuration.md - All the knobs
  - .env variables
  - .operator.conf
  - WEB_HOSTNAME and OAuth
- [x] upgrading.md - Version upgrades
  - `./operator.sh upgrade` workflow
  - Rollback procedures
- [x] backup-restore.md - Data protection
- [x] troubleshooting.md - Common issues and fixes

---

## Phase 3: Using (Enable Users) ✅

Create `docs/using/`

- [x] README.md - Getting started as a user
- [x] ingesting.md - Feeding documents to the system
  - CLI: `kg ingest file.pdf`
  - API: POST /ingest
  - What happens during ingestion
- [x] exploring.md - Finding and connecting ideas
  - Web interface walkthrough
  - CLI search commands
- [x] querying.md - Asking questions
  - Via kg CLI
  - Via MCP in Claude/other assistants
  - Via API
- [x] understanding-grounding.md - Trust and contradiction
  - What grounding scores mean
  - How contradictions are tracked
  - Epistemic status of relationships

---

## Phase 4: Reference (Complete the Picture) ✅

Auto-generated reference docs already exist in `docs/reference/`:

- [x] api/ - REST API endpoints (auto-generated from OpenAPI)
- [x] cli/ - kg CLI commands (auto-generated from source)
- [x] mcp/ - MCP server tools (auto-generated from source)
- [x] config.md - Full configuration reference

---

## Phase 5: The Real Point (Future/Research)

This isn't just a knowledge graph. It's infrastructure for AI agents that can
reason about what they know and how well they know it.

Most "AI memory" is vector search. This tracks grounding, contradiction, and
provenance - the foundation for agents that reason epistemically, not just retrieve.

**Current state (Jan 2026):** MCP integration works - agents can query the graph.
Claude Code hooks could inject context at tool boundaries.

**Future vision:** Agent-level integration where the graph shapes reasoning
continuously, not just when explicitly queried. No open source or free
models currently support this architecture yet. This is ready when they are.

Create `docs/integrating/` (or extend `docs/using/`)

- [ ] agent-memory.md - Using as persistent agent memory
  - MCP setup for Claude Code / other agents
  - Automatic recall patterns
  - Memorization workflows
- [ ] hooks-integration.md - Claude Code hooks for continuous memory
  - Pre-tool hooks for recall
  - Post-conversation hooks for memorization
  - Concept-triggered guidance (like ways, but from the graph)
- [ ] epistemic-model.md - How agents should reason about grounding
  - When to trust high-grounding concepts
  - How to handle contradictions
  - Updating beliefs based on new evidence

### Future: Concept-Triggered Ways

Instead of keyword-matching ways:
```
[semantic match: "container naming conventions"]
→ inject context from knowledge graph
→ include grounding score and sources
```

This makes the graph part of how agents think, not just something they query.

---

## Implementation Testing (from todo-operator-deployment-modes.md)

Carried forward - testing matrix for deployment combinations:

| Mode | Image Source | GPU | SSL | Status |
|------|-------------|-----|-----|--------|
| Headless | GHCR | nvidia | Yes | ✅ Working |
| Headless | GHCR | nvidia | No | ❓ Not tested |
| Headless | GHCR | cpu | No | ❓ Not tested |
| Headless | Local | nvidia | No | ❓ Not tested |
| Interactive | GHCR | nvidia | Yes | ✅ Working (0.6.0-dev.28) |
| Interactive | Local | cpu | No | ❓ Not tested |
| Interactive | Local | nvidia | No | ❓ Not tested |
| Dev mode | Local | cpu | No | ❓ Not tested |

Future automation:
- [ ] Add `--ssl` / `--domain` parameter to headless-init
- [ ] Support multiple DNS providers (not just Porkbun)
- [ ] Self-signed cert option for air-gapped setups

---

## Updates to Existing Docs

- [ ] operator/README.md - Add headless section, link to docs/operating/
- [ ] CLAUDE.md - Update quick start, link to docs/
- [ ] ADR-086 - Already captured in operating/production.md

---

## Directory Structure Target

```
docs/
├── concepts/
│   ├── README.md
│   ├── how-it-works.md
│   └── glossary.md
├── using/
│   ├── README.md
│   ├── ingesting.md
│   ├── exploring.md
│   ├── querying.md
│   └── understanding-grounding.md
├── operating/
│   ├── README.md
│   ├── quick-start.md
│   ├── production.md
│   ├── configuration.md
│   ├── upgrading.md
│   ├── backup-restore.md
│   └── troubleshooting.md
├── architecture/
│   ├── ARCHITECTURE_DECISIONS.md
│   ├── ADR-*.md
│   └── overview.md
└── reference/
    ├── api.md
    ├── cli.md
    ├── mcp.md
    └── config.md
```

---

## Session Log

### 2026-01-18 (final)
- **PR #207 merged to main** - Phases 1-3 complete
- 15 new documentation files (2,718 lines added)
- CLI command fixes verified and merged

### 2026-01-18 (continued)
- Created docs/concepts/ (Phase 1): README, how-it-works, glossary
- Created docs/operating/ (Phase 2): README, quick-start, production, configuration, troubleshooting, upgrading, backup-restore
- Created docs/using/ (Phase 3): README, ingesting, exploring, querying, understanding-grounding
- Reference docs already existed (auto-generated)
- Ran code-reviewer subagent on PR #207
- Fixed CLI command syntax (kg concept → kg search, kg auth → kg)
- Branch: docs/documentation-overhaul
- PR: https://github.com/aaronsb/knowledge-graph-system/pull/207

### 2026-01-18
- Created ADR-087 (Documentation Strategy)
- Defined six audiences
- Created non-technical feature inventory
- Revised this tracking file to match ADR phases
- Merged release → main (10 commits including OAuth fix)
