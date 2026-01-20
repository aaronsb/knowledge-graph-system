# Release Matrix

All components are versioned together and must match for compatibility.

| Version | API | Web | Operator | Date | Notes |
|---------|-----|-----|----------|------|-------|
| 0.6.1 | 0.6.1 | 0.6.1 | 0.6.1 | 2026-01-19 | Thin shim operator architecture |
| 0.6.0 | 0.6.0 | 0.6.0 | 0.6.0 | 2026-01-20 | Macvlan networking, admin config UI |
| 0.5.0 | 0.5.0 | 0.5.0 | 0.5.0 | 2026-01-19 | DNS-01 SSL, operator shell commands |
| 0.4.0 | 0.4.0 | 0.4.0 | 0.4.0 | 2026-01-18 | Initial GHCR release |

## Version Policy

- **All components share the same version number**
- Components are tested together and released as a set
- Mixing versions is not supported

## Changelog

### 0.6.1 (2026-01-19)

**Architecture**
- Refactored operator.sh to thin shim pattern (~200 lines)
- All complex logic now lives in kg-operator container
- Container includes docker compose v2 plugin for sibling management
- Watchtower-inspired architecture: operator manages platform via docker socket

**Improvements**
- Better TTY detection for interactive commands
- Fixed container naming for dev vs standalone modes
- Added --no-recreate flag to prevent unnecessary container restarts

### 0.6.0 (2026-01-20)

**Features**
- Macvlan networking support in installer (create/use/delete lifecycle)
- DHCP mode with persistent MAC address generation
- Interactive admin config UI for AI providers, embeddings, and API keys
- Contextual next-steps guidance in install summary

**Improvements**
- Insecure crypto fallback for dev environments (HTTP)
- Better error handling for API key configuration

### 0.5.0 (2026-01-19)

**Features**
- DNS-01 SSL challenge support (acme.sh) for internal networks
- Operator shell commands: `ai-provider`, `embedding`, `api-key`
- Headless installation with full configuration options

**Improvements**
- SSL healthcheck uses HTTP endpoint internally
- Embedding profile activation by provider name

### 0.4.0 (2026-01-18)

**Features**
- Initial release to GitHub Container Registry
- Standalone installer (`install.sh`)
- Basic SSL support (Let's Encrypt, manual, self-signed)

## Image Locations

```
ghcr.io/aaronsb/knowledge-graph-system/kg-api:<version>
ghcr.io/aaronsb/knowledge-graph-system/kg-web:<version>
ghcr.io/aaronsb/knowledge-graph-system/kg-operator:<version>
```

## Upgrade Path

```bash
cd /path/to/knowledge-graph
./operator.sh upgrade
```

This pulls matching images and restarts services with migrations.
