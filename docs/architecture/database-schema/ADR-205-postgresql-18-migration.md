---
status: Draft
date: 2026-05-20
deciders:
  - aaronsb
  - claude
related:
  - ADR-015
  - ADR-016
  - ADR-040
  - ADR-061
  - ADR-201
---

# ADR-205: PostgreSQL 18 Migration

## Context

The platform's database is not PostgreSQL directly — it is the `apache/age`
Docker image, which bundles a specific PostgreSQL version with the Apache AGE
graph extension (ADR-016). Until now that image was pinned by digest to
`apache/age:release_PG17_1.6.0` — PostgreSQL 17 + AGE 1.6.0.

PostgreSQL 18 is now the general baseline, and the `apache/age` project ships
`release_PG18_1.7.0` (PG 18.1 + AGE 1.7.0, multi-arch amd64/arm64, in the
registry since February 2026). Staying on 17 means drifting further from the
upstream baseline. Moving to 18 is therefore desirable — but the move is not a
single-version bump:

- **It is also an AGE bump** (1.6.0 → 1.7.0). The `apache/age` image couples
  the two; there is no way to take PG 18 without taking the AGE release built
  for it. The `-rc0` suffix on AGE git tags is *not* a maturity signal —
  every AGE release is tagged `-rc0` (the PG17/1.6.0 line we ran in production
  carried the same suffix). `release_PG18_1.7.0` is a normal AGE release.
- **The Rust acceleration extension must be rebuilt.** `graph_accel`
  (ADR-201) is a pgrx extension whose `.so` is ABI-bound to the exact
  PostgreSQL it was compiled against. PG 18 requires fresh artifacts.
- **PostgreSQL 18 changed the Docker data-directory convention.** This is the
  single most consequential discovery of the migration and is described below.

A validation spike was run before committing to the move. It split into two
gates: **Gate 1 — does the platform run on PG 18 / AGE 1.7?** and **Gate 2 —
can existing data be migrated across the major-version boundary?**

### Gate 1 — platform compatibility: passed

| Check | Result |
|---|---|
| `apache/age:release_PG18_1.7.0` fresh init | PG 18.1 + AGE 1.7.0; 60 migrations applied; schema v64 |
| `graph_accel` Rust/pgrx extension | Compiles against PG 18 (pgrx 0.16.1), installs, loads |
| `kg-postgres` baked image (`Dockerfile.postgres`) | Builds clean |
| API test suite (`pytest tests/unit tests/api`) | 882 passed; 3 failures, all explained by a freshly-wiped config DB (missing garage/OpenAI keys), none a PG 18 regression |

The `graph_accel` `ext` crate uses only high-level pgrx APIs (`Spi`,
`GucRegistry`) — no raw `pg_sys`, no executor hooks, no tuple-slot access — so
PostgreSQL 18's internal C-API churn (the kind that required source patches in
AGE itself) never reached our code. PG 18 compatibility for `graph_accel` is
delegated entirely to pgrx 0.16.1, and the container build proved it.

### The data-directory convention change

PostgreSQL 18's official Docker images store the cluster in a
**major-version-specific subdirectory** (`PGDATA=/var/lib/postgresql/18/docker`)
and expect the data volume mounted at `/var/lib/postgresql` — **not**
`/var/lib/postgresql/data`, the path used by every pre-18 image. Mounting at
the old path makes PG 18 refuse to start:

```
Error: in 18+, these Docker images are configured to store database data in a
format which is compatible with "pg_ctlcluster"... there appears to be
PostgreSQL data in /var/lib/postgresql/data (unused mount/volume)
```

This is a hard error for anyone upgrading, independent of AGE, and it affects
bind-mount production installs as much as named-volume installs.

### Gate 2 — data migration: logical dump/restore does not carry AGE graphs

A PostgreSQL major-version bump cannot be applied by swapping the container
image — the new server will not start on an older cluster's data directory.
The conventional cross-version path is a logical `pg_dump` / `pg_restore`, and
the platform already ships that tooling (ADR-015). The spike tested it by
dumping the live PG 17 graph (114 Concepts, 191 Instances, ~650 typed edges,
108 source embeddings) and restoring into PG 18. It does **not** round-trip:

1. `pg_restore --clean` aborts — it emits `DROP TABLE` on AGE label tables,
   which AGE rejects (`table "VocabType" is for label "VocabType"`). Restore
   must target an empty database.
2. Restoring into an empty database succeeds and node/edge **counts** come
   back correct — but vertex/edge **content** is unretrievable:
   `ERROR: graph with oid 16987 does not exist`.

Root cause: AGE's graph identity *is* the backing schema's OID. On PG 17 the
`knowledge_graph` schema had OID 16987, so `ag_graph.graphid` was 16987; after
restore the schema has OID 18475, but `ag_graph.graphid` / `ag_label.graph`
were dumped as the literal stale 16987. `pg_dump` never fixes up OIDs — only
`pg_upgrade` and physical replication preserve them. **This is an Apache AGE
limitation, not a PostgreSQL 18 one**: a PG 17 → PG 17 restore into a fresh
cluster would fail identically.

