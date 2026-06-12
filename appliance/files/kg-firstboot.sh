#!/usr/bin/env bash
# ============================================================================
# kg-firstboot.sh — KG thin-appliance first-boot provisioner (ADR-103 Stage 2)
# ============================================================================
#
# Runs EXACTLY ONCE on the first power-on of a freshly cloned appliance VM.
# This is the bake/first-boot split that keeps the image safe to ship:
#
#   - The baked image carries OS + Docker + the repo at /opt/kg, but NO .env
#     and NO secrets. Shipping a baked .env would give every appliance the
#     same ENCRYPTION_KEY / POSTGRES_PASSWORD — catastrophic.
#   - This script mints UNIQUE per-instance secrets here, on first boot, via
#     `operator.sh init --headless` -> operator/lib/init-secrets.sh (python3
#     stdlib, idempotent), then starts the standalone GHCR stack.
#
# Embeddings are local (nomic weights baked into the kg-api image, ADR-103
# invariant), so the box is self-contained for the private/edge half of the
# workload. Only *reasoning/extraction* needs a cloud key, which the operator
# pastes in the web UI after first boot — never required to reach a running
# platform.
#
# Idempotency: guarded by a sentinel file AND by init-secrets.sh's own
# already-configured detection, so a re-run (or a botched first boot) is safe.
# ============================================================================
set -euo pipefail

KG_DIR="/opt/kg"
SENTINEL="${KG_DIR}/.appliance-firstboot-done"
LOG_TAG="kg-firstboot"

log() { echo "[${LOG_TAG}] $*"; }

if [ -f "${SENTINEL}" ]; then
    log "sentinel present (${SENTINEL}); already provisioned — nothing to do."
    exit 0
fi

# --- Wait for the Docker daemon (started in parallel by systemd) -------------
log "waiting for Docker daemon..."
for _ in $(seq 1 60); do
    if docker info >/dev/null 2>&1; then
        break
    fi
    sleep 2
done
if ! docker info >/dev/null 2>&1; then
    log "ERROR: Docker daemon did not become ready in time; aborting first boot."
    log "       fix Docker, then: systemctl start kg-firstboot"
    exit 1
fi

# --- Derive the public hostname from the DHCP-assigned primary IP ------------
# WEB_HOSTNAME feeds OAuth redirect + API URLs; without it the web UI points
# at the wrong origin. We resolve the egress interface's source address.
IP="$(ip route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}')"
IP="${IP:-localhost}"
log "derived WEB_HOSTNAME=${IP}"

# --- Provision: mint per-instance secrets + start the standalone stack -------
# Mirrors ADR-086's cube deployment command, minus the AI key (reasoning is
# configured post-boot in the UI). --gpu=cpu: the generic VM appliance assumes
# no GPU passthrough; nomic embeddings run on CPU.
cd "${KG_DIR}"
log "running operator init (headless, ghcr, cpu, no AI key)..."
./operator.sh init --headless \
    --container-prefix=kg \
    --image-source=ghcr \
    --gpu=cpu \
    --web-hostname="${IP}" \
    --skip-ai-config \
    --skip-cli

# --- Mark done and write the login banner ------------------------------------
touch "${SENTINEL}"
log "provisioning complete; writing login banner."

cat > /etc/motd <<EOF

  Knowledge Graph appliance — ready.

  Web UI:   http://${IP}/
  Manage:   cd ${KG_DIR} && ./operator.sh status | logs api -f | stop | start

  NEXT STEPS (one-time, in the web UI):
    1. Sign in and set the admin password.
    2. Paste a *reasoning* API key (OpenAI/Anthropic) under provider config.
       Embeddings already run locally (nomic) — no key needed for those.

  Updates:  cd ${KG_DIR} && sudo ./operator.sh upgrade

EOF

log "done."
