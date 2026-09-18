#!/bin/bash
# AGE extension catalog reconciliation.  @verified 060280191
#
# Pulling a new postgres image swaps the AGE shared library, but the extension's
# CATALOG entries live in the database and stay at whatever version created them.
# A 1.8.0 library on a 1.7.0 catalog still accepts writes while every read fails
# with "type with OID 0 does not exist" / "cache lookup failed for type 0" —
# 1.8.0 re-signatured three functions the executor uses to build rows
# (_agtype_build_vertex / _agtype_build_edge take agtype where they took
# cstring; _label_name RETURNS agtype, not cstring).
#
# Every path that can bring postgres up on a different image than the one that
# created the volume must run this after postgres answers queries and before
# anything runs Cypher: the container-side start (start-infra.sh), the host
# `operator.sh start` and `operator.sh restart postgres|all`, and upgrade.sh.
# Idempotent — when the versions already agree this is two SELECTs and no output.
#
# The update script comes from docker/age/, COPYed in by docker/Dockerfile.postgres
# (and bind-mounted by docker-compose.dev.yml); the stock apache/age image ships
# none — see apache/age#2570.
#
# Usage:
#   source age-catalog.sh; migrate_age_extension     # POSTGRES_CONTAINER already set
#   operator/lib/age-catalog.sh                      # standalone: resolves the container itself

# migrate_age_extension — reconcile the AGE catalog to the installed library.
# Needs POSTGRES_CONTAINER, and POSTGRES_USER / POSTGRES_DB (defaults admin /
# knowledge_graph). Exits 1 when an update is needed and fails.  @verified 060280191
migrate_age_extension() {
    local psql_args=(-U "${POSTGRES_USER:-admin}" -d "${POSTGRES_DB:-knowledge_graph}" -tAc)
    local installed available err

    installed=$(docker exec "$POSTGRES_CONTAINER" psql "${psql_args[@]}" \
        "SELECT extversion FROM pg_extension WHERE extname='age'" 2>/dev/null) || return 0
    available=$(docker exec "$POSTGRES_CONTAINER" psql "${psql_args[@]}" \
        "SELECT default_version FROM pg_available_extensions WHERE name='age'" 2>/dev/null) || return 0

    # Extension absent, or version unreadable — nothing to reconcile.
    [ -n "$installed" ] && [ -n "$available" ] || return 0
    [ "$installed" = "$available" ] && return 0

    echo -e "${BLUE}  Updating AGE extension catalog: ${installed} → ${available}...${NC}"
    if ! err=$(docker exec "$POSTGRES_CONTAINER" psql \
            -U "${POSTGRES_USER:-admin}" -d "${POSTGRES_DB:-knowledge_graph}" \
            -v ON_ERROR_STOP=1 -c "ALTER EXTENSION age UPDATE" 2>&1); then
        echo -e "${RED}✗ AGE extension update ${installed} → ${available} failed${NC}"
        echo "$err" | sed 's/^/    /'
        echo ""
        echo -e "${RED}Refusing to continue: the AGE library is ${available} but the catalog is"
        echo -e "still ${installed}. Graph writes would succeed and every graph read would fail.${NC}"
        echo "  If this is \"no update path\", the image is missing"
        echo "  /usr/share/postgresql/18/extension/age--${installed}--${available}.sql"
        echo "  (see docker/age/ and apache/age#2570)."
        exit 1
    fi
    echo -e "${GREEN}✓ AGE extension updated ${installed} → ${available}${NC}"
}

# Standalone invocation: resolve the container name and wait for postgres to
# answer queries (a freshly recreated container can take a few seconds).
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    set -e
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    # shellcheck source=common.sh
    source "$SCRIPT_DIR/common.sh"
    BLUE='\033[0;34m'; GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
    POSTGRES_CONTAINER=$(get_container_name postgres)
    for i in $(seq 1 30); do
        docker exec "$POSTGRES_CONTAINER" psql -U "${POSTGRES_USER:-admin}" -d "${POSTGRES_DB:-knowledge_graph}" \
            -tAc "SELECT 1" >/dev/null 2>&1 && break
        [ "$i" -eq 30 ] && { echo -e "${RED}✗ postgres (${POSTGRES_CONTAINER}) not answering; AGE catalog not checked${NC}"; exit 1; }
        sleep 2
    done
    migrate_age_extension
fi
