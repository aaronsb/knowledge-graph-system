# catalog

> Auto-generated from MCP tool schema

### catalog

Browse what is actually stored in the knowledge graph (ADR-501).

A deterministic, filesystem-like view of the ontology -> document -> concept hierarchy. Use this to answer "what's in here?" structurally — by document or domain — as opposed to the 'search' tool, which finds concepts by semantic similarity. This is the right tool when you want to enumerate the corpus, drill into a specific document's concepts, or let a reasoning chain navigate by source rather than by meaning.

The hierarchy is fixed and self-describing via each node's 'kind':
  root      -> ontology   (knowledge domains)
  ontology  -> document   (ingested sources; may be text or image)
  document  -> concept    (leaf — extracted concepts appearing in that document)

A concept can appear under many documents (the graph is a DAG, not a tree). Membership is read from the graph's canonical edges, so it stays correct even as autonomous annealing (ADR-200) reorganizes ontologies.

Actions:
  - ls:   list children of a node (or root ontologies if no id). Supports a name fragment filter.
  - stat: full metadata for one node by id.

**Parameters:**

- `action` (`string`) **(required)** - 'ls' to list children, 'stat' for single-node detail
  - Allowed values: `ls`, `stat`
- `id` (`string`) - For ls: parent node id (omit to list root ontologies). For stat: the node id to inspect.
- `kind` (`string`) - Optional kind hint to disambiguate an id that collides across kinds.
  - Allowed values: `ontology`, `document`, `concept`
- `query` (`string`) - ls only: case-insensitive name fragment to filter children by.
- `sort` (`string`) - ls only: sort order for children (default name).
  - Allowed values: `name`, `child_count`, `created`
  - Default: `"name"`
- `limit` (`number`) - ls only: max children per page (1-1000, default 100).
  - Default: `100`
- `offset` (`number`) - ls only: pagination offset (default 0).
  - Default: `0`

---
