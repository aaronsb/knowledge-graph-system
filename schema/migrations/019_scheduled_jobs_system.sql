-- Migration 019: Scheduled Jobs System
-- ADR-050: Add scheduled jobs configuration and job ownership tracking
-- Date: 2025-10-28

-- ============================================================================
-- Part 1: Migrate Jobs Table from SQLite to PostgreSQL
-- ============================================================================

-- Create jobs table in PostgreSQL (replacing SQLite implementation)
-- This consolidates all job tracking into PostgreSQL for unified access
CREATE TABLE IF NOT EXISTS kg_api.jobs (
    job_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    content_hash TEXT,
    ontology TEXT,
    client_id TEXT,
    status TEXT NOT NULL,
    progress TEXT,
    result TEXT,
    error TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    job_data JSONB NOT NULL,

    -- ADR-014: Approval workflow fields
    analysis TEXT,
    approved_at TIMESTAMP,
    approved_by TEXT,
    expires_at TIMESTAMP,
    processing_mode TEXT DEFAULT 'serial',

    -- ADR-050: Job ownership and source tracking
    job_source VARCHAR(50) DEFAULT 'user_cli',
    created_by VARCHAR(100) DEFAULT 'unknown',
    is_system_job BOOLEAN DEFAULT FALSE
);

-- Create indexes for job queries
CREATE INDEX IF NOT EXISTS idx_jobs_content_hash
ON kg_api.jobs(content_hash, ontology, status);

CREATE INDEX IF NOT EXISTS idx_jobs_status
ON kg_api.jobs(status);

CREATE INDEX IF NOT EXISTS idx_jobs_ownership
ON kg_api.jobs(created_by, is_system_job);

CREATE INDEX IF NOT EXISTS idx_jobs_created_at
ON kg_api.jobs(created_at DESC);

-- Add comments documenting the table and columns
COMMENT ON TABLE kg_api.jobs IS 'Unified job queue for all background tasks (ingestion, backup, vocab, scheduled)';
COMMENT ON COLUMN kg_api.jobs.job_id IS 'Unique job identifier (UUID)';
COMMENT ON COLUMN kg_api.jobs.job_type IS 'Type of job: ingestion, restore, backup, vocab_refresh, vocab_consolidate';
COMMENT ON COLUMN kg_api.jobs.content_hash IS 'SHA256 hash for deduplication (used with ontology to detect duplicates)';
COMMENT ON COLUMN kg_api.jobs.ontology IS 'Target ontology for the job';
COMMENT ON COLUMN kg_api.jobs.client_id IS 'Client identifier for SSE streaming';
COMMENT ON COLUMN kg_api.jobs.status IS 'Job status: pending_approval, approved, running, completed, failed, cancelled';
COMMENT ON COLUMN kg_api.jobs.progress IS 'Progress message for UI display';
COMMENT ON COLUMN kg_api.jobs.result IS 'Final result data (JSON)';
COMMENT ON COLUMN kg_api.jobs.error IS 'Error message if failed';
COMMENT ON COLUMN kg_api.jobs.job_data IS 'Job-specific parameters (JSON)';
COMMENT ON COLUMN kg_api.jobs.analysis IS 'Pre-approval analysis (cost/time estimates)';
COMMENT ON COLUMN kg_api.jobs.approved_at IS 'When job was approved by user';
COMMENT ON COLUMN kg_api.jobs.approved_by IS 'Who approved the job';
COMMENT ON COLUMN kg_api.jobs.expires_at IS 'When pending approval expires';
COMMENT ON COLUMN kg_api.jobs.processing_mode IS 'Execution mode: serial or parallel';
COMMENT ON COLUMN kg_api.jobs.job_source IS 'Source of job creation: user_cli, user_api, scheduled_task, system';
COMMENT ON COLUMN kg_api.jobs.created_by IS 'User or system identifier that created the job';
COMMENT ON COLUMN kg_api.jobs.is_system_job IS 'True for system-scheduled jobs (cannot be deleted by users)';

-- ============================================================================
-- Part 2: Scheduled Jobs Configuration
-- ============================================================================

-- Create scheduled_jobs table for cron-based job scheduling
CREATE TABLE IF NOT EXISTS kg_api.scheduled_jobs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    launcher_class VARCHAR(255) NOT NULL,
    schedule_cron VARCHAR(100) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    max_retries INTEGER DEFAULT 5,
    retry_count INTEGER DEFAULT 0,
    last_run TIMESTAMP,
    last_success TIMESTAMP,
    last_failure TIMESTAMP,
    next_run TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Add comments documenting the table
