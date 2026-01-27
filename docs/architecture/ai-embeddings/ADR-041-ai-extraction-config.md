---
status: Proposed
date: 2025-10-21
deciders: Development Team
related:
  - ADR-031
  - ADR-039
---

# ADR-041: AI Extraction Provider Configuration

## Overview

Every time you ingest a document, the system uses an LLM to extract concepts and relationships from the text. But here's the question: which LLM? OpenAI's GPT-4? Anthropic's Claude? A local model running via Ollama? And critically, where should this configuration live—in environment variables that require server restarts to change, or somewhere more dynamic?

The current system hardcodes the extraction provider in environment variables. Want to switch from GPT-4 to Claude? You need to edit `.env`, restart the API server, and hope you didn't break anything. This is fine for static deployments, but it becomes painful when you want to experiment with different models, manage costs by mixing providers per ontology, or let operators change settings through an admin UI without touching configuration files.

Think of it like this: should your TV's channel selection be hardwired into the circuit board, or controlled by a remote? Right now, we've hardwired it. This ADR proposes moving extraction configuration from static environment variables into the database, where it can be queried, updated via API, and changed at runtime without restarting services.

The design follows a simple priority system: database configuration takes precedence when available, falling back to environment variables for development workflows and system initialization. This means operators can manage production settings through a web interface while developers can still use familiar `.env` files during local testing. The key insight is that configuration is data, not code—it should be stored where data lives, not buried in deployment files.

---

## Context

The knowledge graph system uses LLM APIs (OpenAI GPT-4, Anthropic Claude) to extract concepts from documents. Currently, provider and model selection is configured via environment variables:

```bash
# .env
AI_PROVIDER=openai                              # Which provider to use
OPENAI_EXTRACTION_MODEL=gpt-4o                  # OpenAI model selection
ANTHROPIC_EXTRACTION_MODEL=claude-sonnet-4-20250514  # Anthropic model selection
```

### Problems with Environment Variable Configuration

1. **Static deployment**: Changing providers/models requires restarting the API server
2. **No runtime management**: Cannot switch providers via API without redeployment
3. **Inconsistent with embeddings**: Embeddings use database-first configuration (ADR-039)
4. **Difficult testing**: Hard to test different models without environment changes
5. **No validation**: Model name typos won't be caught until extraction fails
6. **Split architecture**: API keys in database (ADR-031), but config in .env

### Current Architecture (Split)

```
API Keys (ADR-031)               Configuration (Current)
┌────────────────────┐          ┌────────────────────┐
│ Database           │          │ Environment (.env) │
│ system_api_keys    │          │ AI_PROVIDER        │
│ - openai: sk-...   │          │ *_EXTRACTION_MODEL │
│ - anthropic: sk-...│          └────────────────────┘
└────────────────────┘
```

### Desired Architecture (Unified)

```
┌─────────────────────────────────────────┐
│ Database (Unified Configuration)        │
│                                         │
│ system_api_keys                         │
│ - openai: sk-... (encrypted)            │
│ - anthropic: sk-... (encrypted)         │
│                                         │
│ ai_extraction_config ← NEW              │
│ - provider: openai                      │
│ - model_name: gpt-4o                    │
│ - active: true                          │
└─────────────────────────────────────────┘
```

## Decision

Implement **database-first AI extraction provider configuration**, following the same pattern as ADR-039 (Local Embedding Service).

### Key Principles

1. **Database-First Configuration**
   - Active configuration stored in `kg_api.ai_extraction_config` table
   - No environment variable fallback in production
   - Environment variables supported for development/testing

2. **Hot-Swappable Providers**
   - Switch between OpenAI and Anthropic via API
   - Change models without server restart
   - Validated before activation (test API call)

3. **Consistency with Embeddings**
   - Same configuration pattern as `embedding_config` (ADR-039)
   - Single active configuration at a time
   - Admin API for management

4. **Backward Compatibility**
   - Supports .env during migration period
   - Graceful degradation if no database config exists
   - Clear migration path documented

## Implementation

### Database Schema

```sql
-- Migration 004: AI Extraction Configuration Table
CREATE TABLE IF NOT EXISTS kg_api.ai_extraction_config (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL CHECK (provider IN ('openai', 'anthropic')),
    model_name VARCHAR(200) NOT NULL,

    -- Model capabilities
    supports_vision BOOLEAN DEFAULT FALSE,
    supports_json_mode BOOLEAN DEFAULT TRUE,
    max_tokens INTEGER,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    active BOOLEAN DEFAULT TRUE
);

-- Only one active configuration at a time
CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_extraction_config_unique_active
ON kg_api.ai_extraction_config(active) WHERE active = TRUE;

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION kg_api.update_ai_extraction_config_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'ai_extraction_config_update_timestamp'
    ) THEN
        CREATE TRIGGER ai_extraction_config_update_timestamp
            BEFORE UPDATE ON kg_api.ai_extraction_config
            FOR EACH ROW
            EXECUTE FUNCTION kg_api.update_ai_extraction_config_timestamp();
    END IF;
END $$;

-- Seed default OpenAI configuration
INSERT INTO kg_api.ai_extraction_config (
    provider, model_name, supports_vision, supports_json_mode, max_tokens, updated_by, active
) VALUES (
    'openai', 'gpt-4o', TRUE, TRUE, 16384, 'system_migration', TRUE
) ON CONFLICT DO NOTHING;
```

