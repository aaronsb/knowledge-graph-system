-- Migration 074: ai_vision_config — active vision provider selection (ADR-802 / #378)
--
-- ADR-802 makes vision a first-class provider capability resolved independently
-- like embedding, under the ADR-801 uniform contract. Vision previously had no
-- persisted selection at all: the worker resolved the provider as a bare
-- hardcoded `"openai"` (ingestion_worker.py) / `VISION_PROVIDER` env default
-- (vision_providers.py), independent of what was configured or active (#378).
--
-- This table is the vision capability's active pointer, mirroring
-- ai_extraction_config's per-provider-row + single-`active`-flag pattern
-- (migration 062, ADR-801 §2). It is SELECTION-ONLY: connectivity (base_url,
-- API keys) is NOT duplicated here — it is reused from the existing
-- per-provider mechanisms (encrypted key store + env / provider config), since
-- a provider's endpoint is the same whether it serves extraction or vision.
-- The only vision-specific state is which provider/model is active and its
-- reasoning controls.
--
-- model_name defaults to '' (the not-yet-chosen sentinel): an empty model is
-- resolved from the dynamic model catalog's supports_vision rows at request
-- time (vision_providers._resolve_vision_model), exactly as extraction does.
--
-- NO seed row is inserted. With no active vision config, resolution falls to
-- the sensible default defined in ADR-802 §2 — the active EXTRACTION provider
-- when its catalog has a supports_vision model — so single-provider
-- deployments need zero vision configuration, and we do not re-introduce a
-- hardcoded provider literal in seed data.

BEGIN;

CREATE TABLE IF NOT EXISTS kg_api.ai_vision_config (
    id SERIAL PRIMARY KEY,

    -- Which provider performs image->prose. Same provider set as extraction
    -- (vllm excluded: placeholder, no connector). Connectivity is shared with
    -- that provider's existing config; this row only selects it for vision.
    provider VARCHAR(50) NOT NULL
        CHECK (provider IN ('openai', 'anthropic', 'ollama', 'openrouter', 'llamacpp')),

    -- Vision model id. '' = resolve from the catalog's supports_vision rows.
    model_name VARCHAR(200) NOT NULL DEFAULT '',

    -- Reasoning controls (ADR-801 surface 3), optional, applied to describe_image.
    max_tokens INTEGER,
    temperature DOUBLE PRECISION
        CHECK (temperature IS NULL OR (temperature >= 0.0 AND temperature <= 1.0)),

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),

    -- The single live vision provider (ADR-801 §2: active pointer decoupled
    -- from provider identity). Per-provider rows persist independently; only
    -- one is active at a time (enforced by the partial unique index below).
    active BOOLEAN DEFAULT TRUE,

    CONSTRAINT ai_vision_config_provider_key UNIQUE (provider)
);

-- Only one active vision config at a time (PostgreSQL partial unique index;
-- same construct as ai_extraction_config's active guard).
CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_vision_config_unique_active
ON kg_api.ai_vision_config(active) WHERE active = TRUE;

COMMENT ON TABLE kg_api.ai_vision_config IS 'Active vision (image->prose) provider selection — ADR-802 / #378. Selection-only; connectivity reused from per-provider config.';
COMMENT ON COLUMN kg_api.ai_vision_config.provider IS 'Provider performing image->prose description';
COMMENT ON COLUMN kg_api.ai_vision_config.model_name IS 'Vision model id; '''' resolves from the catalog supports_vision rows';
COMMENT ON COLUMN kg_api.ai_vision_config.active IS 'Only one vision config active at a time (enforced by partial unique index)';

-- Reuse the same updated_at trigger function created in migration 004.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'ai_vision_config_update_timestamp'
    ) THEN
        CREATE TRIGGER ai_vision_config_update_timestamp
            BEFORE UPDATE ON kg_api.ai_vision_config
            FOR EACH ROW
            EXECUTE FUNCTION kg_api.update_ai_extraction_config_timestamp();
    END IF;
END $$;

INSERT INTO public.schema_migrations (version, name)
VALUES (74, 'ai_vision_config')
ON CONFLICT (version) DO NOTHING;

COMMIT;
