#!/bin/bash
# ============================================================================
# common.sh - Shared functions for operator scripts
# ============================================================================

# Get project root (relative to this script in operator/lib/)
_COMMON_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="${PROJECT_ROOT:-$( cd "$_COMMON_DIR/../.." && pwd )}"

# Detect standalone vs repo install (only if DOCKER_DIR not already set)
# Standalone: docker-compose.yml in root, no docker/ subdirectory
# Repo: docker-compose.yml in docker/ subdirectory
if [ -z "$DOCKER_DIR" ]; then
    if [ -d "$PROJECT_ROOT/docker" ]; then
        DOCKER_DIR="$PROJECT_ROOT/docker"
    else
        DOCKER_DIR="$PROJECT_ROOT"
    fi
fi
CONFIG_FILE="$PROJECT_ROOT/.operator.conf"
ENV_FILE="$PROJECT_ROOT/.env"

# Load configuration from .operator.conf
load_operator_config() {
    if [ -f "$CONFIG_FILE" ]; then
        source "$CONFIG_FILE"
    fi
    # Defaults if no config file or missing values
    DEV_MODE="${DEV_MODE:-false}"
    GPU_MODE="${GPU_MODE:-cpu}"
    CONTAINER_PREFIX="${CONTAINER_PREFIX:-knowledge-graph}"
    CONTAINER_SUFFIX="${CONTAINER_SUFFIX:-}"
    COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
    IMAGE_SOURCE="${IMAGE_SOURCE:-local}"
    # ADR-105: in-VM Traefik router. `none` (default) leaves the platform on
    # direct per-service ports; `traefik` adds the unified HTTP ingress overlay.
    ROUTER_MODE="${ROUTER_MODE:-none}"
    export ROUTER_MODE
    # ADR-105: TLS termination mode for the in-VM router. `none` (default) keeps
    # the HTTP-only ingress; `selfsigned` adds the websecure :443 entrypoint with
    # Traefik's built-in self-signed cert. Only meaningful with ROUTER_MODE=traefik.
    TLS_MODE="${TLS_MODE:-none}"
    export TLS_MODE
    # ADR-105: public base URL (scheme+host). Single source of public identity —
    # the web overlay substitutes it into VITE_* so the OAuth redirect scheme
    # matches what init registered. Empty default lets compose fall back to
    # http://localhost; init writes the real value to both .env and .operator.conf.
    EXTERNAL_URL="${EXTERNAL_URL:-}"
    export EXTERNAL_URL

    # ADR-101: derive kg-api image tag via the shared helper (see
    # operator/lib/image-tag.sh for the single source of truth).
    # docker-compose.ghcr.yml substitutes ${KG_API_IMAGE_TAG:-latest} into
    # the api service's image: line, so AMD ROCm hosts pull the matching
    # variant instead of the CUDA-bundled :latest. Explicit override in
    # .operator.conf (or environment) wins.
    if [ -z "$KG_API_IMAGE_TAG" ]; then
        # shellcheck source=operator/lib/image-tag.sh
        source "$_COMMON_DIR/image-tag.sh"
        KG_API_IMAGE_TAG=$(derive_kg_api_image_tag "$GPU_MODE" "$ROCM_VERSION")
    fi
    export KG_API_IMAGE_TAG
}

# Get container name for a service
# Usage: get_container_name <service>
# Services: postgres, garage, api, web, operator
#
# Naming conventions:
#   Development (knowledge-graph prefix):
#     infra: knowledge-graph-postgres, knowledge-graph-garage
#     apps:  kg-api-dev, kg-web-dev (with volume mounts, hot reload)
#
#   Production (kg prefix):
#     all:   kg-postgres, kg-garage, kg-api, kg-web
get_container_name() {
    local service=$1
    load_operator_config

    # Determine if we're in "short prefix" mode (kg-* naming)
    local short_prefix=false
    if [[ "$CONTAINER_PREFIX" == "kg" ]]; then
        short_prefix=true
    fi

    case "$service" in
        postgres|garage)
            # Infrastructure containers
            echo "${CONTAINER_PREFIX}-${service}"
            ;;
        api|web)
            # App containers - add -dev suffix unless using short prefix
            if [ "$short_prefix" = true ]; then
                echo "kg-${service}"
            else
                echo "kg-${service}-dev"
            fi
            ;;
        operator)
            echo "kg-operator"
            ;;
        *)
            echo "unknown-$service"
            ;;
    esac
}

# Get regex pattern for container names (for use with grep)
# Note: No trailing $ anchor - patterns used with "grep -E pattern.*healthy"
get_container_pattern() {
    local service=$1
    load_operator_config

    # Use get_container_name for consistency
    local name=$(get_container_name "$service")

    case "$service" in
        postgres|garage|api|web|operator)
            echo "^${name}"
            ;;
        all)
            echo "^(kg-|${CONTAINER_PREFIX}-)"
            ;;
        *)
            echo "^$service"
            ;;
    esac
}

