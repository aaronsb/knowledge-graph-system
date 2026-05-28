# Endpoint Security Audit — Pre-Internet-Exposure Hardening

**Date:** 2026-05-28
**Scope:** All FastAPI endpoints (`api/app/routes/`), background workers (`api/app/workers/` + dispatch services), and the `kg` CLI surface (`cli/src/`), audited for correct authentication and authorization ahead of serving the platform on the open internet.
**Method:** Multi-agent audit workflow (`endpoint-security-audit`, 47 agents). The **operative RBAC model was reconstructed from the SQL migration chain (`schema/migrations/`) and the enforcement code**, *not* from the ADRs — the ADRs are stale (most are still `Proposed`) and several are contradicted by the implemented migrations. Every high/critical finding was adversarially re-verified against the code; the two criticals were additionally hand-verified.
**Status of this document:** canonical shared context for the `internet-hardening` issue cluster. Generated from workflow run `wf_6089d737-29a` (raw structured output retained locally, not committed — see Appendix).

---

## 1. Verdict — NOT READY for internet exposure

The endpoint surface has **one catastrophic root cause**, **one critical unauthenticated router**, and a **broad systemic authorization gap** where handlers authenticate but never authorize.

### Hard blockers (must close before exposure)

| # | Severity | Surface | Gap |
|---|----------|---------|-----|
| **1** | 🔴 critical | `POST /auth/register` | Public endpoint writes the **client-supplied `role`** (validator allows `platform_admin`) straight into `primary_role`. Anyone on the internet can self-provision a `platform_admin`. Defeats the entire RBAC model. |
| **2** | 🔴 critical | `/admin/models/catalog/*` (6 endpoints) | **Entire router has zero auth dependency** — anonymous catalog read, model enable/disable (extraction DoS), per-token price overwrite (corrupts cost-approval), outbound API amplification. |
| **3** | 🟠 high | `database.py` (`/database/query`, etc.) | Authenticated-only. Arbitrary Cypher **reads** reachable by any user; `database:execute` seeded `platform_admin`-only but never enforced at the route. |
| **4** | 🟠 high | All ingestion entry points + projection/polarity jobs | Auth-only; `ingest:create` never checked → **denial-of-wallet** via auto-approved LLM jobs. |
| **5** | 🟠 high | `documents/*`, `sources/*` | Raw original document bytes, base64 image bytes, and Garage storage keys returned with no permission/ownership check. |

> Both criticals were verified end-to-end against the source: `auth.py:80-122` + `models/auth.py:21-28` (BLOCKER 1); `models.py` imports no `Depends` and the router is wired at `main.py:533` with no dependency (BLOCKER 2).

### Systemic root cause

A large class of handlers depend only on `CurrentUser` / `get_current_active_user` and **never call `require_permission`, despite docstrings claiming they do**. `read_only` users — deliberately denied `graph:read` to keep them off graph surfaces — can reach all of it. A secondary pattern (`get_current_user` instead of `get_current_active_user`) lets **disabled accounts keep working** (artifacts, all `/programs/*`, some grants reads).

---

## 2. The operative RBAC model (reconstructed from SQL + code)

This is the **ground-truth yardstick** the audit measured against. It is derived from the migration chain and the Python enforcement path, which is authoritative — the ADRs are not (see §5).

### Roles & inheritance

Inheritance is resolved **at check time** by walking `kg_auth.roles.parent_role`:

```
platform_admin ──▶ admin ──▶ curator ──▶ contributor      (read_only is STANDALONE)
```

| Role | parent_role | Notes |
|------|-------------|-------|
| `read_only` | *(none)* | Standalone — nothing inherits it, it inherits nothing. Holds only `concepts:read`, `vocabulary:read`, `jobs:read{owner=self}`. **Lacks `graph:read`** by design. |
| `contributor` | *(none)* | Base of the chain. Content create/modify. Seeded baseline + 028 + 040 + 041. |
| `curator` | `contributor` | Approve/manage content. `parent_role` set by migration 029. |
| `admin` | `curator` | User/content mgmt, full job control, backups, **graph CRUD (040)**, **workers:manage (057)**, `sources:delete (054)`. |
| `platform_admin` | `admin` | Critical ops: `api_keys`/`embedding_config`/`extraction_config` writes, `backups:restore`, `rbac` write/create/delete, `database:execute`, `graph:execute`, `oauth_clients` full. Default `admin` user (id=1000) upgraded to `platform_admin` by migration 038. |

