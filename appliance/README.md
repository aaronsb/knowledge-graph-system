# KG x86 Thin Appliance

Build tooling for the **x86 thin-appliance VM image** — Stage 2 of the
distribution strategy in
[ADR-103](../docs/architecture/infrastructure/ADR-103-distribution-strategy-nomic-first-thin-appliance-with-app-store-tenancy.md).

The appliance is **ADR-117's "cube" deployment, baked into a VM**: a minimal
Debian host with Docker + the repo at `/opt/kg`, configured to pull GHCR images,
plus a oneshot first-boot unit that mints per-instance secrets and starts the
platform. It is **thin** — container images are pulled on first boot, so updates
keep flowing through `operator.sh upgrade`.

## The bake / first-boot split (why this is safe to ship)

| Phase | Where | What | Secrets? |
|-------|-------|------|----------|
| **Bake** | `build-appliance.sh` on a build host | Debian base + Docker + repo at `/opt/kg` + enabled first-boot unit | **None baked** |
| **First boot** | per-VM, once | `kg-firstboot.sh` → `operator.sh init --headless` → unique secrets → start stack | minted here |
| **Day-1** | operator, browser | set admin password + paste a *reasoning* key (embeddings already local) | — |

Shipping a baked `.env` would give every appliance the same `ENCRYPTION_KEY` /
`POSTGRES_PASSWORD`. The image deliberately carries **no `.env` and no secrets**;
`operator/lib/init-secrets.sh` (python3 stdlib, idempotent) mints them per
instance on first boot.

## Prerequisites (Debian/Ubuntu build host)

```bash
sudo apt install libguestfs-tools qemu-utils git curl jq
```

`virt-customize` (libguestfs) customizes the cloud image **in place** — no VM
boot during the build.

## Build

```bash
# qcow2 only (Proxmox / QEMU / libvirt)
./appliance/build-appliance.sh

# also emit an OVA (VMware / VirtualBox)
./appliance/build-appliance.sh --ova

# pin a ref / label; opt out of the Cockpit host console
./appliance/build-appliance.sh --ref v0.15.1 --version 0.15.1 --ova --no-cockpit
```

Artifacts land in `appliance/out/`. The Debian base is cached in
`appliance/.cache/` between builds (both are git-ignored).

The qcow2/OVA is built **locally** and attached to the matching GitHub Release,
together with a `SHA256SUMS` file — `./publish.sh appliance` automates the build,
`.xz` compression, checksums, and upload (the previously-manual step). Same
philosophy as the container images (build where it's fast, push, let CI
integrate).

The OVA is a **bootstrap seed, not a per-release artifact** (ADR-103): you
download it once, run it, and thereafter `operator.sh upgrade` pulls fresh GHCR
images to stay current. The *images* are the per-release artifacts; the OVA is
republished only occasionally to move the baseline — hence `publish.sh appliance`
is its own command, decoupled from `release`. CI does **not** build the image:
emulated `virt-customize` under TCG
is slow and re-proves the least-interesting layer. Instead, the
`appliance-integration.yml` workflow pulls the published GHCR images and runs
this appliance's real first-boot path (`operator.sh init --headless
--image-source=ghcr`) on a native-CPU runner, asserting the stack comes up
healthy with per-instance secrets. That's the integration surface that actually
regresses.

## Control plane

The appliance has three management layers, in ascending privilege:

| Layer | Surface | Manages |
|-------|---------|---------|
| **Host** | Cockpit (`https://<ip>:9090`) · console TUI (tty1) · cloud-init | the VM/OS: network, storage, updates, logs |
| **Platform** | `kg-operator` container, via `operator.sh` (console menu option 6) | the graph platform: config, admin, lifecycle (Docker socket + config authority) |
| **Application** | web UI (`http://<ip>/`) · REST API | content: graphs, ontologies, ingestion |

