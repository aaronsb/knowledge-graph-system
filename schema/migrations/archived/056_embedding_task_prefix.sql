-- Migration: 056_embedding_task_prefix
-- Description: Add task prefix columns to embedding_profile for purpose-aware embedding
-- Date: 2026-02-10
--
-- Rationale:
-- Nomic v1.5 (and other models) support task prefixes like search_query: and
-- search_document: that improve embedding quality by signaling intent. Our pipeline
-- currently sends all text bare. These columns let profiles declare their prefixes
-- so the embedding manager can apply them automatically based on purpose (query vs document).

-- ============================================================================
-- DDL: add prefix columns (idempotent via IF NOT EXISTS)
-- ============================================================================

ALTER TABLE kg_api.embedding_profile ADD COLUMN IF NOT EXISTS
    text_query_prefix VARCHAR(200);

ALTER TABLE kg_api.embedding_profile ADD COLUMN IF NOT EXISTS
    text_document_prefix VARCHAR(200);

COMMENT ON COLUMN kg_api.embedding_profile.text_query_prefix IS 'Prefix prepended for search queries (e.g. search_query: )';
COMMENT ON COLUMN kg_api.embedding_profile.text_document_prefix IS 'Prefix prepended for stored documents (e.g. search_document: )';

-- ============================================================================
-- DML: set prefixes on existing profiles (guarded by schema_migrations)
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.schema_migrations WHERE version = 56) THEN
        RAISE NOTICE 'Migration 056 already applied, skipping';
        RETURN;
    END IF;

    -- Set Nomic v1.5 prefixes (these are optional for v1.5 but improve quality)
    UPDATE kg_api.embedding_profile
    SET text_query_prefix = 'search_query: ',
        text_document_prefix = 'search_document: ',
        updated_by = 'migration-056'
    WHERE vector_space = 'nomic-v1.5';

    RAISE NOTICE 'Migration 056: task prefixes set on Nomic v1.5 profile';
END $$;

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (56, 'embedding_task_prefix')
ON CONFLICT (version) DO NOTHING;
