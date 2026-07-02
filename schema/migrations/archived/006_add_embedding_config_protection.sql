-- Migration: 006_add_embedding_config_protection
-- Description: Add delete and change protection flags to embedding configurations
-- ADR: ADR-039 (Local Embedding Service)
-- Date: 2025-10-22
--
-- Rationale:
-- Changing embedding dimensions breaks vector search across the entire system.
-- Example: Switching from 1536D (OpenAI) to 768D (nomic-embed) makes all
-- existing embeddings incompatible, causing vector search failures.
--
-- Protection flags prevent accidental breaking changes:
-- - delete_protected: Prevents deletion of default configs
-- - change_protected: Requires explicit unlock before provider/dimension changes

BEGIN;

-- ============================================================================
-- Add Protection Columns
-- ============================================================================

-- Add delete_protected flag (prevents accidental deletion)
ALTER TABLE kg_api.embedding_config
ADD COLUMN IF NOT EXISTS delete_protected BOOLEAN DEFAULT FALSE;

-- Add change_protected flag (prevents changing provider/dimensions)
ALTER TABLE kg_api.embedding_config
ADD COLUMN IF NOT EXISTS change_protected BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN kg_api.embedding_config.delete_protected IS 'Prevents deletion without first removing protection (default configs)';
COMMENT ON COLUMN kg_api.embedding_config.change_protected IS 'Prevents changing provider/dimensions without explicit unlock (safety)';

-- ============================================================================
-- Enable Protection on Default Configs
-- ============================================================================

-- Protect the default OpenAI config (seeded in migration 003)
UPDATE kg_api.embedding_config
SET
    delete_protected = TRUE,
    change_protected = TRUE
WHERE provider = 'openai'
  AND model_name = 'text-embedding-3-small'
  AND updated_by = 'system';

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (6, 'add_embedding_config_protection')
ON CONFLICT (version) DO NOTHING;

COMMIT;
