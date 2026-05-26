---
status: Draft
date: 2026-05-18
deciders:
  - aaronsb
  - claude
related: [200]
---

# ADR-204: Node Type and Abstract Property Representation for Concept Nodes

> **Renumbered from ADR-203** (was a draft slot reserved while this PR sat
> open; ADR-203 is now occupied by the merged "Graph Epoch Event Log"
> decision). No content change beyond the heading.

## Context

### What prompted this

We want to give graph entities visual distinction beyond colour —
specifically a platonic-solid glyph encoding where colour carries one axis
("which namespace/domain") and *shape* carries a second ("what kind of
thing"). The solids (icosahedron / octahedron / tetrahedron / dodecahedron)
read as one coherent family and also reduce to flat UTF-8-friendly SVG
silhouettes for legends, lists, and web content.

The **rendering** half of this needs no schema decision and is out of scope
here: the unified engine already partitions nodes into one `InstancedMesh`
per class via `Scene.tsx`'s `nodeClasses` + `geometryByClass` props (Document
Explorer uses it today for document glyphs). A `shapeFor(ontology)` mapping
plus the SVG legend glyphs can ship against the **existing** ontology string
with zero schema change — and that should be done first as a separate PR.

This ADR is the **data-model decision** that gates anything richer than
"shape mirrors ontology": when the user says they are "considering how to
represent other node types, or possibly, abstract properties attached to
concept nodes," what — if anything — changes in the graph schema?

### The current model

Knowledge nodes are effectively one type: `:Concept` (with `:Source` and
`:Instance` as ingestion-provenance nodes). A concept's organizational
membership is the `ontology` string. There is no first-class notion of a
node *type* discriminator, nor of typed *abstract properties* (facets) hung
off a concept distinct from its evidence/edges.

### Who consumes this — the decisive premise

The principal consumer of the graph is **agents**, through the MCP server
and programmatic APIs — not humans through the visualization. Agents
discover, filter, and traverse by *querying*; the UI is a secondary,
human-facing lens over the same data.

This reorders everything below. A representation choice that costs
**query power** costs the *primary* consumer; a choice that costs **UI
legibility** costs only the secondary one. So the lozenge-label
mitigation introduced later closes a *secondary* gap — it must not be
read as offsetting any loss of query power, which is the expensive axis
here. "Can an agent select all nodes of a kind, cheaply and
unambiguously, without bespoke knowledge?" is the question that should
dominate the decision.

### The tension with ADR-200

ADR-200 deliberately **collapses the TBox/ABox distinction**: "a concept is
just an extremely narrow ontology," the concept/ontology split is
*operational, not ontological*, and rigid human-imposed taxonomy was the
problem it dissolved. Introducing a hard `type` label on nodes risks
re-importing exactly the rigidity ADR-200 removed — a new static
classification layer that the emergent structure will not respect.

So the real question is a *dual* constraint, and both halves are
load-bearing: **can entity distinction be additive / emergent / demotable
(consistent with ADR-200) _while still giving agents label-grade query
power_ over it?** A solution that satisfies only the first half (a clean
emergent property an agent cannot cheaply select on) fails the primary
consumer; one that satisfies only the second (a rigid label) fails
ADR-200. The design must hit both — that is the bar, and what makes this
a real decision rather than a rename.

## Decision

> Status: **Draft** — this records the decision space and a leading
> proposal to anchor debate. Not yet accepted.

**Leading proposal:** Represent entity distinction as an optional, additive
**abstract facet property** on `:Concept` (working name `node_class`), *not*
as new Cypher node labels — **contingent on it delivering agent-grade query
power**. If that contingency fails, this proposal fails (see the residual
negative and the hybrid alternative); it is not accepted on ADR-200
fidelity alone.

