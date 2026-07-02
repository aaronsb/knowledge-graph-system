-- Migration 060: Remove hardcoded Ollama catalog seeds (ADR-800)
--
-- Ollama is a local provider that can interrogate itself via /api/tags
-- (OllamaProvider.fetch_model_catalog). Seeding hardcoded Ollama models in
-- migration 059 was the same hardcoding anti-pattern ADR-800 set out to
-- remove: it shows aspirational models that may not be installed locally.
--
-- After this migration the Ollama catalog is empty until an operator runs a
-- catalog Refresh, which discovers the models actually present on the
-- Ollama server. OpenAI/Anthropic seeds are intentionally kept (Anthropic
-- has no catalog API; OpenAI pricing is hardcoded), per ADR-800.

DELETE FROM kg_api.provider_model_catalog
WHERE provider = 'ollama';

-- ===========================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (60, 'remove_ollama_catalog_seeds')
ON CONFLICT (version) DO NOTHING;
