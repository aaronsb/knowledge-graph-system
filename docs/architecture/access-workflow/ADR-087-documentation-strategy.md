---
status: Accepted
date: 2026-06-15
deciders:
  - aaronsb
  - claude
related:
  - ADR-900
  - ADR-061
  - ADR-086
amends: 2026-01-18 audience-framework decision (see Amendment below)
---

# ADR-087: Documentation Strategy and Audience Framework

> **Status:** Accepted (amended 2026-06-15). The original 2026-01 decision —
> recorded below from "The Real Point" onward — framed documentation by
> *audience*. The amendment that follows supersedes the audience-based *folder
> layout* (§2) with a Diátaxis taxonomy and a documentation catalog, while
> keeping the original principles (§5). Read the amendment first; the original
> text is retained as the historical record.

## Amendment (2026-06-15): Diátaxis Taxonomy + Documentation Catalog

### What changed and why

The 2026-01 decision was directionally right: operators, users, developers, and
agents have different needs, and the old docs mixed them. But organizing the
*folder tree* by audience (`concepts/`, `using/`, `operating/`) made every
feature live in several places at once — an operator's TLS page and a user's TLS
page drift apart, and a contributor never knows which one to edit. Audience is a
real lens, but it is the wrong axis for the directory structure.

We adopt **Diátaxis** as the organizing taxonomy instead. Each page has one
*mode* and serves one reader job:

| Mode | Folder | The page answers |
|------|--------|------------------|
| Tutorial | `get-started/` | "Walk me through my first success." |
| How-to | `how-to/` | "I have a goal; give me the steps." |
| Reference | `reference/` | "State the facts I look up." |
| Explanation | `explanation/` | "Help me understand why." |
| Operations | `self-host/` | "I run the platform; deploy and keep it healthy." |

`self-host/` is a fifth, operations-flavored section — Diátaxis-adjacent rather
than canonical — because running the appliance is a distinct, large reader job.
Architecture/ADRs remain a separate tree (the builder-pair audience) reachable
from their index.

The consolidation that applied this taxonomy is recorded in
`specs/documentation-consolidation-spec.md` (an intermediary spec, not an ADR):
**154 hand-written pages collapsed to 47**, with reference material generated
from code and an explicit `mkdocs.yml` nav.

### The documentation catalog (frontmatter IDs)

Diátaxis tells a *reader* where to look. It does not give the *maintainers* a
stable handle on each page — a way to say "this is the auth reference page" that
survives renames, moves, and rewrites. For that, every page carries a catalog ID
in its frontmatter, the way an IKEA part or an automotive component carries a
part number that is invisible on the showroom floor:

```yaml
---
id: 4.R.01          # <domain-digit>.<MODE-letter>.<serial>
domain: auth         # ADR-900 domain key — the shared "first octet"
mode: reference      # Diátaxis: tutorial | how-to | reference | explanation | operations
---
```

- **domain** reuses the ADR-900 domain bands (1 infra · 2 db · 3 ingest ·
  4 auth · 5 query · 6 vocab · 7 ui · 8 ai · 9 meta). A doc and the ADRs that
  govern it share the leading digit, so "everything about auth" spans both trees.
- **mode** is the Diátaxis mode (letter `T` / `H` / `R` / `E` / `O` in the ID).
- **serial** is a 2-digit sequence within `(domain, mode)`.

These keys are **management metadata, not display**. mkdocs ignores unknown
frontmatter keys, so the catalog is stripped from GitHub Pages — readers never
see `4.R.01`, maintainers and the linter do. Diátaxis stays a *principle* for
readers; the catalog is the *index* for maintainers. The two are facets of the
same page, not competing schemes.

Generated reference pages (`reference/{cli,mcp,fuse,schema}.md`) are overwritten
by their generators on every docs build, so their frontmatter is **emitted by the
generator**, not hand-injected — otherwise the next regen wipes it.

### Graph linting

The catalog is enforced by `docs/scripts/doclint.py`, which extends the ADR
linter's approach (it reuses `adr.yaml`'s domain config) and treats docs and ADRs
as one **decision graph**: nodes are records, edges are `related`/`supersedes`
references. It lints for:

1. **Frontmatter validity** — every doc has a well-formed `id`/`domain`/`mode`;
   the ID's domain digit and mode letter agree with the `domain`/`mode` fields.
2. **Reference graph** — every `related`/`supersedes` target resolves (no
   dangling references), no orphan pages outside the nav, no supersede cycles.
