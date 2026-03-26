-- Migration 059: Provider model catalog and OpenRouter support (ADR-800)
--
-- Creates the provider_model_catalog table for dynamic model discovery,
-- seeds it with known models and pricing, and adds openrouter to the
-- ai_extraction_config provider check constraint.

-- ============================================================
-- Table: provider_model_catalog
-- ============================================================

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
    price_prompt_per_m NUMERIC,
    price_completion_per_m NUMERIC,
    price_cache_read_per_m NUMERIC,

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

-- ============================================================
-- Update provider check constraint to include openrouter
-- ============================================================

ALTER TABLE kg_api.ai_extraction_config
    DROP CONSTRAINT IF EXISTS ai_extraction_config_provider_check;

ALTER TABLE kg_api.ai_extraction_config
    ADD CONSTRAINT ai_extraction_config_provider_check
    CHECK (provider IN ('openai', 'anthropic', 'ollama', 'openrouter'));

-- ============================================================
-- Seed: OpenAI extraction models
-- ============================================================

INSERT INTO kg_api.provider_model_catalog
    (provider, model_id, display_name, category, context_length, supports_vision, supports_json_mode, supports_tool_use, price_prompt_per_m, price_completion_per_m, enabled, is_default, sort_order)
VALUES
    ('openai', 'gpt-4o', 'GPT-4o', 'extraction', 128000, TRUE, TRUE, TRUE, 2.50, 10.00, TRUE, TRUE, 1),
    ('openai', 'gpt-4o-mini', 'GPT-4o Mini', 'extraction', 128000, TRUE, TRUE, TRUE, 0.15, 0.60, TRUE, FALSE, 2),
    ('openai', 'gpt-4-turbo', 'GPT-4 Turbo', 'extraction', 128000, TRUE, TRUE, TRUE, 10.00, 30.00, FALSE, FALSE, 3),
    ('openai', 'o1-preview', 'o1 Preview', 'extraction', 128000, FALSE, FALSE, FALSE, 15.00, 60.00, FALSE, FALSE, 4),
    ('openai', 'o1-mini', 'o1 Mini', 'extraction', 128000, FALSE, FALSE, FALSE, 3.00, 12.00, FALSE, FALSE, 5)
ON CONFLICT (provider, model_id, category) DO NOTHING;

-- Seed: OpenAI embedding models
INSERT INTO kg_api.provider_model_catalog
    (provider, model_id, display_name, category, context_length, supports_vision, supports_json_mode, price_prompt_per_m, price_completion_per_m, enabled, is_default, sort_order)
VALUES
    ('openai', 'text-embedding-3-small', 'Embedding v3 Small', 'embedding', 8191, FALSE, FALSE, 0.02, NULL, TRUE, TRUE, 1),
    ('openai', 'text-embedding-3-large', 'Embedding v3 Large', 'embedding', 8191, FALSE, FALSE, 0.13, NULL, TRUE, FALSE, 2),
    ('openai', 'text-embedding-ada-002', 'Embedding Ada 002', 'embedding', 8191, FALSE, FALSE, 0.10, NULL, FALSE, FALSE, 3)
ON CONFLICT (provider, model_id, category) DO NOTHING;

-- ============================================================
-- Seed: Anthropic extraction models
-- ============================================================

INSERT INTO kg_api.provider_model_catalog
    (provider, model_id, display_name, category, context_length, supports_vision, supports_json_mode, supports_tool_use, price_prompt_per_m, price_completion_per_m, enabled, is_default, sort_order)
VALUES
    ('anthropic', 'claude-sonnet-4-20250514', 'Claude Sonnet 4', 'extraction', 200000, TRUE, TRUE, TRUE, 3.00, 15.00, TRUE, TRUE, 1),
    ('anthropic', 'claude-3-5-sonnet-20241022', 'Claude 3.5 Sonnet', 'extraction', 200000, TRUE, TRUE, TRUE, 3.00, 15.00, TRUE, FALSE, 2),
    ('anthropic', 'claude-3-opus-20240229', 'Claude 3 Opus', 'extraction', 200000, TRUE, TRUE, TRUE, 15.00, 75.00, FALSE, FALSE, 3),
    ('anthropic', 'claude-3-sonnet-20240229', 'Claude 3 Sonnet', 'extraction', 200000, TRUE, TRUE, TRUE, 3.00, 15.00, FALSE, FALSE, 4),
    ('anthropic', 'claude-3-haiku-20240307', 'Claude 3 Haiku', 'extraction', 200000, TRUE, TRUE, TRUE, 0.25, 1.25, TRUE, FALSE, 5)
