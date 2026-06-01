---
status: Draft
date: 2026-05-31
deciders:
  - aaronsb
  - claude
related:
  - ADR-031
  - ADR-034
  - ADR-054
  - ADR-067
  - ADR-075
  - ADR-083
  - ADR-400
  - ADR-705
---

# ADR-704: Unified User-Scoped Resource Dispensing

## Context

This started from a UI observation — the web application doesn't visibly
reflect being logged out — and unwound into a more fundamental gap: the things
that *belong to a user* are dispensed inconsistently, even though most of them
are already stored and access-controlled on the server.

A codebase verification (below) found that the backends largely **already
exist**. What is missing is not storage — it is a consistent *location* and
*way* these user-owned elements are dispensed: listed, read, edited, and
access-controlled, in one place for a user ("what is mine") and one place for an
admin ("what is everyone's").

### What already exists (verified)

| Element | Backend status | Where |
|---------|----------------|-------|
| **Credentials / API grants** | **Fully built.** `oauth_clients` table; self-service `GET/POST/DELETE /auth/oauth/clients/personal` + secret rotation; admin client/token routes; MCP uses the builtin `kg-mcp` confidential client. Secrets bcrypt-hashed, tokens SHA-256, revocation + rotation present. | `schema/migrations/022_oauth_client_management.sql`; `api/app/routes/oauth.py`; web `AccountTab` already lists a user's own clients |
| **Saved queries / programs / block diagrams** | **Fully built.** `kg_api.query_definitions` (`owner_id`, typed: `block_diagram`, `polarity`, `exploration`, `program`, `cypher`, `projection`); full CRUD with owner-or-admin filtering + pagination. | `schema/migrations/035_artifact_persistence.sql`; `api/app/routes/query_definitions.py`; web `queryDefinitionStore`, `SavedQueriesPanel`, `blockDiagramStore` |
| **Computed artifacts** | **Built.** `kg_api.artifacts` (`owner_id`, 19 types, Garage/inline payloads). | `api/app/routes/artifacts.py`; web `artifactStore` |
| **owner-or-admin access** | **Exists but scattered.** `verify_resource_ownership()` (best reusable helper), `JobPermissionChecker`, `kg_auth.resource_grants` + `has_access()` (migration 034), and the same inline `owner_id == user_id or admin` check repeated across routes. | `api/app/routes/grants.py:34`; `api/app/lib/job_permissions.py`; `schema/migrations/034_user_scoping_groups.sql` |
| **Admin surface** | **Built, global/resource-oriented.** `AdminDashboard` has Account, Users, Roles, System, Ontology, Vocabulary tabs. | `web/src/components/admin/AdminDashboard.tsx` |
| **Settings** (default ontology, ingest defaults, etc.) | **Not on the server.** localStorage-only, per-browser, no management surface. | web `usePreferencesStore`, `useThemeStore` |

So the contract this ADR defines is **retrofitted onto a pattern the codebase
already implements** (`owner_id` + list-by-owner + owner-or-admin), not invented.

### Why this is adjacent to the logged-out-visibility problem

The dispensing surfaces are exactly where authentication state becomes
*consequential* rather than cosmetic. "Show me what is mine" only means something
relative to *who I am right now* — anonymous, authenticated, or expired. A
server-backed resource must visibly gate to read-only when the session is gone; a
device-backed one stays editable. The visible-logged-out treatment and the
dispensing surface are two faces of one UX. That is why an instinct about the
front door led straight here.

This ADR is **paired** with the companion capability-gating decision
(forthcoming, `ui` domain): that ADR defines the `anonymous | authenticated |
expired` session status and the `<Gated>` / `useCapability` primitives; this ADR
defines what gets gated and where it is shown. Neither is complete without the
other.

## Decision

### 1. Separate two axes: storage (heterogeneous) vs dispensing (uniform)

| Axis | Stance |
|------|--------|
| **Storage** | Stays per-type and appropriate, and mostly **already exists**. Settings → new validated DTO. Theme → `localStorage` (ADR-075). Credentials → `oauth_clients`/encrypted-OAuth (ADR-031/054). Saved items → `query_definitions`/`artifacts` (ADR-083). **No unification here, by design.** |
| **Dispensing** | Unified. One provider contract, one consolidated access policy, two rendering surfaces. **This is the decision.** |