The spike also exposed two pre-existing bugs in the restore tooling,
independent of PG 18 and tracked for separate fixes (issues #397, #398):

- `operator/database/restore-database.sh` pipes `pg_restore` through
  `grep -v`, so the pipeline's exit code is `grep`'s, not `pg_restore`'s — it
  reported `✓ Database restored successfully!` on a fully aborted restore.
- `pg_restore --clean` against a database that already holds an AGE graph is
  hazardous even for a same-version restore, for the label-table reason above.

This project has no production data to preserve — the only live instance holds
development data — so the practical move is a clean cut. But the *tooling* must
still behave correctly for any operator who does have data.

## Decision

**Hard-cut the platform from PostgreSQL 17 / AGE 1.6.0 to PostgreSQL 18 /
AGE 1.7.0.** No parallel-version support is retained.

1. **Base image** — `docker/Dockerfile.postgres` and
   `graph-accel/Dockerfile.build` pin `apache/age` by digest to
   `release_PG18_1.7.0`
   (`sha256:e7de1717e487dac7c1be93a1cd5360a2cf07ff4170342c2af2ac4713c21baf00`).
   Dev compose pins the same release tag.
2. **Data-directory mount** — all compose files mount the postgres data volume
   at `/var/lib/postgresql` (PG 18's version-subdirectory layout), replacing
   the pre-18 `/var/lib/postgresql/data`.
3. **graph_accel** — the pgrx `ext` crate's default feature is `pg18`;
   artifacts are rebuilt for PG 18 into `graph-accel/dist/pg18/{amd64,arm64}/`,
   and `dist/pg17/` is removed. All build/deploy/publish references and the
   `/usr/lib|share/postgresql/18/` install paths are cut to 18.
4. **Operator safety gate** — `operator.sh upgrade` (`cmd_upgrade`) gains
   `check_pg_major_compatibility`: it compares the live cluster's
   `PGDATA/PG_VERSION` against the target image's `PG_MAJOR` and, on a
   mismatch, **refuses the upgrade before any container is recreated**. This
   is the deliberate scope choice — *detect and refuse*, not *migrate*.
5. **Major-version data migration is deferred.** Because logical dump/restore
   cannot carry an AGE graph across clusters, no automated major-version
   migration path is shipped. An operator who must preserve a graph across a
   PostgreSQL major version performs a deliberate, separate procedure
   (`pg_upgrade`, which preserves OIDs, or rebuild-by-re-ingestion). The
   operator gate above ensures they cannot do so accidentally.

## Consequences

### Positive

- The platform tracks the current PostgreSQL baseline (18.1) and the current
  AGE release (1.7.0).
- `operator.sh upgrade` can no longer silently destroy a cluster by swapping a
  PG-major-incompatible image — it fails fast with an explanatory message
  instead of a cryptic container crash loop.
- The data-directory mount is now correct for PG 18+, so future minor-version
  image bumps within the 18 series are clean.
- The validation spike turned two latent restore-tooling bugs into tracked
  work.

### Negative

- There is no one-command path to migrate an existing graph across a
  PostgreSQL major version. Operators with data must run a manual procedure.
  This is an honest reflection of an AGE limitation rather than a regression
  introduced here.
- The hard cut means a single supported PostgreSQL/AGE pair; targeting an
  older AGE for any reason requires reverting the pins.
- A PG-major upgrade requires the data volume to be re-created at the new
  mount path — the old `/var/lib/postgresql/data` volume cannot be reused
  in place even by `pg_upgrade` without remapping.

### Neutral

- Existing `apache/age` installs that copy `graph_accel` artifacts must use
  the `dist/pg18/` files; the PG 17 artifacts are gone.
- Multi-arch `graph_accel` artifacts (amd64 + arm64) are committed so the
  `kg-postgres` image can be published for both architectures.
- `cargo pgrx test pg18` requires a host pgrx initialised for PG 18; the
  canonical, ABI-correct build remains `build-in-container.sh`.

## Alternatives Considered

- **Logical `pg_dump` / `pg_restore` as the migration vehicle.** Rejected on
  empirical evidence: the spike proved AGE graphs do not round-trip across
  clusters (the OID-identity problem above). It remains valid only for
  same-cluster backup/restore.
- **`pg_upgrade` as a shipped, automated path.** `pg_upgrade` preserves OIDs,
  so it *would* carry an AGE graph intact — but it requires both PostgreSQL
  major versions' binaries and the AGE `.so` for both majors present in one
  image, and AGE's catalog-migration scripts make no `pg_upgrade` guarantees.
  Too heavy to bake in for a platform with no production data to preserve;
  left as a documented manual option.
- **Post-restore catalog fixup** (rewriting `ag_graph.graphid` /
  `ag_label.graph` from the stale OID to the new schema OID). Technically
  possible but fragile — it requires dropping and re-adding the `fk_graph_oid`
  constraint and is unverified surgery, not a blessed path.
- **Staying on PostgreSQL 17.** Rejected — it accumulates drift from the
  upstream baseline with no offsetting benefit; AGE 1.7.0 for PG 18 is a
  normal release.
- **Parallel PG 17 / PG 18 support** (multi-version `dist/`, dual base pins).
  Rejected — the platform has a single deployment target; carrying two
  versions multiplies build and CI surface for no consumer.
