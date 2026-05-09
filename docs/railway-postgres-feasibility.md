# Railway feasibility — kg-postgres (Apache AGE + graph_accel)

Investigation branch: `claude/railway-postgres-investigation-gMTRn`

## TL;DR

**Feasible.** Railway supports the only thing this stack actually requires from a
host: deploy a custom Dockerfile as a database service with a persistent volume.
Railway's *managed* Postgres template is irrelevant here — we ship our own image
(`docker/Dockerfile.postgres`) on top of `apache/age`, and Railway treats it like
any other container. There is even an existing community "Deploy Apache AGE"
template, which is direct evidence this pattern works on the platform.

The non-trivial issues are operational, not blockers: build platform / TARGETARCH
for the prebuilt `graph_accel.so`, RAM sizing for the in-memory graph cache, and
the Garage object-storage dependency (which is a separate service on Railway).

---

## What kg-postgres actually needs from a host

From `docker/Dockerfile.postgres` and `graph-accel/`:

1. **Base image:** `apache/age` (digest-pinned), which is Postgres 17 + AGE
   compiled and registered.
2. **Custom extension:** `graph_accel` — a Rust/pgrx extension distributed as
   prebuilt artifacts in `graph-accel/dist/pg17/{amd64,arm64}/`:
   - `graph_accel.so` → `/usr/lib/postgresql/17/lib/`
   - `graph_accel.control` → `/usr/share/postgresql/17/extension/`
   - `graph_accel--*.sql` → `/usr/share/postgresql/17/extension/`
   - **ABI-locked** to the `apache/age` image. Cannot be installed on Railway's
     managed Postgres template — must ride along in our Dockerfile.
3. **Init scripts:** `schema/00_baseline.sql`, `schema/11_graph_accel.sql` copied
   into `/docker-entrypoint-initdb.d/` (only run on first boot against an empty
   `PGDATA`).
4. **Persistent volume** at `/var/lib/postgresql/data`.
5. **Network:** TCP 5432 reachable by the API service.

That's the entire host contract. Anything that satisfies "run my Dockerfile,
attach a volume at this path, expose this port" works.

## Mapping requirements onto Railway

| Requirement | Railway support | Notes |
|---|---|---|
| Custom Dockerfile as a service | Yes — first-class. `docs.railway.com/builds/dockerfiles` and `docs.railway.com/databases/build-a-database-service` cover it. | Build context is the connected Git repo; prebuilt `graph-accel/dist/...` artifacts ride along. |
| Postgres 17 + AGE | Yes — `apache/age` runs unmodified. There's a public `railway.com/deploy/apache-age` template as proof. | We use a digest-pinned base, not the template. |
| Custom .so extension | Yes — under our own Dockerfile. | Railway's *managed* template forbids extension installs and resets `ALTER SYSTEM` on restart. That restriction does **not** apply to a self-built image. |
| `shared_preload_libraries` / `postgresql.conf` control | Yes — we own the image, so we own the config. | AGE doesn't strictly require preloading, but if we want it, we bake it into a `postgresql.conf` baked into the image or the entrypoint. |
| Persistent volume | Yes — Hobby/Pro plans, up to 1 TB, live resize without downtime. | Mount at `/var/lib/postgresql/data`. Railway exposes `RAILWAY_VOLUME_MOUNT_PATH`; PGDATA must match. |
| Backups | Volume snapshots on services-with-volumes; community `postgres-s3-backups` template for `pg_dump` to S3-compatible storage. | Recommend both: snapshot for DR, `pg_dump` for portability across hosts. |
| Internal networking to API service | Yes — services in the same project share a private network. | API connects via internal DNS, no public TCP proxy needed unless you want external admin access. |

## Things that need verification before committing

These are not show-stoppers; they're items I would test on a throwaway Railway
project before migrating real data.

1. **TARGETARCH propagation.** Our Dockerfile uses
   `COPY graph-accel/dist/pg17/${TARGETARCH}/graph_accel.so ...`. Railway's
   builders are x86-64; BuildKit normally sets `TARGETARCH=amd64` on a native
   build, which matches our `dist/pg17/amd64/` layout. **Action:** confirm in a
   build log that `TARGETARCH` resolves to `amd64`, otherwise set it explicitly
   via a Railway build arg or hardcode the path. The arm64 prebuilt only matters
   if Railway ever runs us on Graviton — currently it does not.

