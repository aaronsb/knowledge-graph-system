-- Migration: 002_example_add_query_cache
-- Description: Example migration - adds query result caching table
-- Date: 2025-10-20
--
-- This is an EXAMPLE migration that demonstrates the migration system.
-- It adds a query_cache table for caching frequently executed queries.
--
-- To test the migration system:
--   ./scripts/migrate-db.sh --dry-run  (preview)
--   ./scripts/migrate-db.sh -y         (apply)
--
-- To remove this example:
--   DELETE FROM public.schema_migrations WHERE version = 2;
--   DROP TABLE IF EXISTS kg_api.query_cache;

BEGIN;

-- ============================================================================
-- Example: Add Query Cache Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS kg_api.query_cache (
    query_hash VARCHAR(64) PRIMARY KEY,
    query_text TEXT NOT NULL,
    result JSONB NOT NULL,
    hit_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

-- Index for expiration cleanup
CREATE INDEX IF NOT EXISTS idx_query_cache_expires
ON kg_api.query_cache(expires_at);

-- Index for access tracking
CREATE INDEX IF NOT EXISTS idx_query_cache_last_accessed
ON kg_api.query_cache(last_accessed_at DESC);

-- Table comment
COMMENT ON TABLE kg_api.query_cache IS 'Cache for frequently executed queries (EXAMPLE - ADR-040 demonstration)';
COMMENT ON COLUMN kg_api.query_cache.query_hash IS 'SHA256 hash of normalized query text';
COMMENT ON COLUMN kg_api.query_cache.hit_count IS 'Number of times this cached result was used';
COMMENT ON COLUMN kg_api.query_cache.expires_at IS 'When this cache entry should be invalidated';

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (2, 'example_add_query_cache')
ON CONFLICT (version) DO NOTHING;

COMMIT;
