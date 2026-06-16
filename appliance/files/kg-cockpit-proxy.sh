#!/usr/bin/env bash
# ============================================================================
# kg-cockpit-proxy.sh — configure Cockpit to sit behind Traefik at /cockpit
# ============================================================================
#
# Cockpit defaults to serving at the root of :9090 with its own self-signed cert.
# To front it through Traefik at https://<host>/cockpit/ (sharing the trusted
# Let's Encrypt cert), Cockpit must be told its URL root and the external origin
# it will be reached from. This writes /etc/cockpit/cockpit.conf accordingly.
#
# Pairs with docker-compose.traefik-cockpit.yml (the socat sidecar + Traefik
# route). kg-firstboot.sh calls this; it is idempotent and re-runnable standalone
# to (re)point Cockpit at a new external URL on a running appliance.
#
# Input (environment; kg-firstboot sources /etc/kg/provision.env first):
#   KG_EXTERNAL_URL   public https URL, e.g. https://kg.example.com. Required —
#                     the Origins/cert hostname derives from it. No-op if unset.
# ============================================================================
set -euo pipefail

log() { echo "[kg-cockpit-proxy] $*"; }

if [ "$(id -u)" -ne 0 ]; then
    echo "[kg-cockpit-proxy] must run as root (try: sudo $0)" >&2
    exit 1
fi

EXTERNAL="${KG_EXTERNAL_URL:-}"
if [ -z "${EXTERNAL}" ]; then
    log "KG_EXTERNAL_URL unset; nothing to do (Cockpit stays on :9090)."
    exit 0
fi

# Bare host (no scheme/port/path) — Cockpit's Origins + the cert hostname.
HOST="${EXTERNAL#*://}"
HOST="${HOST%%[:/]*}"

mkdir -p /etc/cockpit
cat > /etc/cockpit/cockpit.conf <<EOF
# Managed by kg-cockpit-proxy.sh — Cockpit behind Traefik at /cockpit.
[WebService]
# Serve under the /cockpit path so Traefik can route to it by prefix.
UrlRoot = /cockpit
# Allow the external origin for the login WebSocket / CSRF check.
Origins = https://${HOST} wss://${HOST}
# Trust Traefik's X-Forwarded-Proto so Cockpit knows the edge is https.
ProtocolHeader = X-Forwarded-Proto
# Traefik terminates TLS and speaks plain HTTP to the sidecar; accept it.
AllowUnencrypted = true
EOF

# Apply: Cockpit reads cockpit.conf per ws process; restart the socket+service.
systemctl restart cockpit.socket cockpit 2>/dev/null || true
log "Cockpit configured under /cockpit for ${HOST}."
