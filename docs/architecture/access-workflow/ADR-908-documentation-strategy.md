---
status: Accepted
date: 2026-06-15
deciders:
  - aaronsb
  - claude
related:
  - ADR-900
  - ADR-211
  - ADR-117
amends: 2026-01-18 audience-framework decision (see Amendment below)
---

# ADR-908: Documentation Strategy and Audience Framework

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
*mode* — the reader's epistemic posture — and serves one reader job:

| Mode | The page answers |
|------|------------------|
| Tutorial | "Walk me through my first success." |
| How-to | "I have a goal; give me the steps." |
| Reference | "State the facts I look up." |
| Explanation | "Help me understand why." |

These four are not a list to extend — they are a closed 2×2 derived from two
orthogonal axes (*action* vs *cognition*, *acquisition* vs *application*).
Tutorial and How-to are action; Reference and Explanation are cognition.
Tutorial and Reference serve acquisition-adjacent and lookup needs; How-to and
Explanation serve the working reader. There is no fifth quadrant, because there
is no third axis. Mode is therefore the *highest* level of the catalog: it
classifies every page by reader posture alone, independent of subject.

**Folders are reader destinations, not modes.** The default site layout maps
one mode to one folder — `get-started/` (tutorial), `how-to/`, `reference/`,
`explanation/` — but a folder may hold several modes when it serves a coherent
*audience*. `self-host/` is exactly that: the operator's home, holding a
tutorial (`quick-start`), how-tos (`upgrading`, `tls`, `backup-restore`),
reference (`configuration`), and explanation (`security`, `production`).
"Operations" is an **audience facet**, not a mode — it answers *who reads this*
and *what subsystem* (deployment, networking, backup), which the catalog already
captures on the **domain** axis (`infra`, with the security model under `auth`).
It does not belong in the mode slot. Architecture/ADRs likewise remain a
separate tree (the builder-pair audience) reachable from their index.

> **Correction (2026-06-16).** The 2026-06-15 amendment first defined a fifth
> mode, `operations` (letter `O`), homed in `self-host/` — "Diátaxis-adjacent."
> That was a category error: it placed an *audience* label on the *mode* axis,
> which is reserved for reader posture. Operations content is never outside the
> four modes (it decomposes into a tutorial, how-tos, reference, and
> explanation), and its distinct-job-ness lives on the **domain** axis, which
> the `self-host/` pages already encode correctly (`infra`, plus `auth` for the
> security model). The mode vocabulary is now the canonical four (`T/H/R/E`);
> `O` is retired. The same correction reshapes the catalog id from
> `<digit>.<LETTER>.<serial>` to the octet-style `DD.NNN.P` defined below, so
> that mode (the mutable part) trails the identity instead of sitting inside it.
> **Migration:** re-tag the 11 `self-host/` pages to their true mode, drop
> `operations` from `doclint.py`'s `MODE_LETTER`, renumber every catalog id to
> `DD.NNN.P` with domain-scoped serials, and update the four reference-page
> generators (`cli`, `mcp`, `fuse`, `schema`) to emit the new ids. The
> `self-host/` folder and its nav are unaffected — it remains a multi-mode,
> audience-coherent destination.

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
id: 04.001.H         # <DD domain band>.<NNN serial>.<diátaxis pole>
domain: auth          # ADR-900 domain key — the shared "first octet"
mode: how-to          # Diátaxis: tutorial | how-to | reference | explanation
---
```

The id is a fixed-width, octet-style number — `DD.NNN.P`:

- **domain band (`DD`)** — two digits, the ADR-900 band (`01` infra · `02` db ·
  `03` ingest · `04` auth · `05` query · `06` vocab · `07` ui · `08` ai ·
  `09` meta). A doc and the ADRs that govern it share the band, so "everything
  about auth" spans both trees.
- **serial (`NNN`)** — a three-digit sequence **scoped to the domain**, not to
  `(domain, mode)`. Assigned once at creation and never reused. `DD.NNN`
  together is the page's immutable identity.
- **pole (`P`)** — the Diátaxis mode as a single trailing letter
  (`T`/`H`/`R`/`E`). It is a *classifier*, not part of the identity; it must
  agree with the `mode:` field, and the linter enforces that.

**Why the pole trails and the serial is domain-scoped.** The original scheme was
`<digit>.<LETTER>.<serial>` with the serial scoped to `(domain, mode)` — which
baked a *mutable* attribute into the *middle of the identity*. Re-classifying a
page then forced its part number to change: the 2026-06-16 correction below
re-shelved eleven `self-host/` pages and, under the old scheme, every one of
their ids would have churned. A handle that mutates when you re-shelve the part
is not a handle. Under `DD.NNN.P` the identity is `DD.NNN`; re-classifying flips
only the trailing pole (`…​.H` → `…​.E`) and the number is untouched. The pole
stays visible so the id self-documents, but it is a *view* of the `mode:` field,
never the key. Domain-scoped serials mean the linter can treat any id collision
as a real clash (`check_duplicate_ids`), since two pages in a domain can never
legitimately share a serial.

These keys are **management metadata, not display**. mkdocs ignores unknown
frontmatter keys, so the catalog is stripped from GitHub Pages — readers never
see `04.001.H`, maintainers and the linter do. Diátaxis stays a *principle* for
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

### Upstream: generalized into the agent-ways framework

This catalog — the typed doc+ADR graph, the `DD.NNN.P` id, the `doc`/`doclint`
tooling — was generalized out of this repo into the agent-ways framework as its
canonical *documentation model* (the framework's own `ADR-302`, unrelated to this
project's `ADR-302`). This repo is that model's **reference implementation**, and
`docs/scripts/{doc,doclint.py}` are **vendored copies** of the canonical tools
(copy-not-symlink, refreshed from canonical). That is why the vendored sources
cite `ADR-302` (the upstream model) and credit `ADR-908`/`ADR-900` (this repo's
local decisions) — the two numbers name two different things and both are correct.
The framework-side reference is prose only: do **not** add `ADR-302` to this ADR's
`related:` edges, since here that id resolves to the multimodal-ingestion ADR and
would be a false graph edge.

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

- ADR-211: Operator architecture (informs operating/ docs)
- ADR-117: Deployment topology (source for operating/production.md)