### Configuration Loading

```python
# src/api/lib/ai_extraction_config.py
"""
AI Extraction Provider Configuration Management.

Handles loading and saving extraction provider configuration from/to database.
Implements database-first configuration (ADR-041).
"""

import logging
from typing import Optional, Dict, Any
import psycopg2

logger = logging.getLogger(__name__)


def load_active_extraction_config() -> Optional[Dict[str, Any]]:
    """
    Load the active AI extraction configuration from the database.

    Returns:
        Dict with config parameters if found, None otherwise

    Config dict structure:
        {
            "id": 1,
            "provider": "openai" | "anthropic",
            "model_name": "gpt-4o",
            "supports_vision": True,
            "supports_json_mode": True,
            "max_tokens": 16384,
            "created_at": "...",
            "updated_at": "...",
            "updated_by": "...",
            "active": True
        }
    """
    from .age_client import AGEClient

    try:
        client = AGEClient()
        conn = client.pool.getconn()

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        id, provider, model_name, supports_vision, supports_json_mode,
                        max_tokens, created_at, updated_at, updated_by, active
                    FROM kg_api.ai_extraction_config
                    WHERE active = TRUE
                    LIMIT 1
                """)

                row = cur.fetchone()

                if not row:
                    logger.info("📍 No active AI extraction config in database")
                    return None

                config = {
                    "id": row[0],
                    "provider": row[1],
                    "model_name": row[2],
                    "supports_vision": row[3],
                    "supports_json_mode": row[4],
                    "max_tokens": row[5],
                    "created_at": row[6],
                    "updated_at": row[7],
                    "updated_by": row[8],
                    "active": row[9]
                }

                logger.info(f"✅ Loaded AI extraction config: {config['provider']} / {config['model_name']}")
                return config

        finally:
            client.pool.putconn(conn)

    except Exception as e:
        logger.error(f"Failed to load AI extraction config from database: {e}")
        return None


def save_extraction_config(config: Dict[str, Any], updated_by: str = "api") -> bool:
    """
    Save AI extraction configuration to the database.

    Deactivates any existing active config and creates a new one.

    Args:
        config: Configuration dict with keys:
            - provider: "openai" or "anthropic" (required)
            - model_name: Model identifier (required)
            - supports_vision: True/False
            - supports_json_mode: True/False
            - max_tokens: Maximum tokens for model
        updated_by: User/admin who made the change

    Returns:
        True if saved successfully, False otherwise
    """
    from .age_client import AGEClient

    try:
        client = AGEClient()
        conn = client.pool.getconn()

        try:
            with conn.cursor() as cur:
                # Start transaction
                cur.execute("BEGIN")

                # Deactivate all existing configs
                cur.execute("""
                    UPDATE kg_api.ai_extraction_config
                    SET active = FALSE
                    WHERE active = TRUE
                """)

                # Insert new config as active
                cur.execute("""
                    INSERT INTO kg_api.ai_extraction_config (
                        provider, model_name, supports_vision, supports_json_mode,
                        max_tokens, updated_by, active
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, TRUE
                    )
                """, (
                    config['provider'],
                    config['model_name'],
                    config.get('supports_vision', False),
                    config.get('supports_json_mode', True),
                    config.get('max_tokens'),
                    updated_by
                ))

                # Commit transaction
                cur.execute("COMMIT")

                logger.info(f"✅ Saved AI extraction config: {config['provider']} / {config['model_name']}")
                return True

        except Exception as e:
            # Rollback on error
            try:
                cur.execute("ROLLBACK")
            except:
                pass
            raise e
        finally:
            client.pool.putconn(conn)

    except Exception as e:
        logger.error(f"Failed to save AI extraction config to database: {e}")
        return False


def get_extraction_config_summary() -> Dict[str, Any]:
    """
    Get a summary of the current AI extraction configuration.

    Returns dict suitable for API responses:
        {
            "provider": "openai",
            "model": "gpt-4o",
            "supports_vision": True,
            "supports_json_mode": True,
            "max_tokens": 16384,
            "config_id": 42
        }
    """
    config = load_active_extraction_config()

    if not config:
        return {
            "provider": "none",
            "model": None,
            "supports_vision": False,
            "supports_json_mode": False,
            "max_tokens": None,
            "config_id": None
        }

    return {
        "provider": config['provider'],
        "model": config['model_name'],
        "supports_vision": config.get('supports_vision', False),
        "supports_json_mode": config.get('supports_json_mode', True),
        "max_tokens": config.get('max_tokens'),
        "config_id": config['id']
    }
```

### API Provider Updates

