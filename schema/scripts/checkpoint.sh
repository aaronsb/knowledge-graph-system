#!/bin/bash
set -euo pipefail

# ============================================================================
# Migration Checkpoint Generator
# ============================================================================
# Consolidates the baseline + all migrations into a single "checkpoint"
# baseline (ADR-210 "periodically consolidate").
#
# Method: replay-and-dump against throwaway containers. Nothing here touches
# a running platform database — raw SQL via psql only, no operator tooling.
#
#   replay    Build container A the old way: current 00_baseline.sql +
#             every migration (cold + warm) applied in numeric order.
#   generate  Dump container A's resting state and assemble a candidate
#             consolidated baseline (relational pg_dump + seed data +
#             graph-seeding migrations replayed verbatim).
#   verify    Build container B from the candidate baseline alone, then
#             diff A vs B: full schema dump, AGE label catalog, per-table
#             row counts, and normalized seed data.
#   all       replay + generate + verify
#   clean     Remove throwaway containers and work directory.
#
# Usage:
#   schema/scripts/checkpoint.sh all
#   CHECKPOINT_WORKDIR=/path/to/work schema/scripts/checkpoint.sh all
#
# Output: $WORKDIR/candidate_baseline.sql (plus dumps/diffs for inspection)
# @verified e0becd8
# ============================================================================

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
SCHEMA_DIR="$PROJECT_ROOT/schema"

# Same base image pinned by docker/Dockerfile.postgres (PG18 + AGE 1.7.0)
IMAGE="apache/age:release_PG18_1.7.0"

DB_USER="admin"
DB_NAME="knowledge_graph"
DB_PASS="checkpoint-throwaway"

CONTAINER_A="kg-checkpoint-a"   # old path: baseline + all migrations
CONTAINER_B="kg-checkpoint-b"   # new path: candidate baseline only

WORKDIR="${CHECKPOINT_WORKDIR:-/tmp/kg-checkpoint}"

# Migrations whose cypher sections seed graph state on a fresh install.
# These are carried into the checkpoint verbatim (they are idempotent).
# Backfill-only migrations (e.g. 024, 043) are no-ops on fresh databases
# and are intentionally not carried. verify proves this list is sufficient.
GRAPH_SEED_MIGRATIONS=(
    "migrations/archived/014_vocabulary_as_graph.sql"
    "migrations/archived/044_ontology_graph_nodes.sql"
    "migrations-warm/058_precreate_graph_labels.sql"
    "migrations/archived/078_seed_primordial_ontology.sql"
)

case "$(uname -m)" in
    x86_64)  ARCH=amd64 ;;
    aarch64|arm64) ARCH=arm64 ;;
    *) echo "Unsupported arch: $(uname -m)" >&2; exit 1 ;;
esac
ACCEL_DIST="$PROJECT_ROOT/graph-accel/dist/pg18/$ARCH"

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${BLUE}→ $*${NC}"; }
ok()    { echo -e "${GREEN}✓ $*${NC}"; }
warn()  { echo -e "${YELLOW}⚠ $*${NC}"; }
fail()  { echo -e "${RED}✗ $*${NC}" >&2; exit 1; }

# ----------------------------------------------------------------------------
# Container helpers
# ----------------------------------------------------------------------------

psql_exec() {  # psql_exec <container> [psql args...]
    local c="$1"; shift
    docker exec -i "$c" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 "$@"
}

