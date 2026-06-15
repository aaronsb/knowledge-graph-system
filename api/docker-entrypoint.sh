#!/bin/sh
# Seed baked default embedding models into the persistent HuggingFace cache on
# first boot, then exec the API server.
#
# Why this exists: the HF cache path (~/.cache/huggingface) sits under a mounted
# volume (hf_cache -> /home/api/.cache in every compose variant). Models baked
# directly into that path in the image would be SHADOWED by the empty volume on
# first start, forcing a runtime HuggingFace download and breaking offline /
# air-gapped / Raspberry-Pi appliance boot (ADR-103).
#
# So the image bakes the default text + vision models into /opt/hf-seed (NOT
# under the volume), and this script copies them into the live cache once.
# `cp -n` never clobbers, so models a user later switches to or adds, and any
# updated weights, are preserved across restarts. After seeding,
# EmbeddingModelManager's local_files_only-first load finds the weights and
# never touches the network. See ADR-103 (nomic-first appliance) and ADR-804.
set -e

SEED=/opt/hf-seed
DEST="${HF_HOME:-$HOME/.cache/huggingface}"

if [ -d "$SEED" ]; then
    mkdir -p "$DEST"
    # Trailing /. copies the contents (hub/, modules/) into the cache root.
    # -R recursive, -n no-clobber. Tolerate races/perms — first boot seeds it.
    cp -Rn "$SEED/." "$DEST/" 2>/dev/null || true
fi

exec "$@"
