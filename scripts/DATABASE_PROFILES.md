# PostgreSQL Database Profiles

Quick reference for database resource configurations.

## Available Profiles

### Small - Development Laptop/Workstation
**Target:** 8GB RAM, 8 CPU cores

```bash
./scripts/configure-db-profile.sh small
```

| Setting | Value |
|---------|-------|
| shared_buffers | 2GB |
| work_mem | 32MB |
| maintenance_work_mem | 512MB |
| effective_cache_size | 6GB |
| max_worker_processes | 8 |
| max_parallel_workers | 4 |
| max_parallel_workers_per_gather | 2 |

**Use for:** Local development, testing, personal projects

---

### Medium - Production Workstation/Small Server
**Target:** 16GB RAM, 16 CPU cores

```bash
./scripts/configure-db-profile.sh medium
```

| Setting | Value |
|---------|-------|
| shared_buffers | 4GB |
| work_mem | 64MB |
| maintenance_work_mem | 1GB |
| effective_cache_size | 12GB |
| max_worker_processes | 16 |
| max_parallel_workers | 8 |
| max_parallel_workers_per_gather | 4 |

**Use for:** Small production deployments, team development servers

---

### Large - Production Server/High-Performance System
**Target:** 32GB+ RAM, 32 CPU cores

```bash
./scripts/configure-db-profile.sh large
```

| Setting | Value |
|---------|-------|
| shared_buffers | 8GB |
| work_mem | 128MB |
| maintenance_work_mem | 2GB |
| effective_cache_size | 24GB |
| max_worker_processes | 32 |
| max_parallel_workers | 16 |
| max_parallel_workers_per_gather | 8 |

**Use for:** Production deployments, high-concurrency workloads, multi-user systems

---

## Common Settings (All Profiles)

These are set identically across all profiles:

- `parallel_tuple_cost = 0.01`
- `parallel_setup_cost = 100`
- `wal_buffers = 16MB`
- `checkpoint_timeout = 15min`
- `max_wal_size = 4GB`
- `min_wal_size = 1GB`
- `track_io_timing = on`
- `log_min_duration_statement = 1000` (log queries >1s)

## How It Works

1. Settings applied via `ALTER SYSTEM SET`
2. Persisted in `postgresql.auto.conf` inside data volume
3. Container automatically restarted to apply
4. Settings survive container restarts/recreates

## Custom Tuning

After applying a profile, you can customize further:

```bash
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
  "ALTER SYSTEM SET work_mem = '256MB';"

docker restart knowledge-graph-postgres
```

Profiles are just starting points - customize as needed!

## Monitoring

Check current settings:
```bash
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
  "SELECT name, setting FROM pg_settings WHERE name LIKE '%parallel%';"
```

Monitor performance:
```bash
./scripts/monitor-db.sh
```
