#!/bin/bash
# ============================================================================
# common.sh - Shared functions for operator scripts
# ============================================================================

# Get project root (relative to this script in operator/lib/)
_COMMON_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="${PROJECT_ROOT:-$( cd "$_COMMON_DIR/../.." && pwd )}"
DOCKER_DIR="$PROJECT_ROOT/docker"
CONFIG_FILE="$PROJECT_ROOT/.operator.conf"
ENV_FILE="$PROJECT_ROOT/.env"

# Load configuration from .operator.conf
load_operator_config() {
    if [ -f "$CONFIG_FILE" ]; then
        source "$CONFIG_FILE"
    else
        # Defaults if no config file
        DEV_MODE="${DEV_MODE:-false}"
        GPU_MODE="${GPU_MODE:-cpu}"
    fi
}

# Build docker-compose command with appropriate files based on config
get_compose_cmd() {
    load_operator_config

    local cmd="docker-compose -f $DOCKER_DIR/docker-compose.yml"

    if [ "$DEV_MODE" = "true" ]; then
        if [ -f "$DOCKER_DIR/docker-compose.dev.yml" ]; then
            cmd="$cmd -f $DOCKER_DIR/docker-compose.dev.yml"
        fi
    fi

    case "$GPU_MODE" in
        nvidia)
            if [ -f "$DOCKER_DIR/docker-compose.gpu-nvidia.yml" ]; then
                cmd="$cmd -f $DOCKER_DIR/docker-compose.gpu-nvidia.yml"
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
