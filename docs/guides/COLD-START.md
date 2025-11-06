# Knowledge Graph System - 5-Minute Cold Start

**Get from zero to operational system in under 5 minutes** (excluding optional restore).

**Status:** ✅ Nuclear tested on October 28, 2025 (complete system deletion and rebuild)

## Prerequisites

- Linux/Unix system with Docker installed
- Python 3.11+ and Node.js 18+
- OpenAI API key (or use local embeddings - see below)

## Quick Start (1 Command - Recommended)

**Fastest way to get started:**

```bash
# 1. Clone repository
git clone https://github.com/aaronsb/knowledge-graph-system.git
cd knowledge-graph-system

# 2. Run bootstrap script (handles everything automatically)
./scripts/setup/bootstrap.sh          # Production mode (interactive password)
# OR for development (uses default password 'Password1!'):
./scripts/setup/bootstrap.sh --dev    # Development mode (quick start)
```

**What bootstrap.sh does:**
- ✅ Checks prerequisites (Docker, Python, Node.js)
- ✅ Creates .env from .env.example
- ✅ Starts PostgreSQL + Apache AGE database
- ✅ Starts Garage object storage
- ✅ Starts FastAPI server
- ✅ Configures admin user, OAuth keys, encryption keys, embeddings
- ✅ Installs kg CLI globally
- ✅ Verifies system health

**Total time:** ~3-4 minutes for fresh system! 🚀

## Manual Step-by-Step (Alternative)

If you prefer to run each step manually:

```bash
# 1. Clone repository (30 seconds)
git clone https://github.com/aaronsb/knowledge-graph-system.git
cd knowledge-graph-system

# 2. Start database - auto-applies schema + migrations (15 seconds)
./scripts/services/start-database.sh

# 3. Start Garage object storage (10 seconds)
./scripts/services/start-garage.sh -y

# 4. Start API server - auto-creates venv + installs deps (15 seconds)
./scripts/services/start-api.sh -y

# 5. Initialize auth + configure embeddings (interactive, 60 seconds)
./scripts/setup/initialize-platform.sh          # Production mode (interactive password)
# OR for development (uses default password 'Password1!'):
./scripts/setup/initialize-platform.sh --dev    # Development mode (quick start)

# Steps:
# → Set admin password (or uses Password1! in dev mode)
# → Auto-generates OAuth signing keys
# → Auto-generates encryption key
# → Choose embedding option:
#    Option 1: OpenAI (paste your API key when prompted)
#    Option 2: Local embeddings (Nomic - no API key needed)

# 6. Install kg CLI (20 seconds)
cd client && ./install.sh && cd ..
```

**Verify it worked:**
```bash
kg health          # Should show: API healthy
kg database stats  # Should show: 0 concepts (empty database ready)
```

**Total time:** ~3-4 minutes for fresh system! 🚀

## Configuration Notes

### Development vs Production Mode

**Development Mode (`--dev` flag):**
```bash
./scripts/setup/initialize-platform.sh --dev
```
- Sets admin password to `Password1!` (no prompts)
- Fastest cold start (~30 seconds)
- Perfect for local development, testing, demos
- ⚠️ **NEVER use in production!**

**Production Mode (default):**
```bash
./scripts/setup/initialize-platform.sh
# OR in Docker with environment variable:
ADMIN_PASSWORD='YourSecurePassword!' ./scripts/setup/initialize-platform.sh --non-interactive
```
- Prompts for secure password (interactive)
- OR accepts password via `ADMIN_PASSWORD` environment variable (Docker)
- Required for production deployments
- Password must meet requirements:
  - Minimum 8 characters
  - Uppercase, lowercase, digit, special character

### OpenAI API Key (Recommended for Quick Start)

When running `initialize-platform.sh`, **paste your OpenAI API key directly** when prompted:
- Uses OpenAI embeddings (1536 dimensions)
- Fast and reliable
- Costs ~$0.01 per 1000 concepts

### Local Embeddings (No API Key Required)

Alternative if you don't have OpenAI API key:
- Select option 2 during `initialize-platform.sh`
- Uses Nomic embeddings (768 dimensions)
- Runs locally via Ollama
- Free but requires more setup

## Restoring a Backup

If you have an existing backup to restore:

**Step 1: Match embedder to backup**

Check your backup's embedding dimensions:
```bash
# If backup was created with Nomic (768 dims):
kg admin embedding activate 2 --force  # Activate Nomic
kg admin embedding reload
```

**Step 2: Restore**
```bash
time kg admin restore ~/.local/share/kg/backups/your_backup.json
```

**Expected timing:** ~5 minutes for 30k items (3,436 concepts, 814 sources, 5,535 instances)

**What you'll see:**
- ✅ "Initializing AGE label" messages (normal, not errors!)
- ✅ "Initializing edge type: MITIGATED_BY" (normal parallel processing messages)
- Progress bars for Concepts, Sources, Instances, Relationships

## MCP Server Integration (Optional)

The `kg` CLI installation automatically installs the MCP server at `~/.local/bin/kg-mcp-server`.

To use with Claude Desktop:
1. Restart Claude Desktop after installation (to detect new MCP server)
2. MCP tools will appear automatically (search_concepts, get_database_stats, etc.)

Test it works:
```bash
# In Claude Desktop, try:
"Show me database statistics"
"Search for concepts related to parallel processing"
```

## Troubleshooting

