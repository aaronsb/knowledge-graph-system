-- Migration 062: Widen pricing columns to avoid overflow on high-cost models
-- Some OpenRouter models (image generation, specialized) have per-1M-token
-- costs that exceed NUMERIC(12,6)'s max of 999999.999999

ALTER TABLE kg_api.provider_model_catalog
    ALTER COLUMN price_prompt_per_m TYPE NUMERIC,
    ALTER COLUMN price_completion_per_m TYPE NUMERIC,
    ALTER COLUMN price_cache_read_per_m TYPE NUMERIC;

-- ===========================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (62, 'widen_catalog_pricing')
ON CONFLICT (version) DO NOTHING;
