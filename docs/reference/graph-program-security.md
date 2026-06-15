---
id: 5.R.02
domain: query
mode: reference
---

# GraphProgram Security Model

This page defines the security guarantees, threat model, and defense-in-depth layers for the GraphProgram system (ADR-500). It is written for implementers building the executor and validators, and for security reviewers evaluating trust boundaries.

## Terminology

| Term | Definition |
|------|-----------|
| **H** | The persistent knowledge graph. Immutable during query execution. |
| **W** | The working subgraph. Ephemeral, built during program execution. |
| **Notarization** | Server-side validation and storage of a `GraphProgram` AST. |
| **`Operator`** | One of `+` (union), `-` (difference), `&` (intersect), `?` (optional), `!` (assert). |

For the complete validation rule catalog (V001, V002, etc.), see [GraphProgram Validation](graph-program-validation.md).

---

## Code-signing pattern

Any client (web, CLI, MCP, agent) authors a `GraphProgram` JSON AST and submits it to `POST /programs`. The API validates and notarizes the program — structural checks, safety checks, and boundedness analysis must all pass. The notarized program is stored in `kg_api.query_definitions` with an `owner_id`, timestamp, and `definition_type = program`. Clients then retrieve notarized programs and execute them via `POST /programs/execute`.

The notarization is a trust stamp, not a privilege gate. A client that bypasses notarization and submits an un-notarized AST directly to the executor still faces the same per-statement guards — authentication, rate limiting, read-only enforcement, namespace safety — that apply to all query execution. Notarization adds structural guarantees on top of those execution guards; it does not replace them.

---

## Defense-in-depth layers

Five layers defend independently. A failure in one does not compromise the others.

### Layer 1: AST type system

The `GraphProgram` AST is defined as a Pydantic discriminated union. The type system is an allowlist:

- `Statement.operation` must be one of `CypherOp`, `ApiOp`, or `ConditionalOp`.
- `Statement.op` must be a valid `Operator`: `+`, `-`, `&`, `?`, or `!`.
- `Condition.test` must be one of the enumerated test types (`has_results`, `empty`, `count_gte`, `count_lte`, `has_ontology`, `has_relationship`).

Unknown operation types, unknown operators, and unknown condition tests are rejected at deserialization before any validation logic runs. Adding a new capability requires an explicit AST type change.

**What this layer guarantees:**
- Programs cannot contain operation types absent from the schema.
- Malformed JSON and unexpected fields are rejected before validation.

**What this layer does not guarantee:**
- The content of a `CypherOp.query` string is syntactically valid Cypher.
- The `ApiOp.endpoint` is in the allowlist.
- The program is bounded or safe to execute.

### Layer 2: Validator

`POST /programs/validate` performs structural and safety checks on a well-typed AST. The full rule catalog is in [GraphProgram Validation](graph-program-validation.md). The security-relevant checks are:

| Check | What it catches |
|-------|-----------------|
| **Boundedness** | Total operation count is statically computable and within limits (default: 100). Conditional branches contribute their longer path. |
| **Cypher safety** | Write keywords (`CREATE`, `DELETE`, `SET`, `REMOVE`, `MERGE`, `DROP`, `DETACH`) are rejected. Unbounded `MATCH` without `LIMIT` is flagged. |
| **`ApiOp` allowlist** | `endpoint` must be in the permitted set of internal API paths (e.g., `/search/concepts`, `/search/sources`, `/vocabulary/status`). |
| **Parameter resolution** | All `$param` references resolve to declared parameters or provided values. |
| **Nesting depth** | `ConditionalOp` nesting does not exceed the maximum (default: 3). |
| **Required fields** | All required fields are present and correctly typed. |

**What this layer guarantees:**
- A notarized program will not attempt write operations via Cypher.
- A notarized program will not call arbitrary API endpoints.
- A notarized program has a statically-determinable maximum operation count.
- All parameter references are resolvable.

**What this layer does not guarantee:**
- Cypher queries will return results or perform well.
- `ApiOp` parameters are semantically valid (e.g., `min_similarity: 999`).
- The program produces useful output.

### Layer 3: Storage and ownership

Notarized programs are stored in `kg_api.query_definitions`:

