-- Migration 061: Allow llama.cpp as an extraction provider
--
-- llama.cpp is a local OpenAI-compatible inference server. Adding it to the
-- ai_extraction_config provider check constraint lets operators set it as the
-- active extraction provider. Catalog/keys/UI are already provider-agnostic
-- (ADR-800); this only widens the allowed-provider constraint.

ALTER TABLE kg_api.ai_extraction_config
    DROP CONSTRAINT IF EXISTS ai_extraction_config_provider_check;

ALTER TABLE kg_api.ai_extraction_config
    ADD CONSTRAINT ai_extraction_config_provider_check
    CHECK (provider IN ('openai', 'anthropic', 'ollama', 'openrouter', 'llamacpp'));

-- ===========================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (61, 'llamacpp_provider')
ON CONFLICT (version) DO NOTHING;
