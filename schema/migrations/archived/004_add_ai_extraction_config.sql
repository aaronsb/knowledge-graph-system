-- Migration: 004_add_ai_extraction_config
-- Description: Add AI extraction provider configuration table for runtime-switchable models
-- ADR: ADR-041 (AI Extraction Provider Configuration)
-- Date: 2025-10-21

BEGIN;

-- ============================================================================
-- AI Extraction Configuration Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS kg_api.ai_extraction_config (
    id SERIAL PRIMARY KEY,

    -- Provider configuration
    provider VARCHAR(50) NOT NULL CHECK (provider IN ('openai', 'anthropic')),

    -- Model configuration
    model_name VARCHAR(200) NOT NULL,
    supports_vision BOOLEAN DEFAULT FALSE,
    supports_json_mode BOOLEAN DEFAULT TRUE,
    max_tokens INTEGER,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    active BOOLEAN DEFAULT TRUE
);

-- Partial unique index ensures only one active config at a time
-- (PostgreSQL doesn't support partial UNIQUE constraints, only partial indexes)
CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_extraction_config_unique_active
ON kg_api.ai_extraction_config(active) WHERE active = TRUE;

COMMENT ON TABLE kg_api.ai_extraction_config IS 'AI extraction provider configuration for runtime-switchable models - ADR-041';
COMMENT ON COLUMN kg_api.ai_extraction_config.provider IS 'AI provider: openai or anthropic';
COMMENT ON COLUMN kg_api.ai_extraction_config.model_name IS 'Model identifier (e.g., gpt-4o, claude-sonnet-4-20250514)';
COMMENT ON COLUMN kg_api.ai_extraction_config.supports_vision IS 'Whether the model supports vision/image inputs';
COMMENT ON COLUMN kg_api.ai_extraction_config.supports_json_mode IS 'Whether the model supports JSON mode for structured outputs';
COMMENT ON COLUMN kg_api.ai_extraction_config.max_tokens IS 'Maximum token limit for the model';
COMMENT ON COLUMN kg_api.ai_extraction_config.active IS 'Only one config can be active at a time (enforced by unique index)';

-- Trigger to update 'updated_at' timestamp
CREATE OR REPLACE FUNCTION kg_api.update_ai_extraction_config_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger only if it doesn't exist (PostgreSQL doesn't support IF NOT EXISTS for triggers)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'ai_extraction_config_update_timestamp'
    ) THEN
        CREATE TRIGGER ai_extraction_config_update_timestamp
            BEFORE UPDATE ON kg_api.ai_extraction_config
            FOR EACH ROW
            EXECUTE FUNCTION kg_api.update_ai_extraction_config_timestamp();
    END IF;
END $$;

-- ============================================================================
-- Seed Data: Default OpenAI Configuration
-- ============================================================================

-- Insert default OpenAI configuration (allows system to work out of the box)
INSERT INTO kg_api.ai_extraction_config (
    provider, model_name, supports_vision, supports_json_mode,
    max_tokens, updated_by, active
) VALUES (
    'openai', 'gpt-4o', TRUE, TRUE,
    16384, 'system', TRUE
)
ON CONFLICT (active) WHERE active = TRUE DO NOTHING;

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (4, 'add_ai_extraction_config')
ON CONFLICT (version) DO NOTHING;

COMMIT;
