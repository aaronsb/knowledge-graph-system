-- Migration 026: Add epistemic re-measurement scheduled job
-- ADR-065 Phase 2: Automatic epistemic status re-measurement when vocabulary changes exceed threshold
-- Date: 2025-11-17
--
-- This migration adds the scheduled job configuration for EpistemicRemeasurementLauncher.
-- The job checks vocabulary_change_counter delta every hour and triggers re-measurement
-- when delta >= threshold (default: 10 changes).

-- ============================================================================
-- Add Epistemic Re-measurement Scheduled Job
-- ============================================================================

-- Insert epistemic re-measurement scheduled job (if not already present)
INSERT INTO kg_api.scheduled_jobs (name, launcher_class, schedule_cron, enabled)
VALUES (
    'epistemic_remeasurement',
    'EpistemicRemeasurementLauncher',
    '0 * * * *',  -- Every hour at minute 0
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
        WHERE name = 'epistemic_remeasurement'
    ) THEN
        RAISE EXCEPTION 'Migration failed: epistemic_remeasurement scheduled job not created';
    END IF;

    RAISE NOTICE 'Migration 026: Epistemic re-measurement scheduled job added successfully';
END $$;

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (26, 'epistemic_remeasurement_job')
ON CONFLICT (version) DO NOTHING;
