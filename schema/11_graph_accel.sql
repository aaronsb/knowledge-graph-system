-- ============================================================================
-- graph_accel Extension Initialization
-- ============================================================================
-- Conditionally creates the graph_accel extension if the shared library
-- is installed. Safe to run on stock apache/age images without the extension.
--
-- This script runs via /docker-entrypoint-initdb.d/ on first database
-- initialization only. For existing databases, see migration 051.
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'graph_accel') THEN
        CREATE EXTENSION IF NOT EXISTS graph_accel;
        RAISE NOTICE 'graph_accel extension created successfully';
    ELSE
        RAISE NOTICE 'graph_accel extension not available — skipping (optional)';
    END IF;
END $$;
