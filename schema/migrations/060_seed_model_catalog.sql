-- Migration 060: Seed provider_model_catalog with known models and pricing (ADR-800)
-- Pricing as of 2026-03 in USD per 1M tokens

-- ============================================================
-- OpenAI extraction models
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

-- OpenAI embedding models
INSERT INTO kg_api.provider_model_catalog
    (provider, model_id, display_name, category, context_length, supports_vision, supports_json_mode, price_prompt_per_m, price_completion_per_m, enabled, is_default, sort_order)
VALUES
    ('openai', 'text-embedding-3-small', 'Embedding v3 Small', 'embedding', 8191, FALSE, FALSE, 0.02, NULL, TRUE, TRUE, 1),
    ('openai', 'text-embedding-3-large', 'Embedding v3 Large', 'embedding', 8191, FALSE, FALSE, 0.13, NULL, TRUE, FALSE, 2),
    ('openai', 'text-embedding-ada-002', 'Embedding Ada 002', 'embedding', 8191, FALSE, FALSE, 0.10, NULL, FALSE, FALSE, 3)
ON CONFLICT (provider, model_id, category) DO NOTHING;

-- ============================================================
-- Anthropic extraction models
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
-- Ollama extraction models (local — pricing is $0)
-- ============================================================
INSERT INTO kg_api.provider_model_catalog
    (provider, model_id, display_name, category, context_length, supports_vision, supports_json_mode, price_prompt_per_m, price_completion_per_m, enabled, is_default, sort_order)
VALUES
    -- 7-8B models
    ('ollama', 'mistral:7b-instruct', 'Mistral 7B Instruct', 'extraction', 32768, FALSE, TRUE, 0, 0, TRUE, TRUE, 1),
    ('ollama', 'llama3.1:8b-instruct', 'Llama 3.1 8B Instruct', 'extraction', 131072, FALSE, TRUE, 0, 0, TRUE, FALSE, 2),
    ('ollama', 'qwen2.5:7b-instruct', 'Qwen 2.5 7B Instruct', 'extraction', 131072, FALSE, TRUE, 0, 0, TRUE, FALSE, 3),
    ('ollama', 'phi3.5:3.8b-mini-instruct', 'Phi-3.5 Mini', 'extraction', 128000, FALSE, TRUE, 0, 0, FALSE, FALSE, 4),
    ('ollama', 'gemma2:9b-instruct', 'Gemma 2 9B Instruct', 'extraction', 8192, FALSE, TRUE, 0, 0, FALSE, FALSE, 5),
    -- 14B+
    ('ollama', 'qwen2.5:14b-instruct', 'Qwen 2.5 14B Instruct', 'extraction', 131072, FALSE, TRUE, 0, 0, FALSE, FALSE, 10),
    -- 70B+
    ('ollama', 'llama3.1:70b-instruct', 'Llama 3.1 70B Instruct', 'extraction', 131072, FALSE, TRUE, 0, 0, FALSE, FALSE, 20),
    ('ollama', 'qwen2.5:72b-instruct', 'Qwen 2.5 72B Instruct', 'extraction', 131072, FALSE, TRUE, 0, 0, FALSE, FALSE, 21),
    ('ollama', 'mixtral:8x7b-instruct', 'Mixtral 8x7B', 'extraction', 32768, FALSE, TRUE, 0, 0, FALSE, FALSE, 22),
    ('ollama', 'mixtral:8x22b-instruct', 'Mixtral 8x22B', 'extraction', 65536, FALSE, TRUE, 0, 0, FALSE, FALSE, 23),
    ('ollama', 'deepseek-coder:33b', 'DeepSeek Coder 33B', 'extraction', 16384, FALSE, TRUE, 0, 0, FALSE, FALSE, 24)
ON CONFLICT (provider, model_id, category) DO NOTHING;

-- Ollama vision models
INSERT INTO kg_api.provider_model_catalog
    (provider, model_id, display_name, category, context_length, supports_vision, supports_json_mode, price_prompt_per_m, price_completion_per_m, enabled, sort_order)
VALUES
    ('ollama', 'llava:7b', 'LLaVA 7B', 'vision', 4096, TRUE, FALSE, 0, 0, FALSE, 1),
    ('ollama', 'llava:13b', 'LLaVA 13B', 'vision', 4096, TRUE, FALSE, 0, 0, FALSE, 2),
    ('ollama', 'bakllava:7b', 'BakLLaVA 7B', 'vision', 4096, TRUE, FALSE, 0, 0, FALSE, 3)
ON CONFLICT (provider, model_id, category) DO NOTHING;

-- ===========================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (60, 'seed_model_catalog')
ON CONFLICT (version) DO NOTHING;