**No superuser bypass exists** — `platform_admin` is powerful only because migrations seed its grants. (Which is exactly why BLOCKER 1 is catastrophic: an attacker seeds *themselves* that role.)

### Enforcement mechanism

- **`require_permission(resource, action)`** → resolves `get_current_active_user` (valid, non-disabled OAuth token), then `PermissionChecker.can_user(...)`. Evaluates, in precedence order: explicit DENY → instance-scope → filter-scope (`owner=self`, `is_system=true`, prefix wildcards) → global grant → **inherited** grants (recursively walks `parent_role`). A grant is effective only if a matching `(held-or-ancestor role, resource, action, scope)` row with `granted=TRUE` exists and no DENY shadows it.
- **`require_role(*roles)`** → checks **only** the `primary_role` string, **no hierarchy**. Legacy/trap path: `require_role("admin")` would *reject* the seeded `platform_admin` user. Effectively dead in live routes.
- A few endpoints (jobs, workers) call `check_permission` / `JobPermissionChecker` in-function — same seeded-grant evaluation.
- **Properly protected** = handler forces authentication **and** an authorization decision whose `(resource, action)` pair **actually exists in the seeded grants**. A `require_permission` call for an *unseeded* pair can never pass (permanent 403) — itself a bug.

### Public-by-design (legitimately unauthenticated)

`GET /`, `GET /health`, `/docs|/redoc|/openapi.json`, the OAuth flow endpoints (`/auth/oauth/authorize|token|device|revoke|...`), and the three public config readers (`GET /vocabulary/config`, `GET /embedding/config`, `GET /extraction/config`). `POST /auth/register` is *on this list but dangerous* — see BLOCKER 1.

### Ownership/row-scoped resources (not role-gated)

`jobs` (by `user_id`, migration 020), `artifacts` (by `owner_id`, 035; **NULL = system-owned**), `query_definitions` (035), `resource_grants`/`groups` (034, ADR-082 — `has_access()` resolution), personal OAuth clients (scoped to `current_user` in code).

---

## 3. Findings (19, severity-sorted)

Each finding lists the affected endpoints, the concrete gap, and the specific remediation. `→ #NNN` marks an existing issue that already covers it.

### 🔴 Critical

**F1 — Public `/auth/register` accepts arbitrary role incl. `platform_admin`** *(route / cli / cross-cutting)*
`POST /auth/register`
`register_user` (`auth.py:80-122`) has no auth dependency and inserts the client-supplied role into `primary_role`. Only guard is `UserCreate.validate_role` (`models/auth.py:21-28`), which whitelists `admin` and `platform_admin`. Self-registered `platform_admin` → rbac/api_keys write, `database`/`graph:execute`, `backups:restore`, worker-lane control. The CLI's "admin only" `kg admin user create` is backed by this same open endpoint, so user creation is gated *nowhere*.
**Fix:** stop honoring a client-supplied role — hardcode `read_only`/`contributor` or use a `RegisterRequest` model with no role field; route privileged assignment through the gated admin `POST /users`; disable open registration for internet deployments. Regression test: `/auth/register` cannot produce `admin`/`platform_admin`. Repoint CLI `createUser` at the gated endpoint.

**F2 — Entire `/admin/models/catalog` router is fully unauthenticated** *(route)*
`GET /admin/models/catalog`, `POST .../refresh`, `PUT .../{id}/enable|disable|default|price`
`models.py` never imports `Depends`; router created with no `dependencies=` (line 27); wired at `main.py:533` with no router-level auth. `refresh` triggers outbound provider fetch + DB write; `enable/disable/default` = availability DoS; `price` overwrites per-token pricing feeding ingest cost-approval.
**Fix:** gate `GET` with `require_permission('extraction_config','read')` and all mutators with `require_permission('extraction_config','write')` (platform_admin), or seed a dedicated `models` resource. Test: anonymous `/admin/models/*` → 401/403.

