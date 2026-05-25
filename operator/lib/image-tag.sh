#!/bin/bash
# ============================================================================
# image-tag.sh - Single source of truth for KG_API_IMAGE_TAG derivation
# ============================================================================
#
# Maps GPU_MODE → the kg-api GHCR image tag the operator should pull. Sourced
# by every code path that needs the mapping:
#
#   operator.sh                       (standalone top-level entry point)
#   operator/lib/common.sh            (load_operator_config helper)
#   operator/lib/guided-init.sh       (wizard config persistence)
#
# Why a shared file: ADR-101's first PR shipped the mapping inline in
# load_operator_config (common.sh), then needed a fix-up commit when the
# top-level operator.sh's separate load_config was found to be missing it,
# and another fix-up to add the missing amd-host overlay case alongside.
# Three copies of the same case statement are guaranteed to drift again —
# one shared file ends the drift.
#
# See ADR-101 (docs/architecture/infrastructure/ADR-101-*.md) for the tag
# scheme rationale.
# ============================================================================

# Derive the kg-api image tag for a given GPU_MODE / ROCM_VERSION.
#
# Args:
#   $1 = GPU_MODE       (amd | amd-host | nvidia | mac | cpu)
#   $2 = ROCM_VERSION   (optional override, e.g. rocm60 | rocm61)
#
# Echoes the tag to stdout. Defaults to "latest" for unknown modes —
# kg-api:latest carries PyPI's default torch wheel (CUDA runtime bundled,
# works on NVIDIA + CPU).
#
# Behavior for amd mode: until ROCm 6.x wheel-based variants (rocm60/rocm61)
# are built and published, the amd path resolves to :latest. ADR-101's CPU
# fallback then absorbs the inevitable cuda-init failure (no NVIDIA driver
# on AMD hosts) and the install runs CPU embeddings instead of silent-
# breaking. Once a tester confirms a wheel variant builds, set
# ROCM_VERSION=rocm60 (or rocm61) in .operator.conf to switch over.
derive_kg_api_image_tag() {
    local mode="${1:-cpu}"
    local rocm_ver="$2"

    case "$mode" in
        amd)
            if [ -n "$rocm_ver" ]; then
                echo "$rocm_ver"
            else
                echo "latest"
            fi
            ;;
        amd-host)
            echo "rocm72-host"
            ;;
        *)
            echo "latest"
            ;;
    esac
}
