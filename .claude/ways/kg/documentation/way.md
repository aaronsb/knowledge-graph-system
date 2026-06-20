---
pattern: doc.?catalog|di[aá]taxis|coverage matrix|frontmatter.*id|DD\.NNN|doclint|doc(s)?.*(graph|catalog)|reference page.*generat
files: docs/.*\.md$
commands: docs/scripts/(doc|doclint)
description: The docs/ tree is one typed graph — catalog frontmatter, DD.NNN.P ids, and the doclint CI gate (ADR-908)
vocabulary: documentation catalog diataxis frontmatter id domain mode doclint coverage matrix typed graph reference generated retired range
scope: agent, subagent
---
# KG Documentation Catalog Way

`docs/` is **one typed graph**, not a pile of files — pages and ADRs are nodes,
`related`/`supersedes` are edges. A page's type lives in **frontmatter**, enforced
by a linter; folders are a *view* for human readers. Decision: **ADR-908**. This
repo is the reference implementation that the agent-ways framework generalized into
its canonical documentation model (see ADR-908 → "Upstream").

## Catalog frontmatter

A `docs/` page joins the catalog **only** when it declares these — untagged prose
is ignored (opt-in):

```yaml
id: 04.001.H        # DD.NNN.P  (octet-style)
domain: auth        # ADR-900 domain key — the shared first octet with ADRs
mode: how-to        # Diátaxis: tutorial | how-to | reference | explanation
```

- **Identity is `DD.NNN`** — domain band + domain-scoped serial, assigned once,
  never reused. The trailing **pole `P`** (`T`/`H`/`R`/`E`) is a *classifier* that
  must agree with `mode:`, not part of the key. Re-classifying a page flips only
  the pole; the number is untouched.
- **Mode is reader posture, not audience.** The four modes are a closed 2×2 — there
  is no fifth. "Operations" is an audience facet carried by `domain`, never a mode.
- Domain bands mirror the ADR series (`01` infra · `02` db · `03` ingest ·
  `04` auth · `05` query · `06` vocab · `07` ui · `08` ai · `09` meta).

## Tooling

| Command | Role |
|---------|------|
| `docs/scripts/doc coverage` / `gaps` / `list` | Diagnostic front-end — domain×mode matrix |
| `docs/scripts/doclint.py --check` | The **test** — CI gate, exit 1 on errors |

Both are **vendored copies** of the canonical agent-ways tools (copy-not-symlink);
re-vendor from canonical rather than editing in place. They share `adr.yaml`'s
domain config. Keep lint at **0 errors** — it enforces frontmatter validity,
resolvable edges, no supersede cycles, and the vacated-range guard.

## Gotchas

- **Generated reference pages** (`reference/{cli,mcp,fuse,schema}.md`) are
  overwritten every build — their frontmatter is **emitted by the generator**
  (`cli/scripts/*`), never hand-injected, or the next regen wipes it.
- **Retired-range guard is ON** (`legacy: {retired: true}`): no doc/ADR/source may
  reference the vacated legacy range (ADR numbers 1–99). The scan honors `.gitignore`, so
  gitignored corpora (e.g. `examples/.../claude-ai-history`) and scratch are
  skipped. Raw audit/scan byproducts go to `*-raw.json` (gitignored), not committed.
- mkdocs strips unknown frontmatter, so catalog ids never reach readers — they are
  maintainer/linter metadata only.

## See Also

- `.claude/ways/kg/adr/way.md` — ADR domain numbering (shares `adr.yaml`)
- ADR-908 — the decision; ADR-900 — the domain/numbering system
