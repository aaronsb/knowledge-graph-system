---
id: 5.R.04
domain: query
mode: reference
---

# GraphProgram Validation

The API validates every GraphProgram AST before execution. Validation is server-side authoritative — client-side pre-validation is useful for fast feedback but is never sufficient. Programs submitted from the web app, CLI, MCP, or an agent pass through the same pipeline.

Validation produces structured errors referencing the statement index and field path. Errors block execution; warnings are advisory and do not prevent a program from running.

Related: [GraphProgram Specification](graph-program-spec.md) · [GraphProgram Security](graph-program-security.md)

---

## Validation layers

Validation proceeds through four ordered layers, cheapest first. If Layer 1 fails the program cannot be deserialized and subsequent layers are skipped.

| Layer | Name | Cost | What it checks |
|-------|------|------|----------------|
| 1 | Deserialization | Cheapest | JSON structure, required fields, type correctness |
| 2 | Structural | Low | Semantic invariants beyond the type system |
| 3 | Safety | Medium | Write-keyword rejection, endpoint allowlists, operation count bounds |
| 4 | Semantic | Expensive | Parameter resolution, nesting depth, boundedness (planned) |

### Layer 1 — Deserialization

Pydantic model validation. Catches:

- Non-dict input (must be a JSON object)
- Missing required fields (`version`, `statements`)
- Wrong types (string where int expected, etc.)
- Invalid enum values (unknown operators, unknown operation types)
- Constraint violations (`min_length`, `gt`, `ge`, `le`)
- Unknown discriminator values for the `operation` union

All Layer 1 failures produce rule ID `V000`.

### Layer 2 — Structural

Invariants that the type system cannot express:

- Version compatibility (only version 1 is currently valid)
- Parameter name uniqueness within a program
- Conditional branch non-emptiness

### Layer 3 — Safety

Runtime-safety checks that protect the database:

- Cypher write-keyword detection (prevents mutations via query injection)
- API endpoint allowlist enforcement (prevents calls to unauthorized endpoints)
- Required parameter validation for API operations
- Total operation count bounds
- Conditional nesting depth limits

### Layer 4 — Semantic (planned)

Checks that require deeper analysis, not yet implemented:

- `$param` references resolve to declared parameters or provided values
- Conditional nesting depth relative to available context
- Cross-statement data flow analysis

---

## Validation rules catalog

### Layer 1 — Deserialization

| Rule ID | Description | Severity | Example trigger |
|---------|-------------|----------|-----------------|
| V000 | Deserialization failure | error | Missing `version`, empty `statements`, unknown `op` value, non-dict input |

### Layer 2 — Structural

| Rule ID | Description | Severity | Example trigger |
|---------|-------------|----------|-----------------|
| V001 | Version must be 1 | error | `"version": 2` |
| V002 | Statements must be non-empty | error | `"statements": []` (also caught by V000) |
| V003 | Statement structure invalid | error | Reserved — operator and operation-type checks are enforced by Pydantic at Layer 1 (surfaces as V000) |
| V004 | Duplicate parameter names | error | Two params both named `"x"` |
| V005 | Conditional then-branch empty | error | `"then": []` in `ConditionalOp` |

### Layer 3 — Safety: Cypher write keywords

| Rule ID | Description | Severity | Example trigger |
|---------|-------------|----------|-----------------|
| V010 | Query contains CREATE | error | `"CREATE (c:Concept)"` |
| V011 | Query contains SET | error | `"SET c.label = 'x'"` |
| V012 | Query contains DELETE | error | `"DELETE c"` |
| V013 | Query contains MERGE | error | `"MERGE (c:Concept)"` |
| V014 | Query contains REMOVE | error | `"REMOVE c.label"` |
| V015 | Query contains DROP | error | `"DROP INDEX idx"` |
| V016 | Query contains DETACH | error | `"DETACH DELETE c"` |

Detection rules:

- Case-insensitive — `create` and `CREATE` both trigger.
- Word-boundary matching — `CREATED` does **not** trigger V010.
- String literal content (`'...'`, `"..."`) is excluded.
- Comment content (`--`, `/* */`) is excluded.

### Layer 3 — Safety: API endpoint allowlist

| Rule ID | Description | Severity | Example trigger |
|---------|-------------|----------|-----------------|
| V020 | Endpoint not in allowlist | error | `"/admin/delete"` |
| V021 | Required parameter missing | error | `/search/concepts` without `query` |
| V022 | Unknown parameter | warning | `bogus_param` on any endpoint |
| V023 | Parameter type mismatch | error | `query: 123` (expected string) |

### Layer 3 — Safety: Cypher path bounds

| Rule ID | Description | Severity | Example trigger |
|---------|-------------|----------|-----------------|
| V030 | Unbounded or excessive variable-length path | error | `[*]`, `[*2..]`, `[*1..10]` (max 6) |

Detection rules:

