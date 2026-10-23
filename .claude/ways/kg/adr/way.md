---
pattern: \badr\b|ADR-\d|architecture.*decision|docs/architecture/ADR
files: docs/architecture/ADR
description: Architecture decision records with domain-based numbering for the knowledge graph system
vocabulary: adr architecture decision record proposal design rationale domain numbering
scope: agent, subagent
---
# KG ADR Supplement

## Domain Numbering

This project uses domain-based ADR numbering managed by `docs/scripts/adr`.
Run `docs/scripts/adr domains` for the full series. Key domains:

| Domain | Range | Area |
|--------|-------|------|
| infra | 100-199 | Containers, deployment, storage |
| db | 200-299 | Apache AGE, migrations, schema |
| ingest | 300-399 | Content processing, extraction |
| auth | 400-499 | RBAC, OAuth, API keys |
| query | 500-599 | Pathfinding, search |
| vocab | 600-699 | Relationships, grounding, categorization |
| ui | 700-799 | CLI, web, MCP, visualization |
| ai | 800-899 | Embeddings, extraction, prompts |
| meta | 900-999 | Docs, workflow, ADR system |

The 1-99 range is retired: those ADRs were renumbered into their domains (ADR-900).

## Record Contract

Records are on `adr/v1` (declared in `docs/architecture/adr.yaml`). Each carries
`kind` (decision, spec, evidence), a `capability` from the closed vocabulary in
`adr.yaml`, and, for a decision, a `verb` and a `basis`. `adr config` shows the
vocabulary. Records under `archive/` stay on adr/v0. The 108 active records were
imported from v0 without a `## Summary` section; lint warns until one is written.

## Key ADRs

| ADR | Topic |
|-----|-------|
| ADR-208 | openCypher compatibility (not Neo4j Cypher); archived, still the reference |
| ADR-400 | RBAC and endpoint security baseline |
| ADR-606 | Query safety & GraphQueryFacade |
| ADR-211 | Operator architecture |
| ADR-410 | User scoping & groups |
| ADR-116 | Artifact persistence pattern |
