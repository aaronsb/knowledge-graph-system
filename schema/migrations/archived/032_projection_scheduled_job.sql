-- Migration 032: Add projection refresh scheduled job
-- ADR-078: Embedding Landscape Explorer - scheduled projection refresh
-- Date: 2025-12-12
--
-- This migration adds the scheduled job configuration for ProjectionLauncher.
-- The job checks concept_change_counter delta every hour and triggers projection
-- refresh when delta >= threshold (default: 10 new concepts per ontology).
-- Projection computation is fast (~1s for 400 concepts) so this is low-impact.

-- ============================================================================
-- Add Projection Refresh Scheduled Job
-- ============================================================================

-- Insert projection refresh scheduled job (if not already present)
INSERT INTO kg_api.scheduled_jobs (name, launcher_class, schedule_cron, enabled)
VALUES (
    'projection_refresh',
    'ProjectionLauncher',
    '15 * * * *',  -- Every hour at minute 15 (offset from other jobs)
    TRUE
)
ON CONFLICT (name) DO UPDATE SET
    launcher_class = EXCLUDED.launcher_class,
    schedule_cron = EXCLUDED.schedule_cron,
    enabled = EXCLUDED.enabled;

-- ============================================================================
-- Migration Complete
-- ============================================================================

-- Verify scheduled job was created
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM kg_api.scheduled_jobs
        WHERE name = 'projection_refresh'
    ) THEN
        RAISE EXCEPTION 'Migration failed: projection_refresh scheduled job not created';
    END IF;

    RAISE NOTICE 'Migration 032: Projection refresh scheduled job added successfully';
END $$;

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (32, 'projection_scheduled_job')
ON CONFLICT (version) DO NOTHING;
