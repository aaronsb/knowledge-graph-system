-- Migration 070: Schedule the VocabEmbeddingLauncher
-- Companion to migration 069 (vocab embedding lifecycle counters).
-- Date: 2026-05-26
--
-- ## What this adds
--
-- The hourly scheduled job that fires VocabEmbeddingLauncher. The launcher
-- checks vocabulary_change_counter against last_processed_vocab_change_counter
-- for the 'builtin_vocabulary_embeddings' component and, when the membership
-- counter has advanced, enqueues a vocab_embedding worker job to regenerate
-- any missing embeddings.
--
-- Pattern-matches migration 026 (epistemic_remeasurement scheduled job) —
-- same shape, same cron cadence (hourly at minute 0). The two launchers
-- run independently: epistemic uses get_counter_delta() / mark_measurement_complete()
-- (global cursor on graph_metrics), this one uses last_processed_vocab_change_counter
-- (per-component cursor on system_initialization_status). The two consumers
-- track their progress separately and don't interfere.
--
-- ## Idempotency
--
-- ON CONFLICT (name) DO UPDATE — re-running this migration refreshes the
-- launcher_class / schedule_cron / enabled fields without erroring on the
-- existing row, matching the pattern in 026 / 047 / 048.

BEGIN;

-- ----------------------------------------------------------------------------
-- Schedule vocab embedding launcher
-- ----------------------------------------------------------------------------

INSERT INTO kg_api.scheduled_jobs (name, launcher_class, schedule_cron, enabled)
VALUES (
    'vocab_embedding',
    'VocabEmbeddingLauncher',
    '0 * * * *',  -- Every hour at minute 0 (same cadence as epistemic_remeasurement)
    TRUE
)
ON CONFLICT (name) DO UPDATE SET
    launcher_class = EXCLUDED.launcher_class,
    schedule_cron = EXCLUDED.schedule_cron,
    enabled = EXCLUDED.enabled;

-- ----------------------------------------------------------------------------
-- Verify
-- ----------------------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM kg_api.scheduled_jobs
        WHERE name = 'vocab_embedding'
          AND launcher_class = 'VocabEmbeddingLauncher'
    ) THEN
        RAISE EXCEPTION 'Migration 070 failed: vocab_embedding scheduled job not registered';
    END IF;

    RAISE NOTICE 'Migration 070: vocab_embedding scheduled job registered';
END $$;

-- ----------------------------------------------------------------------------
-- Migration tracking
-- ----------------------------------------------------------------------------

INSERT INTO public.schema_migrations (version, name)
VALUES (70, 'vocab_embedding_scheduled_job')
ON CONFLICT (version) DO NOTHING;

COMMIT;
