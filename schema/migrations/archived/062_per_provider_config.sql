-- Migration 062: ai_extraction_config becomes one row PER PROVIDER (ADR-800 / #8)
--
-- The table was used as a single "active config" (insert-new + deactivate-old).
-- For DB-backed per-provider configuration (base_url, model, reasoning params
-- persisted per provider, decoupled from which one is active) we make
-- `provider` unique and switch the save path to an upsert. `active` still
-- marks the single live provider.
--
-- Dedupe: keep, per provider, the active row if any, else the newest id.

DELETE FROM kg_api.ai_extraction_config x
WHERE x.id NOT IN (
    SELECT DISTINCT ON (provider) id
    FROM kg_api.ai_extraction_config
    ORDER BY provider, active DESC, id DESC
);

ALTER TABLE kg_api.ai_extraction_config
    ADD CONSTRAINT ai_extraction_config_provider_key UNIQUE (provider);

-- ===========================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (62, 'per_provider_config')
ON CONFLICT (version) DO NOTHING;
