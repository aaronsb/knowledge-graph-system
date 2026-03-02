-- Migration 057: Worker lanes and database-driven job dispatch (ADR-100)
--
-- Replaces in-memory thread dispatch with a database-driven poll-and-claim model.
-- Workers poll PostgreSQL for claimable work using atomic UPDATE...RETURNING
-- instead of being pushed work by in-memory submission.
--
-- Adds:
--   1. kg_api.worker_lanes table with default lane configuration
--   2. priority, claimed_by, claimed_at, cancelled columns on kg_api.jobs
--   3. retries/max_retries columns for stale job recovery
--   4. Composite index for the claim query
--   5. jobs:manage and jobs:view RBAC permissions

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.schema_migrations WHERE version = 57) THEN
        RAISE NOTICE 'Migration 057 already applied, skipping';
        RETURN;
    END IF;

    -- =========================================================================
    -- 1. Worker lanes table
    -- =========================================================================

    CREATE TABLE IF NOT EXISTS kg_api.worker_lanes (
        name         TEXT PRIMARY KEY,
        job_types    TEXT[] NOT NULL,
        max_slots    INTEGER NOT NULL DEFAULT 1,
        poll_interval_ms INTEGER NOT NULL DEFAULT 5000,
        stale_timeout_minutes INTEGER NOT NULL DEFAULT 30,
        enabled      BOOLEAN NOT NULL DEFAULT TRUE,
        updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    COMMENT ON TABLE kg_api.worker_lanes IS 'Worker lane configuration for database-driven job dispatch (ADR-100)';

    -- Seed default lanes
    INSERT INTO kg_api.worker_lanes (name, job_types, max_slots, poll_interval_ms, stale_timeout_minutes)
    VALUES
        ('interactive',
         ARRAY['ingestion', 'ingest_image', 'polarity'],
         2, 2000, 30),
        ('maintenance',
         ARRAY['projection', 'vocab_refresh', 'epistemic_remeasurement', 'ontology_annealing', 'proposal_execution'],
         1, 15000, 60),
        ('system',
         ARRAY['restore', 'vocab_consolidate', 'artifact_cleanup', 'source_embedding'],
         1, 30000, 120)
    ON CONFLICT (name) DO NOTHING;

    -- =========================================================================
    -- 2. Job dispatch columns
    -- =========================================================================

    -- Priority: higher = more urgent, default 0
    ALTER TABLE kg_api.jobs ADD COLUMN IF NOT EXISTS priority INTEGER NOT NULL DEFAULT 0;

    -- Claim tracking: which worker claimed this job and when
    ALTER TABLE kg_api.jobs ADD COLUMN IF NOT EXISTS claimed_by TEXT;
    ALTER TABLE kg_api.jobs ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ;

    -- Cancellation flag: workers check this at yield points
    ALTER TABLE kg_api.jobs ADD COLUMN IF NOT EXISTS cancelled BOOLEAN NOT NULL DEFAULT FALSE;

    -- Retry tracking for stale job recovery
    ALTER TABLE kg_api.jobs ADD COLUMN IF NOT EXISTS retries INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE kg_api.jobs ADD COLUMN IF NOT EXISTS max_retries INTEGER NOT NULL DEFAULT 3;

    -- =========================================================================
    -- 3. Indexes for claim query performance
    -- =========================================================================

    -- Primary claim index: supports the poll-and-claim UPDATE...RETURNING query
    -- ORDER BY priority DESC, created_at ASC
    CREATE INDEX IF NOT EXISTS idx_jobs_claim
        ON kg_api.jobs (status, priority DESC, created_at ASC)
        WHERE status = 'approved';

    -- Stale job recovery: find running jobs past their timeout
    CREATE INDEX IF NOT EXISTS idx_jobs_stale_recovery
        ON kg_api.jobs (claimed_at)
        WHERE status = 'running' AND claimed_at IS NOT NULL;

    -- =========================================================================
    -- 4. RBAC permissions
    -- =========================================================================

    -- Register 'workers' resource type
    INSERT INTO kg_auth.resources (resource_type, description, available_actions, supports_scoping)
    SELECT 'workers', 'Worker lane management and job control (ADR-100)',
           ARRAY['view', 'manage'], FALSE
    WHERE NOT EXISTS (
        SELECT 1 FROM kg_auth.resources WHERE resource_type = 'workers'
    );

    -- Grant workers:view to platform_admin
    INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
    SELECT 'platform_admin', 'workers', 'view', 'global', TRUE
    WHERE NOT EXISTS (
        SELECT 1 FROM kg_auth.role_permissions
        WHERE role_name = 'platform_admin' AND resource_type = 'workers' AND action = 'view'
    );

    -- Grant workers:manage to platform_admin
    INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
    SELECT 'platform_admin', 'workers', 'manage', 'global', TRUE
    WHERE NOT EXISTS (
        SELECT 1 FROM kg_auth.role_permissions
        WHERE role_name = 'platform_admin' AND resource_type = 'workers' AND action = 'manage'
    );

    -- Also grant to admin role for convenience
    INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
    SELECT 'admin', 'workers', 'view', 'global', TRUE
    WHERE NOT EXISTS (
        SELECT 1 FROM kg_auth.role_permissions
        WHERE role_name = 'admin' AND resource_type = 'workers' AND action = 'view'
    );

    INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
    SELECT 'admin', 'workers', 'manage', 'global', TRUE
    WHERE NOT EXISTS (
        SELECT 1 FROM kg_auth.role_permissions
        WHERE role_name = 'admin' AND resource_type = 'workers' AND action = 'manage'
    );

    RAISE NOTICE 'Migration 057: Worker lanes and job dispatch columns added (ADR-100)';
END $$;

-- ===========================================================================
-- Record Migration
-- ===========================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (57, 'worker_lanes_and_job_dispatch')
ON CONFLICT (version) DO NOTHING;
