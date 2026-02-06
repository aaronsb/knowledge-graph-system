# GraphProgram Language Reference

GraphProgram is a domain-specific query composition language for the knowledge
graph system. It orchestrates openCypher queries and REST API calls through
set-algebraic operators applied to an ephemeral working graph.

## Documents

| Document | Purpose |
|----------|---------|
| [specification.md](specification.md) | Formal language spec: types, operators, execution semantics |
| [validation.md](validation.md) | Validation rule catalog and endpoint allowlists |
| [security.md](security.md) | Threat model, defense-in-depth layers, security guarantees |
| [lifecycle.md](lifecycle.md) | How programs move from authoring to execution across clients |

## Quick Orientation

A `GraphProgram` is a JSON AST containing an ordered list of statements. Each
statement pairs a **set operator** (`+`, `-`, `&`, `?`, `!`) with an
**operation** (`cypher`, `api`, or `conditional`). Execution walks the
statements sequentially, building up a working graph W from the persistent
knowledge graph H.

```json
{
  "version": 1,
  "statements": [
    {
      "op": "+",
      "operation": {
        "type": "cypher",
        "query": "MATCH (c:Concept)-[r]->(n:Concept) WHERE c.label = 'Machine Learning' RETURN c, r, n"
      },
      "label": "Seed: machine learning neighborhood"
    },
    {
      "op": "+",
      "operation": {
        "type": "api",
        "endpoint": "/search/concepts",
        "params": { "query": "neural networks", "limit": 20 }
      },
      "label": "Add semantically related concepts"
    },
    {
      "op": "-",
      "operation": {
        "type": "cypher",
        "query": "MATCH (c:Concept) WHERE c.grounding_strength < 0 RETURN c"
      },
      "label": "Remove weakly grounded concepts"
    }
  ]
}
```

This program:
1. Queries H for the Machine Learning concept neighborhood (`+` merges into W)
2. Runs a semantic search for neural networks (`+` merges results into W)
3. Removes any concepts with negative grounding strength (`-` subtracts from W)

## Operators

| Op | Name | Effect on W |
|----|------|-------------|
| `+` | Union | Merge result into W |
| `-` | Difference | Remove result from W |
| `&` | Intersect | Keep only the overlap |
| `?` | Optional | Like `+`, empty result is a no-op |
| `!` | Assert | Like `+`, empty result aborts |

## Code-Signing Model

Programs follow a **code-signing pattern**: author anywhere, notarize server-side,
execute notarized programs. The API validates and stores programs; clients retrieve
and execute them. See [security.md](security.md) for the full trust model.

```
Client ──> POST /programs/validate ──> Validation result (dry-run)
Client ──> POST /programs          ──> Validate + store (notarize)
Client ──> GET  /programs/{id}     ──> Retrieve notarized program
Client ──> Execute locally         ──> Per-statement API calls
```

## Executable Specification

The validation rules have a pure-Python executable spec that runs without Docker
or the full platform:

```bash
# Models: api/app/models/program.py
# Validator: api/app/services/program_validator.py
# Tests (105 cases): tests/unit/test_program_validation.py

# Run in container
docker exec kg-api-dev pytest tests/unit/test_program_validation.py -v

# Or with bare pytest (only needs pydantic)
pip install pydantic pytest
pytest tests/unit/test_program_validation.py -v
```

## Canonical ADR

[ADR-500 — Graph Program DSL and AST Architecture](../architecture/query-search/ADR-500-graph-program-dsl-and-ast-architecture.md)
