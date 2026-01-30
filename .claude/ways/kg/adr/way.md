---
match: regex
pattern: \badr\b|ADR-\d|architecture.*decision|docs/architecture/ADR
files: docs/architecture/ADR
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
| ui | 700-799 | CLI, web, MCP, visualization |
| ai | 800-899 | Embeddings, extraction, prompts |
| meta | 900-999 | Docs, workflow, ADR system |

Legacy ADRs (1-99) predate the domain system.

## Key ADRs

| ADR | Topic |
|-----|-------|
| ADR-016 | openCypher compatibility (not Neo4j Cypher) |
| ADR-028 | Dynamic RBAC permissions |
| ADR-048 | Query safety & GraphQueryFacade |
| ADR-061 | Operator architecture |
| ADR-082 | User scoping & groups |
| ADR-083 | Artifact persistence pattern |