```python
# src/api/lib/ai_providers.py (Updated get_provider function)

def get_provider(provider_name: Optional[str] = None) -> AIProvider:
    """
    Factory function to get the configured AI provider.

    Priority order (ADR-041):
    1. Explicit provider_name parameter (for testing/overrides)
    2. Database configuration (kg_api.ai_extraction_config table)
    3. Environment variable AI_PROVIDER (development fallback)
    4. Default to OpenAI

    Args:
        provider_name: Override provider selection (optional)

    Returns:
        AIProvider instance
    """
    # 1. Explicit parameter takes precedence
    if provider_name:
        logger.debug(f"Using explicit provider: {provider_name}")
        provider = provider_name.lower()
        model_name = None  # Will use provider defaults
    else:
        # 2. Try database configuration (ADR-041)
        from .ai_extraction_config import load_active_extraction_config

        config = load_active_extraction_config()

        if config:
            provider = config['provider']
            model_name = config['model_name']
            logger.info(f"📍 AI extraction provider: {provider} / {model_name} (from database)")
        else:
            # 3. Fall back to environment variable
            provider = os.getenv("AI_PROVIDER", "openai").lower()
            model_name = None  # Will read from env vars in provider __init__
            logger.info(f"📍 AI extraction provider: {provider} (from environment)")

    # Instantiate provider
    if provider == "openai":
        return OpenAIProvider(extraction_model=model_name)
    elif provider == "anthropic":
        return AnthropicProvider(extraction_model=model_name)
    elif provider == "mock":
        return MockProvider()
    else:
        raise ValueError(
            f"Unknown AI provider: {provider}. "
            f"Supported: openai, anthropic, mock"
        )
```

### API Endpoints

```python
# src/api/routes/ai_extraction.py
"""
AI Extraction Provider Configuration API endpoints.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Literal, Optional

from ..lib.ai_extraction_config import (
    load_active_extraction_config,
    save_extraction_config,
    get_extraction_config_summary
)
from ..lib.ai_providers import get_provider

# Public router (no auth required)
public_router = APIRouter(prefix="/ai-extraction", tags=["ai-extraction"])

# Admin router (auth required)
admin_router = APIRouter(prefix="/admin/ai-extraction", tags=["admin-ai-extraction"])


class ExtractionConfigResponse(BaseModel):
    """Public extraction config summary"""
    provider: str
    model: str
    supports_vision: bool
    supports_json_mode: bool
    max_tokens: Optional[int]


class ExtractionConfigDetail(BaseModel):
    """Full extraction config details (admin only)"""
    id: Optional[int]
    provider: str
    model_name: str
    supports_vision: bool
    supports_json_mode: bool
    max_tokens: Optional[int]
    created_at: Optional[str]
    updated_at: Optional[str]
    updated_by: Optional[str]
    active: bool


class UpdateExtractionConfigRequest(BaseModel):
    """Update extraction config request"""
    provider: Literal["openai", "anthropic"]
    model_name: str
    supports_vision: Optional[bool] = False
    supports_json_mode: Optional[bool] = True
    max_tokens: Optional[int] = None


class UpdateExtractionConfigResponse(BaseModel):
    """Update extraction config response"""
    status: str
    message: str
    config: ExtractionConfigResponse


@public_router.get("/config", response_model=ExtractionConfigResponse)
async def get_extraction_config():
    """
    Get current AI extraction provider configuration (public).

    Returns summary suitable for client applications.
    """
    summary = get_extraction_config_summary()

    if summary['provider'] == 'none':
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No AI extraction provider configured"
        )

    return ExtractionConfigResponse(**summary)


@admin_router.get("/config", response_model=ExtractionConfigDetail)
async def get_extraction_config_detail():
    """
    Get full AI extraction configuration details (admin only).

    Includes metadata like creation time, last update, etc.
    """
    config = load_active_extraction_config()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active AI extraction configuration found"
        )

    return ExtractionConfigDetail(
        id=config['id'],
        provider=config['provider'],
        model_name=config['model_name'],
        supports_vision=config.get('supports_vision', False),
        supports_json_mode=config.get('supports_json_mode', True),
        max_tokens=config.get('max_tokens'),
        created_at=config['created_at'].isoformat() if config.get('created_at') else None,
        updated_at=config['updated_at'].isoformat() if config.get('updated_at') else None,
        updated_by=config.get('updated_by'),
        active=config.get('active', True)
    )


@admin_router.post("/config", response_model=UpdateExtractionConfigResponse)
async def update_extraction_config(request: UpdateExtractionConfigRequest):
    """
    Update AI extraction provider configuration (admin only).

    Validates the configuration by testing it before activation.
    Deactivates previous config and activates the new one.
    """
    # Validate the configuration by creating a provider instance
    try:
        provider = get_provider(request.provider)

        # Test with a minimal extraction to validate API key + model
        test_text = "The quick brown fox jumps over the lazy dog."
        concepts = provider.extract_concepts(test_text, "test")

        if not concepts:
            raise ValueError("Provider validation returned no concepts")

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Configuration validation failed: {str(e)}"
        )

    # Configuration is valid, save it
    config_dict = {
        "provider": request.provider,
        "model_name": request.model_name,
        "supports_vision": request.supports_vision,
        "supports_json_mode": request.supports_json_mode,
        "max_tokens": request.max_tokens
    }

    success = save_extraction_config(config_dict, updated_by="admin")

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save configuration to database"
        )

    # Return updated config
    summary = get_extraction_config_summary()

    return UpdateExtractionConfigResponse(
        status="success",
        message=f"AI extraction provider updated to {request.provider} / {request.model_name}",
        config=ExtractionConfigResponse(**summary)
    )
```

