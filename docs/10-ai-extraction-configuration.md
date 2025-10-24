# 10 - AI Extraction Configuration

**Part:** II - Configuration
**Reading Time:** ~15 minutes
**Prerequisites:** [Section 03 - Quick Start](03-quick-start-your-first-knowledge-graph.md), [Section 08 - Choosing Your AI Provider](08-choosing-your-ai-provider.md)

---

This section explains how to configure and manage AI extraction models. Extraction models power concept extraction from documents. The system supports multiple providers (OpenAI, Anthropic, Ollama) with different models available for each.

## What Extraction Configuration Controls

Every document ingestion requires an LLM to extract concepts from text. The extraction configuration determines:

1. **Provider:** Which AI provider to use (OpenAI, Anthropic, Ollama)
2. **Model:** Which specific model within that provider (gpt-4o, claude-sonnet-4, etc.)
3. **Capabilities:** Whether the model supports features like vision or JSON mode
4. **Limits:** Maximum tokens the model can generate

These settings affect extraction quality, speed, and cost. Different models produce different results (see Section 08).

## Viewing Current Configuration

Check which extraction provider and model are active:

```bash
kg admin extraction config
```

**Example output:**

```
🤖 AI Extraction Configuration
────────────────────────────────────────

  Provider:       openai
  Model:          gpt-4o
  Vision Support: Yes
  JSON Mode:      Yes
  Max Tokens:     4096

  Config ID: 1
```

This shows the active extraction model used for all future ingestions.

---

## Configuring Extraction Models

### Switch Provider and Model

Update which provider and model to use:

```bash
kg admin extraction set --provider openai --model gpt-4o
```

```bash
kg admin extraction set --provider anthropic --model claude-sonnet-4-20250514
```

```bash
kg admin extraction set --provider ollama --model qwen3:14b
```

After changing extraction configuration, restart the API server:

```bash
./scripts/stop-api.sh && ./scripts/start-api.sh
```

**Note:** Unlike embedding configuration, extraction changes require API restart. Hot reloading is not yet supported.

### Available Models

**OpenAI:**
- `gpt-4o` - Best balance of quality, speed, and cost (recommended)
- `gpt-4o-mini` - Faster and cheaper for testing
- `gpt-4-turbo` - Legacy model

**Anthropic** (as of October 23, 2025):
- `claude-sonnet-4-5` - State-of-the-art quality, excellent performance
- `claude-opus-4-1` - Highest quality, slower but more accurate
- `claude-haiku-4-5` - Fast, cost-effective, still very capable
- `claude-3-5-sonnet-20241022` - Previous generation (legacy)

**Ollama (local models):**
- `qwen3:14b` - Maximum concept extraction (57 concepts/doc)
- `qwen2.5:14b-instruct` - Highest canonical adherence (92%)
- `gpt-oss:20b` - Densest relationship graphs (190 edges)
- `mistral:7b-instruct` - Not recommended (low quality)

See [Section 08](08-choosing-your-ai-provider.md) for detailed model comparisons.

### Advanced Options

**Adjust max tokens:**

```bash
kg admin extraction set --max-tokens 8192
```

Higher max tokens allow the model to generate more output. Useful for complex documents. Default is 4096.

**Enable/disable features:**

```bash
# Enable JSON mode explicitly
kg admin extraction set --json-mode

# Disable vision support
kg admin extraction set --no-vision
```

**Note:** Vision support for processing images and diagrams in documents is planned for future implementation in the intake pipeline.

Most users don't need to adjust these. Defaults work well.

---

## API Key Management

Extraction requires valid API keys for cloud providers (OpenAI, Anthropic). Local providers (Ollama) don't need API keys.

### View API Key Status

Check which API keys are configured and their validation status:

```bash
kg admin keys list
```

**Example output:**

```
🔑 API Keys
────────────────────────────────────────

  ✓ openai
    Status:         Valid
    Key:            sk-...abc123
    Last Validated: 10/22/2025, 9:11:14 AM

  ⚠ anthropic
    Status:         Invalid
    Key:            sk-ant-...xyz789
    Last Validated: 10/22/2025, 8:15:30 AM
    Error:          Authentication failed: invalid API key

  ○ google
    Not configured
```

