#!/usr/bin/env bash
# ============================================================================
# kg-console.sh — appliance console menu (the "DCUI" surface, pfSense/TrueNAS-style)
# ============================================================================
#
# Runs on tty1 in place of a login prompt (installed via a getty@tty1 drop-in).
# This is what someone sees on the hypervisor console: where the box is, and a
# few safe operations — without needing SSH. The shell option drops to an
# authenticated login; everything else is read-mostly or a clean lifecycle call.
#
# Federation seam (not built yet): this menu is the natural place to later show
# a shard's election/peer status once ADR-118 lands. Kept extensible on purpose.
# ============================================================================
set -uo pipefail

KG_DIR="/opt/kg"

primary_ip() {
    ip route get 1.1.1.1 2>/dev/null \
        | awk '{for (i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}'
}

# Egress interface name + its MAC. Surfaced on the banner so an operator can set a
# DHCP reservation (pin the appliance to a stable IP) straight from the console —
# without SSH or hunting through `ip link`. The reservation is also the
# prerequisite for a public DNS A-record / TLS hostname (ADR-105).
egress_iface() {
    ip route get 1.1.1.1 2>/dev/null \
        | awk '{for (i=1;i<=NF;i++) if ($i=="dev") {print $(i+1); exit}}'
}
egress_mac() {
    local ifc; ifc="$(egress_iface)"
    [ -n "${ifc}" ] && cat "/sys/class/net/${ifc}/address" 2>/dev/null
}

pause() { echo; read -rp "  Press Enter to return to the menu... " _; }

banner() {
    local ip; ip="$(primary_ip)"; ip="${ip:-(no network)}"
    local ifc mac; ifc="$(egress_iface)"; mac="$(egress_mac)"
    clear 2>/dev/null || true
    cat <<EOF
  ════════════════════════════════════════════════════════════════
    Kappa Graph Appliance
  ════════════════════════════════════════════════════════════════
    Web UI:     http://${ip}:3000/
    Host mgmt:  https://${ip}:9090/   (Cockpit)
    Hostname:   $(hostname)
    MAC addr:   ${mac:-(unknown)}  on ${ifc:-?}  — pin a DHCP reservation here
  ────────────────────────────────────────────────────────────────
    1) Platform status
    2) Recent API logs
    3) Restart platform
    4) Network info
    5) Appliance / credentials info
    6) Platform config shell (operator container)
    7) Login shell (host)
    c) Cockpit /cockpit access control
    8) Reboot
    9) Power off
  ════════════════════════════════════════════════════════════════
EOF
}

action() {
    case "$1" in
        1) echo; (cd "${KG_DIR}" && ./operator.sh status) 2>&1 | sed 's/^/  /'; pause ;;
        2) echo; (cd "${KG_DIR}" && ./operator.sh logs api --tail 50) 2>&1 | tail -50 | sed 's/^/  /'; pause ;;
        3) echo "  Restarting platform..."; (cd "${KG_DIR}" && ./operator.sh stop && ./operator.sh start) 2>&1 | sed 's/^/  /'; pause ;;
        4) echo; ip -brief address 2>&1 | sed 's/^/  /'; echo; ip route 2>&1 | sed 's/^/  /';
           echo; echo "  Change network settings via Cockpit (https://$(primary_ip):9090/)."; pause ;;
        5) echo; echo "  Install dir:  ${KG_DIR}"; echo "  Version:      $(cat ${KG_DIR}/VERSION 2>/dev/null || echo unknown)"; echo;
           # The console is root- and hypervisor/physically-gated (highest trust
           # tier), so showing the generated admin password here is appropriate —
           # it's the only way a console-only operator (no SSH) can log in.
           if [ -f /root/kg-credentials.txt ]; then
               echo "  Initial admin credentials (change in the web UI, then delete the file):";
               sed 's/^/    /' /root/kg-credentials.txt;
           else
               echo "  Admin: set on first web sign-in, or provisioned via cloud-init.";
           fi; pause ;;
        # The operator container is the platform's privileged control plane
        # (Docker socket + config authority). This is the "close to the metal"
        # surface for the graph itself, distinct from a host shell.
        6) echo "  Entering operator container (Ctrl-D returns to this menu)..."; (cd "${KG_DIR}" && ./operator.sh shell) || true ;;
        7) echo "  Launching host login (Ctrl-D returns to this menu)..."; /bin/login || true ;;
        c|C)
            echo
            (cd "${KG_DIR}" && ./operator.sh cockpit-access) 2>&1 | sed 's/^/  /'
            echo
            echo "  Restrict who can reach the /cockpit host console (before its login):"
            echo "    1) Open  — no restriction (default)"
            echo "    2) Private/LAN only (RFC-1918 ranges)"
            echo "    3) Custom CIDRs"
            read -rp "  Choose [1-3], Enter to cancel: " sub
            case "${sub}" in
                1) (cd "${KG_DIR}" && ./operator.sh cockpit-access open)    2>&1 | sed 's/^/  /' ;;
                2) (cd "${KG_DIR}" && ./operator.sh cockpit-access private) 2>&1 | sed 's/^/  /' ;;
                3) read -rp "  CIDRs (comma-separated, e.g. 192.168.1.0/24): " cidrs
                   [ -n "${cidrs}" ] && (cd "${KG_DIR}" && ./operator.sh cockpit-access "${cidrs}") 2>&1 | sed 's/^/  /' \
                       || echo "  (cancelled)" ;;
                *) echo "  (cancelled)" ;;
            esac
            pause ;;
        8) read -rp "  Reboot the appliance? [y/N] " a; [ "${a,,}" = "y" ] && systemctl reboot ;;
        9) read -rp "  Power off the appliance? [y/N] " a; [ "${a,,}" = "y" ] && systemctl poweroff ;;
        *) ;;
    esac
}

# tty1 may come up before first-boot provisioning finishes; show a wait notice.
if [ ! -f "${KG_DIR}/.appliance-firstboot-done" ]; then
    clear 2>/dev/null || true
    echo "  Kappa Graph appliance — first boot in progress (pulling images)."
    echo "  This menu becomes available once provisioning completes."
    echo "  Follow along: journalctl -u kg-firstboot -f"
    echo
fi

while true; do
    banner
    # Exit cleanly on stdin EOF (console detach, or a login subshell closing
    # stdin) so getty respawns us — without the guard the loop busy-spins at
    # 100% CPU and Restart=always never fires because the process stays alive (H3).
    read -rp "  Select an option [1-9, c]: " choice || { sleep 1; exit 0; }
    action "${choice}"
done
