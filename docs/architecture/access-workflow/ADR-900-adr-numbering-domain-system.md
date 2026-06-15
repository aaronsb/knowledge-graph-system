---
status: Accepted
date: 2026-06-15
deciders:
  - aaronsb
  - claude
related:
  - ADR-908
---

# ADR-900: ADR Numbering Domain System

## Context

The first decision records were numbered sequentially, with no relationship
between a number and the part of the system it touched. That works until the
catalog grows. By the time it held several dozen records, the flat sequence told
you nothing: two adjacent numbers could touch embeddings and OAuth, related only
by the accident of authoring order.

We introduced a domain-based scheme to fix that. Each subsystem reserves a band
of 100 numbers, so the leading digit of an ADR number places it in the system at
a glance. The scheme is configured in `docs/architecture/adr.yaml` and enforced
by `docs/scripts/adr`. This ADR records it, extends the same idea to the `docs/`
tree, and (as of the 2026-06-15 amendment below) renumbers the pre-domain records
into their bands rather than leaving them stranded.

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
`ADR-603.1` is the decision, `ADR-603.2` a follow-on (implementation notes, an
appendix, later findings). The bare base number (`ADR-603`) is the *family*
identifier: a `related: ADR-603` reference cites the decision as a whole and is
satisfied by any of its parts, while `related: ADR-603.2` targets one part
exactly. The graph linter (§5) resolves references this way.

### 2. The pre-domain range is retired (1–99)

ADRs in the 1–99 range predate the domain scheme. They have been **renumbered
into their domain bands** (see the amendment below) and the **1–99 range is
retired**: no ADR uses it, and any reference into that range is invalid and fails
the lint guard (§5). Each ADR's domain is recorded by its folder *and*, now, by
its number. The range is declared in `adr.yaml` so the tooling knows it is
retired.

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
catalog** (ADR-908). Each page carries a catalog ID of the form
`<domain-digit>.<MODE-letter>.<serial>` — the leading digit is the *same* domain
octet used here, so a page and the ADRs that govern it share a number space. The
mode letter is the page's Diátaxis mode. The full scheme, the mode letters, and
the page-to-domain map are ADR-908's concern; this ADR only fixes the shared
domain digit as the common key.

### 5. Graph linting + the retired-range guard

The numbering scheme is only useful if it holds. `docs/scripts/adr lint`
validates ADR frontmatter; `docs/scripts/doclint.py` (ADR-908) treats ADRs and
docs as a single **decision graph** (nodes = records, edges =
`related`/`supersedes`) and lints it for dangling references, orphans, cycles,
and domain×mode coverage. It is enforced on both docs and ADRs in CI.

doclint also carries a **retired-range guard**: it scans the docs *and* the
source tree for any reference into the retired range and fails the build. Because
the range is vacated, this needs no crosswalk table — a reference into it is, by
definition, stale. This is what lets the renumber be a clean break: once
everything lints green, the migration scaffolding (mapping table, aliases) is
deleted, and the guard prevents the old numbers from creeping back. (A genuine
historical mention can opt out with a `doclint-allow-retired` marker on the line;
this ADR and `adr.yaml`, which define the range, are exempt.)

## Consequences

### Positive

- An ADR number tells you the subsystem at a glance — now for the whole corpus,
  not just records authored after the scheme existed.
- New records get a number and a home folder mechanically (`adr new`).
- Docs and ADRs share a domain key, so "everything about auth" is one query.
- The retired-range guard makes stale pre-domain references a build failure, so
  they cannot silently accumulate.

### Negative

- The renumber rewrote references across docs and code. References outside the
  repo (git history, closed issues, the ingested graph) still cite old numbers;
  those are not rewritten — `git log --follow` on a file recovers the mapping.
- Domain assignment for a genuinely cross-cutting decision is a judgment call
  (resolved by picking the dominant subsystem, or `meta` when truly cross-cutting).
  The renumber inherited each ADR's existing folder; a misfiled ADR keeps its
  (wrong) domain until re-filed.

### Neutral

- The scheme is data, not code: `adr.yaml` is the single source of truth, and
  both `adr` and `doclint.py` read it.

## Amendment (2026-06-15): renumber the pre-domain ADRs

This ADR originally **froze** the 1–99 range — renumbering was rejected as
"breaks every cross-reference for a cosmetic gain." That trade-off flipped once
the catalog reached ~76% pre-domain records, making the first-octet benefit
mostly aspirational, and once the reference graph (doclint) made the rewrite
mechanical:

- A generated old→new map assigned each pre-domain ADR the next free slot in its
  domain band (decimal sub-parts renumbered as a unit).
- Every `ADR-<old>` reference was rewritten across docs and the source tree.
- A repo-wide scan confirmed zero references into 1–99 remained, after which the
  mapping table and transitional `aliases` were deleted — the retired-range guard
  (§5) is the only standing mechanism, and it needs no table.

The cost the original freeze feared (broken references) was paid down by
automation and a guard, not avoided. External references are the residual; the
rename history in git is their crosswalk.

## Alternatives Considered

### Keep the pre-domain range frozen (the original decision)

Rejected on amendment: with most of the corpus pre-domain, "the number encodes
the domain" was false for the majority, and the tooling carried a permanent
special case. Automation made the renumber cheap enough to be worth it.

### Per-domain restart (auth-001, infra-001, …)

Rejected: a global number is easier to cite ("ADR-411") than a domain-qualified
pair, and the hundreds digit already encodes the domain without a prefix.