### CLI Commands

```typescript
// client/src/cli/ai-extraction.ts
/**
 * AI Extraction Provider Configuration CLI commands.
 */

import { Command } from 'commander';
import { apiClient } from '../api/client';
import chalk from 'chalk';

export const aiExtractionCommand = new Command('ai-extraction')
  .alias('ai')
  .description('Manage AI extraction provider configuration');

// View current configuration
aiExtractionCommand
  .command('config')
  .description('View current AI extraction provider configuration')
  .option('--detail', 'Show full configuration details (admin)')
  .action(async (options) => {
    try {
      const endpoint = options.detail
        ? '/admin/ai-extraction/config'
        : '/ai-extraction/config';

      const response = await apiClient.get(endpoint);
      const config = response.data;

      console.log(chalk.bold('\n🤖 AI Extraction Provider Configuration\n'));
      console.log(`Provider:         ${chalk.green(config.provider)}`);
      console.log(`Model:            ${chalk.green(config.model || config.model_name)}`);
      console.log(`Vision Support:   ${config.supports_vision ? '✓' : '✗'}`);
      console.log(`JSON Mode:        ${config.supports_json_mode ? '✓' : '✗'}`);

      if (config.max_tokens) {
        console.log(`Max Tokens:       ${config.max_tokens.toLocaleString()}`);
      }

      if (options.detail && config.updated_at) {
        console.log(`\nLast Updated:     ${new Date(config.updated_at).toLocaleString()}`);
        console.log(`Updated By:       ${config.updated_by || 'unknown'}`);
      }

      console.log();

    } catch (error: any) {
      console.error(chalk.red('✗ Failed to fetch configuration'));
      console.error(chalk.gray(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// Set provider configuration
aiExtractionCommand
  .command('set <provider> <model>')
  .description('Set AI extraction provider configuration (admin)')
  .option('--vision', 'Model supports vision/images')
  .option('--no-json', 'Model does not support JSON mode')
  .option('--max-tokens <n>', 'Maximum tokens for model', parseInt)
  .action(async (provider, model, options) => {
    try {
      console.log(chalk.blue(`\n🔄 Updating AI extraction configuration...\n`));
      console.log(`Provider: ${chalk.bold(provider)}`);
      console.log(`Model:    ${chalk.bold(model)}`);

      const requestData = {
        provider,
        model_name: model,
        supports_vision: options.vision || false,
        supports_json_mode: options.json !== false,
        max_tokens: options.maxTokens || null
      };

      console.log(chalk.gray('\nValidating configuration with API call...'));

      const response = await apiClient.post('/admin/ai-extraction/config', requestData);
      const result = response.data;

      console.log(chalk.green(`\n✓ ${result.message}`));
      console.log(chalk.gray('\nConfiguration will be used for all future extractions.'));
      console.log();

    } catch (error: any) {
      console.error(chalk.red('\n✗ Failed to update configuration'));
      console.error(chalk.gray(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });
```

## Migration Strategy

### Phase 1: Add Database Configuration (Backward Compatible)

1. Create migration 004 with `ai_extraction_config` table
2. Seed with current .env values (if present)
3. Update `get_provider()` to check database first, fall back to .env
4. Deploy - **no breaking changes**

### Phase 2: CLI Integration

1. Add `kg ai config` and `kg ai set` commands
2. Document configuration workflow
3. Encourage users to migrate via CLI

### Phase 3: Deprecate .env (Future)

1. Add warnings when using .env configuration
2. Update documentation to recommend database config
3. Eventually remove .env fallback (with major version bump)

## Consequences

### Positive

1. **✅ Unified configuration**: Both API keys and extraction config in database
2. **✅ Hot-swappable**: Change providers/models via API without restart
3. **✅ Validated**: Configuration tested before activation
4. **✅ Consistent**: Same pattern as embedding configuration (ADR-039)
5. **✅ Auditable**: Track who changed config and when
6. **✅ Testable**: Easy to test different models via API

### Negative

1. **❌ Migration effort**: Existing deployments need to migrate from .env
2. **❌ Additional complexity**: One more table to manage
3. **❌ Database dependency**: Configuration requires database access

### Neutral

1. **Database-first**: Matches embedding configuration approach (ADR-039)
2. **Admin-only**: Configuration changes require admin privileges
3. **Single active config**: Only one provider active at a time per shard

## Alternatives Considered

### Alternative 1: Keep Environment Variables

**Rejected**: Inconsistent with ADR-039 (embeddings), requires restart for changes

### Alternative 2: Combine with embedding_config Table

**Rejected**: Different concerns (extraction vs embedding), better separation

### Alternative 3: Per-User Provider Selection

**Rejected**: Adds significant complexity, most deployments use single provider

## Unified Initialization & API Key Usage

### API Key Resource Sharing

API keys stored in `system_api_keys` (ADR-031) are **shared resources** used by multiple systems:

```
system_api_keys (encrypted, ADR-031)
├── openai: sk-...
│   ├── Used by: AI Extraction (GPT-4 for concept extraction)
│   └── Used by: Embedding Generation (OpenAI embeddings, if configured)
│
└── anthropic: sk-ant-...
    └── Used by: AI Extraction (Claude for concept extraction)
```

