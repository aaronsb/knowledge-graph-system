---
status: Accepted
date: 2026-06-15
deciders:
  - aaronsb
  - claude
related:
  - ADR-087
---

# ADR-900: ADR Numbering Domain System

## Context

The first decision records were numbered sequentially — ADR-001 through ADR-038
— with no relationship between a number and the part of the system it touched.
That works until the catalog grows. By the time it held several dozen records,
the flat sequence told you nothing: ADR-031 and ADR-032 could be about embeddings
and OAuth, adjacent only by accident of authoring order.

We introduced a domain-based scheme to fix that. Each subsystem reserves a band
of 100 numbers, so the leading digits of an ADR number place it in the system at
a glance. The scheme is configured in `docs/architecture/adr.yaml` and enforced by
`docs/scripts/adr`, but it was never written down as a decision. This ADR records
it, and extends the same idea to the `docs/` tree.

## Decision

### 1. Domain bands (the "first octet")

Nine domains each reserve a 100-number band. The hundreds digit is the domain —
the "first octet" of the number. The authoritative definition lives in
`docs/architecture/adr.yaml`; this table mirrors it for the record:

| Digit | Domain  | Band    | Covers |
|-------|---------|---------|--------|
| 1     | infra   | 100–199 | Containers, deployment, backup, storage, networking |
| 2     | db      | 200–299 | Apache AGE, migrations, schema, PostgreSQL |
| 3     | ingest  | 300–399 | Content processing, jobs, extraction, deduplication |
| 4     | auth    | 400–499 | RBAC, OAuth, API keys, endpoint security |
| 5     | query   | 500–599 | Pathfinding, projections, diversity, search |
| 6     | vocab   | 600–699 | Relationships, grounding, categorization |
| 7     | ui      | 700–799 | CLI, web, FUSE, MCP, visualization |
| 8     | ai      | 800–899 | Providers, extraction, convergence, prompts |
| 9     | meta    | 900–999 | Documentation, workflow, access models, the ADR system itself |

A new ADR takes the next free number in its domain band: `adr new <domain>
"<title>"` assigns it and scaffolds the file under the domain's folder.

A decision that grows into distinct parts uses **decimal sub-numbers**:
`ADR-032.1` is the decision, `ADR-032.2` a follow-on (implementation notes, an
appendix, later findings). The bare base number (`ADR-032`) is the *family*
identifier: a `related: ADR-032` reference cites the decision as a whole and is
satisfied by any of its parts, while `related: ADR-032.2` targets one part
exactly. The graph linter (§5) resolves references this way.

### 2. Legacy range is frozen

ADRs 1–99 predate the domain scheme. They are **frozen at their numbers** —
we do not renumber them. Renumbering would break every cross-reference (in ADRs,
code comments, commit messages, and external links) for no benefit beyond
cosmetic tidiness. The legacy range is declared in `adr.yaml` (`legacy.range:
[1, 99]`); the linter resolves a legacy ADR's domain from its folder rather than
its number, so a frozen ADR-004 living in `access-workflow/` still reports as
`meta`. New decisions always use domain numbering; the legacy band only shrinks
as old ADRs are superseded, never by mass renumber.

### 3. Frontmatter contract

Every ADR carries YAML frontmatter:

```yaml
---
status: Draft | Proposed | Accepted | Superseded | Deprecated
date: YYYY-MM-DD
deciders:
  - <name>
related: []        # ADR-NNN references this decision relates to
---
```

`supersedes:` and `amends:` are optional and, when present, name the ADR(s) this
record replaces or revises. The status set is defined in `adr.yaml`.

### 4. Extension to the documentation tree

The same first-octet idea extends to `docs/` pages through a **documentation
catalog** (ADR-087). Each page carries a catalog ID of the form
`<domain-digit>.<MODE-letter>.<serial>` — the leading digit is the *same* domain
octet used here, so a page and the ADRs that govern it share a number space. The
mode letter is the page's Diátaxis mode. The full scheme, the mode letters, and
the page-to-domain map are ADR-087's concern; this ADR only fixes the shared
domain digit as the common key.

### 5. Graph linting

The numbering scheme is only useful if it holds. `docs/scripts/adr lint`
validates ADR frontmatter today; ADR-087 introduces `docs/scripts/doclint.py`,
which treats ADRs and docs as a single **decision graph** (nodes = records,
edges = `related`/`supersedes`) and lints it for dangling references, orphans,
cycles, and domain×mode coverage. Linting is enforced on `docs/` and warns on
ADRs until the ADR frontmatter sweep completes.

## Consequences

### Positive

- An ADR number tells you the subsystem at a glance.
- New records get a number and a home folder mechanically (`adr new`).
- Docs and ADRs share a domain key, so "everything about auth" is one query.
- Freezing the legacy range keeps every existing reference valid.

### Negative

- The legacy 1–99 band is a permanent special case the tooling must tolerate.
- Domain assignment for a genuinely cross-cutting decision is a judgment call
  (resolved by picking the dominant subsystem, or `meta` when truly cross-cutting).

### Neutral

- The scheme is data, not code: `adr.yaml` is the single source of truth, and
  both `adr` and `doclint.py` read it.

## Alternatives Considered

### Flat sequential numbering (the original)

Rejected going forward: the number carries no information, and the catalog is now
large enough that grouping by subsystem matters. Kept for the frozen legacy band.

### Renumber the legacy ADRs into domains

Rejected: breaks every existing cross-reference for a cosmetic gain. The folder
already records a legacy ADR's domain; its number need not.

### Per-domain restart (auth-001, infra-001, …)

Rejected: a global number is easier to cite ("ADR-411") than a domain-qualified
pair, and the hundreds digit already encodes the domain without a prefix.
