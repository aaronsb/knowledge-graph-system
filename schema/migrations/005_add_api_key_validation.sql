-- Migration: 005_add_api_key_validation
-- Description: Create system_api_keys table with validation state tracking
-- ADR: ADR-031 (Encrypted API Key Storage), ADR-041 (AI Extraction Provider Configuration)
-- Date: 2025-10-21

BEGIN;

-- ============================================================================
-- Create system_api_keys Table
-- ============================================================================

-- Create table if it doesn't exist (fresh install)
-- Or add validation columns if table already exists (upgrade path)
CREATE TABLE IF NOT EXISTS kg_api.system_api_keys (
    provider VARCHAR(50) PRIMARY KEY,
    encrypted_key BYTEA NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- ADR-041: Validation state tracking
    validation_status VARCHAR(20) DEFAULT 'untested'
        CHECK (validation_status IN ('valid', 'invalid', 'untested')),
    last_validated_at TIMESTAMPTZ,
    validation_error TEXT
);

-- Create index on updated_at
CREATE INDEX IF NOT EXISTS idx_system_api_keys_updated
ON kg_api.system_api_keys(updated_at);

-- Add validation columns if table existed before this migration (upgrade path)
-- These will silently succeed if columns already exist
DO $$
BEGIN
    -- Add validation_status if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'kg_api'
          AND table_name = 'system_api_keys'
          AND column_name = 'validation_status'
    ) THEN
        ALTER TABLE kg_api.system_api_keys
        ADD COLUMN validation_status VARCHAR(20) DEFAULT 'untested'
            CHECK (validation_status IN ('valid', 'invalid', 'untested'));
    END IF;

    -- Add last_validated_at if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'kg_api'
          AND table_name = 'system_api_keys'
          AND column_name = 'last_validated_at'
    ) THEN
        ALTER TABLE kg_api.system_api_keys
        ADD COLUMN last_validated_at TIMESTAMPTZ;
    END IF;

    -- Add validation_error if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'kg_api'
          AND table_name = 'system_api_keys'
          AND column_name = 'validation_error'
    ) THEN
        ALTER TABLE kg_api.system_api_keys
        ADD COLUMN validation_error TEXT;
    END IF;
END $$;

-- Add comments
COMMENT ON TABLE kg_api.system_api_keys IS 'Encrypted system API keys for LLM providers (ADR-031, ADR-041)';
COMMENT ON COLUMN kg_api.system_api_keys.provider IS 'Provider name: openai, anthropic';
COMMENT ON COLUMN kg_api.system_api_keys.encrypted_key IS 'Fernet-encrypted API key (AES-128-CBC + HMAC-SHA256)';
COMMENT ON COLUMN kg_api.system_api_keys.updated_at IS 'Last time key was updated';
COMMENT ON COLUMN kg_api.system_api_keys.validation_status IS 'API key validation state: valid, invalid, or untested';
COMMENT ON COLUMN kg_api.system_api_keys.last_validated_at IS 'Timestamp of last validation check (typically at API startup)';
COMMENT ON COLUMN kg_api.system_api_keys.validation_error IS 'Error message from last failed validation attempt';

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (5, 'add_api_key_validation')
ON CONFLICT (version) DO NOTHING;

COMMIT;