**Key insight:** Local embeddings (ADR-039) don't require API keys, so the embedding worker **skips API key lookup entirely** when `provider='local'`.

### Configuration Independence

```
┌─────────────────────────────────────────────┐
│ Shared: system_api_keys (ADR-031)          │
│  - OpenAI key (extraction + embeddings)    │
│  - Anthropic key (extraction only)         │
└─────────────────────────────────────────────┘
           ↓                      ↓
┌───────────────────────┐  ┌──────────────────────┐
│ ai_extraction_config  │  │ embedding_config     │
│ (This ADR)            │  │ (ADR-039)            │
│                       │  │                      │
│ provider: openai      │  │ provider: local      │
│ model: gpt-4o         │  │ model: nomic-ai/...  │
│ active: true          │  │ active: true         │
└───────────────────────┘  └──────────────────────┘
```

**Example configurations:**

| Extraction | Embeddings | API Key Usage |
|-----------|-----------|---------------|
| OpenAI GPT-4 | OpenAI | Uses OpenAI key for both |
| OpenAI GPT-4 | Local (nomic-embed) | Uses OpenAI key for extraction only |
| Anthropic Claude | Local (nomic-embed) | Uses Anthropic key for extraction only |
| Anthropic Claude | OpenAI | Uses both Anthropic + OpenAI keys |

### Initial Setup Flow

**Fresh installation** via `./scripts/setup/initialize-platform.sh` (enhanced):

```bash
╔════════════════════════════════════════════════════════════╗
║   Knowledge Graph System - Initial Setup                  ║
╚════════════════════════════════════════════════════════════╝

Step 1: Admin Password
→ Enter admin password: ********
→ Confirm password: ********
✓ Password meets requirements

Step 2: API Keys
→ Enter OpenAI API key (required): sk-...
✓ OpenAI key validated

→ Enter Anthropic API key (optional, press Enter to skip): sk-ant-...
✓ Anthropic key validated

Step 3: AI Extraction Configuration
→ Select extraction provider:
  1. OpenAI (gpt-4o) [recommended]
  2. Anthropic (claude-sonnet-4-20250514)
→ Selection: 1
✓ Set extraction provider: OpenAI / gpt-4o

Step 4: Embedding Configuration
→ Select embedding provider:
  1. Local (nomic-ai/nomic-embed-text-v1.5) [free, recommended]
  2. OpenAI (text-embedding-3-small)
→ Selection: 1
✓ Set embedding provider: Local / nomic-embed-text-v1.5

╔════════════════════════════════════════════════════════════╗
║              System Initialized Successfully!              ║
╚════════════════════════════════════════════════════════════╝

Configuration Summary:
  Admin:      admin (password set)
  Extraction: OpenAI / gpt-4o
  Embeddings: Local / nomic-ai/nomic-embed-text-v1.5 (no API cost!)

Next Steps:
  1. Start API: ./scripts/services/start-api.sh
  2. Login: kg auth login
  3. Ingest docs: kg ingest file -o "Ontology" document.txt
```

### Database Reset Security

**Complete database wipe** (intentional security feature):

```bash
docker-compose down -v  # Wipes volumes
docker-compose up -d
```

**Effect:** All secrets erased:
- ✗ Admin password → Must reset via `./scripts/setup/initialize-platform.sh`
- ✗ API keys (OpenAI, Anthropic) → Must re-enter
- ✗ Provider configs → Must reconfigure
- ✗ All ontology data → Lost

**Rationale:** Prevents compromised database backups from containing active API keys. Forces explicit re-authentication and key validation on restore.

### API Key Validation on Startup

**Problem scenario:**
1. User initializes with OpenAI key
2. Switches to local embeddings (months of not using OpenAI key)
3. OpenAI key expires
4. User switches back to OpenAI embeddings → **Ingestion fails with expired key**

**Solution:** Enhanced `system_api_keys` table with validation state tracking:

```sql
-- Migration 005: Add validation state to system_api_keys
ALTER TABLE kg_api.system_api_keys
ADD COLUMN validation_status VARCHAR(20) DEFAULT 'untested'
    CHECK (validation_status IN ('valid', 'invalid', 'untested')),
ADD COLUMN last_validated_at TIMESTAMPTZ,
ADD COLUMN validation_error TEXT;

-- Create index for quick validation status queries
CREATE INDEX idx_system_api_keys_validation_status
ON kg_api.system_api_keys(validation_status);
```

**Schema:**
```
system_api_keys
├── provider (PK)
├── encrypted_key (bytea)
├── updated_at
├── validation_status ('valid' | 'invalid' | 'untested') ← NEW
├── last_validated_at ← NEW
└── validation_error ← NEW
```

**Startup validation with state updates:**

