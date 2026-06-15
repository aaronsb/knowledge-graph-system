#!/bin/bash
# ============================================================================
# recert.sh — TLS cert lifecycle helper (ADR-105 §5)
# ============================================================================
# Invoked by `operator.sh recert` inside the operator container. Traefik owns
# renewal for the automated modes, so this is deliberately THIN — a verify/nudge
# for `manual`, a no-op-with-status for the rest. It is not a renewal engine.
#
#   selfsigned   Traefik regenerates its built-in cert — nothing to do.
#   letsencrypt  Traefik's ACME resolver auto-renews — nothing to do.
#   manual       Operator supplies the cert off-box; the file provider hot-reloads.
#                We verify the cert exists and warn on imminent/past expiry.
#   offload      Upstream edge owns the cert — no-op.
#   none         No TLS at the router — no-op.
#
# Reads TLS_MODE from .operator.conf. @verified
# ============================================================================
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'

# /workspace is the repo root bind-mounted into the operator container.
WORKSPACE="${WORKSPACE:-/workspace}"
CONFIG_FILE="$WORKSPACE/.operator.conf"
ENV_FILE="$WORKSPACE/.env"

TLS_MODE="none"
[ -f "$CONFIG_FILE" ] && TLS_MODE="$(grep -E '^TLS_MODE=' "$CONFIG_FILE" 2>/dev/null | cut -d= -f2 || true)"
TLS_MODE="${TLS_MODE:-none}"
ACME_CHALLENGE="tls-alpn-01"
[ -f "$CONFIG_FILE" ] && ACME_CHALLENGE="$(grep -E '^ACME_CHALLENGE=' "$CONFIG_FILE" 2>/dev/null | cut -d= -f2 || true)"
ACME_CHALLENGE="${ACME_CHALLENGE:-tls-alpn-01}"

# KG_CERT_DIR: read it from .env — the SAME file `docker compose --env-file`
# substitutes into the manual overlay's cert mount — so recert checks exactly the
# path Traefik serves from. Explicit environment wins (matches compose precedence).
if [ -z "${KG_CERT_DIR:-}" ] && [ -f "$ENV_FILE" ]; then
    KG_CERT_DIR="$(grep -E '^KG_CERT_DIR=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
fi

# Days before expiry at which manual mode starts warning.
WARN_DAYS="${RECERT_WARN_DAYS:-21}"

# Resolve the manual cert dir the same way the compose overlay does: KG_CERT_DIR
# (relative paths are under docker/) defaulting to docker/certs.
resolve_cert_dir() {
    local dir="${KG_CERT_DIR:-./certs}"
    case "$dir" in
        /*) echo "$dir" ;;                       # absolute — use as-is
        ./*) echo "$WORKSPACE/docker/${dir#./}" ;;
        *)  echo "$WORKSPACE/docker/$dir" ;;
    esac
}

verify_manual() {
    local cert_dir crt key
    cert_dir="$(resolve_cert_dir)"
    crt="$cert_dir/tls.crt"
    key="$cert_dir/tls.key"

    if [ ! -f "$crt" ] || [ ! -f "$key" ]; then
        echo -e "${RED}✗ manual mode: cert+key not found${NC}"
        echo -e "  Expected: ${crt}"
        echo -e "            ${key}"
        echo -e "  Issue a cert off-box and drop both files here, then re-run recert."
        return 1
    fi

    if ! command -v openssl >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠ openssl not available — cannot check expiry. Cert files present.${NC}"
        return 0
    fi

    if ! openssl x509 -in "$crt" -noout >/dev/null 2>&1; then
        echo -e "${RED}✗ $crt is not a readable PEM certificate${NC}"
        return 1
    fi

    local not_after
    not_after="$(openssl x509 -in "$crt" -noout -enddate | cut -d= -f2)"
    echo -e "${BLUE}→ manual cert: ${crt}${NC}"
    echo -e "  Subject : $(openssl x509 -in "$crt" -noout -subject | sed 's/^subject=//')"
    echo -e "  Expires : ${not_after}"

    # Warn if within WARN_DAYS of expiry (or already expired).
    if openssl x509 -in "$crt" -noout -checkend $(( WARN_DAYS * 86400 )) >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Cert valid for more than ${WARN_DAYS} days. Traefik hot-reloads on replacement.${NC}"
    else
        if openssl x509 -in "$crt" -noout -checkend 0 >/dev/null 2>&1; then
            echo -e "${YELLOW}⚠ Cert expires within ${WARN_DAYS} days — re-issue off-box and replace ${crt}/.key${NC}"
        else
            echo -e "${RED}✗ Cert has EXPIRED — re-issue off-box and replace ${crt}/.key now${NC}"
            return 1
        fi
    fi
    return 0
}

echo -e "${BLUE}TLS mode:${NC} ${TLS_MODE}"
case "$TLS_MODE" in
    manual)
        verify_manual
        ;;
    selfsigned)
        echo -e "${GREEN}✓ selfsigned: Traefik serves/regenerates its built-in cert — nothing to renew.${NC}"
        ;;
    letsencrypt)
        echo -e "${GREEN}✓ letsencrypt (${ACME_CHALLENGE}): Traefik's ACME resolver auto-renews — nothing to do.${NC}"
        echo -e "  Inspect issued certs: docker logs <traefik> | grep -i acme"
        ;;
    offload)
        echo -e "${GREEN}✓ offload: the upstream edge owns the certificate — recert is a no-op.${NC}"
        ;;
    none|"")
        echo -e "${YELLOW}⚠ No TLS configured at the router (TLS_MODE=none) — nothing to recert.${NC}"
        ;;
    *)
        echo -e "${RED}✗ Unknown TLS_MODE: ${TLS_MODE}${NC}"
        exit 1
        ;;
esac
