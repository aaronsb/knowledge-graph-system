# Embedding Configuration Guide

Complete guide to managing embedding model configurations, including protection mechanisms to prevent breaking changes.

## Table of Contents

- [Overview](#overview)
- [Configuration Options](#configuration-options)
- [Protection System](#protection-system)
- [Common Workflows](#common-workflows)
- [CLI Commands](#cli-commands)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Knowledge Graph system supports multiple embedding providers for vector similarity search:

- **OpenAI** - API-based embeddings (text-embedding-3-small, 1536 dimensions)
- **Local** - Self-hosted models via sentence-transformers (e.g., nomic-embed-text-v1.5, 768 dimensions)

### Why Configuration Protection Matters

**Changing embedding dimensions breaks vector search across the entire system.**

Example: Switching from 1536D (OpenAI) to 768D (nomic-embed) makes all existing concept embeddings incompatible, causing vector search to fail or return incorrect results.

The protection system prevents accidental breaking changes while allowing deliberate reconfiguration through a safe workflow.

---

## Configuration Options

### Viewing All Profiles

Embedding is configured via **profiles** stored in `kg_api.embedding_profile`. Each profile bundles text/image providers, models, dimensions, precision, and resource settings (ADR-039). One profile is active at a time.

```bash
# List all profiles with active marker, dimensions, and protection state
kg admin embedding list
```

Output:
```
📋 Embedding Configurations
────────────────────────────────────────

  ✓ ACTIVE Config 1 🔒 🔐
    Provider:   openai
    Model:      text-embedding-3-small
    Dimensions: 1536
    Protection: delete-protected, change-protected
    Updated:    10/22/2025, 9:06:23 AM
    By:         system

  ○ Inactive Config 2
    Provider:   local
    Model:      nomic-ai/nomic-embed-text-v1.5
    Dimensions: 768
    Updated:    10/21/2025, 3:45:12 PM
    By:         admin
```

**Icons:**
- ✓ ACTIVE - Currently active configuration
- ○ Inactive - Historical configuration
- 🔒 - Delete-protected (cannot be deleted)
- 🔐 - Change-protected (cannot change provider/dimensions)

---

## Protection System

### Protection Flags

**Delete Protection (`delete_protected`)**
- Prevents accidental deletion of important configurations
- Typically enabled on default/system configs
- Must be explicitly removed before deletion

**Change Protection (`change_protected`)**
- Prevents changing provider or embedding dimensions
- Critical safety feature - dimension changes break vector search
- Auto-enabled after successful hot reload
- Must be explicitly removed before provider/dimension changes

### Default Protection

The system automatically protects:
1. **Default OpenAI config** - Both delete and change protected (applied during migration 006)
2. **Active config after hot reload** - Automatically change-protected to prevent immediate follow-up accidents

---

## Common Workflows

### Workflow 1: Switch from OpenAI to Local Embeddings

**Safe workflow to change embedding provider:**

```bash
# 1. View current profiles
kg admin embedding list

# 2. Remove change protection from active profile (if set)
kg admin embedding unprotect 1 --change

# 3. Create a new local embedding profile
kg admin embedding create \
  --provider local \
  --model "nomic-ai/nomic-embed-text-v1.5" \
  --dimensions 768 \
  --precision float16 \
  --device cpu \
  --memory 512 \
  --threads 4 \
  --batch-size 8

# 4. Activate the new profile (use the ID printed by `create` or by `list`)
kg admin embedding activate <new-profile-id>

# 5. Hot reload the worker to load the new model (zero-downtime)
kg admin embedding reload

# 6. Verify the new profile is active and auto-protected
kg admin embedding list
```

**Expected result:**
- New config becomes active
- Change protection automatically re-enabled on new config
- Old config deactivated but preserved for rollback

**Important Notes:**
- This changes embedding dimensions (1536→768), making existing embeddings incompatible
- Consider clearing/re-ingesting your data after dimension changes
- The hot reload happens with brief 2x memory usage (1-2 seconds)

### Workflow 2: Switch Back to OpenAI

```bash
# 1. Find or create an OpenAI profile
kg admin embedding list

# 2. If you need a new OpenAI profile:
kg admin embedding create \
  --provider openai \
  --model text-embedding-3-small \
  --dimensions 1536

# 3. Remove change protection from current active profile
kg admin embedding unprotect <active-id> --change

# 4. Activate the OpenAI profile
kg admin embedding activate <openai-profile-id>

# 5. Hot reload
kg admin embedding reload
```

### Workflow 3: Adjust Local Model Settings

To change resource tuning (memory, threads, batch size, etc.) without changing dimensions, create a new profile based on the same provider/model with updated resource values and activate it, then reload. (There is no in-place `set` for an existing profile — use `create` + `activate` + `reload`.)

### Workflow 4: Clean Up Old Configs

```bash
# 1. List all configs
kg admin embedding list

# 2. Remove delete protection if needed
kg admin embedding unprotect 2 --delete

# 3. Delete the config
kg admin embedding delete 2
```

**When prompted:**
```
Delete embedding config 2? (yes/no): yes
```

---

## CLI Commands

### Configuration Management

The full list of `kg admin embedding` subcommands: `list`, `create`, `export`, `activate`, `reload`, `protect`, `unprotect`, `delete`, `status`, `regenerate`.

#### List All Profiles
```bash
kg admin embedding list
```

Shows all profiles with protection status and active indicator.

#### Create a New Profile
```bash
kg admin embedding create [OPTIONS]
```

**Common options:**
- `--provider <provider>` - Text provider: `local` or `openai` (shorthand for `--text-provider`)
- `--model <model>` - Text model name (shorthand for `--text-model`)
- `--dimensions <dims>` - Text embedding dimensions (shorthand for `--text-dimensions`)
- `--precision <precision>` - Precision: `float16`, `float32` (local only)
- `--device <device>` - Device: `cpu`, `cuda`, `mps` (local only)
- `--memory <mb>` - Max memory in MB (local only)
- `--threads <n>` - Number of threads (local only)
- `--batch-size <n>` - Batch size (local only)
- `--multimodal` - Profile handles both text and image embeddings
- `--from-json <file>` - Import a profile definition from a JSON file

Additional `--text-*` / `--image-*` flags let you configure text and image legs independently for multimodal profiles.

#### Activate a Profile
```bash
kg admin embedding activate <profile-id>
```

Switches the active embedding profile. Use `--force` to override dimension-mismatch safety.

**Examples:**

```bash
# Create + activate an OpenAI profile
kg admin embedding create --provider openai --model text-embedding-3-small --dimensions 1536
kg admin embedding activate <new-id>

# Local profile (full)
kg admin embedding create \
  --provider local \
  --model "nomic-ai/nomic-embed-text-v1.5" \
  --dimensions 768 \
  --precision float16 \
  --device cpu \
  --memory 512 \
  --threads 4 \
  --batch-size 8
kg admin embedding activate <new-id>
```

#### Hot Reload Model
```bash
kg admin embedding reload
```

Zero-downtime reload of embedding model from database configuration:
1. Loads new config from database
2. Initializes new model in parallel (old model still serves requests)
3. Atomic swap to new model
4. Auto-protects new active config (change protection)

### Protection Management

#### Enable Protection
```bash
kg admin embedding protect <config-id> [FLAGS]
```

**Flags:**
- `--delete` - Enable delete protection
- `--change` - Enable change protection
- Both flags can be used together

**Examples:**

```bash
# Enable change protection only
kg admin embedding protect 1 --change

# Enable both protections
kg admin embedding protect 1 --delete --change
```

#### Disable Protection
```bash
kg admin embedding unprotect <config-id> [FLAGS]
```

**Flags:**
- `--delete` - Disable delete protection
- `--change` - Disable change protection

**Examples:**

```bash
# Remove change protection (before switching providers)
kg admin embedding unprotect 1 --change

# Remove both protections
kg admin embedding unprotect 1 --delete --change
```

#### Delete Configuration
```bash
kg admin embedding delete <config-id>
```

Prompts for confirmation. Fails if config is delete-protected.

**Example:**

```bash
kg admin embedding delete 2
# Prompts: Delete embedding config 2? (yes/no):
```

---

## Troubleshooting

### Error: "Active config is change-protected"

**Full error:**
```
✗ Failed to update embedding configuration
Active config (ID 1) is change-protected. Changing provider or dimensions breaks
vector search. Remove protection first with: kg admin embedding unprotect --change 1
```

**Solution:**
```bash
# Remove change protection first
kg admin embedding unprotect 1 --change

# Then update configuration
kg admin embedding create --provider local --model "..." --dimensions 768 && kg admin embedding activate <new-id>

# Reload to apply
kg admin embedding reload
```

### Error: "Config is delete-protected"

**Full error:**
```
✗ Failed to delete configuration
Config is delete-protected. Remove protection first with: kg admin embedding unprotect --delete
```

**Solution:**
```bash
# Remove delete protection first
kg admin embedding unprotect <config-id> --delete

# Then delete
kg admin embedding delete <config-id>
```

### Error: "null value in column 'embedding_dimensions'"

**Cause:** Missing required dimensions parameter.

**Solution:**
```bash
# Always specify dimensions for local provider
kg admin embedding create \
  --provider local \
  --model "nomic-ai/nomic-embed-text-v1.5" \
  --dimensions 768
```

### Hot Reload Shows Wrong Provider

**Check:**
1. Did you run `kg admin embedding reload` after changing config?
2. Is the new config actually active?

```bash
# Verify active config
kg admin embedding list

# Force reload
kg admin embedding reload

# Check again
kg admin embedding config
```

### Vector Search Returns Wrong Results After Config Change

**Cause:** Changed embedding dimensions without re-indexing data.

**Solution:**

When you change embedding dimensions (e.g., 1536→768):
1. All existing concept embeddings become incompatible
2. You must re-ingest all ontologies to rebuild embeddings with new dimensions

```bash
# Option 1: Clear and re-ingest
kg ontology delete "My Ontology"
kg ingest file -o "My Ontology" -y document.txt

# Option 2: Full database reset (nuclear option)
kg admin reset
# Then re-ingest all data
```

### Local Model Download Fails

**Error:** Model not found or download timeout.

**Solution:**

Ensure the model is available in HuggingFace:
- Valid model: `nomic-ai/nomic-embed-text-v1.5`
- Invalid: `nomic-embed-text` (wrong format)

Check network access to HuggingFace from your server.

### Memory Issues with Local Model

**Error:** OOM (Out of Memory) during model load.

**Solution:**

Reduce memory allocation or use smaller precision:

```bash
kg admin embedding set \
  --provider local \
  --model "nomic-ai/nomic-embed-text-v1.5" \
  --dimensions 768 \
  --precision float16 \  # Use float16 instead of float32
  --memory 256 \          # Reduce from 512
  --batch-size 4          # Reduce from 8
```

---

## Best Practices

1. **Always use hot reload** instead of restarting the API
   - Zero downtime
   - In-flight requests complete with old model
   - Auto-protection prevents follow-up accidents

2. **Test configuration changes in non-production first**
   - Create snapshot before major changes: `./scripts/snapshot-db.sh`
   - Verify vector search still works after dimension changes

3. **Document your configurations**
   - Use meaningful `updated_by` values when using API directly
   - CLI uses "api" by default

4. **Don't delete the default OpenAI config**
   - It's there for rollback purposes
   - Keep it delete-protected

5. **Re-ingest data after dimension changes**
   - Changing dimensions (e.g., 1536→768) requires rebuilding all embeddings
   - Plan for downtime during re-ingestion

---

## Advanced Topics

### Manual API Calls

If you need to use the API directly (not via CLI):

```bash
# Get active config (public endpoint)
curl http://localhost:8000/embedding/config

# Get full config details (admin endpoint)
curl http://localhost:8000/admin/embedding/config

# Update config (admin endpoint)
curl -X POST http://localhost:8000/admin/embedding/config \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "local",
    "model_name": "nomic-ai/nomic-embed-text-v1.5",
    "embedding_dimensions": 768,
    "precision": "float16",
    "device": "cpu",
    "max_memory_mb": 512,
    "num_threads": 4,
    "batch_size": 8
  }'

# Hot reload
curl -X POST http://localhost:8000/admin/embedding/config/reload

# List all configs
curl http://localhost:8000/admin/embedding/configs

# Set protection
curl -X POST "http://localhost:8000/admin/embedding/config/1/protect?change_protected=true"

# Delete config
curl -X DELETE http://localhost:8000/admin/embedding/config/2
```

### Database Schema

Configurations are stored in `kg_api.embedding_config`:

```sql
-- View all configs
SELECT id, provider, model_name, embedding_dimensions,
       active, delete_protected, change_protected
FROM kg_api.embedding_config
ORDER BY id DESC;

-- Check active config
SELECT * FROM kg_api.embedding_config WHERE active = TRUE;
```

### Auto-Protection Implementation

After `kg admin embedding reload`:
1. Reload succeeds
2. System queries for newly active config
3. Automatically sets `change_protected = TRUE` on that config
4. Logs: "🔒 Auto-protected config {id} after hot reload"

This ensures safety immediately after a risky operation.

---

## Related Documentation

- [CLI Usage Guide](../01-getting-started/02-CLI_USAGE.md) - General CLI commands
- [Database Migrations](../05-maintenance/02-DATABASE_MIGRATIONS.md) - Schema migration workflow
- [AI Providers Guide](01-AI_PROVIDERS.md) - AI provider configuration
- [Authentication Guide](../04-security-and-access/01-AUTHENTICATION.md) - API key management

---

## Migration 006

The protection system was introduced in migration 006:

```bash
# Check if migration 006 is applied
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph \
  -c "SELECT version, name FROM public.schema_migrations WHERE version = 6"

# Apply pending migrations
./scripts/database/migrate-db.sh -y
```

Migration 006 adds:
- `delete_protected` column (default: false)
- `change_protected` column (default: false)
- Auto-protects default OpenAI config (both flags set to true)

---

## Quick Reference

| Task | Command |
|------|---------|
| View active config | `kg admin embedding config` |
| List all configs | `kg admin embedding list` |
| Switch to local | `kg admin embedding create --provider local --model "..." --dimensions 768 && kg admin embedding activate <new-id>` |
| Switch to OpenAI | `kg admin embedding set --provider openai` |
| Hot reload | `kg admin embedding reload` |
| Remove change lock | `kg admin embedding unprotect <id> --change` |
| Enable protection | `kg admin embedding protect <id> --change --delete` |
| Delete config | `kg admin embedding delete <id>` |

**Safe workflow for provider switch:**
1. `kg admin embedding unprotect <id> --change`
2. `kg admin embedding set --provider ... --dimensions ...`
3. `kg admin embedding reload`
4. Verify with `kg admin embedding list`