ON CONFLICT (provider, model_id, category) DO NOTHING;

-- ============================================================
-- Seed: Ollama extraction models (local — pricing is $0)
-- ============================================================

INSERT INTO kg_api.provider_model_catalog
    (provider, model_id, display_name, category, context_length, supports_vision, supports_json_mode, price_prompt_per_m, price_completion_per_m, enabled, is_default, sort_order)
VALUES
    ('ollama', 'mistral:7b-instruct', 'Mistral 7B Instruct', 'extraction', 32768, FALSE, TRUE, 0, 0, TRUE, TRUE, 1),
    ('ollama', 'llama3.1:8b-instruct', 'Llama 3.1 8B Instruct', 'extraction', 131072, FALSE, TRUE, 0, 0, TRUE, FALSE, 2),
    ('ollama', 'qwen2.5:7b-instruct', 'Qwen 2.5 7B Instruct', 'extraction', 131072, FALSE, TRUE, 0, 0, TRUE, FALSE, 3),
    ('ollama', 'phi3.5:3.8b-mini-instruct', 'Phi-3.5 Mini', 'extraction', 128000, FALSE, TRUE, 0, 0, FALSE, FALSE, 4),
    ('ollama', 'gemma2:9b-instruct', 'Gemma 2 9B Instruct', 'extraction', 8192, FALSE, TRUE, 0, 0, FALSE, FALSE, 5),
    ('ollama', 'qwen2.5:14b-instruct', 'Qwen 2.5 14B Instruct', 'extraction', 131072, FALSE, TRUE, 0, 0, FALSE, FALSE, 10),
    ('ollama', 'llama3.1:70b-instruct', 'Llama 3.1 70B Instruct', 'extraction', 131072, FALSE, TRUE, 0, 0, FALSE, FALSE, 20),
    ('ollama', 'qwen2.5:72b-instruct', 'Qwen 2.5 72B Instruct', 'extraction', 131072, FALSE, TRUE, 0, 0, FALSE, FALSE, 21),
    ('ollama', 'mixtral:8x7b-instruct', 'Mixtral 8x7B', 'extraction', 32768, FALSE, TRUE, 0, 0, FALSE, FALSE, 22),
    ('ollama', 'mixtral:8x22b-instruct', 'Mixtral 8x22B', 'extraction', 65536, FALSE, TRUE, 0, 0, FALSE, FALSE, 23),
    ('ollama', 'deepseek-coder:33b', 'DeepSeek Coder 33B', 'extraction', 16384, FALSE, TRUE, 0, 0, FALSE, FALSE, 24)
ON CONFLICT (provider, model_id, category) DO NOTHING;

-- Seed: Ollama vision models
INSERT INTO kg_api.provider_model_catalog
    (provider, model_id, display_name, category, context_length, supports_vision, supports_json_mode, price_prompt_per_m, price_completion_per_m, enabled, sort_order)
VALUES
    ('ollama', 'llava:7b', 'LLaVA 7B', 'vision', 4096, TRUE, FALSE, 0, 0, FALSE, 1),
    ('ollama', 'llava:13b', 'LLaVA 13B', 'vision', 4096, TRUE, FALSE, 0, 0, FALSE, 2),
    ('ollama', 'bakllava:7b', 'BakLLaVA 7B', 'vision', 4096, TRUE, FALSE, 0, 0, FALSE, 3)
ON CONFLICT (provider, model_id, category) DO NOTHING;

-- ===========================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (59, 'provider_model_catalog')
ON CONFLICT (version) DO NOTHING;
