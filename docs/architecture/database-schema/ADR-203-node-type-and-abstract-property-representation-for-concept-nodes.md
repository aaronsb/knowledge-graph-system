---
status: Draft
date: 2026-05-18
deciders:
  - aaronsb
  - claude
related: [200]
---

# ADR-203: Node Type and Abstract Property Representation for Concept Nodes

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

### The tension with ADR-200

ADR-200 deliberately **collapses the TBox/ABox distinction**: "a concept is
just an extremely narrow ontology," the concept/ontology split is
*operational, not ontological*, and rigid human-imposed taxonomy was the
problem it dissolved. Introducing a hard `type` label on nodes risks
re-importing exactly the rigidity ADR-200 removed — a new static
classification layer that the emergent structure will not respect.

So the real question is not "how do we add node types" but: **can the thing
the user wants (visual + semantic distinction of entity kinds) be expressed
as an additive, emergent, demotable *property* — consistent with ADR-200 —
rather than a fundamental new node kind?**

## Decision

> Status: **Draft** — this records the decision space and a leading
> proposal to anchor debate. Not yet accepted.

**Leading proposal:** Represent entity distinction as an optional, additive
**abstract facet property** on `:Concept` (working name `node_class`), *not*
as new Cypher node labels.

- The facet is a property, not a label — so it can emerge, change, and be
  demoted exactly like ontology membership under ADR-200. It does not create
  a TBox.
- It is optional and defaulted: absent ⇒ the node is an ordinary concept and
  the visualization falls back to ontology-derived shape/colour. No
  migration backfill is forced.
- The visualization derives the glyph from `node_class` when present, else
  from `ontology` — a strict superset of the no-schema rendering PR, so that
  PR is not wasted work.
- Genuinely non-concept entities (if any are ever needed — e.g. an external
  artifact that is categorically not a claim) remain the *only* candidates
  for a new node label, decided case-by-case in their own ADR, not
  pre-authorized here.

**Open questions for the debate (must resolve before this leaves Draft):**

1. Is `node_class` single-valued or a set (a concept may be many things)?
2. Who writes it — the extraction/AI layer, an operator action, or an
   emergent annealing process like ADR-200's promotion/demotion?
3. How does it interact with the ontology facet — orthogonal axes, or does
   one subsume the other?
4. Does AGE property indexing make per-class query/partition cheap enough at
   the InstancedMesh-per-class granularity the renderer wants?

## Consequences

### Positive

- Stays inside ADR-200's TBox/ABox collapse — distinction is an emergent
  property, not a rigid type system.
- Additive and optional — no forced migration; existing graphs render
  unchanged until a facet is written.
- The no-schema glyph-rendering PR remains valid as the fallback path; this
  only extends it.

### Negative

- A property-based facet is weaker for query/constraint than a real label
  (no native `MATCH (n:Type)`); per-class rendering must filter on a
  property, with whatever AGE indexing cost that implies.
- Yet another self-organizing axis to steward (open question 2/3) — risks
  the same maintenance burden ADR-200 calls out if ownership is unclear.

### Neutral

- The shape vocabulary is bounded by the renderer's solid family (4 today);
  the facet's cardinality and the glyph mapping must be designed together.
- Forces a decision on facet-write ownership that the system will need
  regardless of glyphs.

## Alternatives Considered

- **New Cypher node labels per type** (`:Concept` / `:Entity` / `:Property`
  …). Strong for query, but reintroduces the rigid TBox ADR-200 dissolved
  and forces migration semantics for every relabel. Rejected as the default;
  reserved only for genuinely non-concept entities, case-by-case.
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