### "kg: command not found"

Add `~/.local/bin` to your PATH:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### API server errors about OpenAI key

If you see API key errors after starting the server:
1. Run `./scripts/setup/initialize-platform.sh` to configure embeddings
2. Paste your OpenAI API key when prompted
3. OR choose option 2 for local embeddings

### Dimension mismatch when restoring

Your backup uses different embeddings than active config:
```bash
# Check what embedders are available
kg admin embedding list

# Switch to match backup (use --force if database is empty)
kg admin embedding activate <config-id> --force
kg admin embedding reload
```

### Database won't start

Hard reset:
```bash
docker-compose down -v
./scripts/services/start-database.sh
```

## What Just Happened?

**Bootstrap Script (bootstrap.sh) - Recommended:**
- Checked all prerequisites (Docker, Python, Node.js)
- Created `.env` from `.env.example` if needed
- Started PostgreSQL + Apache AGE + Garage + API server
- Configured admin user, OAuth keys, encryption keys, embeddings
- Installed kg CLI globally
- Verified system health
- **Total time:** ~3-4 minutes

**OR if you ran individual scripts:**

**Database (start-database.sh):**
- Created `.env` from `.env.example`
- Started PostgreSQL + Apache AGE container
- Applied baseline schema + all migrations automatically
- Ready in ~15 seconds

**Garage (start-garage.sh):**
- Started Garage object storage container
- S3-compatible storage for image assets (ADR-057)
- Ready in ~10 seconds

**API Server (start-api.sh):**
- Created Python virtual environment
- Installed all dependencies from requirements.txt
- Started FastAPI server in background
- Logs: `logs/api_*.log`

**Auth Setup (initialize-platform.sh):**
- Created admin user in database
- Generated OAuth signing keys (ADR-054)
- Generated encryption keys in `.env` (ADR-031)
- Configured embedding provider (OpenAI or Nomic)
- **Dev mode (`--dev`)**: Uses password `Password1!` for quick start
- **Production mode**: Prompts for secure password or uses `ADMIN_PASSWORD` env var

**CLI Install (client/install.sh):**
- Built TypeScript client
- Linked `kg` command to `~/.local/bin/kg`
- Installed `kg-mcp-server` for Claude Desktop integration

## Nuclear Test Validation

**Test date:** October 28, 2025

**Test procedure:**
1. Deleted entire repository (`rm -rf knowledge-graph-system`)
2. Fresh clone from GitHub
3. Followed 5-command quick start
4. Pasted OpenAI API key into `initialize-platform.sh`
5. Switched to Nomic embeddings (to match backup)
6. Restored production backup (3,436 concepts)

**Results:**
- ✅ System operational in 3 minutes (fresh install)
- ✅ Backup restored in 5 minutes
- ✅ All 3,436 concepts verified intact
- ✅ All 20,335 relationships verified
- ✅ Embeddings working (92.4% similarity on test queries)
- ✅ MCP server functional (all tools tested)
- ✅ Clean logs (no scary ERROR messages)

**Total time:** 8 minutes from deletion to fully restored production system 🎉

## Next Steps

Once system is running:

**Ingest your first document:**
```bash
kg ingest file -o "My Ontology" document.txt
```

**Search the graph:**
```bash
kg search query "your search term"
kg search details <concept-id>
kg search connect "concept A" "concept B"
```

**Backup your data:**
```bash
kg admin backup
# Creates: ~/.local/share/kg/backups/full_backup_YYYYMMDD_HHMMSS.json
```

**Explore via MCP (Claude Desktop):**
- Search concepts semantically
- Find connections between ideas
- Get database statistics
- All through natural conversation!

## Performance Tips

**For restore operations:**
- Default 2 parallel workers = stable and fast
- Don't increase beyond 2 (causes AGE concurrency conflicts)
- ~5 minutes is expected for 30k items

**For ingestion:**
- Cloud APIs (OpenAI/Anthropic) = 2-5s per chunk
- Local (Ollama) = 3-10s per chunk
- Job approval workflow prevents surprise costs (ADR-014)

## Key Files & Locations

**Configuration:**
- `.env` - Environment variables (auto-created)
- `docker-compose.yml` - Database container config

**Data:**
- Database: Docker volume `knowledge-graph-system_postgres_data`
- Backups: `~/.local/share/kg/backups/`
- Logs: `logs/api_*.log`

**Scripts:**
- `./scripts/services/start-database.sh` - Start database
- `./scripts/services/start-api.sh` - Start API server
- `./scripts/setup/initialize-platform.sh` - Configure auth + embeddings
- `./scripts/services/stop-api.sh` - Stop API server
- `./scripts/services/stop-database.sh` - Stop database

**Documentation:**
- `docs/guides/QUICKSTART.md` - User quickstart guide
- `CLAUDE.md` - Developer guide for Claude Code
- `README.md` - Project overview

## Summary

**The entire cold start is just 5 commands and takes under 5 minutes.** The system handles all complexity automatically:
- ✅ Auto-creates configuration
- ✅ Auto-applies database migrations
- ✅ Auto-installs dependencies
- ✅ Auto-configures embeddings
- ✅ Ready for production use

No manual configuration files to edit, no complex setup steps. Just run the scripts and go! 🚀

---

**Document Version:** 2.0
**Last Updated:** October 28, 2025
**Validation:** Nuclear test (complete system deletion + rebuild)
