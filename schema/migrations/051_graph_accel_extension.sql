-- ============================================================================
-- Migration 051: Create graph_accel extension (if available)
-- ============================================================================
-- The graph_accel extension provides in-memory graph traversal acceleration
-- for Apache AGE (ADR-201). It is optional — the API's GraphFacade detects
-- availability and falls back to Cypher queries when absent.
--
-- The extension's bootstrap SQL (via pgrx extension_sql!) automatically
-- creates the graph_accel.generation table for cache invalidation.
-- No separate table creation is needed here.
--
-- Safe on stock apache/age images: checks pg_available_extensions first.
-- ============================================================================

BEGIN;

DO $$
BEGIN
    -- Skip if already applied
    IF EXISTS (SELECT 1 FROM public.schema_migrations WHERE version = 51) THEN
        RAISE NOTICE 'Migration 051 already applied, skipping';
        RETURN;
    END IF;

    -- Only create extension if the .so file is installed
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'graph_accel') THEN
        CREATE EXTENSION IF NOT EXISTS graph_accel;
        RAISE NOTICE 'Migration 051: graph_accel extension created';
    ELSE
        RAISE NOTICE 'Migration 051: graph_accel not available — skipping (extension is optional)';
    END IF;
END $$;

INSERT INTO public.schema_migrations (version, name)
VALUES (51, 'graph_accel_extension')
ON CONFLICT (version) DO NOTHING;

COMMIT;