start_container() {  # start_container <name> <baseline.sql path>
    local name="$1" baseline="$2"
    docker rm -f "$name" >/dev/null 2>&1 || true

    local accel_mounts=()
    if [ -d "$ACCEL_DIST" ]; then
        local sql_file
        sql_file=$(ls "$ACCEL_DIST"/graph_accel--*.sql | head -1)
        accel_mounts=(
            -v "$ACCEL_DIST/graph_accel.so":/usr/lib/postgresql/18/lib/graph_accel.so:ro
            -v "$ACCEL_DIST/graph_accel.control":/usr/share/postgresql/18/extension/graph_accel.control:ro
            -v "$sql_file":"/usr/share/postgresql/18/extension/$(basename "$sql_file")":ro
        )
    else
        warn "graph-accel dist not found ($ACCEL_DIST) — extension init will be skipped"
    fi

    info "Starting $name from $IMAGE"
    docker run -d --name "$name" \
        -e POSTGRES_DB="$DB_NAME" \
        -e POSTGRES_USER="$DB_USER" \
        -e POSTGRES_PASSWORD="$DB_PASS" \
        -v "$baseline":/docker-entrypoint-initdb.d/10-baseline.sql:ro \
        -v "$SCHEMA_DIR/11_graph_accel.sql":/docker-entrypoint-initdb.d/11-graph-accel.sql:ro \
        "${accel_mounts[@]}" \
        "$IMAGE" >/dev/null

    # TCP probe only passes once the real (post-initdb) server is listening
    local i
    for i in $(seq 1 60); do
        if [ "$(docker inspect -f '{{.State.Running}}' "$name" 2>/dev/null)" != "true" ]; then
            docker logs "$name" 2>&1 | tail -40
            fail "$name exited during init (baseline error?) — logs above"
        fi
        if docker exec "$name" pg_isready -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
            ok "$name ready"
            return 0
        fi
        sleep 2
    done
    docker logs "$name" 2>&1 | tail -40
    fail "$name did not become ready in 120s"
}

