---
status: Accepted
date: 2026-05-28
deciders:
  - aaronsb
  - claude
related:
  - ADR-017
  - ADR-027
  - ADR-028
  - ADR-031
  - ADR-054
  - ADR-060
  - ADR-074
  - ADR-082
---

# ADR-400: Operative RBAC and Endpoint Security Baseline

## Context

The authentication and authorization design of this platform accreted across nine
legacy-numbered ADRs (ADR-017, 027, 028, 031, 054, 060, 062, 074, 082) and a long
chain of SQL migrations. Over time the **documents drifted from the implementation**.
Most of the governing ADRs were never accepted — ADR-017, 028, 060, and 074 are still
`Proposed`, ADR-027 is `Superseded` — yet the system shipped a concrete RBAC model
seeded by migrations and enforced by Python code that quietly overran what those
proposals describe.

The 2026-05-28 endpoint security audit
(`docs/security/endpoint-security-audit-2026-05-28.md`), performed ahead of exposing
the platform on the open internet, reconstructed the **operative** model from the SQL
migration chain and the enforcement code (treating the ADRs only as a cross-check) and
confirmed six material divergences:

1. **ADR-060** documents three security levels enforced via `require_role("admin")`.
   In reality `require_role` checks only the `primary_role` string with no hierarchy —
   `require_role("admin")` would *reject* the seeded default admin (upgraded to
   `platform_admin` by migration 038). The live mechanism is `require_permission`
   against seeded grants with check-time `parent_role` inheritance.
2. **ADR-074** implies the admin/platform_admin split removed critical operations from
   `admin`. Migrations 037/040/057 re-granted `backups:restore`, full graph CRUD, and
   `workers:manage` back to `admin`.
3. **ADR-027/074** state user creation is admin-gated. In reality `POST /auth/register`
   is public and writes a client-supplied role (the validator permits `platform_admin`).
4. **ADR-054** is mostly accurate (legacy login + API-key auth removed) but residual
   dead surfaces remain (`get_api_key_user()` queries a dropped table;
   `OAuth2PasswordBearer` still advertises `tokenUrl=/auth/login`).
5. **ADR-028** presents `kg_auth.has_permission()` as the canonical, hierarchy-aware
   check. The SQL function ignores `primary_role` and does not walk `parent_role`; the
   authoritative path is the Python `PermissionChecker`.
6. **ADR-028** describes a `jobs` resource with `read/write/approve/delete`. Migration
   041 re-registered jobs as `read/cancel/delete` and orphaned the baseline
   `jobs:write`/`approve` grants; the baseline `roles`/`resources` resources were
   superseded by the `rbac` resource.

Numbering note: the legacy auth ADRs predate the domain numbering scheme. The
Auth/Security domain (400–499) is otherwise empty. This baseline is the first correctly
domain-numbered Auth/Security ADR, and a natural point to "find the sum" of the drifted
chain and write a clean base — the same discipline the SQL migrations follow.

## Decision

**This ADR is the single source of truth for the RBAC and endpoint-security model.**
Where any prior ADR conflicts with what follows, this ADR governs and the prior ADR is
superseded. The model below is descriptive of the *implemented* system (it documents
what the migrations and code do); divergences between code and this baseline are bugs to
be fixed against this document, tracked in the `internet-hardening` issue cluster.

### Roles and inheritance

Five roles. Inheritance is resolved **at check time** by walking
`kg_auth.roles.parent_role`:

```
platform_admin ──▶ admin ──▶ curator ──▶ contributor      (read_only is STANDALONE)
```

| Role | parent_role | Capability summary |
|------|-------------|--------------------|
| `read_only` | *(none)* | Standalone. Holds only `concepts:read`, `vocabulary:read`, `jobs:read{owner=self}`. Deliberately **lacks `graph:read`**. |
| `contributor` | *(none)* | Base of the chain. Content create/modify; `ingest:create`; `graph:read/create`. |
| `curator` | `contributor` | Approve/manage content (set by migration 029). |
| `admin` | `curator` | User/content management, full job control, backups (incl. `restore`), graph CRUD, `workers:manage`, `sources:delete`. |
| `platform_admin` | `admin` | Critical operations: `api_keys`/`embedding_config`/`extraction_config` writes, `backups:restore`, `rbac` create/write/delete, `database:execute`, `graph:execute`, `oauth_clients` full. Default `admin` user (id=1000) is upgraded here by migration 038. |

There is **no superuser bypass**. `platform_admin` is powerful only because migrations
seed its grants. This is a deliberate property: the role hierarchy and grants are data,
not hardcoded privilege.

### Enforcement mechanism

Authorization is **per-endpoint and in-function** — `main.py` wires routers with no
router-level dependencies, so every endpoint must declare its own auth.

- **`require_permission(resource, action[, resource_id_param, resource_context])`** is
  the canonical mechanism. It resolves `get_current_active_user` (a valid, non-revoked,
  non-expired OAuth access token mapping to a **non-disabled** user), then calls
  `PermissionChecker.can_user(...)`, which:
  1. resolves the user's roles: `primary_role` (+ its `parent_role` chain) plus any
     non-expired `kg_auth.user_roles` rows;
  2. evaluates, in precedence order: explicit **DENY** (`granted=FALSE`, always blocks)
     → instance-scoped grant → filter-scoped grant (`owner=self`, `is_system=true`,
     `prefix*` wildcards; all keys must match) → global grant → **inherited** grants
     (recursively walks `parent_role`).
