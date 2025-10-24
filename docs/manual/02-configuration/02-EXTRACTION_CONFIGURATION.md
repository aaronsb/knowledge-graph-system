# AI Extraction Configuration Guide

Complete guide to managing AI extraction model configurations and API keys for concept extraction from documents.

## Table of Contents

- [Overview](#overview)
- [Configuration Options](#configuration-options)
- [API Key Management](#api-key-management)
- [Common Workflows](#common-workflows)
- [CLI Commands](#cli-commands)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Knowledge Graph system uses Large Language Models (LLMs) to extract structured concepts, relationships, and metadata from documents during the ingestion process.

### What Extraction Models Do

During ingestion, extraction models:
1. **Analyze document chunks** - Process semantic chunks of text (~1000 words)
2. **Extract concepts** - Identify key ideas, entities, and relationships
3. **Generate metadata** - Create search terms, descriptions, and relationship types
4. **Structure knowledge** - Convert unstructured text into graph-ready format

### Supported Providers

**OpenAI** (ADR-041)
- `gpt-4o` - Latest GPT-4 Omni (recommended, supports vision)
- `gpt-4o-mini` - Faster, cheaper variant
- `gpt-4-turbo` - Previous generation
- JSON mode support

**Anthropic** (ADR-041)
- `claude-sonnet-4` - Latest Claude Sonnet (recommended)
- `claude-3-5-sonnet-20241022` - Previous generation
- `claude-opus-4` - Most capable (higher cost)
- Native JSON support

### Configuration vs API Keys

The system has two separate but related configurations:

1. **Extraction Configuration** - Which model to use and its settings
2. **API Keys** - Credentials for each provider (encrypted, validated)

Both must be configured for extraction to work.

---

## Configuration Options

### Viewing Current Configuration

```bash
# Show active extraction configuration
kg admin extraction config
```

Output:
```
🤖 AI Extraction Configuration
────────────────────────────────────────

  Provider:      openai
  Model:         gpt-4o
  Vision Support: Yes
  JSON Mode:     Yes
  Max Tokens:    4096

  Config ID: 1
```

### Configuration Parameters

| Parameter | Description | Values | Default |
|-----------|-------------|--------|---------|
| `provider` | AI provider | `openai`, `anthropic` | `openai` |
| `model` | Model name | See model lists below | `gpt-4o` |
| `supports_vision` | Vision API support | `true`, `false` | `true` (for gpt-4o) |
| `supports_json_mode` | JSON mode | `true`, `false` | `true` |
| `max_tokens` | Max output tokens | 1024-8192 | 4096 |

### Recommended Models

**OpenAI:**
- **Production**: `gpt-4o` - Best balance of quality, speed, and cost
- **Development**: `gpt-4o-mini` - Faster and cheaper for testing
- **Legacy**: `gpt-4-turbo` - If you need older model behavior

**Anthropic:**
- **Production**: `claude-sonnet-4-5` - Excellent quality, competitive pricing
- **High-quality**: `claude-opus-4` - Best quality, higher cost
- **Legacy**: `claude-3-5-sonnet-20241022` - Previous generation

---

## API Key Management

### Security Features

The system includes robust API key management (ADR-031, ADR-041):

- **Encryption at rest** - Keys encrypted using ENCRYPTION_KEY
- **Validation on storage** - Keys tested before saving (prevents invalid keys)
- **Periodic validation** - Keys validated at startup and periodically
- **Masked display** - Keys never shown in full (`sk-...abc123`)
- **Per-provider keys** - Independent keys for each provider

### Viewing API Keys

```bash
# List all configured API keys
kg admin keys list
```

Output:
```
🔑 API Keys
────────────────────────────────────────

  ✓ openai
    Status:        Valid
    Key:           sk-...abc123
    Last Validated: 10/22/2025, 9:11:14 AM

  ⚠ anthropic
    Status:        Invalid
    Key:           sk-ant-...xyz789
    Last Validated: 10/22/2025, 8:15:30 AM
    Error:         Authentication failed: invalid API key

  ○ google
    Not configured
```

**Icons:**
- ✓ Valid and working key
- ⚠ Invalid or expired key
- ○ No key configured

### Setting API Keys

```bash
# Interactive mode (prompts for key)
kg admin keys set openai

# Non-interactive mode (provide key directly)
kg admin keys set openai --key sk-...

# Set Anthropic key
kg admin keys set anthropic
```

**Interactive example:**
```
🔑 Set openai API Key
────────────────────────────────────────

⚠️  API key will be validated before storage
  A minimal API call will be made to verify the key

Enter openai API key: [hidden input]

Validating API key...

✓ API key configured and validated

  Provider: openai
  Status:   valid
```

**Key validation:**
- OpenAI: Makes a minimal chat completion request
- Anthropic: Makes a minimal message request
- Keys are only stored if validation succeeds

### Deleting API Keys

```bash
# Delete a provider's API key
kg admin keys delete openai
```

**Confirmation prompt:**
```
Delete openai API key? (yes/no): yes

✓ API key deleted

  Provider: openai
```

---

## Common Workflows

### Workflow 1: Initial Setup (OpenAI)

**Set up OpenAI for concept extraction:**

```bash
# 1. Set OpenAI API key
kg admin keys set openai
# Enter your sk-... key when prompted

# 2. Verify key is valid
kg admin keys list

# 3. Configure extraction model (optional - defaults to gpt-4o)
kg admin extraction config

# 4. Test with ingestion
kg ingest file -o "Test Ontology" -y test-document.txt
```

### Workflow 2: Switch from OpenAI to Anthropic

**Switch extraction provider:**

```bash
# 1. Set Anthropic API key
kg admin keys set anthropic
# Enter your sk-ant-... key when prompted

# 2. Verify key is valid
kg admin keys list

# 3. Update extraction configuration
kg admin extraction set --provider anthropic --model claude-sonnet-4

# 4. Restart API to apply changes
./scripts/stop-api.sh && ./scripts/start-api.sh

# 5. Test with ingestion
kg ingest file -o "Test Ontology" -y test-document.txt
```

**Note:** Unlike embedding configs, extraction changes require API restart (no hot reload yet).

### Workflow 3: Switch to Cost-Optimized Model

**Use cheaper model for development/testing:**

```bash
# Switch to gpt-4o-mini for faster, cheaper extraction
kg admin extraction set \
  --provider openai \
  --model gpt-4o-mini \
  --max-tokens 2048

# Restart API
./scripts/stop-api.sh && ./scripts/start-api.sh

# Switch back to gpt-4o for production
kg admin extraction set \
  --provider openai \
  --model gpt-4o \
  --max-tokens 4096

# Restart API
./scripts/stop-api.sh && ./scripts/start-api.sh
```

### Workflow 4: Enable/Disable Features

**Configure model capabilities:**

```bash
# Enable JSON mode explicitly
kg admin extraction set --json-mode

# Disable vision support
kg admin extraction set --no-vision

# Adjust max tokens
kg admin extraction set --max-tokens 8192

# Restart API to apply
./scripts/stop-api.sh && ./scripts/start-api.sh
```

### Workflow 5: Fix Invalid API Key

**When a key expires or becomes invalid:**

```bash
# 1. Check key status
kg admin keys list

# 2. Delete old key
kg admin keys delete openai

# 3. Set new key
kg admin keys set openai
# Enter new key when prompted

# 4. Restart API (picks up new key automatically)
./scripts/stop-api.sh && ./scripts/start-api.sh

# 5. Verify
kg admin keys list
```

---

## CLI Commands

### Extraction Configuration

#### View Configuration
```bash
kg admin extraction config
```

Shows active extraction configuration (provider, model, capabilities).

#### Set Configuration
```bash
kg admin extraction set [OPTIONS]
```

**Options:**
- `--provider <provider>` - Provider: `openai` or `anthropic`
- `--model <model>` - Model name (e.g., `gpt-4o`, `claude-sonnet-4`)
- `--vision` - Enable vision support
- `--no-vision` - Disable vision support
- `--json-mode` - Enable JSON mode
- `--no-json-mode` - Disable JSON mode
- `--max-tokens <n>` - Max output tokens (1024-8192)

**Examples:**

```bash
# Switch to Anthropic Claude Sonnet 4
kg admin extraction set --provider anthropic --model claude-sonnet-4

# Use gpt-4o-mini with reduced tokens
kg admin extraction set --provider openai --model gpt-4o-mini --max-tokens 2048

# Enable JSON mode explicitly
kg admin extraction set --json-mode

# Disable vision support
kg admin extraction set --no-vision
```

**Important:** Extraction config changes require API restart (no hot reload yet):
```bash
./scripts/stop-api.sh && ./scripts/start-api.sh
```

### API Key Management

#### List API Keys
```bash
kg admin keys list
```

Shows all providers with validation status, masked keys, and last validation time.

#### Set API Key
```bash
kg admin keys set <provider> [OPTIONS]
```

**Arguments:**
- `<provider>` - Provider name: `openai` or `anthropic`

**Options:**
- `--key <key>` - API key (prompts if not provided)

**Examples:**

```bash
# Interactive (prompts for key)
kg admin keys set openai

# Non-interactive
kg admin keys set openai --key sk-...

# Set Anthropic key
kg admin keys set anthropic
```

**Validation:**
- Keys are validated before storage
- Invalid keys are rejected immediately
- Successful validation confirms key works

#### Delete API Key
```bash
kg admin keys delete <provider>
```

**Arguments:**
- `<provider>` - Provider name: `openai` or `anthropic`

**Example:**

```bash
kg admin keys delete openai
# Prompts: Delete openai API key? (yes/no):
```

---

## Troubleshooting

### Error: "No API key configured"

**Full error:**
```
✗ Ingestion failed
No API key configured for provider: openai
```

**Solution:**
```bash
# Set the API key
kg admin keys set openai

# Restart API
./scripts/stop-api.sh && ./scripts/start-api.sh
```

### Error: "API key validation failed"

**Full error:**
```
✗ Failed to set API key
Authentication failed: invalid API key
```

**Causes:**
- Wrong API key
- Expired API key
- Incorrect provider (e.g., using OpenAI key for Anthropic)

**Solution:**
```bash
# Verify you're using the correct key format
# OpenAI: sk-...
# Anthropic: sk-ant-...

# Try setting the key again
kg admin keys set openai
```

### Error: "Extraction model not found"

**Full error:**
```
✗ Failed to update extraction configuration
Model not found: gpt-5
```

**Cause:** Invalid model name.

**Solution:**

Use valid model names:

**OpenAI:**
- `gpt-4o`
- `gpt-4o-mini`
- `gpt-4-turbo`

**Anthropic:**
- `claude-sonnet-4`
- `claude-opus-4`
- `claude-3-5-sonnet-20241022`

```bash
# Correct command
kg admin extraction set --provider openai --model gpt-4o
```

### Error: "Rate limit exceeded"

**Error during ingestion:**
```
✗ Chunk processing failed
Rate limit exceeded: 429 Too Many Requests
```

**Causes:**
- Too many concurrent ingestion jobs
- Provider rate limits reached
- Insufficient tier/quota

**Solutions:**

1. **Reduce concurrent jobs:**
   ```bash
   # Cancel running jobs
   kg jobs list --status running
   kg jobs cancel <job-id>
   ```

2. **Wait and retry:**
   ```bash
   # Wait a few minutes, then retry
   kg ingest file -o "My Ontology" -y document.txt
   ```

3. **Switch to a model with higher limits:**
   ```bash
   # OpenAI: Higher tier accounts have higher limits
   # Anthropic: Contact support for rate limit increases
   ```

4. **Use batch processing:**
   ```bash
   # Ingest files one at a time instead of in parallel
   kg ingest file -o "Ontology" -y file1.txt
   # Wait for completion...
   kg ingest file -o "Ontology" -y file2.txt
   ```

### Ingestion Produces Poor Quality Concepts

**Symptoms:**
- Concepts are too generic
- Missing important relationships
- Incorrect metadata

**Causes:**
- Using a weaker model (e.g., gpt-4o-mini vs gpt-4o)
- Insufficient max_tokens
- Complex/technical documents

**Solutions:**

1. **Switch to a more capable model:**
   ```bash
   # OpenAI: Use gpt-4o instead of gpt-4o-mini
   kg admin extraction set --provider openai --model gpt-4o

   # Anthropic: Use claude-opus-4 for highest quality
   kg admin extraction set --provider anthropic --model claude-opus-4

   # Restart API
   ./scripts/stop-api.sh && ./scripts/start-api.sh
   ```

2. **Increase max_tokens:**
   ```bash
   kg admin extraction set --max-tokens 8192
   ./scripts/stop-api.sh && ./scripts/start-api.sh
   ```

3. **Re-ingest with better config:**
   ```bash
   # Delete old ontology
   kg ontology delete "My Ontology"

   # Re-ingest with new config
   kg ingest file -o "My Ontology" -y document.txt
   ```

### API Startup Shows Key Validation Failures

**Startup log:**
```
⚠️  anthropic: API key validation failed - Authentication error
✓ openai: API key validated successfully
🔐 API key validation complete: 1/2 valid
```

**Meaning:**
- Anthropic key is invalid or expired
- OpenAI key is valid
- System will continue startup with only OpenAI available

**Solution:**
```bash
# Fix the invalid key
kg admin keys delete anthropic
kg admin keys set anthropic

# Restart API
./scripts/stop-api.sh && ./scripts/start-api.sh
```

### Config Changes Not Applied

**Symptom:** Changed extraction config but ingestion still uses old model.

**Cause:** Forgot to restart API.

**Solution:**
```bash
# Extraction config changes require restart
./scripts/stop-api.sh && ./scripts/start-api.sh

# Verify new config is active
kg admin extraction config
```

---

## Best Practices

1. **Always validate API keys before production**
   ```bash
   kg admin keys list
   # Ensure all providers show "Valid" status
   ```

2. **Use appropriate models for your use case**
   - **Development/Testing**: gpt-4o-mini (faster, cheaper)
   - **Production**: gpt-4o or claude-sonnet-4 (best quality)
   - **High-stakes**: claude-opus-4 (highest quality)

3. **Monitor API costs**
   - Check provider dashboards regularly
   - Use cheaper models for non-critical ingestion
   - Batch similar documents together

4. **Set reasonable max_tokens**
   - 4096 is good for most documents
   - 8192 for complex/technical content
   - Lower values (2048) for simple documents to reduce cost

5. **Keep API keys secure**
   - Never commit keys to git
   - Use environment variables or Docker secrets in production
   - Rotate keys regularly

6. **Test configuration changes before production**
   ```bash
   # Test with a small document first
   kg ingest file -o "Test" -y small-test.txt

   # Verify quality
   kg search query "test concept"

   # Then proceed with full ingestion
   ```

7. **Have backup provider configured**
   - Configure both OpenAI and Anthropic
   - Switch providers if one has downtime
   - Different models have different strengths

---

## Advanced Topics

### Manual API Calls

If you need to use the API directly:

```bash
# Get extraction config (public endpoint)
curl http://localhost:8000/extraction/config

# Get full config details (admin endpoint)
curl http://localhost:8000/admin/extraction/config

# Update extraction config (admin endpoint)
curl -X POST http://localhost:8000/admin/extraction/config \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model_name": "gpt-4o",
    "supports_vision": true,
    "supports_json_mode": true,
    "max_tokens": 4096
  }'

# List API keys (admin endpoint)
curl http://localhost:8000/admin/keys

# Set API key (admin endpoint)
curl -X POST http://localhost:8000/admin/keys/openai \
  -H "Content-Type: application/json" \
  -d '{"api_key": "sk-..."}'

# Delete API key (admin endpoint)
curl -X DELETE http://localhost:8000/admin/keys/openai
```

### Database Schema

**Extraction Configuration:**
```sql
-- View extraction configs
SELECT id, provider, model_name, supports_vision, supports_json_mode, max_tokens, active
FROM kg_api.ai_extraction_config
ORDER BY id DESC;

-- Check active config
SELECT * FROM kg_api.ai_extraction_config WHERE active = TRUE;
```

**API Keys:**
```sql
-- View API keys (encrypted)
SELECT provider, encrypted_api_key, validation_status, last_validated_at
FROM kg_api.encrypted_api_keys;
```

**Note:** API keys are encrypted at rest and cannot be decrypted via SQL.

### Encryption Key Management

API keys are encrypted using the `ENCRYPTION_KEY` environment variable:

```bash
# Generate new encryption key (32-byte hex)
openssl rand -hex 32

# Set in .env file
ENCRYPTION_KEY=your-generated-key-here

# Restart API to use new key
./scripts/stop-api.sh && ./scripts/start-api.sh
```

**Warning:** Changing ENCRYPTION_KEY invalidates all stored API keys!

### Provider-Specific Features

**OpenAI:**
- JSON mode: Stricter JSON output
- Vision: Can process images (future feature)
- Structured outputs: More reliable JSON schemas

**Anthropic:**
- Native JSON: Built-in JSON mode
- Large context: Better for long documents
- Claude Opus: Best reasoning capabilities

---

## Related Documentation

- [Embedding Configuration Guide](03-EMBEDDING_CONFIGURATION.md) - Embedding model configuration
- [AI Providers Guide](01-AI_PROVIDERS.md) - Provider comparison and setup
- [CLI Usage Guide](../01-getting-started/02-CLI_USAGE.md) - General CLI commands
- [Ingestion Guide](../01-getting-started/03-INGESTION.md) - Document ingestion workflow
- [Authentication Guide](../04-security-and-access/01-AUTHENTICATION.md) - System authentication

---

## Quick Reference

| Task | Command |
|------|---------|
| View extraction config | `kg admin extraction config` |
| Switch to Anthropic | `kg admin extraction set --provider anthropic --model claude-sonnet-4` |
| Switch to OpenAI | `kg admin extraction set --provider openai --model gpt-4o` |
| List API keys | `kg admin keys list` |
| Set OpenAI key | `kg admin keys set openai` |
| Set Anthropic key | `kg admin keys set anthropic` |
| Delete API key | `kg admin keys delete <provider>` |
| Restart API | `./scripts/stop-api.sh && ./scripts/start-api.sh` |
| Test configuration | `kg ingest file -o "Test" -y test.txt` |

**Common workflows:**
1. Set key → Configure model → Restart API → Test
2. List keys → Check validation status → Fix invalid keys → Restart
3. Switch provider → Set key → Configure model → Restart → Test
