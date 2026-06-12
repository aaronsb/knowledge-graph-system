#!/usr/bin/env bash
# ============================================================================
# build-appliance.sh — build the KG x86 thin-appliance VM image (ADR-103 §Stage 2)
# ============================================================================
#
# Produces a bootable qcow2 (and optionally an OVA) that is "ADR-086's cube
# deployment, baked": a minimal Debian host with Docker + the repo at /opt/kg,
# configured to pull GHCR images, with a oneshot first-boot unit that mints
# per-instance secrets and starts the platform.
#
# THIN by design (ADR-103): container images are NOT baked. They are pulled on
# first boot, so updates keep flowing through `operator.sh upgrade`. Only the
# nomic embedding weights are offline — and those live inside the kg-api image,
# pulled on first boot like everything else.
#
# NOT baked, by invariant: no .env, no secrets. Secrets are minted per-instance
# on first boot (see appliance/files/kg-firstboot.sh).
#
# Tooling: virt-customize (libguestfs) — customizes the cloud image in place,
# no VM boot required. A Packer/QEMU template is a deferred alternative for
# CI-driven release builds (ADR-103 build-tool note).
#
# Usage:
#   ./appliance/build-appliance.sh [options]
#     --ref REF          git ref to bake (default: HEAD)
#     --version LABEL    artifact version label (default: derived from git describe)
#     --debian VER       Debian release number (default: 12)
#     --size SIZE        root disk size (default: 20G)
#     --output DIR       output directory (default: ./appliance/out)
#     --ova              also emit an OVA (qcow2 -> vmdk -> OVF wrap)
#     --help
#
# Prerequisites (Debian/Ubuntu host):
#   sudo apt install libguestfs-tools qemu-utils
# ============================================================================
set -euo pipefail

# --- Resolve paths -----------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# --- Defaults ----------------------------------------------------------------
REF="HEAD"
VERSION=""
DEBIAN_VER="12"
DISK_SIZE="20G"
OUTPUT_DIR="${SCRIPT_DIR}/out"
MAKE_OVA="false"
CACHE_DIR="${SCRIPT_DIR}/.cache"

# --- Parse args --------------------------------------------------------------
while [ $# -gt 0 ]; do
    case "$1" in
        --ref)      REF="$2"; shift 2 ;;
        --version)  VERSION="$2"; shift 2 ;;
        --debian)   DEBIAN_VER="$2"; shift 2 ;;
        --size)     DISK_SIZE="$2"; shift 2 ;;
        --output)   OUTPUT_DIR="$2"; shift 2 ;;
        --ova)      MAKE_OVA="true"; shift ;;
        --help|-h)  sed -n '2,40p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

[ -n "${VERSION}" ] || VERSION="$(cd "${REPO_ROOT}" && git describe --tags --always --dirty 2>/dev/null || echo dev)"

log()  { echo -e "\033[0;34m[build]\033[0m $*"; }
die()  { echo -e "\033[0;31m[build] ERROR:\033[0m $*" >&2; exit 1; }

# --- Preflight ---------------------------------------------------------------
for tool in virt-customize qemu-img git curl; do
    command -v "$tool" >/dev/null 2>&1 || die "missing '$tool' (sudo apt install libguestfs-tools qemu-utils git curl)"
done
if [ "${MAKE_OVA}" = "true" ]; then
    command -v sha1sum >/dev/null 2>&1 || die "--ova needs sha1sum (coreutils)"
fi

mkdir -p "${OUTPUT_DIR}" "${CACHE_DIR}"

# --- 1. Fetch the Debian genericcloud base (cached) --------------------------
# genericcloud: cloud-init enabled, no cloud-vendor agents, small. The qcow2 is
# already a sparse, resizeable disk.
BASE_NAME="debian-${DEBIAN_VER}-genericcloud-amd64.qcow2"
BASE_URL="https://cloud.debian.org/images/cloud/$( [ "${DEBIAN_VER}" = "12" ] && echo bookworm || echo "debian-${DEBIAN_VER}" )/latest/${BASE_NAME}"
BASE_IMG="${CACHE_DIR}/${BASE_NAME}"
if [ ! -f "${BASE_IMG}" ]; then
    log "downloading Debian ${DEBIAN_VER} genericcloud base..."
    curl -fSL "${BASE_URL}" -o "${BASE_IMG}.tmp"
    mv "${BASE_IMG}.tmp" "${BASE_IMG}"
else
    log "using cached base image: ${BASE_IMG}"
fi

# --- 2. Stage the repo tarball (git archive — tracked files only, no cruft) --
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT
REPO_TAR="${WORK}/kg-repo.tar"
log "archiving repo at ref '${REF}'..."
(cd "${REPO_ROOT}" && git archive --format=tar --prefix=kg/ "${REF}") > "${REPO_TAR}"