- **Agent query power is a first-class requirement, not a hope.** The
  property must be backed by an AGE index and exposed through an MCP
  `node_class` filter so an agent selects a kind via a tool parameter
  (the agent's normal interface), never by hand-writing a property
  predicate or carrying bespoke knowledge. Raw-Cypher ergonomics
  (`WHERE n.node_class = …` vs `MATCH (n:Kind)`) is the part this does
  *not* fully recover — acceptable only if MCP-mediated selection covers
  the real agent access patterns at scale. Resolving open question 4 is
  therefore a *gate on this proposal*, not a detail.
- The facet is a property, not a label — so it can emerge, change, and be
  dissolved exactly like ontology membership under ADR-200 (see ADR-206 for
  the closed action vocabulary that governs these transitions). It does not
  create a TBox.
- It is optional and defaulted: absent ⇒ the node is an ordinary concept and
  the visualization falls back to ontology-derived shape/colour. No
  migration backfill is forced.
- The visualization derives the glyph from `node_class` when present, else
  from `ontology` — a strict superset of the no-schema rendering PR, so that
  PR is not wasted work.
- The facet value is surfaced as an **optional lozenge label** — a small
  pill beside the node, distinct from the name label, toggling on/off
  independently. Off by default for an uncluttered canvas; on when a human
  is introspecting *what kinds of things* are present. This serves the
  **secondary (human) consumer only** — it closes the UI-legibility gap, it
  is explicitly *not* part of the agent query-power story above.
- Genuinely non-concept entities (if any are ever needed — e.g. an external
  artifact that is categorically not a claim) remain the *only* candidates
  for a new node label, decided case-by-case in their own ADR, not
  pre-authorized here.

**Open questions for the debate (must resolve before this leaves Draft):**

1. Is `node_class` single-valued or a set (a concept may be many things)?
2. Who writes it — the extraction/AI layer, an operator action, or an
   emergent annealing process like ADR-200's CLEAVE/DISSOLVE cycle
   (see ADR-206)?
3. How does it interact with the ontology facet — orthogonal axes, or does
   one subsume the other?
4. **(Gating)** Does AGE property indexing + an MCP `node_class` filter
   give agents label-grade selectivity and cost — at graph scale, across
   the access patterns agents actually use (filter, traverse-by-kind,
   count) — such that not having `MATCH (n:Kind)` is genuinely a
   non-issue for the primary consumer? If no, the leading proposal is
   rejected in favour of the hybrid or the label alternative.

## Consequences

### Positive

- Stays inside ADR-200's TBox/ABox collapse — distinction is an emergent
  property, not a rigid type system.
- Additive and optional — no forced migration; existing graphs render
  unchanged until a facet is written.
- The no-schema glyph-rendering PR remains valid as the fallback path; this
  only extends it.
- Optional, toggleable lozenge labels recover the *human-legibility* a real
  label would have provided — the facet is readable on demand — while
  keeping the default canvas uncluttered. They double as an introspection
  tool: flip them on to audit what `node_class` values the graph actually
  carries, independent of the (lossy, 4-way) shape encoding.

### Negative

- **The central risk, not a residual.** A property-based facet is weaker
  for query/constraint than a real label (no native `MATCH (n:Type)`,
  property-predicate + index instead). Because agents — the *primary*
  consumer — discover and traverse by querying, this lands on the consumer
  that matters most, which is why it gates the whole proposal (open
  question 4). The lozenge-label affordance does *not* relieve it: that
  serves the secondary human consumer. Mitigated only if MCP-mediated
  selection + AGE indexing genuinely matches label-grade access; if the
  graph grows to where agents need ad-hoc Cypher by kind, the property
  approach is the wrong call and the hybrid/label alternative wins.
- Yet another self-organizing axis to steward (open question 2/3) — risks
  the same maintenance burden ADR-200 calls out if ownership is unclear.

### Neutral

- The shape vocabulary is bounded by the renderer's solid family (4 today);
  the facet's cardinality and the glyph mapping must be designed together.
  Shape collisions (many facet values, 4 solids) are tolerable precisely
  because the lozenge label disambiguates exactly — shape is the
  at-a-glance gestalt, the lozenge is the precise read.
- Forces a decision on facet-write ownership that the system will need
  regardless of glyphs.

## Alternatives Considered

- **New Cypher node labels per type** (`:Concept` / `:Entity` / `:Property`
  …). Strongest for the *primary* (agent) consumer: native `MATCH
  (n:Kind)`, AGE stores each label as its own relation so selection and
  counting are cheap and ergonomic with zero bespoke knowledge. The cost
  is ADR-200 fidelity — a rigid TBox and relabel-migration semantics on
  every change. Not rejected outright anymore: if open question 4 shows
  property+MCP can't match this for agents, the consumer priority says
  *labels win and ADR-200 must bend*, not the reverse.
- **Hybrid: emergent property as source of truth, a derived label kept in
  sync.** `node_class` stays the mutable/dissolvable property ADR-200 wants;
  a projection process (the same annealing that issues CLEAVE/DISSOLVE
  actions, per ADR-206) writes a matching Cypher label so agents get
  `MATCH (n:Kind)` while emergence still owns the truth. Buys both halves
  of the dual constraint at the price of a sync mechanism and relabel
  churn on change (bounded — the annealing executor already mutates the
  graph). This is the natural fallback if Q4 fails, and may deserve
  promotion to the leading proposal.
- **No schema change — derive shape purely from the existing `ontology`
  string.** Zero risk, ships immediately, and is the recommended *first* PR.
  Rejected as the *end state* only because it conflates "which bucket" with
  "what kind of thing" onto a single axis — the user explicitly wants the
  second axis.
- **Separate "property nodes" linked by edges (RDF-style reification).**
  Maximally flexible and graph-native, but heavy: every abstract property
  becomes a node + edge, inflating node count and the physics sim, and
  complicating the very visualization this is meant to clarify. Revisit only
  if facets need their own relationships/provenance.