- **`get_current_active_user`** (aliased `CurrentUser`) is the authentication floor. It
  enforces the `disabled` flag. `get_current_user` does **not** check `disabled` and
  must not be used to gate sensitive operations.
- **`require_role(*roles)`** is a **legacy/trap path**: it checks only the `primary_role`
  string with no hierarchy and must not be used for admin gating (it would reject
  `platform_admin`). Retained only for documentation/middleware examples; new code uses
  `require_permission`.
- The Python `PermissionChecker` is authoritative. The SQL `kg_auth.has_permission()`
  function is **non-operative** and must not be relied upon (it ignores `primary_role`
  and does not walk `parent_role`).

### Definition of "properly protected"

For internet exposure, an endpoint is properly protected only if its handler forces:

1. **Authentication** — depends (directly or transitively) on `get_current_active_user`;
   and
2. **Authorization** — for any state-changing or sensitive read, an authorization
   decision via `require_permission(resource, action)` (or an in-function
   `check_permission`/`JobPermissionChecker`) whose `(resource, action)` pair **is
   actually present in the seeded grants**.

A `require_permission` call referencing an **unseeded** `(resource, action)` pair can
never pass (permanent 403) and is a bug. An endpoint with no auth dependency at all is
unprotected and must appear on the public-by-design list below or it is a defect.

### Public-by-design endpoints

`GET /`, `GET /health`, `/docs|/redoc|/openapi.json`, the OAuth flow endpoints
(`/auth/oauth/authorize|login-and-authorize|device|device-status|token|revoke`), and the
three public config readers (`GET /vocabulary/config`, `GET /embedding/config`,
`GET /extraction/config`).

`POST /auth/register` is public **only for self-registration**. It **must not** honor a
client-supplied privileged role — self-registered accounts are clamped server-side to a
non-privileged role; elevated roles are assigned only through the authenticated,
`users:create`-gated admin path. (The current code violates this; see the
`internet-hardening` cluster.)

### Ownership / row-scoped resources

Some resources are scoped by row ownership in code rather than by a role grant: `jobs`
(`user_id`, migration 020), `artifacts` (`owner_id`, 035; **NULL = system-owned,
admin-only**), `query_definitions` (035), `resource_grants`/`groups` (034, via
`kg_auth.has_access()`), and personal OAuth clients (scoped to `current_user`).

### Relationship to other ADRs

- **Supersedes** (drifted/contradicted): ADR-017, ADR-027, ADR-028, ADR-060, ADR-074.
  Their historical context is preserved; their normative claims are replaced by this
  baseline.
- **Cross-references** (still accurate, remain in force): **ADR-031** (encrypted API key
  storage), **ADR-054** (OAuth 2.0 client management — modulo the residual dead surfaces
  it should be updated to acknowledge), **ADR-082** (user scoping and artifact ownership
  — the ownership model above), **ADR-062** (MCP file-ingestion security — the audit
  confirmed the client-side path allowlist is the correct trust boundary; workers never
  dereference client-supplied paths).

## Consequences

### Positive

- One authoritative description of the auth model, derived from and kept honest against
  the migrations + code, replacing five stale proposals.
- Gives reviewers and future contributors a concrete yardstick: "does this endpoint call
  `require_permission` with a seeded `(resource, action)` pair?" — directly checkable.
- Makes the `require_role`-vs-`require_permission` trap and the non-operative SQL
  `has_permission()` explicit, preventing reintroduction.
- Establishes the Auth/Security domain (400–499) with a clean baseline that subsequent
  auth ADRs extend rather than contradict.

### Negative

- Documenting the *implemented* model surfaces that the implementation currently
  violates parts of it (public-register role escalation, unauthenticated `models`
  router, authenticated-only data surfaces). This ADR sets the target; the code must be
  brought into compliance (tracked separately).
- Superseding `Proposed` ADRs that were never accepted is slightly unusual, but
  accurately reflects that they shaped real migrations and must be formally retired so
  they are not mistaken for current guidance.

### Neutral

- Orphaned/vestigial seeded grants (`jobs:write`/`approve`, the old `roles`/`resources`
  resources) should be cleaned up via a migration so the seeded data matches this
  baseline. Tracked in the `internet-hardening` cluster.
- A future migration may seed a dedicated `models` resource (currently the model catalog
  has no resource); until then `extraction_config` is the gating resource for it.

## Alternatives Considered

- **Update each drifted ADR in place.** Rejected: five separate edits would leave the
  reader to reconcile overlapping, partially-contradictory documents with no single
  authority. The drift is pervasive enough that a clean baseline is clearer — the same
  reason a SQL migration chain eventually gets a squashed baseline snapshot.
- **Write the ADR as aspirational (describe the *intended* model, not the implemented
  one).** Rejected: the entire failure mode being corrected here is documentation that
  describes intent while the code does something else. This baseline is deliberately
  *descriptive* of the operative system, with the gaps between code and baseline tracked
  as bugs to fix — not papered over as if already done.
- **Renumber the legacy auth ADRs into the 400–499 range.** Rejected: renumbering breaks
  inbound references and rewrites history. The legacy numbers are preserved; this
  baseline simply supersedes their normative content.