# --- 3. Copy base -> working disk and resize ---------------------------------
OUT_QCOW="${OUTPUT_DIR}/kg-appliance-${VERSION}.qcow2"
log "preparing working disk ${OUT_QCOW} (${DISK_SIZE})..."
qemu-img convert -O qcow2 "${BASE_IMG}" "${OUT_QCOW}"
qemu-img resize "${OUT_QCOW}" "${DISK_SIZE}"

# --- 4. Customize in place with virt-customize -------------------------------
# Docker via the official convenience script (gives docker-ce + the v2 compose
# plugin operator.sh needs). python3/openssl/curl/git: secret-gen + operator.
log "customizing image (no VM boot; --network lets apt + get.docker.com fetch)..."
virt-customize -a "${OUT_QCOW}" \
    --network \
    --hostname "kg-appliance" \
    --run-command 'apt-get update' \
    --install qemu-guest-agent,ca-certificates,curl,python3,openssl,git,jq \
    --run-command 'curl -fsSL https://get.docker.com | sh' \
    --run-command 'systemctl enable docker qemu-guest-agent' \
    --upload "${REPO_TAR}:/tmp/kg-repo.tar" \
    --run-command 'tar -xf /tmp/kg-repo.tar -C /opt && rm -f /tmp/kg-repo.tar' \
    --run-command 'chmod +x /opt/kg/operator.sh /opt/kg/appliance/files/kg-firstboot.sh' \
    --run-command 'cp /opt/kg/appliance/files/kg-firstboot.service /etc/systemd/system/kg-firstboot.service' \
    --run-command 'systemctl enable kg-firstboot.service' \
    --run-command 'truncate -s 0 /etc/machine-id' \
    --run-command 'rm -f /var/lib/dbus/machine-id && ln -s /etc/machine-id /var/lib/dbus/machine-id' \
    --run-command 'cloud-init clean --logs 2>/dev/null || true' \
    --run-command 'apt-get clean && rm -rf /var/lib/apt/lists/*' \
    --run-command 'printf "\n  Knowledge Graph appliance — first boot in progress.\n  Run: journalctl -u kg-firstboot -f   (provisioning + image pull)\n\n" > /etc/motd'

# --- 5. Sparsify -------------------------------------------------------------
log "sparsifying..."
virt-sparsify --in-place "${OUT_QCOW}" >/dev/null 2>&1 || log "(sparsify skipped)"

log "qcow2 ready: ${OUT_QCOW}"
qemu-img info "${OUT_QCOW}" | sed 's/^/    /'

# --- 6. Optional OVA wrap ----------------------------------------------------
if [ "${MAKE_OVA}" = "true" ]; then
    log "wrapping OVA..."
    OVA_TMP="${WORK}/ova"
    mkdir -p "${OVA_TMP}"
    VMDK="${OVA_TMP}/kg-appliance-disk1.vmdk"
    qemu-img convert -O vmdk -o subformat=streamOptimized "${OUT_QCOW}" "${VMDK}"

    CAPACITY_BYTES="$(qemu-img info --output=json "${OUT_QCOW}" | jq -r '.["virtual-size"]')"
    VMDK_BYTES="$(stat -c%s "${VMDK}")"

    OVF="${OVA_TMP}/kg-appliance.ovf"
    sed -e "s|@@VERSION@@|${VERSION}|g" \
        -e "s|@@CAPACITY_BYTES@@|${CAPACITY_BYTES}|g" \
        -e "s|@@VMDK_BYTES@@|${VMDK_BYTES}|g" \
        -e "s|@@VMDK_FILE@@|kg-appliance-disk1.vmdk|g" \
        "${SCRIPT_DIR}/ovf/kg-appliance.ovf.template" > "${OVF}"

    # Manifest (.mf) with SHA1 of ovf + vmdk, then tar in OVF-first order.
    ( cd "${OVA_TMP}"
      {
        echo "SHA1(kg-appliance.ovf)= $(sha1sum kg-appliance.ovf | cut -d' ' -f1)"
        echo "SHA1(kg-appliance-disk1.vmdk)= $(sha1sum kg-appliance-disk1.vmdk | cut -d' ' -f1)"
      } > kg-appliance.mf
    )
    OUT_OVA="${OUTPUT_DIR}/kg-appliance-${VERSION}.ova"
    ( cd "${OVA_TMP}" && tar -cf "${OUT_OVA}" kg-appliance.ovf kg-appliance.mf kg-appliance-disk1.vmdk )
    log "OVA ready: ${OUT_OVA}"
fi

log "build complete (version ${VERSION})."
