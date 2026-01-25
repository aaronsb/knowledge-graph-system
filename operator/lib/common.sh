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
        amd)
            if [ -f "$DOCKER_DIR/docker-compose.gpu-amd.yml" ]; then
                cmd="$cmd -f $DOCKER_DIR/docker-compose.gpu-amd.yml"
            fi
            ;;
        amd-host)
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
