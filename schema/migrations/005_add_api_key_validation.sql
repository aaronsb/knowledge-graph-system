-- Migration: 005_add_api_key_validation
-- Description: Add validation state tracking to system API keys
-- ADR: ADR-041 (AI Extraction Provider Configuration)
-- Date: 2025-10-21

BEGIN;

-- ============================================================================
-- Add Validation Fields to system_api_keys
-- ============================================================================

-- Add validation status field
ALTER TABLE kg_api.system_api_keys
ADD COLUMN IF NOT EXISTS validation_status VARCHAR(20) DEFAULT 'untested'
    CHECK (validation_status IN ('valid', 'invalid', 'untested'));

-- Add validation timestamp field
ALTER TABLE kg_api.system_api_keys
ADD COLUMN IF NOT EXISTS last_validated_at TIMESTAMPTZ;

-- Add validation error field
ALTER TABLE kg_api.system_api_keys
ADD COLUMN IF NOT EXISTS validation_error TEXT;

-- Add comments for new columns
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