```python
# src/api/main.py - Startup event
@app.on_event("startup")
async def startup_validation():
    """Validate active provider configurations and update key status"""
    from .lib.encrypted_keys import validate_and_update_key_status

    # Load active extraction config
    extraction_config = load_active_extraction_config()
    if extraction_config:
        provider = extraction_config['provider']
        logger.info(f"Validating extraction provider: {provider}")

        # Validate and update status in database
        is_valid = await validate_and_update_key_status(provider, 'extraction')

        if is_valid:
            logger.info(f"✓ Extraction provider {provider} validated")
        else:
            logger.warning(f"⚠ Extraction provider {provider} validation failed")
            logger.warning(f"   View details: kg admin keys list")
            logger.warning(f"   Update key: kg admin keys set {provider} <new-key>")

    # Load active embedding config
    embedding_config = load_active_embedding_config()
    if embedding_config and embedding_config['provider'] != 'local':
        provider = embedding_config['provider']
        logger.info(f"Validating embedding provider: {provider}")

        is_valid = await validate_and_update_key_status(provider, 'embedding')

        if is_valid:
            logger.info(f"✓ Embedding provider {provider} validated")
        else:
            logger.warning(f"⚠ Embedding provider {provider} validation failed")
            logger.warning(f"   View details: kg admin keys list")
```

**Validation function:**

```python
# src/api/lib/encrypted_keys.py
def validate_and_update_key_status(
    provider: str,
    usage_type: str  # 'extraction' or 'embedding'
) -> bool:
    """
    Validate API key and update validation status in database.

    Args:
        provider: 'openai' or 'anthropic'
        usage_type: 'extraction' or 'embedding'

    Returns:
        True if valid, False otherwise
    """
    from .age_client import AGEClient

    client = AGEClient()
    conn = client.pool.getconn()

    try:
        # Get encrypted key
        key_store = EncryptedKeyStore(conn)
        api_key = key_store.get_key(provider)

        # Test the key
        if usage_type == 'extraction':
            ai_provider = get_provider(provider)
            ai_provider.extract_concepts("test", "validation")
        else:  # embedding
            # Test embedding generation
            if provider == 'openai':
                import openai
                client = openai.OpenAI(api_key=api_key)
                client.embeddings.create(
                    model="text-embedding-3-small",
                    input="test"
                )

        # Validation succeeded - update status
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE kg_api.system_api_keys
                SET
                    validation_status = 'valid',
                    last_validated_at = NOW(),
                    validation_error = NULL
                WHERE provider = %s
            """, (provider,))
            conn.commit()

        logger.info(f"✓ {provider} key validated and marked as valid")
        return True

    except Exception as e:
        # Validation failed - update status with error
        error_msg = str(e)[:500]  # Truncate long errors

        with conn.cursor() as cur:
            cur.execute("""
                UPDATE kg_api.system_api_keys
                SET
                    validation_status = 'invalid',
                    last_validated_at = NOW(),
                    validation_error = %s
                WHERE provider = %s
            """, (error_msg, provider))
            conn.commit()

        logger.warning(f"✗ {provider} key validation failed: {error_msg}")
        return False

    finally:
        client.pool.putconn(conn)
```

**CLI view of key status:**

```bash
$ kg admin keys list

API Keys Configuration
=======================

Provider    Key Preview        Status    Last Validated           Error
--------    -----------        ------    --------------           -----
openai      sk-proj-...a1B2c3  ✓ valid   2025-10-21 07:30:00 UTC  -
anthropic   sk-ant-...x7Y8z9   ✗ invalid 2025-10-21 07:30:05 UTC  API key expired

Update invalid keys:
  kg admin keys set anthropic sk-ant-...
```

**Behavior:**
- ✅ **Valid keys**: Marked 'valid' with timestamp
- ⚠️ **Invalid keys**: Marked 'invalid' with error message, API still starts
- 📋 **Untested keys**: Newly added keys before first validation
- 🔄 **Re-validation**: Occurs on every API startup
- 📊 **Visibility**: Users see key status via `kg admin keys list`

### Administrative API Endpoints for Key Management

**Enhanced endpoints from ADR-031 with validation status:**