# Migrations in numeric order across cold + warm directories. archived/ is
# NOT included: post-checkpoint, replay = current baseline + migrations 081+.
# The existence filter keeps unexpanded globs out when a directory is empty.
migration_files() {
    local f
    for f in "$SCHEMA_DIR"/migrations/*.sql "$SCHEMA_DIR"/migrations-warm/*.sql; do
        [ -f "$f" ] || continue
        printf '%s\n' "$f"
    done | awk -F/ '{print $NF "\t" $0}' | sort | cut -f2
}

# ----------------------------------------------------------------------------
# replay — container A: old baseline + every migration, raw psql
# ----------------------------------------------------------------------------

cmd_replay() {
    mkdir -p "$WORKDIR/logs"
    start_container "$CONTAINER_A" "$SCHEMA_DIR/00_baseline.sql"

    local f base
    while IFS= read -r f; do
        base=$(basename "$f")
        info "apply $base"
        if ! psql_exec "$CONTAINER_A" < "$f" > "$WORKDIR/logs/$base.log" 2>&1; then
            tail -20 "$WORKDIR/logs/$base.log"
            fail "migration $base failed — log: $WORKDIR/logs/$base.log"
        fi
    done < <(migration_files)

    ok "replay complete: $(migration_files | wc -l) migrations applied to $CONTAINER_A"
    psql_exec "$CONTAINER_A" -t -A -c \
        "SELECT 'schema_migrations rows: ' || count(*) FROM public.schema_migrations"
}

# ----------------------------------------------------------------------------
# generate — dump container A into a candidate consolidated baseline
# ----------------------------------------------------------------------------

# Everything except the graph itself. ag_catalog is included on purpose:
# AGE's own objects are extension members (pg_dump skips them), but the old
# baseline's search_path (ag_catalog first) parked a few helper functions
# there and the checkpoint must carry them where they live.
relational_schemas() {
    psql_exec "$CONTAINER_A" -t -A -c \
        "SELECT nspname FROM pg_namespace
         WHERE nspname NOT IN ('pg_catalog','information_schema','knowledge_graph')
           AND nspname NOT LIKE 'pg_%'
         ORDER BY nspname"
}

cmd_generate() {
    mkdir -p "$WORKDIR"
    local candidate="$WORKDIR/candidate_baseline.sql"
    local schemas n_flags=()
    schemas=$(relational_schemas)
    info "relational schemas: $(echo $schemas | tr '\n' ' ')"
    local s
    for s in $schemas; do n_flags+=(-n "$s"); done

    info "dumping schema (DDL)"
    docker exec "$CONTAINER_A" pg_dump -U "$DB_USER" -d "$DB_NAME" \
        --schema-only --no-owner "${n_flags[@]}" \
        | sed -e '/^\\restrict /d' -e '/^\\unrestrict /d' \
              -e 's/^CREATE SCHEMA public;/-- CREATE SCHEMA public; (exists)/' \
              -e 's/^CREATE SCHEMA ag_catalog;/-- CREATE SCHEMA ag_catalog; (owned by age extension)/' \
        > "$WORKDIR/dump_schema.sql"

    info "dumping seed data"
    docker exec "$CONTAINER_A" pg_dump -U "$DB_USER" -d "$DB_NAME" \
        --data-only --column-inserts --on-conflict-do-nothing --no-owner \
        "${n_flags[@]}" -T public.schema_migrations -T 'ag_catalog.*' \
        | sed -e '/^\\restrict /d' -e '/^\\unrestrict /d' \
        > "$WORKDIR/dump_data.sql"

    info "generating schema_migrations records"
    psql_exec "$CONTAINER_A" -t -A -c \
        "SELECT format('INSERT INTO public.schema_migrations (version, name) VALUES (%s, %L) ON CONFLICT (version) DO NOTHING;', version, name)
         FROM public.schema_migrations ORDER BY version" \
        > "$WORKDIR/dump_migrations.sql"

    # Extensions the migrations created (beyond age, plpgsql, and graph_accel —
    # graph_accel is handled conditionally by 11_graph_accel.sql at initdb)
    info "collecting extensions"
    psql_exec "$CONTAINER_A" -t -A -c \
        "SELECT format('CREATE EXTENSION IF NOT EXISTS %I WITH SCHEMA %I;', e.extname, n.nspname)
         FROM pg_extension e JOIN pg_namespace n ON e.extnamespace = n.oid
         WHERE e.extname NOT IN ('age','plpgsql','graph_accel') ORDER BY 1" \
        > "$WORKDIR/dump_extensions.sql"

    local git_rev checkpoint_version
    git_rev=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)
    checkpoint_version=$(psql_exec "$CONTAINER_A" -t -A -c \
        "SELECT max(version) FROM public.schema_migrations")

    info "assembling candidate baseline"
    {
        cat <<HEADER
-- ============================================================================
-- Knowledge Graph System - Consolidated Baseline Schema (Checkpoint)
-- ============================================================================
-- Generated by schema/scripts/checkpoint.sh — do not edit by hand.
-- Regenerate: schema/scripts/checkpoint.sh all
--
-- Source commit: $git_rev
-- Checkpoint: schema version $checkpoint_version (migrations 001-$(printf '%03d' "$checkpoint_version") consolidated)
-- Superseded migrations live in schema/migrations/archived/
--
-- Contents:
--   1. AGE extension + knowledge_graph graph
--   2. Relational DDL (pg_dump --schema-only of: $(echo $schemas | tr '\n' ' '))
--   3. Seed data (pg_dump --data-only, fresh fully-migrated database)
--   4. Graph seed (idempotent cypher migrations carried verbatim)
--   5. schema_migrations records for all consolidated versions
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Extensions and graph
-- ----------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, "\$user", public;

DO \$\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM ag_catalog.ag_graph WHERE name = 'knowledge_graph') THEN
        PERFORM ag_catalog.create_graph('knowledge_graph');
    END IF;
END \$\$;

HEADER
        cat "$WORKDIR/dump_extensions.sql"
        cat <<'HEADER'

-- ----------------------------------------------------------------------------
-- 2. Relational DDL
-- ----------------------------------------------------------------------------
HEADER
        cat "$WORKDIR/dump_schema.sql"
        cat <<'SECTION'

-- ----------------------------------------------------------------------------
-- 3. Seed data
-- ----------------------------------------------------------------------------
-- Rows come from a valid fully-migrated database; FK triggers are disabled
-- during load because pg_dump cannot order rows of self-referencing tables
-- (kg_auth.roles.parent_role). Requires superuser — initdb runs as one.
--
-- NOTE: includes development-default credentials seeded by the migrations
-- (e.g. the default admin user's bcrypt hash). CHANGE THESE IN PRODUCTION —
-- operator init / configure.py handles rotation on managed deployments.
SET session_replication_role = replica;
SECTION
        cat "$WORKDIR/dump_data.sql"
        cat <<'SECTION'

SET session_replication_role = DEFAULT;

-- ----------------------------------------------------------------------------
-- 4. Graph seed (carried migrations, idempotent)
-- ----------------------------------------------------------------------------
SECTION
        local g
        for g in "${GRAPH_SEED_MIGRATIONS[@]}"; do
            echo ""
            echo "-- ======== carried from $g ========"
            cat "$SCHEMA_DIR/$g"
        done
        cat <<'SECTION'

-- ----------------------------------------------------------------------------
-- 5. Migration records (consolidated versions)
-- ----------------------------------------------------------------------------
SECTION
        cat "$WORKDIR/dump_migrations.sql"
    } > "$candidate"

    ok "candidate baseline: $candidate ($(wc -l < "$candidate") lines)"
}

# ----------------------------------------------------------------------------
# verify — container B from candidate only; diff A vs B
# ----------------------------------------------------------------------------

collect_state() {  # collect_state <container> <outdir>
    local c="$1" out="$2"
    mkdir -p "$out"

    # The two sed expressions after the header filters canonicalize varchar
    # IN-list casts: PG stores `(ARRAY[...])::text[]` when parsed from the
    # original migration SQL but `ARRAY[(x)::text, ...]` when re-parsed from
    # pg_dump output — semantically identical round-trip noise.
    docker exec "$c" pg_dump -U "$DB_USER" -d "$DB_NAME" --schema-only --no-owner \
        | sed -E -e '/^\\restrict /d' -e '/^\\unrestrict /d' -e '/^-- Dumped/d' \
              -e "s/\('([^']*)'::character varying\)::text/'\1'::character varying/g" \
              -e 's/\(ARRAY\[([^]]*)\]\)::text\[\]/ARRAY[\1]/g' \
        > "$out/schema_full.sql"

    psql_exec "$c" -t -A -c \
        "SELECT g.name || '.' || l.name || ' (' || l.kind::text || ')'
         FROM ag_catalog.ag_label l JOIN ag_catalog.ag_graph g ON l.graph = g.graphid
         ORDER BY 1" > "$out/age_labels.txt"

    # Per-table row counts across every non-system schema (incl. graph label tables)
    local t
    while IFS= read -r t; do
        printf '%s\t%s\n' "$t" "$(psql_exec "$c" -t -A -c "SELECT count(*) FROM $t")"
    done < <(psql_exec "$c" -t -A -c \
        "SELECT format('%I.%I', schemaname, tablename) FROM pg_tables
         WHERE schemaname NOT IN ('pg_catalog','information_schema')
         ORDER BY 1") > "$out/row_counts.txt"

    # Seed data with volatile values normalized (timestamps, uuids) and lines
    # sorted: physical row order differs legitimately (carried migrations
    # record their versions before section 5; upserts rewrite heap tuples)
    docker exec "$c" pg_dump -U "$DB_USER" -d "$DB_NAME" \
        --data-only --column-inserts --no-owner \
        | sed -E \
            -e '/^\\restrict /d' -e '/^\\unrestrict /d' -e '/^-- Dumped/d' \
            -e "s/'[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9:.+-]+'/'<TS>'/g" \
            -e "s/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/<UUID>/g" \
        | sort > "$out/data_normalized.sql"
}

cmd_verify() {
    local candidate="$WORKDIR/candidate_baseline.sql"
    [ -f "$candidate" ] || fail "no candidate baseline — run generate first"

    start_container "$CONTAINER_B" "$candidate"

    info "collecting state from both containers"
    collect_state "$CONTAINER_A" "$WORKDIR/state_a"
    collect_state "$CONTAINER_B" "$WORKDIR/state_b"

    local status=0 check
    for check in schema_full.sql age_labels.txt row_counts.txt data_normalized.sql; do
        if diff -u "$WORKDIR/state_a/$check" "$WORKDIR/state_b/$check" \
            > "$WORKDIR/diff_${check%.*}.txt" 2>&1; then
            ok "$check matches"
        else
            warn "$check DIFFERS — $WORKDIR/diff_${check%.*}.txt"
            status=1
        fi
    done

    if [ $status -eq 0 ]; then
        ok "VERIFIED: candidate baseline is a faithful checkpoint"
    else
        fail "verification found differences — inspect diffs in $WORKDIR"
    fi
}

cmd_clean() {
    docker rm -f "$CONTAINER_A" "$CONTAINER_B" >/dev/null 2>&1 || true
    rm -rf "$WORKDIR"
    ok "cleaned"
}

case "${1:-}" in
    replay)   cmd_replay ;;
    generate) cmd_generate ;;
    verify)   cmd_verify ;;
    all)      cmd_replay; cmd_generate; cmd_verify ;;
    clean)    cmd_clean ;;
    *) echo "Usage: $0 {replay|generate|verify|all|clean}"; exit 1 ;;
esac