COMMENT ON TABLE kg_api.scheduled_jobs IS 'Configuration for scheduled background jobs (ADR-050)';
COMMENT ON COLUMN kg_api.scheduled_jobs.name IS 'Unique identifier for the scheduled job';
COMMENT ON COLUMN kg_api.scheduled_jobs.launcher_class IS 'Python class name in launcher registry (e.g., CategoryRefreshLauncher)';
COMMENT ON COLUMN kg_api.scheduled_jobs.schedule_cron IS 'Cron expression for schedule (e.g., "0 */6 * * *" = every 6 hours)';
COMMENT ON COLUMN kg_api.scheduled_jobs.enabled IS 'Whether this schedule is active (can be disabled on failure)';
COMMENT ON COLUMN kg_api.scheduled_jobs.max_retries IS 'Max consecutive failures before auto-disabling schedule';
COMMENT ON COLUMN kg_api.scheduled_jobs.retry_count IS 'Current consecutive failure count (reset on success or skip)';
COMMENT ON COLUMN kg_api.scheduled_jobs.last_run IS 'Last time the schedule was checked (success, skip, or failure)';
COMMENT ON COLUMN kg_api.scheduled_jobs.last_success IS 'Last time a job was successfully enqueued';
COMMENT ON COLUMN kg_api.scheduled_jobs.last_failure IS 'Last time the launcher failed with an exception';
COMMENT ON COLUMN kg_api.scheduled_jobs.next_run IS 'Calculated next run time (from cron expression or backoff)';

-- Create indexes for scheduler queries
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_next_run
ON kg_api.scheduled_jobs(next_run)
WHERE enabled = TRUE;

CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_enabled
ON kg_api.scheduled_jobs(enabled);

-- ============================================================================
-- Part 3: Migrate Data from Legacy Table
-- ============================================================================

-- Migrate existing jobs from kg_api.ingestion_jobs (if it exists)
DO $$
BEGIN
    IF EXISTS (
        SELECT FROM pg_tables
        WHERE schemaname = 'kg_api' AND tablename = 'ingestion_jobs'
    ) THEN
        -- Copy data from old table to new table
        INSERT INTO kg_api.jobs (
            job_id, job_type, content_hash, ontology, client_id,
            status, progress, result, error, created_at, started_at,
            completed_at, job_data, analysis, approved_at, approved_by,
            expires_at, processing_mode, job_source, created_by, is_system_job
        )
        SELECT
            job_id, job_type, content_hash, ontology, client_id,
            status, progress, result, error_message, created_at, started_at,
            completed_at, job_data, analysis, approved_at, approved_by,
            expires_at, processing_mode,
            'user_cli', -- default job_source
            'unknown', -- default created_by
            FALSE -- not a system job
        FROM kg_api.ingestion_jobs
        ON CONFLICT (job_id) DO NOTHING;

        -- Drop old table
        DROP TABLE kg_api.ingestion_jobs;

        RAISE NOTICE 'Migrated data from kg_api.ingestion_jobs to kg_api.jobs';
    END IF;
END $$;

-- ============================================================================
-- Part 4: Initial Scheduled Jobs
-- ============================================================================

-- Insert default scheduled jobs (if not already present)
INSERT INTO kg_api.scheduled_jobs (name, launcher_class, schedule_cron, enabled)
VALUES
    ('category_refresh', 'CategoryRefreshLauncher', '0 */6 * * *', TRUE),
    ('vocab_consolidation', 'VocabConsolidationLauncher', '0 */12 * * *', TRUE)
ON CONFLICT (name) DO NOTHING;

-- Add comments describing each scheduled job
COMMENT ON TABLE kg_api.scheduled_jobs IS E'Scheduled background jobs:\n'
    '- category_refresh: Re-integrate LLM-generated vocabulary categories (every 6 hours)\n'
    '- vocab_consolidation: Auto-consolidate vocabulary based on hysteresis thresholds (every 12 hours)';

-- ============================================================================
-- Part 5: Launcher Configuration (Optional - for GenericJobLauncher)
-- ============================================================================

-- Optional table for generic launcher configuration (future enhancement)
-- Not created by default - only needed if using GenericJobLauncher
--
-- CREATE TABLE IF NOT EXISTS kg_api.launcher_config (
--     id SERIAL PRIMARY KEY,
--     schedule_name VARCHAR(100) REFERENCES kg_api.scheduled_jobs(name) ON DELETE CASCADE,
--     job_type VARCHAR(100) NOT NULL,
--     job_data_template JSONB NOT NULL,
--     condition_sql TEXT,
--     created_at TIMESTAMP DEFAULT NOW(),
--     UNIQUE(schedule_name)
-- );

-- ============================================================================
-- Migration Complete
-- ============================================================================

-- Verify tables exist
DO $$
BEGIN
    -- Check scheduled_jobs table
    IF NOT EXISTS (
        SELECT FROM pg_tables
        WHERE schemaname = 'kg_api' AND tablename = 'scheduled_jobs'
    ) THEN
        RAISE EXCEPTION 'Migration failed: kg_api.scheduled_jobs table not created';
    END IF;

    -- Check job ownership columns
    IF NOT EXISTS (
        SELECT FROM information_schema.columns
        WHERE table_schema = 'kg_api'
        AND table_name = 'jobs'
        AND column_name = 'is_system_job'
    ) THEN
        RAISE EXCEPTION 'Migration failed: kg_api.jobs.is_system_job column not created';
    END IF;

    RAISE NOTICE 'Migration 019: Scheduled jobs system installed successfully';
END $$;