```python
# src/api/routes/admin_keys.py (Updated)

class APIKeyInfo(BaseModel):
    """API key information with validation status"""
    provider: str
    configured: bool
    key_preview: Optional[str]  # Masked key preview (e.g., "sk-...xyz123")
    validation_status: Optional[str]  # 'valid', 'invalid', 'untested'
    last_validated_at: Optional[str]
    validation_error: Optional[str]
    updated_at: Optional[str]


def mask_api_key(plaintext_key: str) -> str:
    """
    Mask API key for display, showing only prefix and last 6 characters.

    Examples:
        "sk-proj-abc123...xyz789" → "sk-...xyz789"
        "sk-ant-abc123...xyz789" → "sk-ant-...xyz789"
    """
    if not plaintext_key or len(plaintext_key) < 10:
        return "***"

    # Determine prefix length (sk- or sk-ant- or sk-proj-)
    if plaintext_key.startswith("sk-ant-"):
        prefix = "sk-ant-"
    elif plaintext_key.startswith("sk-proj-"):
        prefix = "sk-proj-"
    elif plaintext_key.startswith("sk-"):
        prefix = "sk-"
    else:
        prefix = ""

    # Show last 6 characters
    suffix = plaintext_key[-6:]

    return f"{prefix}...{suffix}"


@router.get("/", response_model=list[APIKeyInfo])
async def list_api_keys(
    _admin = Depends(require_admin),
    age_client = Depends(get_age_client)
):
    """
    List all API keys with validation status (admin only).

    Returns validation state, last check time, and any errors.
    Keys are masked (only show prefix + last 6 chars).
    """
    key_store = EncryptedKeyStore(age_client.conn)

    with age_client.conn.cursor() as cur:
        cur.execute("""
            SELECT
                provider,
                encrypted_key,
                updated_at,
                validation_status,
                last_validated_at,
                validation_error
            FROM kg_api.system_api_keys
            ORDER BY provider
        """)

        configured_keys = []
        for row in cur.fetchall():
            # Decrypt key to get masked preview
            encrypted_key = bytes(row[1])
            plaintext_key = key_store.cipher.decrypt(encrypted_key).decode()
            key_preview = mask_api_key(plaintext_key)

            configured_keys.append({
                'provider': row[0],
                'key_preview': key_preview,
                'updated_at': row[2].isoformat() if row[2] else None,
                'validation_status': row[3],
                'last_validated_at': row[4].isoformat() if row[4] else None,
                'validation_error': row[5]
            })

    # Return all possible providers
    all_providers = ["openai", "anthropic"]
    configured_map = {k['provider']: k for k in configured_keys}

    return [
        APIKeyInfo(
            provider=provider,
            configured=provider in configured_map,
            key_preview=configured_map[provider]['key_preview'] if provider in configured_map else None,
            validation_status=configured_map[provider]['validation_status'] if provider in configured_map else None,
            last_validated_at=configured_map[provider]['last_validated_at'] if provider in configured_map else None,
            validation_error=configured_map[provider]['validation_error'] if provider in configured_map else None,
            updated_at=configured_map[provider]['updated_at'] if provider in configured_map else None
        )
        for provider in all_providers
    ]


@router.post("/{provider}/validate")
async def validate_api_key(
    provider: Literal["openai", "anthropic"],
    _admin = Depends(require_admin)
):
    """
    Manually trigger API key validation (admin only).

    Useful for testing keys after update without restarting API.
    """
    from ..lib.encrypted_keys import validate_and_update_key_status

    # Determine usage type based on active configs
    extraction_config = load_active_extraction_config()
    embedding_config = load_active_embedding_config()

    validated_extraction = False
    validated_embedding = False

    # Validate for extraction if provider matches
    if extraction_config and extraction_config['provider'] == provider:
        validated_extraction = await validate_and_update_key_status(provider, 'extraction')

    # Validate for embedding if provider matches
    if embedding_config and embedding_config.get('provider') == provider:
        validated_embedding = await validate_and_update_key_status(provider, 'embedding')

    # Get updated validation status
    key_store = EncryptedKeyStore(...)
    status = key_store.get_validation_status(provider)

    return {
        "provider": provider,
        "validation_status": status['validation_status'],
        "last_validated_at": status['last_validated_at'],
        "validation_error": status['validation_error'],
        "validated_for": {
            "extraction": validated_extraction,
            "embedding": validated_embedding
        }
    }
```

**Example API responses:**

```bash
# GET /admin/keys
curl http://localhost:8000/admin/keys -H "Authorization: Bearer <token>"
```

```json
[
  {
    "provider": "openai",
    "configured": true,
    "key_preview": "sk-proj-...a1B2c3",
    "validation_status": "valid",
    "last_validated_at": "2025-10-21T07:30:00Z",
    "validation_error": null,
    "updated_at": "2025-10-20T10:00:00Z"
  },
  {
    "provider": "anthropic",
    "configured": true,
    "key_preview": "sk-ant-...x7Y8z9",
    "validation_status": "invalid",
    "last_validated_at": "2025-10-21T07:30:05Z",
    "validation_error": "AuthenticationError: API key has been revoked",
    "updated_at": "2025-09-15T08:00:00Z"
  }
]
```

```bash
# POST /admin/keys/openai/validate
curl -X POST http://localhost:8000/admin/keys/openai/validate \
  -H "Authorization: Bearer <token>"
```

```json
{
  "provider": "openai",
  "validation_status": "valid",
  "last_validated_at": "2025-10-21T08:15:30Z",
  "validation_error": null,
  "validated_for": {
    "extraction": true,
    "embedding": true
  }
}
```

## Development Mode vs Production Mode

### Configuration Source Control

**Problem:** Need to support both local development (quick .env edits) and production (database-first) without spaghetti code.

**Solution:** Explicit `DEVELOPMENT_MODE` flag controls configuration source.

```bash
# .env
DEVELOPMENT_MODE=true   # .env is source of truth
# or
DEVELOPMENT_MODE=false  # Database is source of truth (production)
```

### Mode Behavior

| Aspect | Development Mode | Production Mode |
|--------|-----------------|-----------------|
| **Flag** | `DEVELOPMENT_MODE=true` | `DEVELOPMENT_MODE=false` (or omitted) |
| **Config source** | `.env` file | Database tables |
| **API keys** | From `.env` | From `system_api_keys` (encrypted) |
| **Extraction config** | From `.env` (`AI_PROVIDER`, `*_EXTRACTION_MODEL`) | From `ai_extraction_config` table |
| **Embedding config** | From `.env` (`EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`) | From `embedding_config` table |
| **Startup warning** | ⚠️ Logs "DEVELOPMENT MODE ACTIVE" | ℹ️ Logs "Production mode" |
| **Database writes** | Never (read-only) | Config stored in database |
| **Hot reload** | Restart required | API endpoints update config |