### 🟠 High

**F3 — `database` router is authenticated-only** *(route)*
`POST /database/query`, `GET /database/stats|info|counters|epoch`, `POST /database/counters/refresh`
Every handler depends only on `CurrentUser`, no `require_permission`, despite docstrings claiming `database:read`/`execute`. `execute_cypher_query` (`database.py:438-442`) runs arbitrary Cypher; the safety guard blocks writes but **not arbitrary reads** → full-graph exfiltration by any authenticated (incl. self-registered) user. `refresh_graph_counters` mutates+commits (docstring claims `database:write`, an *unseeded* action).
**Fix:** `require_permission('database','execute')` on `query` + `counters/refresh` (do NOT use unseeded `database:write`); `require_permission('database','read')` on stats/info/counters; document `/database/epoch` as authenticated-by-design (it's on the polling allowlist).

**F4 — Graph query surface (`queries.py`) is authenticated-only** *(route)*
`POST /query/search|sources/search|related|connect|connect-by-search|cypher|polarity-axis|polarity-axis/jobs`, `GET /query/concept/{id}`
Zero `require_permission` in the file despite docstrings claiming `graph:read`. Returns descriptions, evidence quotes, full_text, source provenance, `ingested_by` user IDs. `POST /query/cypher` runs arbitrary read Cypher (`graph:execute` is platform_admin-only but unenforced). `/polarity-axis/jobs` enqueues + **auto-approves** worker jobs (up to 8 workers).
**Fix:** `require_permission('graph','read')` on all read/search/connect/polarity endpoints (excludes `read_only`); `require_permission('graph','execute')` on `/query/cypher`; add a job-creation gate + server-side clamp on the polarity job path.

**F5 — Ingestion entry points enforce authentication only → denial-of-wallet** *(route / worker)* → **#417**
`POST /ingest`, `POST /ingest/text`, `POST /ingest/image`
Depend only on `CurrentUser`, never call `require_permission('ingest','create')` though docstrings assert it. Seeded `ingest:create` (contributor only, 028) is unenforced → any authenticated principal (incl. `read_only`, or anonymous-then-self-registered via F1) enqueues LLM jobs, often `auto_approve=true`.
**Fix:** `require_permission('ingest','create')` on all three; disallow `auto_approve` for non-curator roles; per-user rate limiting. Pairs with the unwired per-provider semaphore (**#417**).

**F6 — Bulk raw-content exfiltration** *(route)*
`GET /documents/{id}/content`, `GET /sources/{id}/document|image`, `GET /sources/{id}`, `GET /sources`, `GET /documents`, `POST /query/documents/search|by-concepts`, `GET /documents/{id}/concepts`, `POST /documents/concepts/bulk`
`documents.py` and `sources.py` depend only on `get_current_active_user`, no permission/ownership check (sources router doesn't even import `require_permission`). Returns original document text, base64 image bytes, and internal `storage_key`/`garage_key`.
**Fix:** `require_permission('sources','read')` on content/source endpoints; `require_permission('graph','read')` on metadata/search/linkage; restrict returning internal storage keys to admins; track deferred ownership scoping.

**F7 — Anonymous full-graph scan via `GET /vocabulary/category-flows`** *(route)*
The **only zero-dependency endpoint in the API** — `get_category_flows` (`vocabulary.py:1380`) takes no params, no `CurrentUser`, no `Depends`. Runs two full-graph scans, returns totals + full inter-category flow matrix to anonymous callers.
**Fix:** add `current_user: CurrentUser` + `Depends(require_permission('vocabulary','read'))`.

**F8 — Projection regenerate enqueues auto-approved expensive cross-ontology jobs** *(route)*
`POST /projection/{ontology}/regenerate`
Depends only on `CurrentUser` (`projection.py:228-394`). Any user can fetch all concept embeddings cross-ontology (`__all__`), compute t-SNE/UMAP, persist an artifact, and enqueue+auto-approve a job. No `graph:create/write` check.
**Fix:** `require_permission('graph','create')`; per-ontology ownership scoping for `__all__`; clamp the work.

**F9 — Web jobs view drops to "could not verify credentials" — inconsistent session invalidation** *(cross-cutting)* → **#419**
Jobs-polling view surfaces a 401 after extended watching while other tabs stay navigable — half-authenticated state, no global 401 interceptor, divergent token lifetimes.
**Fix:** global 401 interceptor forcing uniform re-auth; reconcile token lifetimes. Tracked by **#419** (add these acceptance criteria there).

### 🟡 Medium

**F10 — Graph/projection read+delete lack `graph:read`/`graph:delete`** *(route)*
`GET /projection/{ontology}`, `DELETE /projection/{ontology}`, `GET /projection/algorithms`
`get_projection` returns full coords with no `graph:read`; `invalidate_projection` deletes the cache with no `graph:delete` (`read_only` can force expensive recompute — DoS, recomputable cache).
**Fix:** `require_permission('graph','read')` on reads; `require_permission('graph','delete')` on invalidate.

**F11 — Ontology read endpoints lack `ontologies:read`** *(route)*
`GET /ontology/`, `/ontology/proposals`, `/ontology/proposals/{id}`, `/ontology/{name}`, `/{name}/node|files|scores|candidates|affinity|edges`
Take only `CurrentUser` though sibling mutators correctly gate on `ontologies:write` and annealing endpoints on `ontologies:read`. Exposes counts, file paths, source_ids, proposal reasoning/scores, cross-ontology affinity to `read_only`.
**Fix:** `Depends(require_permission('ontologies','read'))` on all ten.

**F12 — Artifact delete/regenerate: disabled-check bypass + NULL-owner guard bypass + auto-approve** *(route)*
`DELETE /artifacts/{id}`, `POST /artifacts/{id}/regenerate`
Both use `get_current_user` (no `disabled` check). Ownership guard `if owner_id is not None and owner_id != user_id` is **skipped when owner_id is NULL** (system-owned) → any user can delete/regenerate system artifacts. `regenerate` auto-approves a job with no gate.
**Fix:** switch to `get_current_active_user`; restructure guard so NULL-owner artifacts are admin-only; gate the regenerate enqueue.

**F13 — `grants.py` reads use `get_current_user` with no authZ → user enumeration + ACL disclosure** *(route)*
`GET /groups`, `GET /groups/{id}/members`, `GET /resources/{type}/{id}/grants`
No `disabled` check, no permission/ownership gate, while sibling mutators verify ownership. `/groups/{id}/members?include_implicit=true` on the public group returns every non-system user; `/resources/.../grants` returns full ACLs.
**Fix:** `require_permission('rbac','read')` or the ownership gate the mutators use; switch to `get_current_active_user`.

**F14 — `/programs/*` use `get_current_user` → disabled accounts can still notarize/execute** *(route / worker)*
`POST /programs`, `POST /programs/validate`, `POST /programs/execute`
All use `get_current_user` (`programs.py:39,54,135,152,330,396`) — no `disabled` check. Disabled-but-tokened user can notarize/execute server-side program ASTs. Execution is read-only-safe and writes are self-scoped, so this is an auth-state bypass + compute consumption, not graph mutation.
**Fix:** switch all to `get_current_active_user`; consider a per-user quota.

**F15 — Dangling/misleading CLI paths and incorrect RBAC role guidance** *(cli)*
`client.ts:1314` `resetDatabase()` POSTs to removed `/admin/reset` (404); `auth-client.ts:135` `login()` POSTs to removed `/auth/login` (ADR-054); `database.ts` labels the group "read-only" though `db query` runs mutating Cypher; `rbac.ts` help claims reads need "admin or curator" and mutations need "admin", but `rbac:read` = admin/platform_admin (curator vestigial) and `rbac:create/write/delete` = **platform_admin only** → operators mis-provision and hit persistent 403s.
**Fix:** remove dead `resetDatabase()`/`login()`/`AuthChallenge`; relabel the database group; correct all `rbac.ts` strings; add a shared pre-flight `requireAuth` to privileged groups.

### 🟢 Low

**F16 — Vocabulary read endpoints lack `vocabulary:read`** *(route)* — `GET /vocabulary/status|types|category-scores/{type}|similar/{type}|analyze/{type}|epistemic-status|epistemic-status/{type}`. Doc-vs-code gap, low sensitivity. Fix: `Depends(require_permission('vocabulary','read'))`.

**F17 — `GET /ingest/image/health` is fully unauthenticated** *(route)* — `ingest_image.py:311-344` exposes GPU/CPU device, VRAM, model info, vision providers anonymously. Fix: require `CurrentUser` or `require_permission('admin','status')`.

**F18 — `admin_workers` cancel bypasses `JobPermissionChecker`** *(worker)* — `POST /admin/workers/jobs/{id}/cancel` checks only `workers:manage` (admin) then cancels any running job, so an admin can cancel system-lane jobs that `jobs:cancel{is_system}` reserves for platform_admin. Bounded (admin is trusted). Fix: document the supersession (ADR-100) or cross-check `is_system`.

**F19 — `oauth_clients:write` is platform_admin-only by accident** *(cross-cutting)* — `PATCH /oauth/clients/{id}`, `POST .../rotate-secret`, `DELETE /oauth/tokens/{hash}`. Migration 028 gives admin `create/delete` but not `write`, so admin is locked out of PATCH/rotate/delete-token. Likely unintended product gap. Fix: seed `oauth_clients:write` for admin, or document as platform_admin-only.

---

## 4. Worker & CLI specifics

**Workers** — the worst worker finding *is* F1 (self-registered platform_admin → full worker-lane control: disable lanes, cancel any job, reprioritize the queue). F5 (ingestion trigger) and F14 (disabled-account program execution) also bear on workers. **Cleared:** `source_path` is provenance metadata only — workers write received *bytes* to a tempfile and never `open()` a client-supplied path, so the ADR-062 path-traversal concern does **not** apply server-side (the allowlist correctly lives client-side in the MCP server). Keep that invariant if a future "ingest by server path" feature is added.

**CLI** — coherence gaps, all folded into F15: the "admin only" `kg admin user create` is illusory (backed by open `/auth/register`); the "read-only" `database` group runs mutating Cypher; `rbac.ts` role guidance is wrong; dead `/admin/reset` and `/auth/login` paths remain; privileged groups lack a uniform pre-flight auth check (server still rejects, but UX is inconsistent).

---

## 5. ADR drift — the docs are stale, the migrations are truth

The user's instinct was correct: the migration chain is the operative model and the ADRs have drifted. Note that **ADR-017/028/060/074 are still `Proposed`** and **ADR-027 is `Superseded`** — these are stale *proposals*, not drifted accepted decisions, which the migrations quietly overran. **Six confirmed divergences:**

| ADR | Claim | Reality |
|-----|-------|---------|
| **060** Endpoint Security | 3 levels PUBLIC/USER/ADMIN via `require_role("admin")`; all `/auth/*` public | `require_role` is hierarchy-blind dead code that would *reject* the seeded `platform_admin`. Live model is `require_permission` + seeded grants + `parent_role` inheritance. `/auth/*` is not all public (`/users/*`, oauth client mgmt gate on permissions). |
| **074** Platform Admin | admin/platform_admin split removes critical ops from admin | Migrations 037/040/057 **re-granted** `backups:restore`, full graph CRUD, and `workers:manage` to admin. |
| **027/074** User mgmt | user creation/role assignment is admin-gated | `POST /auth/register` is public and writes client-supplied role (validator allows platform_admin). **Code wrong, ADR right.** |
| **054** OAuth | legacy login + API-key auth removed | Mostly true (022 drops `api_keys`), but `get_api_key_user()` still queries the dropped table (dead code) and `OAuth2PasswordBearer` advertises `tokenUrl=/auth/login`. |
| **028** RBAC SQL fn | `kg_auth.has_permission()` is canonical, hierarchy-aware | SQL fn reads `user_roles` only, ignores `primary_role`, doesn't walk `parent_role` — would under-grant. Python `PermissionChecker` is authoritative. |
| **028** jobs resource | jobs = read/write/approve/delete | Migration 041 re-registered jobs as `read/cancel/delete`; baseline `jobs:write`/`approve` orphaned. Baseline `roles`/`resources` superseded by `rbac`. |

### Re-baselining the auth-security ADR domain

Per the user's framing — *"ADRs are like SQL migrations; eventually you find the sum of all the docs and write a clean base."* The recommended approach:

1. **Author a new baseline ADR in the Auth/Security domain (`ADR-4xx`).** The current auth ADRs (017/027/028/031/054/060/062/074/082) use legacy sub-100 numbering; `adr.yaml` reserves **400–499** for Auth/Security, currently empty. The baseline should document the *operative* model from §2 (seeded grants + `PermissionChecker` inheritance, the `require_permission` convention, the public-by-design list, ownership scoping) as the single source of truth.
2. **Supersede** the drifted proposals (017/027/028/060/074) — mark them `Superseded by ADR-4xx`, preserving them as history (don't delete).
3. **Fold or reference** the still-accurate accepted ADRs (031 encrypted keys, 054 OAuth, 082 user-scoping) — keep accepted, cross-reference from the baseline.
4. **Clean up the orphaned/vestigial grants** (`jobs:write`/`approve`, `roles`/`resources` resources) via a migration so the seeded model and the baseline ADR agree.

This is itself an architectural decision and should go through the ADR workflow (`docs/scripts/adr`) — not a silent rewrite.

---

## 6. Phased remediation plan

**Phase 0 — Stop the bleeding (blockers; do first, smallest surface):**
- F1: clamp `/auth/register` role server-side + regression test. *(One-line-ish fix, highest impact.)*
- F2: add auth deps to the `/admin/models/catalog` router + test.

**Phase 1 — Close the systemic authZ gaps (high):**
- F3 database, F4 graph queries, F6 documents/sources, F7 vocabulary-anonymous, F8 projection regenerate, F5 ingestion (`ingest:create` + auto-approve clamp).

**Phase 2 — Consistency & hardening (medium):**
- F10–F14: projection/ontology read gates, `get_current_user`→`get_current_active_user` (artifacts, programs, grants), NULL-owner artifact guard.
- F15: CLI coherence (dead paths, role guidance, pre-flight auth).

**Phase 3 — Low-severity & polish:**
- F16 vocabulary reads, F17 image health, F18 worker-cancel scoping, F19 `oauth_clients:write`.

**Phase 4 — ADR re-baseline (§5):**
- Author `ADR-4xx` operative baseline; supersede drifted proposals; migration to clean orphaned grants.

**Cross-references:** #419 (folds F9 — add the 401-interceptor criteria there), #417 (concurrency semaphore — partial mitigation for F5), #386 (actor attribution for the audit trail — relevant once mutations are gated).

**Recommended after Phase 0–1 land:** re-run the `endpoint-security-audit` workflow as a regression check, and add tests asserting (a) `/auth/register` cannot mint admin/platform_admin and (b) anonymous calls to `/admin/models/*` are rejected.

---

## 7. Issue cluster

All remediation issues are tagged **`internet-hardening`** and linked from a tracking issue. See that label for the live list. This document is the common context each issue references.

---

## Appendix — Method & provenance

- **Workflow:** `endpoint-security-audit` (run `wf_6089d737-29a`), 47 agents, ~2.1M tokens, ~15 min wall-clock.
- **Pipeline:** (1) reconstruct operative contract from SQL+code; (2) per-route-file audit (28 files) + worker + CLI side-audits, measured against the seeded-grants table; (3) adversarial verify of every high/critical finding (skeptic default, false-positives stripped); (4) synthesis.
- **Ground-truth note:** the contract was deliberately derived from `schema/migrations/` + `dependencies/auth.py` + `lib/permissions.py`, with ADRs used only as a cross-check. 65 seeded permission grants were enumerated. The full structured output (all 65 grants, per-file audits, verifier verdicts) is retained locally as a workflow artifact and can be regenerated by re-running the `endpoint-security-audit` workflow; it is intentionally not committed here to keep this document the curated summary.