### 2. The `UserScopedResource` provider contract

Each dispensable thing implements one thin contract — a *convention*, not a
framework. It standardizes enumeration, access, and presentation while delegating
storage to whatever already backs it:

```
UserScopedResource {
  kind:    string                         // "settings" | "theme" | "credentials" | "saved-queries" | "artifacts" | ...
  backing: "server" | "device"            // where it lives — varies per kind, and that is fine
  list(userId)            → item[]
  read(userId, itemId)    → item
  write(userId, item)                      // create/update; validated by the provider
  delete(userId, itemId)
  access:  owner-or-admin                  // uniform policy (see §4)
  present: { label, panel }                // how it renders in the shared UI
}
```

Most providers wrap existing endpoints/stores: the saved-queries provider is a
thin adapter over `queryDefinitionStore`, the credentials provider over the
`/auth/oauth/clients/personal` routes, the theme provider over `localStorage`.
The `backing` field is what the gating surface keys on: `server` providers gate
read-only when unauthenticated/expired, `device` providers stay editable.

### 3. Two surfaces, one registry

Providers register into a single registry; exactly two surfaces render it:

- **Preferences view** — every provider scoped to the current user, where they
  are the owner. This is where a user sees and manages *what is mine* — including
  (newly) listing and revoking their own credentials/grants. `AccountTab` is the
  existing seed of this surface (it already lists a user's own OAuth clients).
- **Admin view** — every provider across all users, gated by admin. The existing
  `AdminDashboard` is the host; this adds a per-user drill-down (select a user →
  see their providers), which does not exist today.

Adding a new dispensable kind means implementing the contract once; it then
appears in both surfaces automatically, with correct access. No component
re-solves listing, placement, or access control.

### 4. Uniform access: consolidate the scattered owner-or-admin checks

The owner-or-admin rule already exists in at least three forms
(`verify_resource_ownership()`, `JobPermissionChecker`, repeated inline checks).
This ADR consolidates them into **one** reusable helper (e.g.
`api/app/lib/owner_access.py`), built on the ADR-400 baseline and aware of the
system-owner (`owner_id` NULL / system user) convention, and routes the
dispensing layer through it. Provider-specific authorization (e.g. a credential's
revocation semantics) still lives in the provider. The `resource_grants` /
`has_access()` infrastructure (migration 034) remains available for
group/instance grants beyond simple ownership.

### 5. First new provider — settings (server-backed, validated)

The only element without a server backend. The settings provider is the
reference `server`-backed implementation and resolves the original per-browser
problem.

- **Storage (new):** one validated JSONB blob per user. The server owns the shape
  via a Pydantic `UserSettings` model; every write is validated and
  unknown/invalid properties are rejected (`422`). Adding a setting is a one-field
  model edit, not a DB migration.

  ```sql
  CREATE TABLE kg_auth.user_settings (
      user_id    UUID PRIMARY KEY REFERENCES kg_auth.users(id) ON DELETE CASCADE,
      settings   JSONB NOT NULL DEFAULT '{}'::jsonb,  -- server-validated shape
      revision   INTEGER NOT NULL DEFAULT 0,          -- concurrency token
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
  );
  ```

- **Dispensing:** `list/read/write` map to `GET/PUT /users/me/settings` (admin
  surface `/admin/users/{id}/settings`), alongside the existing `/users/me/*`
  endpoints in `api/app/routes/auth.py`. `PUT` validates against `UserSettings`
  and replaces the whole object; `If-Match: <revision>` guards concurrent writes
  with a `409`.

- **Contents** (the agreed server-synced set — these *follow the person*): default
  ontology, ingest tuning (chunk size, overlap, processing mode), job
  notifications, a small set of UI preferences, and auto-approve.

- **Defaults-only boundary:** the server never *acts* on a stored setting — it may
  pre-fill a form, but consequential behavior (notably ingest **auto-approve**) is
  always driven by an explicit, separately-validated request parameter, never read
  from the settings blob. Auto-approve travels as a convenience default; it never
  silently authorizes a job.

Device-shaped preferences (theme, fonts, color, compact mode, animations) are a
separate `device`-backed provider and stay in `localStorage`.

### 6. Non-goal — storage unification (esp. secrets)

This ADR moves no element's storage. **Credentials and grants are never stored in
the settings DTO.** The credentials provider lists and revokes against the
existing `oauth_clients`/OAuth machinery (ADR-031/054); the preferences view only
*surfaces* them. Each provider's backing is its own concern.

### 7. Scope of new work

Because the backends largely exist, the build is mostly unification:

- **New:** the settings provider (table + `UserSettings` model + `/users/me/settings`).
- **New:** one consolidated `owner-or-admin` helper, replacing scattered checks.
- **New (UI):** the provider registry + the two surfaces, reusing `AccountTab`,
  `SavedQueriesPanel`, and existing stores; finishing the credentials management
  UI; the per-user admin drill-down.
- **Reused as-is:** `oauth_clients` + personal-client routes, `query_definitions`
  + `artifacts` + their routes/stores, `resource_grants`/`has_access()`.
- **Deferred / separate ADRs if pursued:** standardizing `owner_id` NULL
  semantics across all tables; adding save support to Force Graph / Catalog
  explorers; OAuth scope enforcement.

### 8. Keep the registry honest: an enumeration check

A registry is where unused abstraction hides — a provider registered once and
never questioned is how a thin convention silently becomes a framework nobody
needs. To keep it honest, add a make target / lint (alongside
`scripts/development/lint/`) that **enumerates every registered provider** — its
`kind`, `backing`, the surfaces it appears in, and (where cheap to detect)
whether it is actually rendered/used.

The enumeration serves two purposes at once:

- **"We did X"** — a single, current list of what dispensing surfaces expose, as
  provenance and onboarding context (useful after a multi-month gap).
- **"Do we need X?"** — by making every provider visible in one place, it turns
  each into a standing question. A provider that earns its place stays; one that
  no longer does is obvious and can be removed. The check is the forcing function
  that prevents silent accumulation.

Like the §7 work, this is small and static; it wires into CI with a `--check`
exit code the same way `adr lint --check` does.

## Consequences

### Positive

- One place a user manages everything that is theirs; one place an admin manages
  everyone's — including credentials/grants, which have no user surface today.
- New user-owned resources implement one contract and appear, correctly
  access-controlled, in both surfaces — no re-solving listing/placement/access.
- Most of the work is wrapping existing, verified backends, not greenfield —
  materially lower risk than the original "build server preferences" framing.
- Consolidating the scattered owner-or-admin checks removes a real source of
  drift and inconsistency.
- The dispensing surface and the logged-out-visibility treatment become the same
  UX, defined once.

### Negative

- A registry + provider abstraction is new surface; over-engineered, it could
  become a framework nobody needs. Mitigation: keep it a thin convention, grow it
  provider-by-provider as real providers land, and run the §8 enumeration check
  so every registered provider stays a standing "do we still need this?" question
  rather than silent accumulation.
- Two rendering surfaces (preferences, admin) must stay in step as the contract
  evolves.
- Consolidating access checks touches many routes; must be done carefully to
  avoid changing existing authorization behavior.
- Couples to the companion capability-gating ADR; should not land before it.

### Neutral

- Device-backed providers remain editable while unauthenticated (they are local);
  server-backed ones gate read-only. The contract carries this via `backing`.
- The grant/group infrastructure (migration 034) is available but not required by
  this ADR; simple ownership covers the initial providers.

## Alternatives Considered

- **Unify storage too (one per-user store for everything).** Superficially
  simpler. Rejected outright: it would put secrets in a settings blob, discard the
  encrypted/OAuth model (ADR-031/054) and the existing `query_definitions`/
  `artifacts` tables, and force one shape onto values with very different
  validation, size, and security needs.
- **Just add server-side preferences, nothing more (original ADR-704 scope).**
  Solves settings but leaves the actual goal — a unified location/way to dispense
  *all* user-owned elements — unaddressed, and ignores that credentials and saved
  items already have backends needing only a surface.
- **Keep everything in `localStorage`, label it clearly.** Smallest change;
  resolves only the perception bug. Rejected because it gives neither cross-device
  settings nor any management surface for the elements that already persist
  server-side.
- **A heavyweight per-user "profile service".** Overkill for a single-tenant,
  self-hosted platform; the thin provider convention gets the unification without
  standing infrastructure.