- **Console TUI** runs on the VM console (tty1) in place of a login prompt —
  status, logs, restart, network, **the initial admin credentials**, the
  operator (platform) shell, a host login, reboot/poweroff. No SSH required —
  a console-only operator can retrieve the generated admin password here.
- **Cockpit** (default on; `--no-cockpit` to omit) is the host web console for
  network/storage/updates/logs — including growing the root disk.

## First boot

### Interactive (zero config)

1. Import the qcow2/OVA, give it a **bridged or NAT NIC with internet** (first
   boot pulls images), 2 vCPU / 4 GiB minimum.
2. Power on. Watch provisioning on the console (tty1) or
   `journalctl -u kg-firstboot -f`.
3. When the banner shows the Web UI URL, browse to it. The generated admin
   password is in `/root/kg-credentials.txt` (and the console "info" menu).
   Paste a reasoning (OpenAI/Anthropic) API key under provider config —
   embeddings run locally via baked nomic, no key needed.

### Declarative (cloud-init user-data)

Supply config at deploy time and the box comes up fully configured. Drop a
`provision.env` via cloud-init `write_files` (see
[`files/provision.env.example`](files/provision.env.example)):

```yaml
#cloud-config
write_files:
  - path: /etc/kg/provision.env
    permissions: '0600'
    content: |
      KG_WEB_HOSTNAME=kg.example.com
      KG_AI_PROVIDER=anthropic
      KG_AI_MODEL=claude-sonnet-4
      KG_AI_KEY=sk-ant-...
```

`provision.env` is the appliance's single declarative control surface — sourced
by `kg-firstboot.sh`, extensible (unknown keys ignored), and the natural channel
a future fleet orchestrator would template per node.

## Deploy gotchas (libvirt/KVM) — learned the hard way

- **Attach the NoCloud seed as a VIRTIO disk, not a SATA/IDE cdrom.** The Debian
  *cloud* kernel ships no AHCI/SATA driver, so a `sr0`/`sda` seed is invisible →
  `ds-identify` finds no datasource → cloud-init is disabled → `provision.env`
  never lands and the box comes up with defaults. Attach the `cidata` ISO as
  `bus=virtio` (it shows up as `/dev/vdb`) and cloud-init finds it.
  ```
  virt-install ... \
    --disk path=kg-appliance.qcow2,bus=virtio \
    --disk path=kg-seed.iso,format=raw,bus=virtio,readonly=on
  ```
- **Changing the NIC MAC is safe.** The image disables cloud-init's network
  rendering and ships a DHCP netplan matched by interface *name* (`e*`), not MAC,
  so you can repoint the VM at a pinned DHCP reservation (`virt-xml <dom> --edit
  --network mac=<reserved>`) and it still gets an address. (cloud-init's default,
  MAC-pinned, would strand the NIC.)
- **Modern Docker Engine just works.** Engine ≥25 raised its minimum served API
  to 1.40, which Traefik v3's hard-coded 1.24 client would be rejected by; the
  image bakes `DOCKER_MIN_API_VERSION=1.24` as a `docker.service` drop-in.

## Layout

```
appliance/
├── build-appliance.sh                # the build (virt-customize)
├── files/
│   ├── kg-firstboot.sh               # per-VM first-boot provisioner (secrets + start)
│   ├── kg-firstboot.service          # oneshot systemd unit (self-disarms via sentinel)
│   ├── kg-console.sh                 # console TUI (DCUI) menu
│   ├── getty-console-override.conf   # getty@tty1 drop-in → runs the console
│   └── provision.env.example         # cloud-init declarative config template
└── ovf/
    └── kg-appliance.ovf.template     # OVF descriptor for the OVA wrap
```

## Deferred

- **Packer/QEMU template** — a CI-driven alternative to virt-customize for
  release builds (ADR-103 build-tool note). virt-customize is the current path.
- **Warm variant** (images pre-baked) — kept thin for now per ADR-103.
- **arm64 / Raspberry Pi image** — blocked on the ADR-103 arm64 gates
  (AGE/Garage arm64 variants, 4 GiB RAM budget).
