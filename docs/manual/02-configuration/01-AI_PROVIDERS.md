# AI Provider Configuration

## Overview

The Knowledge Graph System uses a modular AI provider architecture (`api/app/lib/ai_providers.py`) that supports:
- **OpenAI** (GPT-4o family + embeddings)
- **Anthropic** (Claude models)
- **Ollama** (local LLMs - Mistral, Llama, Qwen, etc.)
- **OpenRouter** (unified gateway to many providers)
- **llama.cpp** (server-mode local inference, OpenAI-compatible)

Embeddings come from either OpenAI (`text-embedding-3-small`) or a local sentence-transformers model (e.g. `nomic-embed-text-v1.5`). Embeddings are configured separately via `kg admin embedding` — see [Embedding Configuration](03-EMBEDDING_CONFIGURATION.md).

## Configuration

All provider configuration is stored in PostgreSQL (encrypted for API keys) and managed via the operator container or the `kg` CLI. Do not edit `.env` directly.

### Configure the Extraction Provider

```bash
# Via operator (operator container)
./operator.sh ai-provider <provider> [--model <model>] [--max-tokens <n>]

# Via kg CLI
kg admin extraction set --provider <provider> --model <model>
```

Supported providers: `openai`, `anthropic`, `ollama`, `openrouter`.

### Store API Keys (Encrypted)

```bash
# Via operator
./operator.sh api-key <provider>          # prompts for the key
./operator.sh api-key <provider> --key <key>

# Via kg CLI
kg admin keys set <provider>
```

Keys are validated against the provider before being stored encrypted in `kg_api.system_api_keys` (ADR-031).

## Supported Models

The catalog is driven by a database table (`kg_api.provider_model_catalog`, ADR-800). The defaults below are what `./operator.sh ai-provider <provider>` selects if you omit `--model`. Use `./operator.sh models list <provider>` to see the live catalog and `./operator.sh models refresh <provider>` to pull the latest list from the provider.

### OpenAI

**Extraction defaults:** `gpt-4o`

**Embedding:** `text-embedding-3-small` (1536-dim) by default; `text-embedding-3-large` (3072-dim) also supported.

### Anthropic

**Extraction defaults:** `claude-sonnet-4-20250514`

**Note:** Anthropic does not provide embeddings, so a working embedding provider (OpenAI or local) must still be configured.

### Ollama

**Extraction defaults:** `mistral:7b-instruct`

Requires a running Ollama service. See [Switching Extraction Providers](04-SWITCHING_EXTRACTION_PROVIDERS.md) and [Local Inference Implementation](05-LOCAL_INFERENCE_IMPLEMENTATION.md) for setup.

### OpenRouter

**Extraction defaults:** `openai/gpt-4o`

OpenRouter exposes models from many providers under one API. Set the routed slug (e.g. `anthropic/claude-3.5-sonnet`) via `--model`.

## Status / Validation

```bash
# Show currently active extraction config
kg admin extraction config

# Show which provider keys are configured (no plaintext is ever returned)
kg admin keys list

# Operator-side status
./operator.sh status
```

## Choosing a Provider

### OpenAI (GPT-4)

**Pros:**
- Single API key for everything
- Fast inference
- JSON mode ensures structured output
- Good at following extraction schema
- Cost-effective with gpt-4o-mini

**Cons:**
- Less capable than Claude Sonnet 4 for complex reasoning
- Token limits can be restrictive for long documents

**Best for:**
- Simple concept extraction
- High-volume processing
- When cost is a concern

### Anthropic (Claude)

**Pros:**
- Claude Sonnet 4.5 is current SOTA for reasoning
- Better at understanding nuanced relationships
- Larger context windows (200K tokens)
- More thoughtful analysis

**Cons:**
- Requires two API keys (Anthropic + OpenAI)
- Slower inference
- Higher cost
- Requires JSON extraction from response

**Best for:**
- Complex philosophical/technical documents
- When quality > speed
- Nuanced relationship extraction

## Model Selection Guide

### For Extraction

**Quality Priority:**
1. `claude-sonnet-4-20250514` (Anthropic) - SOTA
2. `gpt-4o` (OpenAI) - Excellent balance
3. `o1-preview` (OpenAI) - Complex reasoning

**Speed Priority:**
1. `gpt-4o-mini` (OpenAI) - Fast and cheap
2. `claude-3-haiku-20240307` (Anthropic) - Fast Claude
3. `gpt-4o` (OpenAI) - Good balance

**Cost Priority:**
1. `gpt-4o-mini` (OpenAI) - Cheapest capable model
2. `gpt-4o` (OpenAI) - Best value
3. `claude-3-haiku-20240307` (Anthropic) - Cheapest Claude

### For Embeddings

**Recommended:**
- `text-embedding-3-small` - Best balance of quality/speed/cost

**High Accuracy:**
- `text-embedding-3-large` - 2x dimensions, better similarity

## Testing and Validation

### Validate API Keys

```bash
# Show key status (validity, last validated)
kg admin keys list

# Operator status (all components)
./operator.sh status
```

### List Available Models

```bash
./operator.sh models list openai
./operator.sh models list anthropic
./operator.sh models list ollama
```

### Test Extraction

```bash
# Submit a small test ingestion; the active provider is used end-to-end
kg ingest text "The universe is vast and complex." -o "test"
kg job list done -l 1
```

## Troubleshooting

### "API key invalid"

```bash
# Re-store the key (validated against the provider before being saved)
kg admin keys set openai

# Confirm
kg admin keys list
```

### "Rate limit exceeded"

- Reduce ingestion batch size
- Add delays between requests
- Upgrade API plan

### "Model not found"

- Check model name spelling
- Verify API access (some models require approval)
- Use `list_available_models()` to see what's accessible

### "JSON parsing failed" (Anthropic)

- Claude may include markdown
- Provider handles cleaning automatically
- Check `_extract_json()` method if issues persist

## Advanced Usage

### Custom Provider

Provider classes live in `api/app/lib/ai_providers.py` and extend the `AIProvider` abstract base class. Add a new subclass there, register it in `get_provider()`, and add a row in `kg_api.provider_model_catalog` for any models it exposes (ADR-800).

### Hybrid Approach

The extraction provider and embedding provider are configured independently. For example, you can run extraction on Anthropic Claude and embeddings on local sentence-transformers — switch extraction with `kg admin extraction set --provider anthropic ...` and embeddings with `kg admin embedding activate <profile-id>`.
