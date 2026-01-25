-- Migration 039: Add metadata column to query_definitions
--
-- Adds a JSONB metadata column to store additional info like:
-- - nodeCount/edgeCount for block diagrams
-- - description
-- - other user-defined metadata
--
-- Idempotent: Safe to run multiple times.

BEGIN;

-- Add metadata column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'kg_api'
          AND table_name = 'query_definitions'
          AND column_name = 'metadata'
    ) THEN
        ALTER TABLE kg_api.query_definitions
        ADD COLUMN metadata JSONB DEFAULT '{}';
    END IF;
END $$;

COMMENT ON COLUMN kg_api.query_definitions.metadata IS 'Optional metadata (nodeCount, edgeCount, description, etc.)';

-- Record migration (idempotent)
INSERT INTO public.schema_migrations (version, name)
VALUES (39, 'query_definition_metadata')
ON CONFLICT (version) DO NOTHING;

COMMIT;
