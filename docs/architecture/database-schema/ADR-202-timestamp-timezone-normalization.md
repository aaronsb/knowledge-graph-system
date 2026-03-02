---
status: Proposed
date: 2026-03-02
deciders:
  - aaronsb
  - claude
related:
  - ADR-040
  - ADR-056
  - ADR-100
---

# ADR-202: Timestamp Timezone Normalization

## Overview

The database schema has a split personality on timestamp types. Approximately 75 columns use `TIMESTAMP WITH TIME ZONE` (correct), but 15 columns — concentrated in the job dispatch tables introduced or modified over several migrations — use bare `TIMESTAMP` (without time zone). PostgreSQL stores bare timestamps without UTC offset, and when serialized via JSON they lack a `Z` suffix. JavaScript's `new Date()` then interprets these as local time, producing wrong durations and negative elapsed times on any client not running in UTC.

This ADR normalizes all 15 bare `TIMESTAMP` columns to `TIMESTAMPTZ` and establishes the invariant: **all timestamps in the system are stored, transmitted, and interpreted as UTC. Clients are responsible for local-time display.**

## Context

### The Problem (observed 2026-03-02)

The Workers panel in the web UI displayed negative durations (e.g., `-21584s`) for active jobs on a fresh install. Root cause:

1. `kg_api.jobs.started_at` is `TIMESTAMP WITHOUT TIME ZONE`
2. PostgreSQL serializes it as `2026-03-02 18:45:12` (no offset, no Z)
3. FastAPI/Pydantic passes it through as-is in JSON
4. Browser JavaScript: `new Date("2026-03-02 18:45:12")` — parsed as **local time** (CST, UTC-6)
5. `Date.now() - localParsed` yields a 6-hour error, producing negative elapsed times

A client-side workaround (appending `Z` if missing) was applied to the CLI, web, and MCP formatter, but the real fix is ensuring the database emits proper `timestamptz` values.

### Audit Results

**15 bare `TIMESTAMP` columns across 5 tables:**

| Table | Column | Migration |
|-------|--------|-----------|
| `kg_api.jobs` | `created_at` | 009 |
| `kg_api.jobs` | `started_at` | 009 |
| `kg_api.jobs` | `approved_at` | 009 |
| `kg_api.jobs` | `completed_at` | 009 |
| `kg_api.jobs` | `expires_at` | 009 |
| `kg_api.scheduled_jobs` | `created_at` | 050 |
| `kg_api.scheduled_jobs` | `updated_at` | 050 |
| `kg_api.scheduled_jobs` | `last_run_at` | 050 |
| `kg_api.scheduled_jobs` | `next_run_at` | 050 |
| `kg_api.scheduled_jobs` | `disabled_at` | 050 |
| `kg_api.scheduled_jobs` | `last_error_at` | 050 |
| `kg_api.aggressiveness_profiles` | `created_at` | 050 |
| `kg_api.aggressiveness_profiles` | `updated_at` | 050 |
| `public.graph_metrics` | `created_at` | 016 |
| `public.graph_metrics` | `measured_at` | 016 |

**~75 columns already use `TIMESTAMPTZ`** — auth tables, embedding configs, ontology tables, etc.

### Python Datetime Patterns (related to ADR-056)

ADR-056 introduced `datetime_utils.py` with `utcnow()` and friends. However, adoption is incomplete (21 of 34 violations remain). Three competing patterns exist in the API:

| Pattern | Timezone | Correct? |
|---------|----------|----------|
| `datetime.now()` | Local (naive) | No |
| `datetime.utcnow()` | UTC (naive) | No |
| `datetime.now(timezone.utc)` | UTC (aware) | Yes |
| `datetime_utils.utcnow()` | UTC (aware) | Yes (preferred) |

With `TIMESTAMPTZ` columns, PostgreSQL + psycopg2 will return aware datetimes to Python, and naive inputs get auto-interpreted as the session timezone (UTC for our containers). This provides a safety net but does not eliminate the need to use aware datetimes in application code.

## Decision

### Principle

**UTC everywhere, client transforms to local.**

- Database: all columns `TIMESTAMPTZ`
- API serialization: ISO 8601 with `Z` suffix (or `+00:00`)
- Python: `datetime_utils.utcnow()` per ADR-056
- JavaScript/TypeScript: parse as UTC, display in user's locale

### Migration

A single schema migration (`ALTER COLUMN ... TYPE TIMESTAMPTZ`) converts all 15 columns. PostgreSQL interprets existing bare timestamp values using the session timezone, which is `UTC` in our containers. This means existing data is preserved correctly — `2026-03-02 18:45:12` becomes `2026-03-02 18:45:12+00`.

`ALTER COLUMN ... TYPE TIMESTAMPTZ` acquires an `ACCESS EXCLUSIVE` lock on the table. For the tables involved (jobs, scheduled_jobs, aggressiveness_profiles, graph_metrics), this is acceptable:

