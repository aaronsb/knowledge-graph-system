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

# --- Optional declarative config (cloud-init drops it at /etc/kg/provision.env)
# This is the appliance's single declarative control surface. Sourced if present;
# absent → DHCP-IP + no AI key (finish in the UI). See provision.env.example.
PROVISION="/etc/kg/provision.env"
if [ -f "${PROVISION}" ]; then
    log "found ${PROVISION}; provisioning declaratively."
    # shellcheck disable=SC1090
    . "${PROVISION}"
else
    log "no ${PROVISION}; provisioning with defaults (DHCP IP, no AI key)."
fi

# --- Resolve WEB_HOSTNAME: explicit override, else DHCP primary IP ------------
# WEB_HOSTNAME feeds OAuth redirect + API URLs; without it the web UI points at
# the wrong origin. We resolve the egress interface's source address.
IP="${KG_WEB_HOSTNAME:-}"
if [ -z "${IP}" ]; then
    IP="$(ip route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}')"
    IP="${IP:-localhost}"
fi
log "WEB_HOSTNAME=${IP}"

# --- Assemble the operator init invocation -----------------------------------
# Mirrors ADR-117's cube deployment. --gpu=cpu: the generic VM appliance assumes
# no GPU passthrough; nomic embeddings run on CPU. Reasoning creds are passed
# through only if provision.env supplied them — otherwise --skip-ai-config.
INIT_ARGS=(
    --headless
    --container-prefix=kg
    --image-source=ghcr
    --gpu=cpu
    --web-hostname="${IP}"
    --skip-cli
    --password-mode=random
)
if [ -n "${KG_AI_PROVIDER:-}" ] && [ -n "${KG_AI_KEY:-}" ]; then
    log "reasoning provider supplied (${KG_AI_PROVIDER}); configuring AI."
    INIT_ARGS+=( --ai-provider="${KG_AI_PROVIDER}" --ai-key="${KG_AI_KEY}" )
    [ -n "${KG_AI_MODEL:-}" ] && INIT_ARGS+=( --ai-model="${KG_AI_MODEL}" )
else
    log "no reasoning key supplied; deferring AI config to the web UI."
    INIT_ARGS+=( --skip-ai-config )
fi

# --- TLS / ingress (ADR-105) -------------------------------------------------
# Declarative TLS via provision.env. For a PRIVATE box with a public DNS name,
# --tls=letsencrypt --acme-challenge=dns-01 (porkbun) is the self-renewing path:
# DNS-01 is the only ACME challenge that works without inbound :443/:80. The DNS
# provider credentials are exported into the operator's env (never the command
# line) so the operator persists them to .env for Traefik/lego.
[ -n "${KG_EXTERNAL_URL:-}" ] && INIT_ARGS+=( --external-url="${KG_EXTERNAL_URL}" )
if [ -n "${KG_TLS_MODE:-}" ]; then
    # In-VM TLS modes need the traefik router; default it so provision.env can
    # just set KG_TLS_MODE.
    INIT_ARGS+=( --router="${KG_ROUTER:-traefik}" --tls="${KG_TLS_MODE}" )
    [ -n "${KG_LE_EMAIL:-}" ] && INIT_ARGS+=( --le-email="${KG_LE_EMAIL}" )
    if [ -n "${KG_ACME_CHALLENGE:-}" ]; then
        INIT_ARGS+=( --acme-challenge="${KG_ACME_CHALLENGE}" )
        [ -n "${KG_DNS_PROVIDER:-}" ] && INIT_ARGS+=( --dns-provider="${KG_DNS_PROVIDER}" )
        [ -n "${KG_PORKBUN_API_KEY:-}" ] && export PORKBUN_API_KEY="${KG_PORKBUN_API_KEY}"
        [ -n "${KG_PORKBUN_SECRET_API_KEY:-}" ] && export PORKBUN_SECRET_API_KEY="${KG_PORKBUN_SECRET_API_KEY}"
        log "TLS: ${KG_TLS_MODE} via ${KG_ACME_CHALLENGE} (${KG_DNS_PROVIDER:-porkbun})."
    else
        log "TLS: ${KG_TLS_MODE}."
    fi
elif [ -n "${KG_ROUTER:-}" ]; then
    INIT_ARGS+=( --router="${KG_ROUTER}" )
fi

# --- Provision: mint per-instance secrets + start the standalone stack -------
# Tee to a log so we can recover the generated admin password (operator prints
# it once to stdout; there's no read-it-back path since it's stored encrypted).
cd "${KG_DIR}"
PROV_LOG="/var/log/kg-firstboot.log"
# Pre-create root-only — this log captures operator output that includes the
# generated admin password, so it must not be world-readable (the umask below
# only applies after this point) (L5).
touch "${PROV_LOG}"; chmod 600 "${PROV_LOG}"
log "running operator init..."
./operator.sh init "${INIT_ARGS[@]}" 2>&1 | tee "${PROV_LOG}"

# --- Recover + persist the generated admin password --------------------------
# Strip ANSI, grab the value after "Admin password:". The grep is guarded with
# `|| true` so a no-match (e.g. an operator-output wording change) yields an
# empty string the [ -n ] check handles — rather than aborting first boot under
# `set -euo pipefail` before the sentinel is written (H1).
ADMIN_PW="$( { sed -E 's/\x1b\[[0-9;]*m//g' "${PROV_LOG}" | grep -iE 'Admin password:' || true; } \
    | head -1 | sed -E 's/.*Admin password:[[:space:]]*//')"
if [ -n "${ADMIN_PW}" ]; then
    umask 077
    cat > /root/kg-credentials.txt <<EOF
Kappa Graph appliance — initial credentials (generated $(date -Iseconds))
Admin username: admin
Admin password: ${ADMIN_PW}

Change this in the web UI. Delete this file once you've recorded it.
EOF
    log "admin password saved to /root/kg-credentials.txt"
fi

# --- Mark done and write the login banner ------------------------------------
touch "${SENTINEL}"
log "provisioning complete; writing login banner."

CRED_LINE="  Admin pw:  generated — see /root/kg-credentials.txt (or set in the UI)"
[ -z "${ADMIN_PW}" ] && CRED_LINE="  Admin pw:  set it on first sign-in"

cat > /etc/motd <<EOF

  Kappa Graph appliance — ready.

  Web UI:    http://${IP}:3000/
  Host mgmt: https://${IP}:9090/   (Cockpit — network, storage, logs, updates)
${CRED_LINE}

  NEXT STEPS (in the web UI):
    1. Sign in (admin) and set/confirm the admin password.
    2. If no reasoning key was provisioned, paste one (OpenAI/Anthropic) under
       provider config. Embeddings run locally (nomic) — no key needed.

  Console menu: switch to tty1.   Updates: sudo ${KG_DIR}/operator.sh upgrade

EOF

log "done."
