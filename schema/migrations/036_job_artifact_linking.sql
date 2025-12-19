-- Migration 036: Job Artifact Linking (ADR-083 Phase 4)
--
-- Links jobs to artifacts they produce, enabling:
-- - Tracking which job created an artifact
-- - Automatic artifact creation on job completion
-- - Job-based artifact regeneration
--
-- Changes:
-- 1. Add artifact_id column to jobs table
-- 2. Add index for artifact lookups

BEGIN;

-- ============================================================================
-- Add artifact_id to jobs table
-- ============================================================================

ALTER TABLE kg_api.jobs
    ADD COLUMN artifact_id INTEGER REFERENCES kg_api.artifacts(id) ON DELETE SET NULL;

-- Index for looking up jobs by artifact
CREATE INDEX IF NOT EXISTS idx_jobs_artifact_id
    ON kg_api.jobs(artifact_id)
    WHERE artifact_id IS NOT NULL;

-- Documentation
COMMENT ON COLUMN kg_api.jobs.artifact_id IS 'Artifact created by this job (ADR-083). NULL for jobs that do not produce artifacts.';

-- ============================================================================
-- Helper: Link job to artifact
-- ============================================================================

CREATE OR REPLACE FUNCTION kg_api.link_job_to_artifact(
    p_job_id TEXT,
    p_artifact_id INTEGER
) RETURNS VOID AS $$
BEGIN
    UPDATE kg_api.jobs
    SET artifact_id = p_artifact_id
    WHERE job_id = p_job_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION kg_api.link_job_to_artifact IS 'Link a job to its created artifact (ADR-083)';

-- ============================================================================
-- Artifact Cleanup Scheduled Job
-- ============================================================================

INSERT INTO kg_api.scheduled_jobs (name, launcher_class, schedule_cron, enabled)
VALUES (
    'artifact_cleanup',
    'ArtifactCleanupLauncher',
    '0 2 * * *',  -- Daily at 2 AM
    TRUE
)
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (36, 'job_artifact_linking')
ON CONFLICT (version) DO NOTHING;

COMMIT;