- `[*]` and `[*N..]` (no upper bound) are always rejected.
- `[*N..M]` and `[*M]` are rejected when the upper bound exceeds `MAX_VARIABLE_PATH_LENGTH` (default: 6).

### Layer 3 — Safety: Program bounds

| Rule ID | Description | Severity | Example trigger |
|---------|-------------|----------|-----------------|
| V006 | Exceeds max operation count | error | >100 total operations |
| V007 | Exceeds max nesting depth | error | >3 levels of nested conditionals |

---

## Endpoint allowlist

The following REST API endpoints are permitted in `ApiOp` statements:

| Endpoint | Required params | Optional params |
|----------|----------------|-----------------|
| `/search/concepts` | `query` (str) | `min_similarity` (int/float), `limit` (int), `ontology` (str), `offset` (int) |
| `/search/sources` | `query` (str) | `min_similarity` (int/float), `limit` (int), `ontology` (str), `offset` (int) |
| `/vocabulary/status` | *(none)* | `status_filter` (str), `relationship_type` (str) |
| `/concepts/batch` | `concept_ids` (list) | `include_details` (bool) |
| `/concepts/details` | `concept_id` (str) | `include_diversity` (bool), `include_grounding` (bool) |
| `/concepts/related` | `concept_id` (str) | `max_depth` (int), `relationship_types` (list) |

Parameter types are enforced by V023. New endpoints are added by extending `API_ENDPOINT_ALLOWLIST` in `api/app/models/program.py`.

---

## Operator allowlist

Valid operators for statements:

| Operator | Name | Semantics |
|----------|------|-----------|
| `+` | Add | Query H, merge results into W |
| `-` | Subtract | Query H or W, remove matches from W |
| `&` | Intersect | Query H, keep only overlap with W |
| `?` | Optional | Like `+`, but empty result is not an error |
| `!` | Assert | Like `+`, but empty result aborts the program |

---

## Cypher write-keyword deny list

The following keywords are rejected in `CypherOp.query`:

```
CREATE  SET  DELETE  MERGE  REMOVE  DROP  DETACH
```

Defined as `CYPHER_WRITE_KEYWORDS` in `api/app/models/program.py`.

---

## Bounds configuration

| Constant | Default | Description |
|----------|---------|-------------|
| `MAX_STATEMENTS` | 100 | Maximum total operation count; conditional branches use the longer path |
| `MAX_NESTING_DEPTH` | 3 | Maximum conditional nesting depth |
| `MAX_VARIABLE_PATH_LENGTH` | 6 | Maximum hops for variable-length Cypher paths (`[*1..N]`) |
| `CURRENT_VERSION` | 1 | Only supported program version |

---

## Error response format

```json
{
  "valid": false,
  "errors": [
    {
      "rule_id": "V010",
      "severity": "error",
      "statement": 3,
      "field": "operation.query",
      "message": "Cypher query contains write keyword: CREATE"
    }
  ],
  "warnings": [
    {
      "rule_id": "V022",
      "severity": "warning",
      "statement": 1,
      "field": "operation.params.bogus",
      "message": "Unknown parameter: bogus"
    }
  ]
}
```

Each issue includes:

| Field | Type | Description |
|-------|------|-------------|
| `rule_id` | string | Catalog identifier (e.g., `V010`) |
| `severity` | string | `error` (blocks execution) or `warning` (advisory) |
| `statement` | int \| null | 0-based index into `program.statements`; null for program-level issues |
| `field` | string | Dot-separated path to the problematic field |
| `message` | string | Human-readable description |

---

## Client-side pre-validation

Clients should validate locally before submitting programs to the API:

- Faster feedback (no network round-trip)
- Syntax highlighting and error indicators in editors
- Reduced server load from obviously invalid programs

Client validation is advisory. The server is authoritative. A program that passes client-side checks may still fail server-side if the server carries a stricter or updated rule set.

---

## Extending validation

### Add a new validation rule

1. Assign the next available rule ID in the appropriate layer range.
2. Implement the check in the corresponding `_layer*` function in `api/app/services/program_validator.py`.
3. Add a test in `tests/unit/test_program_validation.py` that exercises the rule.
4. Add the rule to this catalog.

### Add a new API endpoint

1. Add the endpoint to `API_ENDPOINT_ALLOWLIST` in `api/app/models/program.py`.
2. Specify `required` and `optional` parameter lists.
3. Add a test verifying the endpoint passes with required params.

### Add a new operation type

1. Define a new `*Op` Pydantic model in `api/app/models/program.py`.
2. Add it to the `Operation` union type.
3. Add the new discriminator value.
4. Add validation logic in the appropriate layer.
5. Update this catalog.

---

## Implementation

| Component | Path |
|-----------|------|
| Models | `api/app/models/program.py` |
| Validator | `api/app/services/program_validator.py` |
| Tests | `tests/unit/test_program_validation.py` (109 tests — executable specification) |
