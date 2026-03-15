-- Migration 059: Provider model catalog (ADR-800)
-- Dynamic model discovery and curation for all AI providers

CREATE TABLE IF NOT EXISTS kg_api.provider_model_catalog (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,              -- 'openai', 'anthropic', 'ollama', 'openrouter'
    model_id VARCHAR(300) NOT NULL,             -- Provider's model identifier
    display_name VARCHAR(300),                  -- Human-friendly name
    category VARCHAR(50) NOT NULL,              -- 'extraction', 'embedding', 'vision', 'translation'
    context_length INTEGER,
    max_completion_tokens INTEGER,
    supports_vision BOOLEAN DEFAULT FALSE,
    supports_json_mode BOOLEAN DEFAULT FALSE,
    supports_tool_use BOOLEAN DEFAULT FALSE,
    supports_streaming BOOLEAN DEFAULT TRUE,

    -- Pricing (USD per 1M tokens, NULL = unknown/free)
    price_prompt_per_m NUMERIC(12, 6),
    price_completion_per_m NUMERIC(12, 6),
    price_cache_read_per_m NUMERIC(12, 6),

    -- Curation
    enabled BOOLEAN DEFAULT FALSE,
    is_default BOOLEAN DEFAULT FALSE,
    sort_order INTEGER DEFAULT 0,

    -- Metadata
    upstream_provider VARCHAR(100),             -- For OpenRouter: actual upstream provider
    raw_metadata JSONB,                         -- Full provider response preserved
    fetched_at TIMESTAMPTZ,                     -- When catalog was last refreshed from provider

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(provider, model_id, category)
);

-- Only one default per provider+category
CREATE UNIQUE INDEX IF NOT EXISTS idx_catalog_default
ON kg_api.provider_model_catalog(provider, category)
WHERE is_default = TRUE;

-- Fast lookups by provider
CREATE INDEX IF NOT EXISTS idx_catalog_provider
ON kg_api.provider_model_catalog(provider, enabled);

COMMENT ON TABLE kg_api.provider_model_catalog IS 'Cached model catalog per AI provider with curation and pricing (ADR-800)';
