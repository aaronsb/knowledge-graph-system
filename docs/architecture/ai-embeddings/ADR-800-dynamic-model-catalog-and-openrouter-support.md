---
status: Draft
date: 2026-03-15
deciders:
  - aaronsb
  - claude
related:
  - ADR-031
  - ADR-041
  - ADR-042
  - ADR-049
---

# ADR-800: Dynamic Model Catalog and OpenRouter Support

## Context

Model lists for each AI provider are currently hardcoded in `ai_providers.py`. When providers add or retire models, the code must be updated and redeployed. There is no way for operators to discover available models at runtime or curate a preferred subset for their deployment.

Additionally, pricing information is driven by environment variables (`TOKEN_COST_*`) with static defaults. This makes cost tracking fragile — prices change, new models appear, and operators must manually research and update values.

The system currently supports three inference providers (OpenAI, Anthropic, Ollama). **OpenRouter** is a fourth provider type that offers a unified API across 200+ models from multiple upstream providers (OpenAI, Anthropic, Google, Meta, Mistral, etc.) via an OpenAI-compatible endpoint. OpenRouter is interesting because:

- It exposes the same models available directly from other providers (e.g., `openai/gpt-4o`, `anthropic/claude-sonnet-4`), creating overlap
- It includes per-model pricing in its catalog API (`GET /api/v1/models`), with prompt and completion costs per token
- It provides automatic provider routing and fallback for the same model across multiple GPU providers
- Its API is OpenAI-SDK-compatible (`https://openrouter.ai/api/v1`), so the implementation can reuse existing OpenAI client code with a different base URL

The desired operator workflow is:

1. **Select a provider endpoint** (OpenAI, Anthropic, Ollama, OpenRouter)
2. **Validate the connection** (API key check or endpoint reachability)
3. **Browse available models** — either from a previously-fetched cached catalog, or by fetching the full list from the provider API
4. **Curate a subset** — select which models to offer for extraction/embedding use
5. **Persist the curated list** — stored per-provider in the database, including pricing metadata where available

## Decision

### 1. New database table: `kg_api.provider_model_catalog`

A single table stores the cached model catalog for all providers. Each row is one model from one provider.

```sql
CREATE TABLE kg_api.provider_model_catalog (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,           -- 'openai', 'anthropic', 'ollama', 'openrouter'
    model_id VARCHAR(300) NOT NULL,          -- Provider's model identifier
    display_name VARCHAR(300),               -- Human-friendly name
    category VARCHAR(50) NOT NULL,           -- 'extraction', 'embedding', 'vision', 'translation'
    context_length INTEGER,
    max_completion_tokens INTEGER,
    supports_vision BOOLEAN DEFAULT FALSE,
    supports_json_mode BOOLEAN DEFAULT FALSE,
    supports_tool_use BOOLEAN DEFAULT FALSE,
    supports_streaming BOOLEAN DEFAULT TRUE,

    -- Pricing (USD per 1M tokens, NULL = unknown/free)
    price_prompt_per_m NUMERIC(12, 6),       -- Input/prompt cost
    price_completion_per_m NUMERIC(12, 6),   -- Output/completion cost
    price_cache_read_per_m NUMERIC(12, 6),   -- Cached input cost (if applicable)

    -- Curation
    enabled BOOLEAN DEFAULT FALSE,           -- Operator has selected this model
    is_default BOOLEAN DEFAULT FALSE,        -- Default model for this provider+category
    sort_order INTEGER DEFAULT 0,            -- Display ordering

    -- Metadata
    upstream_provider VARCHAR(100),          -- For OpenRouter: the actual provider (e.g., 'anthropic')
    raw_metadata JSONB,                      -- Full provider response for this model
    fetched_at TIMESTAMPTZ,                  -- When catalog was last refreshed
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(provider, model_id, category)
);

-- One default per provider+category
CREATE UNIQUE INDEX idx_catalog_default
ON kg_api.provider_model_catalog(provider, category)
WHERE is_default = TRUE;
```

### 2. Provider catalog fetch implementations

Each provider implements a `fetch_model_catalog()` class method that returns normalized model metadata:

| Provider | Source | Pricing available? |
|----------|--------|--------------------|
| **OpenAI** | `GET /v1/models` (API) | No — hardcode known prices, flag unknown models |
| **Anthropic** | Hardcoded list (no catalog API) | Hardcode known prices |
| **Ollama** | `GET /api/tags` (local instance) | N/A — local, cost is $0 |
| **OpenRouter** | `GET /api/v1/models` (API) | Yes — `pricing.prompt` and `pricing.completion` per-token in response |

For OpenRouter, the catalog response includes:
```json
{
  "id": "anthropic/claude-sonnet-4",
  "name": "Claude Sonnet 4",
  "context_length": 200000,
  "pricing": { "prompt": "0.000003", "completion": "0.000015" },
  "architecture": { "modality": "text->text", "input_modalities": ["text", "image"] },
  "supported_parameters": ["temperature", "tools", "response_format", ...]
}
```

Pricing values from OpenRouter are per-token strings; the fetch implementation converts to per-1M-token numeric values for storage.

### 3. OpenRouter provider implementation

`OpenRouterProvider` extends the provider interface, reusing the OpenAI Python SDK with:

