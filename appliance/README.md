# KG x86 Thin Appliance

Build tooling for the **x86 thin-appliance VM image** — Stage 2 of the
distribution strategy in
[ADR-103](../docs/architecture/infrastructure/ADR-103-distribution-strategy-nomic-first-thin-appliance-with-app-store-tenancy.md).

The appliance is **ADR-086's "cube" deployment, baked into a VM**: a minimal
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

# pin a ref / label
./appliance/build-appliance.sh --ref v0.15.1 --version 0.15.1 --ova
```

Artifacts land in `appliance/out/`. The Debian base is cached in
`appliance/.cache/` between builds (both are git-ignored).

## First boot

1. Import the qcow2/OVA, give it a **bridged or NAT NIC with internet** (first
   boot pulls images), 2 vCPU / 4 GiB minimum.
2. Power on. Watch provisioning: `journalctl -u kg-firstboot -f`.
3. When the login banner shows the Web UI URL, browse to it, set the admin
   password, and paste a reasoning (OpenAI/Anthropic) API key. Embeddings run
   locally via the baked nomic model — no key needed for those.

## Layout

```
appliance/
├── build-appliance.sh            # the build (virt-customize)
├── files/
│   ├── kg-firstboot.sh           # per-VM first-boot provisioner (secrets + start)
│   └── kg-firstboot.service      # oneshot systemd unit (self-disarms via sentinel)
└── ovf/
    └── kg-appliance.ovf.template # OVF descriptor for the OVA wrap
```

## Deferred

- **Packer/QEMU template** — a CI-driven alternative to virt-customize for
  release builds (ADR-103 build-tool note). virt-customize is the current path.
- **Warm variant** (images pre-baked) — kept thin for now per ADR-103.
- **arm64 / Raspberry Pi image** — blocked on the ADR-103 arm64 gates
  (AGE/Garage arm64 variants, 4 GiB RAM budget).