3. **Coverage matrix** — which `(domain, mode)` cells are populated, surfacing
   gaps (e.g. an auth subsystem with reference but no how-to).

Linting is **enforced on `docs/`** (errors fail CI) and **warns on ADRs** until
the ADR frontmatter sweep lands (tracked separately as the #520 fast-follow).

### Numbering freeze

Per ADR-900, legacy ADRs (1–99) are frozen at their numbers — we do not
renumber. The doc catalog's domain digit is keyed to the *current* domain bands;
legacy ADRs resolve their domain by folder, so the shared-octet relationship
holds without touching their numbers.

### What this amendment supersedes

- **§2 "Organize by Audience, Not Feature"** and its `concepts/ using/
  operating/` folder tree are superseded by the Diátaxis taxonomy above.
- **§5 "Documentation Principles"** stands unchanged — progressive disclosure,
  task-orientation, no "astral plane" language, currency. The voice guide
  (`docs/contributing/voice.md`) operationalizes these.
- The audience analysis (§1, §3, §4) stands as *context*: it explains *why* the
  modes exist (who each mode serves), even though it no longer dictates folders.

---

## The Real Point

This isn't just a knowledge graph. It's infrastructure for AI agents that can reason about what they know and how well they know it.

Most "AI memory" is vector search. This system tracks **grounding** (how well-supported), **contradiction** (where sources disagree), and **provenance** (where ideas came from). That's the foundation for agents that don't just retrieve - they *reason epistemically*.

Current integration: MCP tools, query-driven.
Future integration: agent-level, where the graph shapes cognition continuously.

No open models support that architecture yet. This is ready when they are.

---

## Context

After several months of focused architectural work and research, we have a mostly functional platform. The knowledge graph system works - you can ingest documents, extract concepts, explore relationships, and query via CLI, API, or web interface.

However, the documentation hasn't kept pace. It's scattered, internally-focused, and assumes familiarity with implementation details. A documentation coherency review revealed:

- No deployment guide for operators
- No user guide for working with the knowledge system
- No conceptual explanation for non-technical audiences
- Existing docs mix audiences (developer notes alongside user instructions)
- Features exist that aren't documented anywhere

This is a natural pause point to consolidate before continuing feature development.

## Decision

### 1. Document for Six Distinct Audiences

| Audience | What They Need | Primary Format |
|----------|----------------|----------------|
| **Builder Pair** (us) | Shared state, coherency, decision history | ADRs, `.claude/` tracking, ways |
| **Operators** | Deploy, configure, maintain, upgrade | Runbooks, config reference, troubleshooting |
| **Users** | Work with the knowledge system | Task-oriented guides, examples |
| **Developers** | Extend, integrate, contribute | Architecture docs, API reference, code patterns |
| **AI Agents** | Autonomous operation | Self-describing APIs, structured metadata |
| **Non-Technical** | Conceptual understanding | Plain-language explanations, no jargon |

### 2. Organize by Audience, Not Feature

```
docs/
├── concepts/              # What this is and why it matters
│   ├── README.md          # The 30-second explanation
│   ├── how-it-works.md    # Conceptual model (no code)
│   └── glossary.md        # Terms in plain language
│
├── using/                 # For users of the knowledge system
│   ├── README.md          # Getting started as a user
│   ├── ingesting.md       # Feeding documents to the system
│   ├── exploring.md       # Finding and connecting ideas
│   ├── querying.md        # Asking questions (CLI, API, MCP)
│   └── understanding-grounding.md  # Trust and contradiction
│
├── operating/             # For operators running the platform
│   ├── README.md          # Deployment overview
│   ├── quick-start.md     # Minimal path to running system
│   ├── production.md      # Full production deployment
│   ├── configuration.md   # All the knobs
│   ├── upgrading.md       # Version upgrades
│   ├── backup-restore.md  # Data protection
│   └── troubleshooting.md # When things break
│
├── architecture/          # For developers and the builder pair
│   ├── ARCHITECTURE_DECISIONS.md  # ADR index
│   ├── ADR-*.md           # Decision records
│   └── overview.md        # System architecture summary
│
└── reference/             # Technical reference (all audiences)
    ├── api.md             # REST API endpoints
    ├── cli.md             # kg CLI commands
    ├── mcp.md             # MCP server tools
    └── config.md          # Environment variables, .operator.conf
```

### 3. Feature Inventory (Non-Technical Perspective)

What can you **do** with this system?

| Capability | Plain Description |
|------------|-------------------|
| **Ingest documents** | Feed it text, PDFs, markdown. It reads and remembers. |
| **Extract ideas** | It finds the concepts in your documents automatically. |
| **Connect ideas** | It discovers how concepts relate - causes, supports, contradicts. |
| **Find contradictions** | When sources disagree, it notices and tracks both sides. |
| **Search by meaning** | Find concepts similar to what you're thinking, not just keyword matches. |
| **Trace sources** | Every idea links back to where it came from. |
| **Assess confidence** | Some ideas are well-supported, others contested. It knows the difference. |
| **Explore visually** | Web interface to browse and navigate the knowledge graph. |
| **Query conversationally** | Ask questions through Claude or other AI assistants (via MCP). |
| **Build on it** | REST API for custom integrations. |

What does it **remember**?

| Element | Plain Description |
|---------|-------------------|
| **Concepts** | The ideas themselves - things like "climate change causes migration" |
| **Relationships** | How ideas connect - implies, supports, contradicts, causes |
| **Sources** | The original text where each idea was found |
| **Grounding** | How well-supported each idea is across all sources |
| **Provenance** | The chain from document → chunk → extraction → concept |

### 4. The "You" Depends on Who You Are

The feature inventory above assumes a human user. But this system is equally - perhaps primarily - **agent infrastructure**.

| Audience | What this system is to them |
|----------|----------------------------|
| Human browsing | A tool for exploring connected ideas |
| Human querying | A way to ask questions with grounded answers |
| AI agent (query) | Persistent memory accessible via MCP |
| AI agent (integrated) | **Part of how the agent thinks** |

The integrated AI agent case is the most interesting. Consider:

- **Claude Code hooks** that automatically memorize decisions and recall relevant context
- **Concept-triggered ways** - instead of keyword matching, concepts from the graph inject guidance
- **Continuous integration memory** - every conversation builds the knowledge base, every new session inherits it

This isn't "documentation for AI to read" - it's the system becoming cognitive infrastructure. The MCP integration points this direction; hooks would make it automatic rather than query-driven.

This has documentation implications:
- The **AI agents** audience needs integration guides, not just API reference
- Examples should show agent workflows, not just human workflows
- The "concepts" documentation should explain the epistemic model clearly enough for an agent to reason about grounding and contradiction

### 5. Documentation Principles

1. **Progressive disclosure** - Overview first, details on demand
2. **Task-oriented** - Organize by what people want to accomplish
3. **No "astral plane" language** - Concrete explanations, not mystical AI terminology
4. **Audience-appropriate** - Don't mix operator details into user guides
5. **Maintain currency** - Outdated docs are worse than no docs

## Consequences

### Positive

- Clear entry points for each audience type
- Non-technical stakeholders can understand the value proposition
- Operators can deploy without reading source code
- Users can work with the system without understanding internals
- AI agents have structured, predictable documentation to parse
- Consolidation prevents documentation debt from growing

### Negative

- Significant effort to create initial documentation set
- Multiple docs may describe same feature from different angles (maintenance burden)
- Risk of docs diverging from implementation if not maintained

### Neutral

- Existing ADRs remain in `docs/architecture/` - they serve the builder pair well
- CLAUDE.md continues as project entry point, linking to appropriate docs
- `.claude/` tracking files continue for cross-session work

## Alternatives Considered

### Feature-organized documentation
```
docs/
├── ingestion/
├── extraction/
├── querying/
└── deployment/
```

Rejected: Mixes audiences. An operator reading "deployment" doesn't need extraction algorithm details.

### Single comprehensive README
Everything in one document with sections.

Rejected: Doesn't scale. Already seeing this problem with operator/README.md becoming outdated.

### Wiki-style documentation
Unstructured pages with cross-links.

Rejected: Hard to maintain coherency. No clear entry points per audience.

## Implementation Plan

Phase 1: **Concepts** (non-technical foundation)
- Write the 30-second explanation
- Document the conceptual model without code
- Create plain-language glossary

Phase 2: **Operating** (unblock operators)
- Deployment quick-start
- Production deployment guide
- Configuration reference

Phase 3: **Using** (enable users)
- Getting started guide
- Task-oriented workflows
- Understanding grounding/confidence

Phase 4: **Reference** (complete the picture)
- API documentation
- CLI command reference
- MCP tools documentation

## Related ADRs

- ADR-061: Operator architecture (informs operating/ docs)
- ADR-086: Deployment topology (source for operating/production.md)