```python
client = openai.OpenAI(
    api_key=openrouter_api_key,
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": "https://github.com/aaronsb/knowledge-graph-system",
        "X-OpenRouter-Title": "Knowledge Graph System"
    }
)
```

Key differences from direct OpenAI:
- Model IDs are namespaced: `openai/gpt-4o`, `anthropic/claude-sonnet-4`, `google/gemini-2.5-pro`
- No direct embedding support — extraction only, pairs with existing embedding providers
- Provider routing preferences can be passed via `extra_body={"provider": {...}}`

### 4. Operator workflow via configure.py and API

**CLI flow** (via `configure.py models`):
```
$ configure.py models list openai          # Show cached catalog (enabled models)
$ configure.py models refresh openai       # Fetch fresh catalog from provider API
$ configure.py models enable openai gpt-4o # Enable a model for use
$ configure.py models disable openai gpt-4o
$ configure.py models default openai gpt-4o extraction  # Set default
```

**API endpoints** (admin):
```
GET  /admin/models/catalog?provider=openai         # List catalog
POST /admin/models/catalog/refresh                  # Fetch from provider
PUT  /admin/models/catalog/{id}/enable              # Enable/disable
PUT  /admin/models/catalog/{id}/default             # Set as default
```

**Validation flow on first configuration**:
1. Operator selects provider and provides API key
2. System validates connectivity (existing `validate_api_key` pattern)
3. If no cached catalog exists, prompt to fetch
4. Operator selects models from fetched list
5. Selected models stored as `enabled=TRUE` in catalog table
6. `ai_extraction_config` references catalog entries for the active model

### 5. Cost tracking integration

The existing `job_analysis.py` cost estimator currently looks up `TOKEN_COST_*` env vars. This changes to:

1. Look up the active model in `provider_model_catalog`
2. Use `price_prompt_per_m` and `price_completion_per_m` from the catalog row
3. Fall back to env vars if catalog pricing is NULL (backward compatibility)
4. OpenRouter pricing auto-populates from their catalog API; other providers use hardcoded defaults that operators can override via `configure.py models price <provider> <model> --prompt <cost> --completion <cost>`

### 6. OpenRouter model overlap handling

When the same underlying model is available both directly and via OpenRouter (e.g., `gpt-4o` via OpenAI and `openai/gpt-4o` via OpenRouter):

- Both appear in the catalog as separate rows (different `provider` column)
- The `upstream_provider` field on OpenRouter entries identifies the actual provider
- Cost comparison is visible in the catalog listing
- The operator chooses which route to use — no automatic arbitrage
- The UI/CLI can flag overlap: "This model is also available directly via OpenAI at $X vs OpenRouter at $Y"

## Consequences

### Positive

- Models are discoverable at runtime — no code changes when providers add models
- Pricing data is fetched from the source (OpenRouter) or maintained in one place (catalog table) rather than scattered across env vars
- Operators can curate exactly which models are available to users
- OpenRouter support opens access to 200+ models through a single API key
- Cost estimates become more accurate with per-model pricing from the catalog
- The pattern is extensible — future providers (Google AI, AWS Bedrock) fit the same `fetch_model_catalog()` interface

### Negative

- Additional database table and migration to maintain
- Catalog staleness — fetched data can drift from reality (mitigated by `fetched_at` timestamp and refresh workflow)
- OpenRouter adds a proxy hop and markup vs. direct provider access
- Anthropic has no catalog API — their model list remains partially hardcoded until they offer one

### Neutral

- `ai_extraction_config` remains the "active config" table — this ADR adds a catalog that feeds into it, not a replacement
- Existing env var cost overrides continue to work as fallback
- The hardcoded `AVAILABLE_MODELS` dicts in `ai_providers.py` become seed data for initial catalog population rather than the runtime source of truth

## Alternatives Considered

### A. Keep model lists hardcoded, just add OpenRouter

Simpler, but doesn't solve the maintenance burden. Every new model requires a code change and redeploy. Pricing stays in env vars. Rejected because the catalog pattern solves multiple problems at once.

### B. External model registry (separate service or config file)

A YAML/JSON config file or separate microservice for model metadata. Rejected because we already have PostgreSQL for configuration (ADR-041) and adding another config source increases operational complexity.

### C. Auto-select cheapest provider for a given model

Automatically route requests to the cheapest available provider when the same model is offered by multiple providers. Rejected for now — adds complexity and the operator should make deliberate cost/latency/reliability tradeoffs. Can be revisited as an enhancement.

## Implementation Notes

### Migration sequence

1. Schema migration: create `provider_model_catalog` table
2. Seed migration: populate with currently hardcoded models + known pricing
3. Add `OpenRouterProvider` class to `ai_providers.py`
4. Add `fetch_model_catalog()` to each provider
5. Update `configure.py` with `models` subcommand
6. Add admin API endpoints for catalog management
7. Update `job_analysis.py` cost estimator to read from catalog
8. Update web UI provider configuration to show catalog

### OpenRouter API details

- Base URL: `https://openrouter.ai/api/v1`
- Auth: `Authorization: Bearer <key>`
- Catalog: `GET /api/v1/models` — returns full model list with pricing (no auth required, but rate-limited)
- Completions: `POST /api/v1/chat/completions` — OpenAI-compatible format
- Generation stats: `GET /api/v1/generation?id={id}` — token usage and cost for a specific request