# Build docker-compose command with appropriate files based on config
get_compose_cmd() {
    load_operator_config

    # Start with base compose file (default or configured)
    local base_file="${COMPOSE_FILE:-docker-compose.yml}"
    local cmd="docker compose -f $DOCKER_DIR/$base_file"

    # Add prod overlay for production mode (container naming, resource limits)
    if [ "$DEV_MODE" != "true" ]; then
        if [ -f "$DOCKER_DIR/docker-compose.prod.yml" ]; then
            cmd="$cmd -f $DOCKER_DIR/docker-compose.prod.yml"
        fi
    fi

    # Add GHCR overlay if using registry images
    if [ "$IMAGE_SOURCE" = "ghcr" ]; then
        if [ -f "$DOCKER_DIR/docker-compose.ghcr.yml" ]; then
            cmd="$cmd -f $DOCKER_DIR/docker-compose.ghcr.yml"
        fi
    fi

    # Add standalone overlay if present (curl installer deployments)
    if [ -f "$DOCKER_DIR/docker-compose.standalone.yml" ]; then
        cmd="$cmd -f $DOCKER_DIR/docker-compose.standalone.yml"
    fi

    # Add SSL overlay if present
    if [ -f "$DOCKER_DIR/docker-compose.ssl.yml" ]; then
        cmd="$cmd -f $DOCKER_DIR/docker-compose.ssl.yml"
    fi

    # Add Traefik router overlay (ADR-105) when enabled, plus the TLS overlays
    # selected by TLS_MODE. selfsigned/manual/letsencrypt terminate TLS in-VM and
    # share the websecure baseline (traefik-tls.yml); manual and letsencrypt add a
    # cert-source overlay on top. `offload` and `none` stay HTTP-only at the router.
    if [ "$ROUTER_MODE" = "traefik" ] && [ -f "$DOCKER_DIR/docker-compose.traefik.yml" ]; then
        cmd="$cmd -f $DOCKER_DIR/docker-compose.traefik.yml"
        case "$TLS_MODE" in
            selfsigned|manual|letsencrypt)
                [ -f "$DOCKER_DIR/docker-compose.traefik-tls.yml" ] && cmd="$cmd -f $DOCKER_DIR/docker-compose.traefik-tls.yml"
                case "$TLS_MODE" in
                    manual)      [ -f "$DOCKER_DIR/docker-compose.traefik-tls-manual.yml" ]      && cmd="$cmd -f $DOCKER_DIR/docker-compose.traefik-tls-manual.yml" ;;
                    letsencrypt)
                        # dns-01 uses the lego DNS overlay; otherwise TLS-ALPN-01.
                        if [ "${ACME_CHALLENGE:-tls-alpn-01}" = "dns-01" ] && [ -f "$DOCKER_DIR/docker-compose.traefik-tls-letsencrypt-dns.yml" ]; then
                            cmd="$cmd -f $DOCKER_DIR/docker-compose.traefik-tls-letsencrypt-dns.yml"
                        elif [ -f "$DOCKER_DIR/docker-compose.traefik-tls-letsencrypt.yml" ]; then
                            cmd="$cmd -f $DOCKER_DIR/docker-compose.traefik-tls-letsencrypt.yml"
                        fi
                        ;;
                esac
                ;;
        esac
    fi

    # Add dev overlay if in development mode
    if [ "$DEV_MODE" = "true" ]; then
        if [ -f "$DOCKER_DIR/docker-compose.dev.yml" ]; then
            cmd="$cmd -f $DOCKER_DIR/docker-compose.dev.yml"
        fi
    fi

    # Add GPU-specific overlay
    case "$GPU_MODE" in
        nvidia)
            if [ -f "$DOCKER_DIR/docker-compose.gpu-nvidia.yml" ]; then
                cmd="$cmd -f $DOCKER_DIR/docker-compose.gpu-nvidia.yml"
            fi
            ;;
        amd|amd-host)
            # `amd` is a deprecated alias for `amd-host` (see image-tag.sh
            # warning). Both modes resolve to the host-ROCm compose overlay.
            if [ -f "$DOCKER_DIR/docker-compose.gpu-amd-host.yml" ]; then
                cmd="$cmd -f $DOCKER_DIR/docker-compose.gpu-amd-host.yml"
            fi
            ;;
        mac)
            if [ -f "$DOCKER_DIR/docker-compose.override.mac.yml" ]; then
                cmd="$cmd -f $DOCKER_DIR/docker-compose.override.mac.yml"
            fi
            ;;
    esac

    cmd="$cmd --env-file $ENV_FILE"
    echo "$cmd"
}

# Run docker-compose with the configured files
run_compose() {
    local compose_cmd=$(get_compose_cmd)
    $compose_cmd "$@"
}