**Icons:**
- ✓ Valid and working key
- ⚠ Invalid or expired key
- ○ No key configured

### Set API Key

Add or update an API key for a provider:

```bash
# Interactive mode (prompts for key)
kg admin keys set openai

# Non-interactive mode
kg admin keys set openai --key sk-your-key-here
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

The system validates the key before storing it. Invalid keys are rejected immediately.

### Delete API Key

Remove a provider's API key:

```bash
kg admin keys delete openai
```

**Confirmation prompt:**

```
Delete openai API key? (yes/no): yes

✓ API key deleted

  Provider: openai
```

### Key Security

API keys are:
- **Encrypted at rest** using AES encryption
- **Validated on storage** to catch invalid keys early
- **Masked in display** - only show `sk-...abc123` format
- **Validated at startup** - catch expired keys before ingestion fails

Keys never appear in logs or API responses in plain text.

---

## Common Workflows

### Initial Setup (OpenAI)

Set up extraction for the first time:

```bash
# 1. Set API key
kg admin keys set openai

# 2. Verify key is valid
kg admin keys list

# 3. Configure extraction model (optional - defaults to gpt-4o)
kg admin extraction config

# 4. Test with ingestion
kg ingest file test-document.txt --ontology "Test" -y
```

### Switch from OpenAI to Anthropic

Change providers without losing existing data:

```bash
# 1. Set Anthropic API key
kg admin keys set anthropic

# 2. Verify key is valid
kg admin keys list

# 3. Update extraction configuration
kg admin extraction set --provider anthropic --model claude-sonnet-4-20250514

# 4. Restart API
./scripts/stop-api.sh && ./scripts/start-api.sh

# 5. Test with ingestion
kg ingest file test-document.txt --ontology "Test" -y
```

New ingestions use Anthropic. Existing data remains unchanged.

### Switch to Local Models (Ollama)

Move to cost-free local inference:

```bash
# 1. Start Ollama container
./scripts/start-ollama.sh -y

# 2. Pull model
docker exec kg-ollama ollama pull qwen3:14b

# 3. Configure system to use Ollama
kg admin extraction set --provider ollama --model qwen3:14b

# 4. Restart API
./scripts/stop-api.sh && ./scripts/start-api.sh

# 5. Test extraction
kg admin extraction test
```

See [Section 12](12-local-llm-inference-with-ollama.md) for detailed Ollama setup.

### Use Cost-Optimized Model

Switch to cheaper model for development/testing:

```bash
# Switch to gpt-4o-mini (faster, cheaper)
kg admin extraction set --provider openai --model gpt-4o-mini --max-tokens 2048

# Restart API
./scripts/stop-api.sh && ./scripts/start-api.sh

# Later, switch back to production model
kg admin extraction set --provider openai --model gpt-4o --max-tokens 4096
./scripts/stop-api.sh && ./scripts/start-api.sh
```

### Fix Invalid or Expired Key

When a key becomes invalid:

```bash
# 1. Check key status
kg admin keys list

# 2. Delete old key
kg admin keys delete openai

# 3. Set new key
kg admin keys set openai

# 4. Restart API
./scripts/stop-api.sh && ./scripts/start-api.sh

