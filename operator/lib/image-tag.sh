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

# Derive the kg-api image tag for a given GPU_MODE.
#
# Args:
#   $1 = GPU_MODE       (amd-host | nvidia | mac | cpu)
#   $2 = ROCM_VERSION   (legacy; ignored — kept for backward-compatible
#                        signature with older callers that still pass it)
#
# Echoes the tag to stdout. Defaults to "latest" for unknown modes —
# kg-api:latest carries PyPI's default torch wheel (CUDA runtime bundled,
# works on NVIDIA + CPU).
#
# AMD ROCm: only the host-ROCm variant (amd-host -> rocm72-host) is
# supported. The previous wheel-based amd variants (rocm60/rocm61) were
# never published; ADR-101 update 2026-05-28 removed that path. Legacy
# values of GPU_MODE=amd in older .operator.conf files are treated as
# an alias for amd-host with a warning.
derive_kg_api_image_tag() {
    local mode="${1:-cpu}"

    case "$mode" in
        amd-host)
            echo "rocm72-host"
            ;;
        amd)
            # Deprecated alias. Emit warning to stderr so it shows up
            # in logs without polluting the stdout tag value.
            echo "GPU_MODE=amd is deprecated; treating as amd-host" >&2
            echo "Edit .operator.conf or re-run ./operator.sh init" >&2
            echo "rocm72-host"
            ;;
        *)
            echo "latest"
            ;;
    esac
}