2. **RAM headroom for `graph_accel`.** The extension loads the full graph as
   in-memory adjacency lists. Hobby's default per-service RAM is small; for any
   non-toy graph use Pro and provision deliberately. Sizing rule of thumb:
   roughly `vertices * (avg_degree + 4) * 8 bytes` plus property-value
   serialisation overhead. Re-priming after every container restart (deploy,
   crash, host migration) requires a `graph_accel_load()` call — already true
   locally, just more visible in a managed environment.

3. **Volume snapshot semantics.** Railway snapshots are filesystem-level. Postgres
   should be quiesced or the snapshot taken via `pg_basebackup` for
   crash-consistency guarantees. For now, layer a periodic `pg_dump` into the
   strategy regardless.

4. **Region pinning.** Pick the same region as wherever the API service runs.
   Cross-region egress is metered.

## What is *not* in scope here but lives next door

The repo's `docker-compose.yml` also runs:

- **Garage** (S3-compatible object storage) — needs to live somewhere. Options:
  another Railway service from the Garage Docker image with its own volume; or
  swap to Cloudflare R2 / Backblaze B2 / AWS S3 and only deploy Postgres on
  Railway. R2 in particular has zero egress and a generous free tier; for image
  assets it's usually a better fit than self-hosting Garage.
- **API**, **Web**, **Operator** — straightforward Railway services from
  Dockerfiles. Operator currently mounts the Docker socket for container
  lifecycle management; that pattern does **not** translate to Railway (no
  socket access). The operator would need a Railway-API-driven adapter, or be
  replaced by Railway's own deploy/restart primitives. This is the largest
  architectural rework if the goal is "lift and shift the whole compose file."

If the question is strictly *the data backing*, only Postgres + a volume + a
backup target are involved, and the rest can stay wherever it is today.

## Recommended path

1. Fork-or-branch a minimal Railway project containing just
   `docker/Dockerfile.postgres` and the `schema/` + `graph-accel/dist/` paths it
   copies from. Point Railway's service at this repo + Dockerfile path.
2. Attach a 10–20 GB volume at `/var/lib/postgresql/data`. Set
   `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` via Railway variables.
   Confirm `PGDATA` defaults align with the mount path or set `PGDATA` explicitly.
3. Deploy. Inspect the build log for `TARGETARCH=amd64`. Connect with `psql`,
   run `CREATE EXTENSION age; CREATE EXTENSION graph_accel;` if not already
   created by the init scripts, and run the existing test suite against the
   Railway endpoint.
4. Layer in `pg_dump` → R2/S3 backups via the `postgres-s3-backups` template or
   a small cron service.
5. Decide on Garage vs R2/S3 separately based on whether self-hosted object
   storage is a hard requirement.

## Cost sketch (order of magnitude)

- Hobby ($5/mo) — fine for evaluation, not for a real graph workload.
- Pro ($20/mo seat) + usage. Realistic monthly for a small-to-medium kg-postgres:
  ~2 vCPU / 4–8 GB RAM, 50 GB volume, modest egress → roughly $25–60/mo on top
  of the seat. Anything that needs more RAM for `graph_accel` scales linearly.
- Egress is metered; keep API and DB in the same region.

## Sources

- [Railway: PostgreSQL](https://docs.railway.com/databases/postgresql)
- [Railway: Build a Database Service](https://docs.railway.com/databases/build-a-database-service)
- [Railway: Dockerfiles](https://docs.railway.com/builds/dockerfiles)
- [Railway: Volumes](https://docs.railway.com/volumes)
- [Railway: Volumes reference](https://docs.railway.com/volumes/reference)
- [Railway template: Deploy Apache AGE](https://railway.com/deploy/apache-age)
- [Railway template: postgres-ssl (extension pattern)](https://github.com/railwayapp-templates/postgres-ssl)
- [Railway template: postgres-s3-backups](https://github.com/railwayapp-templates/postgres-s3-backups)
- [Railway Help: Install Postgres Extensions](https://station.railway.com/feedback/install-postgres-extensions-c815caee)
- [Railway Help: Modifying postgresql.conf](https://station.railway.com/questions/modifying-postgresql-conf-f7ec0398)
