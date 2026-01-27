---
status: Draft
date: 2026-01-17
deciders:
  - aaronsb
  - claude
---

# ADR-087: Documentation Strategy and Audience Framework

Status: Proposed
Date: 2026-01-18
Deciders: @aaronsb, @claude

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