- `jobs`: active platform writes, but jobs are short-lived and the ALTER is fast
- `scheduled_jobs`: low write frequency
- `aggressiveness_profiles`: rarely written
- `graph_metrics`: append-only, low frequency

### Client-Side Z-Append Workaround

The Z-append workaround in `workers.ts`, `system.ts`, and `SystemTab.tsx` should be kept as defensive code even after migration — it costs nothing and protects against any future bare-timestamp regressions.

## Draft Migration

```sql
-- Migration 058: Normalize bare TIMESTAMP columns to TIMESTAMPTZ (ADR-202)
--
-- All 15 bare TIMESTAMP columns across 5 tables are converted to TIMESTAMPTZ.
-- PostgreSQL interprets existing values using session timezone (UTC in our containers),
-- so data is preserved: '2026-03-02 18:45:12' becomes '2026-03-02 18:45:12+00'.
--
-- This is safe to run on a live platform. Each ALTER acquires ACCESS EXCLUSIVE briefly.

BEGIN;

-- ============================================================
-- kg_api.jobs (5 columns) — introduced in migration 009
-- ============================================================
ALTER TABLE kg_api.jobs
    ALTER COLUMN created_at   TYPE TIMESTAMPTZ,
    ALTER COLUMN started_at   TYPE TIMESTAMPTZ,
    ALTER COLUMN approved_at  TYPE TIMESTAMPTZ,
    ALTER COLUMN completed_at TYPE TIMESTAMPTZ,
    ALTER COLUMN expires_at   TYPE TIMESTAMPTZ;

-- ============================================================
-- kg_api.scheduled_jobs (6 columns) — introduced in migration 050
-- ============================================================
ALTER TABLE kg_api.scheduled_jobs
    ALTER COLUMN created_at    TYPE TIMESTAMPTZ,
    ALTER COLUMN updated_at    TYPE TIMESTAMPTZ,
    ALTER COLUMN last_run_at   TYPE TIMESTAMPTZ,
    ALTER COLUMN next_run_at   TYPE TIMESTAMPTZ,
    ALTER COLUMN disabled_at   TYPE TIMESTAMPTZ,
    ALTER COLUMN last_error_at TYPE TIMESTAMPTZ;

-- ============================================================
-- kg_api.aggressiveness_profiles (2 columns) — introduced in migration 050
-- ============================================================
ALTER TABLE kg_api.aggressiveness_profiles
    ALTER COLUMN created_at TYPE TIMESTAMPTZ,
    ALTER COLUMN updated_at TYPE TIMESTAMPTZ;

-- ============================================================
-- public.graph_metrics (2 columns) — introduced in migration 016
-- ============================================================
ALTER TABLE public.graph_metrics
    ALTER COLUMN created_at  TYPE TIMESTAMPTZ,
    ALTER COLUMN measured_at TYPE TIMESTAMPTZ;

-- ============================================================
-- public.schema_migrations (1 column) — introduced in migration 040
-- ============================================================
ALTER TABLE public.schema_migrations
    ALTER COLUMN applied_at TYPE TIMESTAMPTZ;

COMMIT;

-- Record migration
INSERT INTO public.schema_migrations (version, name)
VALUES (58, 'timestamp_timezone_normalization')
ON CONFLICT (version) DO NOTHING;
```

**Note:** The migration number (058) is provisional — assign the next available number at implementation time. The `schema_migrations.applied_at` column (1 additional column found during audit, total: 16 columns) is included for completeness.

## Consequences

### Benefits

- JSON serialization will include timezone offset, eliminating client-side guesswork
- Python code receives aware datetimes from psycopg2, preventing naive/aware comparison errors (ADR-056)
- Schema is consistent: 100% `TIMESTAMPTZ` across all tables
- Worker status, job durations, and all time-based displays work correctly regardless of client timezone

### Trade-offs

- Brief `ACCESS EXCLUSIVE` lock on each table during ALTER (milliseconds for small tables)
- Client-side Z-append workaround becomes redundant but should remain as defense-in-depth
- Requires running migration on all deployed instances

### Follow-up Work

- [ ] Implement migration (assign next available migration number)
- [ ] Complete ADR-056 Python datetime migration (21 remaining violations)
- [ ] Audit FastAPI response models to ensure datetime fields serialize with `Z`/`+00:00`
- [ ] Remove or annotate Z-append workarounds as defense-in-depth after migration is deployed

## References

- [ADR-056: Timezone-Aware Datetime Utilities](../infrastructure/ADR-056-timezone-aware-datetime-utilities.md)
- [ADR-040: Database Schema Migrations](ADR-040-database-schema-migrations.md)
- [ADR-100: Database-Driven Job Dispatch](../infrastructure/ADR-100-database-driven-job-dispatch.md)
- [PostgreSQL TIMESTAMPTZ](https://www.postgresql.org/docs/current/datatype-datetime.html)