- `owner_id`: The authenticated user who created the program.
- `created_at` / `updated_at`: Timestamps for audit trail.
- `definition_type`: Set to `program` for GraphProgram ASTs.

Access control rules (from `query_definitions.py`):

| Operation | Who can perform it |
|-----------|-------------------|
| List | Owner sees own programs; `admin`/`platform_admin` see all. |
| Read | Owner or admin. |
| Update | Owner or admin. |
| Delete | Owner or admin. |

Programs with `owner_id = NULL` (system-provided programs) are visible to all authenticated users.

**What this layer guarantees:**
- Programs have author attribution.
- Non-admin users cannot read, modify, or delete other users' programs.
- The stored AST is the exact AST that was validated — no post-notarization mutation by unauthorized parties.

**What this layer does not guarantee:**
- Programs are immutable after notarization. The owner (or admin) can update the stored definition via `PUT /query-definitions/{id}`. Re-validation is not currently enforced on update — see [T6](#t6-post-notarization-mutation).
- Cross-user program sharing. There is no grants or sharing model yet.

### Layer 4: Per-statement execution guards

When the executor runs a program's statements, each statement passes through the same guards that apply to direct query execution:

| Guard | Mechanism | Source |
|-------|-----------|--------|
| **Authentication** | OAuth 2.0 access token required (`get_current_user` / `CurrentUser` dependency). | `dependencies/auth.py` |
| **Authorization** | Role-based and permission-based access control (`require_role`, `require_permission`, `require_scope`). | `dependencies/auth.py` |
| **Namespace safety** | `GraphQueryFacade` enforces explicit labels on Cypher queries, preventing namespace collisions between concept and vocabulary graphs. | `lib/query_facade.py` (ADR-048) |
| **Audit logging** | `QueryAuditLog` tracks every query with timestamp, namespace, and raw/safe classification. | `lib/query_facade.py` |
| **Rate limiting** | Per-user rate limits apply to the executor endpoint the same as any other endpoint. | Application middleware |

**What this layer guarantees:**
- An unauthenticated client cannot execute programs.
- Every Cypher statement is audited.
- Namespace collisions between concept and vocabulary graphs are prevented for facade-routed queries.

**What this layer does not guarantee:**
- That all Cypher goes through the facade. The current `POST /cypher` endpoint executes raw queries via `client._execute_cypher()` directly without facade routing. The program executor should use the facade, but this is an implementation requirement, not a current enforcement.

### Layer 5: Database-level constraints

Apache AGE and PostgreSQL 18 provide the final defense layer:

| Constraint | Effect |
|-----------|--------|
| **Cypher syntax validation** | AGE 1.7.0 rejects syntactically invalid Cypher. |
| **Graph schema** | Node labels (`:Concept`, `:Source`, `:Instance`, `:VocabType`) enforce structure. |
| **Connection limits** | PostgreSQL `max_connections` bounds concurrent access. |
| **Transaction isolation** | Each query runs in a transaction; failures roll back cleanly. |
| **Read-only connections** | If the database connection is configured read-only, write attempts fail regardless of what the application allows. |

**What this layer guarantees:**
- Invalid Cypher never executes.
- The database schema constrains what nodes and relationships can exist.

**What this layer does not guarantee:**
- Query performance. A valid query can still be expensive.
- That the application uses read-only connections — this is a deployment choice.

---

## Trust boundary diagram

```
                    Trust Boundary
                         |
  Client (untrusted)     |     API Server (trusted)
  ───────────────────    |     ────────────────────
                         |
  Author program ──────────> Validate AST (Layer 1+2)
                         |     │
                         |     ├── Type check (Pydantic)
                         |     ├── Write-keyword scan
                         |     ├── ApiOp allowlist
                         |     ├── Boundedness check
                         |     └── Parameter resolution
                         |
  Submit for notarization ──> Store notarized program (Layer 3)
                         |     │
                         |     └── owner_id, timestamps
                         |
  Execute program ─────────> Per-statement guards (Layer 4)
                         |     │
                         |     ├── OAuth authentication
                         |     ├── Role/permission checks
                         |     ├── Namespace safety (facade)
                         |     ├── Audit logging
                         |     └── Rate limiting
                         |
                         |   Database (Layer 5)
                         |     │
                         |     ├── Cypher syntax validation
                         |     ├── Schema constraints
                         |     ├── Connection limits
                         |     └── Read-only enforcement
```

---

## Threat model

### T1: Malicious client crafting programs

An authenticated user submits a program designed to exfiltrate data, corrupt H, or cause denial of service.

**Mitigations:**
- **Write operations.** Layer 2 rejects Cypher containing write keywords. Layer 5 rejects writes if using read-only connections.
- **Data exfiltration.** Not mitigated by the program system itself. An authenticated user with `graph:execute` permission can already read any data their role permits. Programs do not expand read access beyond existing permissions.
- **Denial of service via expensive queries.** Layer 2 enforces a bounded operation count. Individual queries can still be expensive (e.g., `MATCH (c:Concept)-[*1..10]-(n) RETURN c, n LIMIT 1000`). This is partially mitigated by PostgreSQL `statement_timeout` but is not fully solved at the program level.
- **ApiOp abuse.** Layer 2 restricts endpoints to the allowlist. Parameters are dispatched to internal service functions, not arbitrary HTTP endpoints.

**Residual risk:** An authenticated user can craft expensive-but-valid queries. This is a resource management concern, not a privilege escalation. Mitigation options include per-user query budgets, statement-level timeouts, and EXPLAIN cost estimation.

### T2: Bypassing the notarization

A client submits an un-notarized AST directly to the executor, skipping validation.

**Mitigations:**
- The executor re-validates incoming ASTs before execution (implemented in `programs.py`). Even without re-validation, per-statement guards (Layer 4) apply: authentication, audit logging, namespace safety.
- **No privilege escalation.** Bypassing notarization does not grant access to write operations, admin endpoints, or other users' data. Notarization provides structural guarantees (well-formedness, boundedness); execution guards provide access control.

The re-validation on execute makes notarization a caching optimization (skip validation for known-good programs) rather than a security gate.

### T3: Injection via Cypher

A program contains Cypher that exploits string interpolation to inject unintended operations.

**Mitigations:**
- **Parameter substitution.** `$param` references are resolved by the executor and passed as query parameters (not string-interpolated into the Cypher text) where the database driver supports parameterized queries.
- **Write-keyword rejection.** Layer 2 scans Cypher strings for write keywords before execution.

**Residual risk:** The write-keyword check is a string-level scan, not a Cypher parser. It cannot distinguish between a keyword in a string literal (`WHERE c.label = "CREATE"`) and an actual write operation. This produces conservative over-rejection — it may reject valid read-only queries containing write keywords in string values. It will not under-reject actual writes because AGE also enforces write restrictions at the database level when read-only connections are used.

**Note on string interpolation:** `GraphQueryFacade` methods build queries using Python f-strings for `WHERE` clauses (see `query_facade.py:133`). When user-supplied values flow into facade queries, they must use parameterized queries (`params` argument) rather than string interpolation. This concern is independent of GraphProgram.

### T4: ApiOp endpoint abuse

A program uses `ApiOp` to call internal endpoints that perform mutations or access privileged data.

**Mitigations:**
- **Strict allowlist.** The validator maintains a set of permitted `ApiOp` endpoints. Only read-oriented internal service functions are allowed (vector search, source search, epistemic status queries, batch concept retrieval).
- **Internal dispatch.** `ApiOp` statements are dispatched as direct function calls within the API worker, not as HTTP requests. They inherit the executor's authentication context and cannot bypass API-level guards.
- **Parameter validation.** Each internal service function validates its own parameters independently of the program system.

**Residual risk:** If a new internal endpoint is added to the allowlist without review, it could expose write or admin operations. Review the allowlist whenever new endpoints are added.

### T5: Ownership and multi-tenancy

A user accesses, modifies, or executes another user's programs.

**Mitigations:**
- Ownership checks on read, update, and delete operations (Layer 3).
- Admin override requires `admin` or `platform_admin` role.
- Programs execute with the **caller's** permissions, not the **author's** permissions. If User A saves a program and User B executes it, User B's authentication and authorization apply.

**Residual risk:** There is no cross-user sharing model. Programs are either private (owned by a user) or system-provided (`owner_id = NULL`). A future grants system would need careful scoping to avoid confused-deputy scenarios.

### T6: Post-notarization mutation

A program is modified after notarization, bypassing validation.

**Current state:** The `PUT /query-definitions/{id}` endpoint allows the owner (or admin) to update the stored definition. Re-validation is not currently enforced on update. An owner can silently introduce write keywords, disallowed endpoints, or unbounded operations by editing a previously-notarized definition.

**Requirement:** Updates to `program`-type definitions MUST trigger re-validation. The update endpoint MUST reject the update if validation fails. As defense-in-depth, the executor SHOULD also verify a stored hash of the validated AST at execution time.

---

## Capability-based security

The AST type system functions as a capability-based security model:

- **The type definitions are the allowlist.** There is no deny-list to bypass. If an operation type does not exist in the discriminated union, it cannot be expressed.
- **New capabilities require explicit type changes.** Adding a new operation type (e.g., `StreamOp`, `BatchWriteOp`) requires modifying the AST schema, updating the validator, and updating the executor. Capabilities cannot be added through configuration alone.
- **Conditions are a closed set.** The `Condition` union defines exactly which tests can be performed against W. Adding new condition types requires a schema change.

The security surface is defined by the AST schema. A security review of the system should start with the type definitions and ask: can any expressible program cause harm? Any new type addition must be evaluated against this question.

---

## What the system guarantees

1. **Structural well-formedness.** Notarized programs have valid operators, valid operation types, and all required fields.
2. **No write operations.** Cypher statements in notarized programs do not contain write keywords. Combined with read-only database connections, writes are prevented at two independent layers.
3. **Bounded execution.** The maximum operation count is statically computable from the AST. The executor can determine the cost ceiling before running any statement.
4. **ApiOp endpoint restriction.** Only allowlisted internal endpoints can be called via `ApiOp`.
5. **Author attribution.** Every notarized program records who created it and when.
6. **Per-execution authentication.** Every program execution requires a valid OAuth token. Programs execute with the caller's permissions.
7. **Audit trail.** Every Cypher statement is logged via `QueryAuditLog` with timestamp and namespace classification.

## What the system does not guarantee

1. **Runtime correctness.** A notarized program may return empty results, match non-existent concepts, or produce semantically meaningless output.
2. **Performance.** Individual queries may be slow. An unbounded `MATCH` with a high `LIMIT` can consume significant database resources. The program-level operation bound does not constrain individual query cost.
3. **Data freshness.** H may change between notarization and execution. Concepts may be deleted, relationships may be added. Programs do not lock H.
4. **Parameter semantic validity.** The validator checks that `$param` references resolve, but does not validate that parameter values are meaningful (e.g., `min_similarity: -5` passes parameter resolution).
5. **Cross-user sharing.** There is no mechanism for one user to grant another access to their programs. This is a future capability.
6. **Immutability after notarization.** Programs can be updated by the owner without re-validation. This is a known gap — see [T6](#t6-post-notarization-mutation).

---

## Implementer requirements and recommendations

1. **Re-validate on update (MUST).** When a `program`-type definition is updated via `PUT /query-definitions/{id}`, re-run the validator. Reject the update if validation fails. Without this, the notarization provides no write-safety guarantee on stored programs.

2. **Re-validate on execute (MUST).** Do not trust that a stored program is still valid. Re-run validation before execution, or verify a stored hash of the validated AST. This is already implemented in `programs.py` but must be maintained.

3. **Route all Cypher through the facade.** The program executor must use `GraphQueryFacade` for all Cypher execution, not `client._execute_cypher()` directly. This ensures namespace safety and audit logging.

4. **Use parameterized queries.** When substituting `$param` values into Cypher, pass them as query parameters to the database driver, not via string interpolation.

5. **Set `statement_timeout`.** Configure PostgreSQL `statement_timeout` for the program executor's database sessions to bound individual query runtime.

6. **Log program execution.** In addition to per-statement query audit logs, log program-level events: which program was executed, by whom, with what parameters, and the resulting step log.

7. **Review the ApiOp allowlist.** When adding new internal endpoints, evaluate whether they should be accessible via `ApiOp`. Default to exclusion.
