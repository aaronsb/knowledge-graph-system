---
status: Draft
date: 2026-05-31
deciders:
  - aaronsb
  - claude
related:
  - ADR-714
  - ADR-400
  - ADR-704
---

# ADR-705: Session Visibility and Declarative Capability Gating

## Context

The web application does not visibly reflect being logged out, and — more
dangerously — it cannot reliably *detect* a session that expired mid-use. A user
can navigate the entire nav bar, toggle controls, and form a false impression of
being logged in. The originating complaint: someone whose session has expired (or
who never logged in) keeps clicking around, and the app neither says so nor
behaves differently, which is misleading and invites inconsistency.

A codebase verification found three concrete structural gaps:

| Gap | Detail | Source |
|-----|--------|--------|
| **No 401 response interceptor** | `client.ts` attaches the bearer token on requests but has no response handler. A token that expires mid-session produces a raw per-call error; the app still believes it is authenticated. | `web/src/api/client.ts:65-76` (request interceptor only) |
| **`isAuthenticated: false` collapses two states** | "never logged in" and "expired" are indistinguishable, so the UI cannot show a quiet "Sign in" for one and a loud "Your session expired" for the other. Expiry is only checked proactively on app mount via `checkAuth()`; there is no background detection. | `web/src/store/authStore.ts` (`isTokenExpired(expires_at, 60)`, `checkAuth`, `refreshToken`) |
| **No capability gating layer** | Routes are unguarded; 20+ nav items are fully navigable. Only `HomeWorkspace` and `AdminDashboard` hand-roll `if (!isAuthenticated)`. Every new component re-invents auth-checking or forgets it. | `web/src/App.tsx`, `web/src/components/home/HomeWorkspace.tsx`, `web/src/components/admin/AdminDashboard.tsx` |

The permission model already exists: `authStore` exposes `hasPermission(resource,
action)` and `isPlatformAdmin()` over a `can['resource:action']` map loaded after
login (ADR-400). What is missing is (a) an explicit session-status notion, (b)
detection of mid-session expiry, and (c) a declarative way to consume both so
components don't each re-solve gating.

A prior decision (this session) chose the **browsable + read-only** model: keep
the nav navigable for discoverability, but make mutating controls visibly inert
when the user cannot act, with ambient treatment that makes logged-out state
unmistakable.

This ADR is the **companion to ADR-704**: ADR-704 defines *what* user-owned
resources are dispensed and *where* (preferences / admin surfaces); this ADR
defines the session-awareness and gating primitives that decide *whether* those
controls are live. ADR-704's `backing: server | device` field keys directly on
the session status defined here. Neither ADR is complete without the other.

## Decision

### 1. Canonical session status

Add a derived selector to `authStore`:

```
sessionStatus: 'anonymous' | 'authenticated' | 'expired'
```

- **`anonymous`** — no stored credentials; the user has never logged in (or has
  explicitly logged out).
- **`authenticated`** — a valid, non-expired token is present.
- **`expired`** — credentials existed but are gone, past expiry, or rejected by
  the server, and refresh did not (or cannot) restore them.

This replaces the boolean `isAuthenticated` collapse for *presentation*
purposes. The distinction is the whole point: `anonymous` gets a quiet "Sign in"
affordance; `expired` gets a loud, interrupting signal because the user's mental
model says "I'm logged in" and must be corrected.

### 2. Global 401 response interceptor (the keystone)

Add a response interceptor to the axios client (`client.ts`). On a `401` for a
request that carried a token:

1. If a refresh token exists and this request has not already been retried,
   attempt a **single** token refresh and replay the original request.
2. If refresh fails or there is no refresh token, set `sessionStatus = 'expired'`,
   clear the access token, and let the UI react (§4).

Constraints, to avoid known failure modes:

- **No retry loops** — mark replayed requests so a second 401 does not recurse.
- **Exempt the auth endpoints** — the token/refresh/revoke routes must not be
  intercepted into a refresh of themselves.
- **Single-flight refresh** — concurrent 401s share one in-flight refresh and
  queue, rather than firing N refreshes.
- **SSE streams** — job-progress streams pass the token as a query param
  (`client.ts:755`) and cannot use this interceptor; they detect auth failure on
  the stream and route to the same `expired` transition.

This interceptor is what makes mid-session expiry *detectable at all*; without
it, none of the visible treatment below can fire.

### 3. Declarative capability primitives

Consume `sessionStatus` + the existing `can['resource:action']` map (ADR-400)
through a small, reusable API so components stop hand-rolling checks:

- **`useCapability(resource, action) → { can, reason }`** where `reason ∈
  { ok, anonymous, expired, forbidden }`. One hook answers "may this user do this
  right now, and if not, why," combining session and permission.
