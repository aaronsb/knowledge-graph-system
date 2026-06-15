---
status: Draft
date: 2026-06-09
deciders:
  - aaronsb
  - claude
related:
  - ADR-400
  - ADR-606
  - ADR-407
---

# ADR-401: Deterministic Security Enforcement Baseline

## Context

ADR-400 reconstructed and ratified the *operative* RBAC and endpoint-security
model after the 2026-05-28 audit, and the #431–#442 issue cluster closed the
concrete gaps. What remains is structural: the platform's security conventions
are upheld by discipline alone, and the 2026-06-09 consistency audit
(`docs/security/security-consistency-audit-2026-06-09.md`) demonstrated that
discipline drifts.

The concrete evidence, each item verified against the working tree:

1. The only security linter in CI (`lint_queries.py`) runs with `|| true` —
   it has never been able to fail a build (`.github/workflows/lint.yml:25`).
2. ~2,000 lines of auth/permission tests exist but are not executed by any
   workflow; they only run when a developer remembers `make test`.
3. Issue #439 fixed `get_current_user` → `get_current_active_user` across
   three route modules in May; `query_definitions.py` has the same defect
   today. A convention enforced by hand was re-broken (or missed) within two
   weeks of being established.
4. Two dormant Cypher-injection sites (`query_facade.py:375`,
   `age_client/query.py:404`) violate the codebase's own validated-
   interpolation pattern. The existing linter cannot see them — it checks
   label hygiene, not parameterization.
5. 155 `str(e)` occurrences in route files leak driver/AGE exception text to
   clients; the safe logging pattern exists in the same files.
6. No secret scanning, dependency auditing, or SAST runs anywhere.

Every one of these is a class of defect that a deterministic check — a grep, a
linter rule, a CI job — can detect with near-zero false positives. The
platform is approaching internet exposure (the motivation behind ADR-400);
conventions that matter for that exposure need to be machine-enforced, not
re-audited every few months.

## Decision

Adopt a **deterministic security enforcement baseline**: every security
convention the codebase already follows by hand gains a blocking automated
check. Conventions without a check are treated as undecided, not adopted.

The baseline consists of seven enforcement items, in priority order:

1. **Make `lint_queries.py` blocking in CI.** Remove `|| true`; correct its
   stale baseline annotations (the three "known unsafe" entries are hardcoded-
   label loops, actually safe).
2. **Extend `lint_queries.py` with an interpolation rule.** Flag f-string /
   `.format` / concatenation that builds `MATCH|WHERE|CREATE|MERGE` text
   interpolating variables that do not pass through the `_validate_*` helpers
   or hardcoded-literal iteration. The two dormant injection sites become the
   rule's first fixtures and are fixed in the same change.
3. **Error-detail hygiene rule.** Reject `HTTPException(... str(e) ...)` and
   f-string equivalents in `api/app/routes/`; burn down the 155 existing
   instances to a generic-detail + `exc_info=True` logging pattern.
4. **Route-contract lint.** Every route decorator declares `response_model=`
   (or sits on an explicit allowlist: 204s, redirects, streaming), and every
   endpoint carries either an auth dependency (`CurrentUser` /
   `require_permission`) or an explicit `# public:` marker citing the
   authorizing ADR. This converts "is this endpoint intentionally public?"
   from archaeology into grep, and structurally prevents recurrence of the
   #439-class regression.
5. **Run the auth test suite in CI.** A compose-based GitHub Actions job
   (Postgres + AGE service containers) executing `tests/api/` security
   markers on every PR.
6. **Infra config asserts.** CI fails if: prod compose publishes 5432/3900/
   3903; HSTS or the standard security headers are absent/commented in
   `nginx.prod.conf`; `.env.example` contains a non-placeholder secret. The
   API refuses to start outside `DEVELOPMENT_MODE` when `POSTGRES_PASSWORD ==
   "password"` or any secret matches `CHANGE_THIS`.
7. **Off-the-shelf hygiene.** gitleaks (secret scanning), pip-audit /
   npm audit / cargo-audit, and dependabot configuration. Wiring, not
   authoring.

Each item lands as its own PR, tracked in the `enforcement-baseline` issue
cluster. New security conventions introduced after this ADR must ship with
their enforcement check in the same PR.

## Consequences

### Positive

- Conventions survive maintainer gaps: the May→June `get_current_active_user`
  regression class becomes impossible to merge.
- "Intentionally public" becomes a greppable, ADR-cited marker rather than
  tribal knowledge.
- The existing 2,000-line auth test investment starts paying out on every PR
  instead of only on manual runs.
- Internet-exposure readiness becomes a CI status, not an audit project.

### Negative

- CI gets slower and stricter; the compose-based test job is the heaviest
  addition. Soft-failing checks that become blocking will occasionally block
  legitimate work until allowlists mature.
- Custom lint rules (items 2–4) are project-maintained code with their own
  bug surface.
- The 155-instance `str(e)` burn-down is real toil before item 3 can block.

### Neutral

- The route-contract marker convention (`# public:`) adds a small authoring
  cost per intentionally-public endpoint and requires documenting the four
  existing public config endpoints against their ADRs.
- Items are independent; partial adoption is coherent (priority order exists
  so the cheapest/highest-leverage items land first).

## Alternatives Considered

- **Periodic manual audits (status quo).** The May and June audits each found
  real defects, but the June audit also found a regression of a May fix —
  audits detect drift, they don't prevent it. Rejected as the sole mechanism.
- **Adopt a general SAST platform (Semgrep/CodeQL) instead of project
  linters.** Generic rules don't understand AGE Cypher-in-SQL strings, the
  `_validate_*` convention, or the `require_permission` dependency pattern —
  the highest-value checks here are project-specific. Off-the-shelf tools are
  adopted where they fit (item 7) rather than as the framework.
- **Enforce via code review checklists.** Solo-maintainer project with
  multi-month gaps and agent-driven development; checklists are discipline by
  another name. Rejected for the same reason as the status quo.
