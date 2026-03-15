-- Migration 061: Add openrouter to ai_extraction_config provider check constraint (ADR-800)

ALTER TABLE kg_api.ai_extraction_config
    DROP CONSTRAINT IF EXISTS ai_extraction_config_provider_check;

ALTER TABLE kg_api.ai_extraction_config
    ADD CONSTRAINT ai_extraction_config_provider_check
    CHECK (provider IN ('openai', 'anthropic', 'ollama', 'openrouter'));

-- ===========================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (61, 'add_openrouter_provider')
ON CONFLICT (version) DO NOTHING;