- **`<Gated resource action>`** — wraps a mutating control. When `!can`, renders
  the control disabled with a standard reason tooltip ("Sign in to …" / "Your
  session expired — sign in to continue" / "You don't have permission"). This is
  the primary primitive future components use; correct gating becomes the default,
  not a thing to remember.
- **`<RequireCapability>` / `<RequireAuth>`** — section wrappers that render
  children, a read-only/placeholder state, or (where appropriate) a sign-in
  prompt. Per the browsable + read-only model, the default is render-with-gated-
  controls, **not** redirect-to-login.

The existing hand-rolled `if (!isAuthenticated)` blocks in `HomeWorkspace` and
`AdminDashboard` are refactored onto these primitives.

### 4. Ambient treatment, defined once

Drive a single chrome-level treatment off `sessionStatus`, defined once in
`AppLayout` rather than scattered:

- **`expired`** → a sticky, full-width banner ("Your session expired — sign in to
  continue"), the loud signal. A context-preserving re-auth modal is an optional
  enhancement.
- **`anonymous`** → a quiet, always-on cue: a muted/desaturated header and a
  "Viewing as guest" indicator, alongside the existing `UserProfile` "Login"
  affordance (top-right) which already flips between Login and the user menu.
- **`authenticated`** → normal chrome.

Because this is keyed on one derived value in one place, every page inherits
consistent logged-out treatment without per-page work.

### 5. Browsable + read-only navigation model

Nav and routes stay navigable (discoverability matters for a knowledge tool).
Gating happens at the control and ambient level, not by hiding nav or bouncing to
login:

- Mutating controls gate via `<Gated>` (disabled + reason).
- Reads are attempted; where they require auth, the failure routes through the
  401 interceptor into the `expired`/`anonymous` treatment rather than a raw
  error.
- A route-level `<RequireAuth>` wrapper exists for the rare page that genuinely
  cannot render anything useful unauthenticated, but it shows a sign-in prompt
  in place — it does not redirect.

### 6. Enforce adoption with a web-UI lint

The primitives only pay off if components actually use them; partial adoption
re-introduces the inconsistency this ADR removes. Rather than rely on memory,
add a web-UI lint (alongside the existing `scripts/development/lint/` family —
`docstring_coverage.py`, `lint_queries.py`) that makes adoption checkable:

- **Flag raw session reads in components** — direct `authStore.isAuthenticated`
  usage outside the sanctioned primitives, which is how the current hand-rolled
  checks crept in.
- **Flag un-gated mutating controls** — interactive elements whose handlers call
  a mutating API method but are not wrapped in `<Gated>` / guarded by
  `useCapability`.
- **Report adoption** — a count of gated vs. un-gated mutating call sites, so
  drift is visible over time.

The lint runs in the static-analysis set (no running platform needed) and wires
into CI with a `--check` exit code, the same way `adr lint --check` does. It
converts "the team must adopt this" from an aspiration into a gate.

## Consequences

### Positive

- Mid-session expiry becomes detectable and visible instead of surfacing as a
  raw error on the next click — the core safety gap is closed.
- `anonymous` vs `expired` are treated distinctly: quiet invite vs loud
  correction.
- New components get correct gating by wrapping a control in `<Gated>` — no
  re-solving auth visuals, which is the cross-cutting "future components don't
  worry about this" goal.
- ADR-704's dispensing surfaces get their read-only behavior for free via the
  shared `sessionStatus` and primitives.
- Consolidates the scattered, hand-rolled `isAuthenticated` checks.

### Negative

- The 401 interceptor has real edge cases (retry loops, single-flight refresh,
  SSE, auth-endpoint exemption) that must be implemented carefully.
- Introduces new shared primitives the team must adopt for the benefit to
  compound; partial adoption leaves inconsistency. Mitigation: the web-UI lint
  (§6) flags raw `isAuthenticated` reads and un-gated mutating controls, making
  adoption an enforceable gate rather than an aspiration.
- Ambient treatment is a visible UX change that needs design polish (banner,
  guest cue) to avoid feeling naggy.

### Neutral

- Nav remains fully browsable by design; this is a deliberate model choice, not
  an oversight.
- The permission map and `hasPermission` API are reused unchanged; this ADR adds
  session-awareness around them, not a new authorization model.

## Alternatives Considered

- **Redirect protected routes to login.** Simplest mental model. Rejected per the
  browsable + read-only choice: it hides the feature surface from prospective
  users and is heavier than a knowledge tool wants.
- **Hide authenticated nav items when logged out.** Cleanest visually, least
  discoverable. Rejected for the same reason.
- **Keep per-component `if (!isAuthenticated)` checks.** The status quo. Rejected:
  it cannot distinguish expired from anonymous, does not detect mid-session
  expiry, and re-invents gating in every component.
- **Background token-expiry polling instead of a 401 interceptor.** Detects
  expiry on a timer. Rejected as redundant and racy: the 401 interceptor reacts to
  the authoritative signal (the server rejecting the token) exactly when it
  matters; proactive `checkAuth()` on mount already covers the load-time case.
