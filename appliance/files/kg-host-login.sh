#!/usr/bin/env bash
# ============================================================================
# kg-host-login.sh — provision the appliance's host-management login
# ============================================================================
#
# Cockpit (the host console on :9090) and the tty1 "Login shell" authenticate
# against OS accounts via PAM — NOT the Kappa Graph app's OAuth admin. A freshly
# baked appliance has only a locked root account, so there is nothing to log in
# with. This script provisions a sudo-enabled system user, declaratively and
# idempotently, so host management has a credential out of the box.
#
# It is the single reusable definition of the host login: kg-firstboot.sh calls
# it on first boot (after sourcing /etc/kg/provision.env), and it can be re-run
# standalone to (re)set the login on a running appliance.
#
# Inputs (environment; kg-firstboot sources provision.env first):
#   KG_HOST_LOGIN_USER      OS username to provision   (default: kgadmin)
#   KG_HOST_LOGIN_PASSWORD  password to set; if unset, a random one is generated
#                           and recorded in /root/kg-credentials.txt
#
# Standalone use on a running box (via the console "Login shell" or guest agent):
#   sudo KG_HOST_LOGIN_PASSWORD='choose-one' /opt/kg/appliance/files/kg-host-login.sh
#   # or let it mint + record one:
#   sudo /opt/kg/appliance/files/kg-host-login.sh
# ============================================================================
set -euo pipefail

USER_NAME="${KG_HOST_LOGIN_USER:-kgadmin}"
PASSWORD="${KG_HOST_LOGIN_PASSWORD:-}"
GENERATED=""

log() { echo "[kg-host-login] $*"; }

if [ "$(id -u)" -ne 0 ]; then
    echo "[kg-host-login] must run as root (try: sudo $0)" >&2
    exit 1
fi

# Mint a password when none was supplied. cut (not head) avoids the SIGPIPE that
# `set -o pipefail` would turn into a fatal error.
if [ -z "${PASSWORD}" ]; then
    PASSWORD="$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-20)"
    GENERATED=1
fi

# Create (idempotent) and ensure sudo membership + a usable shell.
if ! id "${USER_NAME}" >/dev/null 2>&1; then
    useradd -m -s /bin/bash -G sudo "${USER_NAME}"
    log "created user '${USER_NAME}' (sudo)"
else
    usermod -aG sudo -s /bin/bash "${USER_NAME}"
    log "user '${USER_NAME}' already exists; ensured sudo + shell"
fi

echo "${USER_NAME}:${PASSWORD}" | chpasswd
log "password set for '${USER_NAME}' (Cockpit :9090 / console login)"

# Record a generated password so the operator can recover it (same posture as the
# admin password). A caller-supplied password is the operator's to track, so we
# never write it out. Replace any prior host-login block to stay idempotent.
if [ -n "${GENERATED}" ]; then
    umask 077
    CRED="/root/kg-credentials.txt"
    touch "${CRED}"
    # Drop a previous host-login block (from a re-run) before appending a fresh one.
    sed -i '/^# --- host-management login ---$/,/^# --- end host-management login ---$/d' "${CRED}"
    cat >> "${CRED}" <<EOF
# --- host-management login ---
Host management (Cockpit :9090 / console "Login shell") — OS account:
  username: ${USER_NAME}
  password: ${PASSWORD}
# --- end host-management login ---
EOF
    log "generated password recorded in ${CRED}"
fi
