# Knowledge Graph FUSE Driver

Mount the knowledge graph as a filesystem. Browse ontologies, search concepts by creating directories, read documents — all through your file manager or terminal.

## Installation

### Prerequisites

**System FUSE library** (required):
```bash
sudo pacman -S fuse3       # Arch
sudo apt install fuse3     # Debian/Ubuntu
sudo dnf install fuse3     # Fedora
```

**kg CLI** (for authentication setup):
```bash
npm install -g @aaronsb/kg-cli
```

### Install kg-fuse

```bash
pipx install kg-fuse
```

## Quick Start

```bash
# 1. Authenticate with the knowledge graph
kg login
kg oauth create

# 2. Set up a FUSE mount (interactive — detects auth, validates path, offers autostart)
kg-fuse init /mnt/knowledge

# 3. Mount
kg-fuse mount
```

That's it. Browse `/mnt/knowledge/` in your file manager or terminal.

## Commands

```
kg-fuse                          Status of running mounts + help summary
kg-fuse init [mountpoint]        Interactive setup: detect auth, configure mount, offer autostart
kg-fuse mount                    Fork daemons for ALL configured mounts
kg-fuse mount /mnt/knowledge     Fork daemon for just this one
kg-fuse mount /mnt/knowledge -f  Run in foreground (for debugging)
kg-fuse unmount                  Kill all kg-fuse daemons, clean unmount
kg-fuse unmount /mnt/knowledge   Kill just this one
kg-fuse status                   Same as bare kg-fuse
kg-fuse config                   Show configuration with masked secrets
kg-fuse repair                   Detect and fix orphaned mounts, stale PIDs, bad config
kg-fuse update                   Self-update via pipx
```

Bare `kg-fuse` with no arguments shows mount status, daemon process info, API connectivity, and other FUSE mounts on the system.

## Configuration

### File layout

| File | Owner | Purpose |
|------|-------|---------|
| `~/.config/kg/config.json` | kg CLI | Auth credentials, API URL (kg-fuse reads only) |
| `~/.config/kg/fuse.json` | kg-fuse | Mount definitions, per-mount preferences |
| `~/.local/share/kg-fuse/mounts/<id>/queries.toml` | kg-fuse | Saved query directories per mount |
| `~/.local/state/kg-fuse/<id>.pid` | kg-fuse | Daemon PID files |

kg-fuse **never writes** to kg CLI's `config.json` — it only reads auth credentials from it. This isolates failures: a bug in kg-fuse can only damage `fuse.json`, never your kg CLI config.

### Credential resolution

Priority (highest to lowest):
1. CLI flags (`--client-id`, `--client-secret`)
2. `fuse.json` `auth_client_id` → lookup in `config.json` auth
3. `config.json` auth section directly
4. Error with guidance to run `kg login` + `kg oauth create`

### Example fuse.json

```json
{
  "auth_client_id": "kg-cli-admin-ba93368c",
  "mounts": {
    "/mnt/knowledge": {
      "tags": { "enabled": true, "threshold": 0.5 },
      "cache": { "epoch_check_interval": 5.0, "content_cache_max": 52428800 },
      "jobs": { "hide_jobs": false }
    }
  }
}
```

## Filesystem Structure

```
/mnt/knowledge/
├── ontology/                   # System-managed ontology listing
│   ├── ontology-a/
│   │   ├── documents/          # Source documents (read-only, write to ingest)
│   │   │   ├── doc1.md
│   │   │   └── image.png
│   │   └── my-query/           # User query scoped to this ontology
│   │       ├── concept1.concept.md
│   │       ├── concept2.concept.md
│   │       ├── images/         # Image evidence from matching concepts
│   │       └── .meta/          # Query control plane
│   └── ontology-b/
│       └── documents/
└── my-global-query/            # User query across all ontologies
    └── *.concept.md
```

### Query directories

Create a directory → it becomes a semantic search:

```bash
mkdir /mnt/knowledge/ontology/my-ontology/leadership
ls /mnt/knowledge/ontology/my-ontology/leadership/
# → concept files matching "leadership" within that ontology

mkdir /mnt/knowledge/machine-learning
ls /mnt/knowledge/machine-learning/
# → concept files matching "machine learning" across all ontologies
```

### Query control plane (.meta)

Each query directory has a `.meta/` subdirectory for tuning:

```bash
cat .meta/threshold     # Read current threshold (0.0-1.0)
echo 0.3 > .meta/threshold  # Lower threshold for broader matches
echo 100 > .meta/limit      # Increase result limit
echo "noise" >> .meta/exclude   # Filter out a term
echo "AI" >> .meta/union        # Broaden with additional term
```

### Write: Ingest documents

```bash
cp report.pdf /mnt/knowledge/ontology/my-ontology/documents/
# File enters the ingestion pipeline → extracts concepts → links to graph
```

## Autostart

`kg-fuse init` offers to set up autostart:

- **Systemd** (preferred): installs a user service at `~/.config/systemd/user/kg-fuse.service`
- **Shell RC** (fallback): adds `kg-fuse mount` to `.bash_profile`, `.zshrc`, or fish config

Manage systemd service:
```bash
systemctl --user status kg-fuse
systemctl --user restart kg-fuse
journalctl --user -u kg-fuse -f
```

## Safety

kg-fuse includes several safety checks:

- **Mountpoint validation**: refuses system paths (`/home`, `/etc`, etc.) and non-empty directories
- **FUSE collision detection**: checks for existing FUSE mounts (rclone, SSHFS, etc.) at the target path
- **Config isolation**: kg-fuse writes only to `fuse.json`, never to kg CLI's `config.json`
- **Atomic config writes**: `fuse.json` updates use temp file + rename for crash safety
- **PID verification**: before killing a daemon, verifies it's actually a kg-fuse process via `/proc/cmdline`
- **Orphan recovery**: `kg-fuse repair` detects dead mounts ("transport endpoint not connected") and cleans up
- **RC file safety**: shell config changes use delimited blocks with backups

## Debug Mode

```bash
kg-fuse mount /mnt/knowledge -f --debug
```

Runs in foreground with verbose logging. Daemon logs are also available at:
```
~/.local/share/kg-fuse/mounts/<mount-id>/daemon.log
```

## Architecture

The FUSE driver is an independent Python client that:
- Authenticates via OAuth (shared credentials with kg CLI)
- Makes HTTP requests to the knowledge graph API
- Uses epoch-gated caching for directory listings (background refresh, not fixed TTL)
- Persists user query directories in client-side TOML files
- Runs as a daemonized process per mount point

See [ADR-069](../docs/architecture/ADR-069-fuse-filesystem-driver.md) for design rationale.