# 5. Verify
kg admin keys list
```

---

## Testing Configuration

After changing configuration, verify it works:

```bash
kg admin extraction test
```

This runs a minimal extraction test to verify:
- API key is valid
- Model is accessible
- Configuration works correctly

If the test fails, check error messages for guidance.

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
kg admin keys set openai
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
- Incorrect provider (using OpenAI key for Anthropic)

**Solution:**

Verify you're using the correct key format:
- OpenAI: `sk-...` or `sk-proj-...`
- Anthropic: `sk-ant-...`

Try setting the key again with the correct value.

### Error: "Extraction model not found"

**Full error:**
```
✗ Failed to update extraction configuration
Model not found: gpt-5
```

**Cause:** Invalid model name.

**Solution:**

Use valid model names (see "Available Models" section above). Example:

```bash
kg admin extraction set --provider openai --model gpt-4o
```

### Error: "Rate limit exceeded"

**Error during ingestion:**
```
✗ Chunk processing failed
Rate limit exceeded: 429 Too Many Requests
```

**Causes:**
- Too many concurrent jobs
- Provider rate limits reached
- Insufficient API tier/quota

**Solutions:**

1. **Cancel running jobs:**
   ```bash
   kg jobs list --status running
   kg jobs cancel <job-id>
   ```

2. **Wait and retry:**
   ```bash
   # Wait a few minutes, then retry
   kg ingest file document.txt --ontology "My Ontology" -y
   ```

3. **Use local models:**
   ```bash
   # Switch to Ollama (zero rate limits)
   kg admin extraction set --provider ollama --model qwen3:14b
   ```

### Poor Quality Extraction

**Symptoms:**
- Concepts too generic
- Missing relationships
- Incorrect metadata

**Causes:**
- Using weaker model (gpt-4o-mini vs gpt-4o)
- Insufficient max_tokens
- Complex/technical documents

**Solutions:**

1. **Switch to more capable model:**
   ```bash
   # OpenAI: Use gpt-4o instead of gpt-4o-mini
   kg admin extraction set --provider openai --model gpt-4o

   # Anthropic: Use claude-opus-4 for highest quality
   kg admin extraction set --provider anthropic --model claude-opus-4

   ./scripts/stop-api.sh && ./scripts/start-api.sh
   ```

2. **Increase max_tokens:**
   ```bash
   kg admin extraction set --max-tokens 8192
   ./scripts/stop-api.sh && ./scripts/start-api.sh
   ```

3. **Re-ingest with better config:**
   ```bash
   kg ontology delete "My Ontology"
   kg ingest file document.txt --ontology "My Ontology" -y
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

### Always Validate API Keys

Before production ingestion, verify all keys are valid:

```bash
kg admin keys list
# Ensure all providers show "Valid" status
```

### Choose Appropriate Models

- **Development/Testing:** gpt-4o-mini (faster, cheaper)
- **Production:** gpt-4o or claude-sonnet-4 (best quality)
- **High-Stakes:** claude-opus-4 (highest quality)
- **Large Corpora:** Local models (zero cost)

### Monitor API Costs

Check provider dashboards regularly. Use cheaper models for non-critical ingestion.

### Set Reasonable max_tokens

- 4096 is good for most documents
- 8192 for complex/technical content
- 2048 for simple documents (reduces cost)

### Keep API Keys Secure

- Never commit keys to git
- Use environment variables or Docker secrets in production
- Rotate keys regularly
- Delete unused keys

### Test Configuration Changes

Always test with a small document first:

```bash
# Test with small document
kg ingest file small-test.txt --ontology "Test" -y

# Verify quality
kg search query "test concept"

# Then proceed with full ingestion
```

### Have Backup Provider Configured

Configure both OpenAI and Anthropic. Switch providers if one has downtime or rate limits.

---

## What's Next

Now that you understand extraction configuration, you can:

- **[Section 11 - Embedding Models and Vector Search](11-embedding-models-and-vector-search.md)**: How semantic search works
- **[Section 12 - Local LLM Inference with Ollama](12-local-llm-inference-with-ollama.md)**: Setup local models
- **[Section 13 - Managing Relationship Vocabulary](13-managing-relationship-vocabulary.md)**: Customize relationship types

For technical details:
- **Architecture:** [ADR-041 - AI Extraction Configuration](architecture/ADR-041-ai-extraction-config.md)
- **Configuration Guide:** [guides/EXTRACTION_CONFIGURATION.md](guides/EXTRACTION_CONFIGURATION.md)

---

← [Previous: Common Workflows and Use Cases](09-common-workflows-and-use-cases.md) | [Documentation Index](README.md) | [Next: Embedding Models and Vector Search →](11-embedding-models-and-vector-search.md)
