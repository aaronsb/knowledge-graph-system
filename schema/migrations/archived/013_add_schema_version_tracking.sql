-- Migration 013: Add Schema Version Tracking
-- Date: 2025-10-26
-- Description: Adds schema_migrations table to track applied migrations
--              for backup/restore compatibility (ADR-015)

-- Create schema_migrations table to track database schema evolution
CREATE TABLE IF NOT EXISTS kg_api.schema_migrations (
    version INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Insert historical migrations (retroactive tracking)
INSERT INTO kg_api.schema_migrations (version, description, applied_at) VALUES
    (1, 'Initial schema (graph, sources, instances)', '2025-10-01'::timestamp),
    (2, 'Add relationship vocabulary table', '2025-10-05'::timestamp),
    (3, 'Add embedding configuration', '2025-10-08'::timestamp),
    (4, 'Add job queue tables', '2025-10-10'::timestamp),
    (5, 'Add permissions and RBAC', '2025-10-12'::timestamp),
    (6, 'Add API keys and authentication', '2025-10-14'::timestamp),
    (7, 'Add encrypted keys storage', '2025-10-16'::timestamp),
    (8, 'Add backup integrity tracking', '2025-10-18'::timestamp),
    (9, 'Add synonym detection', '2025-10-20'::timestamp),
    (10, 'Add aggressiveness curve configuration', '2025-10-22'::timestamp),
    (11, 'Add grounding metrics (ADR-044)', '2025-10-24'::timestamp),
    (12, 'Add embedding worker support (ADR-045)', '2025-10-25'::timestamp),
    (13, 'Add schema version tracking (ADR-015)', '2025-10-26'::timestamp)
ON CONFLICT (version) DO NOTHING;

-- Comment on table
COMMENT ON TABLE kg_api.schema_migrations IS
'Tracks applied database migrations for backup/restore compatibility.
Schema version is included in backups to ensure restore compatibility
when database schema evolves. See ADR-015 for details.';

-- Comment on columns
COMMENT ON COLUMN kg_api.schema_migrations.version IS
'Migration number matching schema/migrations/NNN_*.sql files';

COMMENT ON COLUMN kg_api.schema_migrations.description IS
'Human-readable description of what this migration does';

COMMENT ON COLUMN kg_api.schema_migrations.applied_at IS
'When this migration was applied to the database';

-- ============================================================================
-- Record Migration in public.schema_migrations
-- ============================================================================
-- Note: This migration creates kg_api.schema_migrations (for backup/restore)
-- but must also record itself in public.schema_migrations (for migration tracking)

INSERT INTO public.schema_migrations (version, name)
VALUES (13, 'add_schema_version_tracking')
ON CONFLICT (version) DO NOTHING;