### Why This Approach?

**Supports all future scenarios:**

```bash
# Scenario 1: All local (no API keys needed)
DEVELOPMENT_MODE=true
AI_PROVIDER=local
LOCAL_EXTRACTION_MODEL=llama-3.1-70b
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=nomic-ai/nomic-embed-text-v1.5
# No API keys! Still development mode.

# Scenario 2: Hybrid development
DEVELOPMENT_MODE=true
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
EMBEDDING_PROVIDER=local  # Cost optimization

# Scenario 3: Production with local providers
DEVELOPMENT_MODE=false
# All config in database:
#   ai_extraction_config: provider='local', model='llama-3.1-70b'
#   embedding_config: provider='local', model='nomic-embed-text-v1.5'
```

**Key insight:** Mode is about **config source**, not **whether you have API keys**.

### Implementation

```python
# src/api/lib/config.py (New centralized config module)
import os
import logging

logger = logging.getLogger(__name__)

# Global development mode flag
DEVELOPMENT_MODE = os.getenv('DEVELOPMENT_MODE', 'false').lower() == 'true'

def is_development_mode() -> bool:
    """Check if running in development mode."""
    return DEVELOPMENT_MODE

def get_config_source() -> str:
    """Get configuration source name."""
    return 'environment' if DEVELOPMENT_MODE else 'database'

# Startup warning
if DEVELOPMENT_MODE:
    logger.warning("╔════════════════════════════════════════╗")
    logger.warning("║   ⚠️  DEVELOPMENT MODE ACTIVE  ⚠️      ║")
    logger.warning("╚════════════════════════════════════════╝")
    logger.warning("Configuration source: .env file")
    logger.warning("Database configuration will be IGNORED")
    logger.warning("Set DEVELOPMENT_MODE=false for production")
```

```python
# src/api/lib/ai_providers.py (Updated get_provider)
from .config import DEVELOPMENT_MODE

def get_provider(provider_name: Optional[str] = None) -> AIProvider:
    """Factory with mode-aware configuration loading."""

    if DEVELOPMENT_MODE:
        # Development: .env is source of truth
        provider = provider_name or os.getenv('AI_PROVIDER', 'openai')
        model = os.getenv(f'{provider.upper()}_EXTRACTION_MODEL')
        logger.debug(f"[DEV] Using .env: {provider}/{model}")
    else:
        # Production: database is source of truth
        from .ai_extraction_config import load_active_extraction_config
        config = load_active_extraction_config()

        if not config:
            raise RuntimeError(
                "No AI extraction config in database. "
                "Initialize via: ./scripts/setup/initialize-platform.sh"
            )

        provider = config['provider']
        model = config['model_name']
        logger.debug(f"[PROD] Using database: {provider}/{model}")

    # Instantiate provider (same for both modes)
    if provider == 'openai':
        return OpenAIProvider(extraction_model=model)
    elif provider == 'anthropic':
        return AnthropicProvider(extraction_model=model)
    else:
        raise ValueError(f"Unknown provider: {provider}")
```

### Health Endpoint Enhancement

```python
@router.get("/health")
async def health_check():
    """Health check with mode information."""
    from .lib.config import DEVELOPMENT_MODE, get_config_source

    response = {
        "status": "healthy",
        "mode": "development" if DEVELOPMENT_MODE else "production",
        "config_source": get_config_source()
    }

    if DEVELOPMENT_MODE:
        response["warnings"] = [
            "Development mode active: using .env configuration",
            "Set DEVELOPMENT_MODE=false for production"
        ]

    return response
```

### .env.example Documentation

```bash
# ============================================================================
# Development Mode
# ============================================================================
# Controls configuration source:
#   true  = Use .env configuration (development, quick iteration)
#   false = Use database configuration (production, runtime updates)
#
# This affects ALL configuration sources:
#   - AI provider selection (OpenAI, Anthropic, Local)
#   - Model selection (gpt-4o, claude-sonnet-4, llama-3.1)
#   - Embedding configuration
#   - API keys (if providers need them)
#
# Default: false (production mode)
# ============================================================================
DEVELOPMENT_MODE=true

# ============================================================================
# AI Configuration (Only used if DEVELOPMENT_MODE=true)
# ============================================================================

# Extraction Provider
AI_PROVIDER=openai  # Options: openai, anthropic, local (future)
OPENAI_EXTRACTION_MODEL=gpt-4o
ANTHROPIC_EXTRACTION_MODEL=claude-sonnet-4-20250514
# LOCAL_EXTRACTION_MODEL=llama-3.1-70b  # Future

# Embedding Provider (already supported)
# EMBEDDING_PROVIDER=local
# EMBEDDING_MODEL=nomic-ai/nomic-embed-text-v1.5

# API Keys (only if providers require them)
# OPENAI_API_KEY=sk-proj-...
# ANTHROPIC_API_KEY=sk-ant-...
```

## References

- Related: ADR-031 (Encrypted API Key Storage) - Shared API keys
- Related: ADR-039 (Local Embedding Service) - Parallel embedding configuration
- Related: ADR-040 (Database Schema Migrations) - Schema evolution
