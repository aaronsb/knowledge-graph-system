-- Migration 047: Breathing cycle infrastructure
-- ADR-200 Phase 3b: Scheduled breathing cycle + configuration options
-- Date: 2026-01-30
--
-- Three additions:
-- 1. breathing_options: key-value config for tunable breathing parameters
-- 2. last_breathing_epoch: graph_metrics counter for epoch gating
-- 3. scheduled_jobs row: cron entry for periodic breathing checks

-- ============================================================================
-- Part 1: Breathing Options (database-driven configuration)
-- ============================================================================

CREATE TABLE IF NOT EXISTS kg_api.breathing_options (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE kg_api.breathing_options IS
    'Tunable parameters for ontology breathing cycles (ADR-200 Phase 3b). '
    'Code defaults apply when a key is absent; database values override.';

-- Seed defaults
INSERT INTO kg_api.breathing_options (key, value, description) VALUES
    ('epoch_interval',        '5',    'Minimum epoch delta before a breathing cycle can trigger'),
    ('demotion_threshold',    '0.15', 'Protection score below which an ontology is a demotion candidate'),
    ('promotion_min_degree',  '10',   'Concept degree above which a concept is a promotion candidate'),
    ('max_proposals',         '5',    'Maximum proposals generated per breathing cycle'),
    ('enabled',               'true', 'Master switch — set to false to disable all breathing')
ON CONFLICT (key) DO NOTHING;

-- ============================================================================
-- Part 2: Epoch counter in graph_metrics
-- ============================================================================

-- Track when breathing last ran (same table as all other epoch/change counters)
INSERT INTO public.graph_metrics (metric_name, counter, last_measured_counter, notes)
VALUES ('last_breathing_epoch', 0, 0, 'Epoch when ontology breathing cycle last executed')
ON CONFLICT (metric_name) DO NOTHING;

-- ============================================================================
-- Part 3: Scheduled Job
-- ============================================================================

INSERT INTO kg_api.scheduled_jobs (name, launcher_class, schedule_cron, enabled)
VALUES (
    'ontology_breathing',
    'BreathingLauncher',
    '30 */6 * * *',  -- Every 6 hours at minute 30 (offset from category_refresh at :00)
    TRUE
)
ON CONFLICT (name) DO UPDATE SET
    launcher_class = EXCLUDED.launcher_class,
    schedule_cron = EXCLUDED.schedule_cron,
    enabled = EXCLUDED.enabled;

-- ============================================================================
-- Verification
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM kg_api.breathing_options WHERE key = 'epoch_interval'
    ) THEN
        RAISE EXCEPTION 'Migration failed: breathing_options not seeded';
    END IF;

    IF NOT EXISTS (
        SELECT FROM public.graph_metrics WHERE metric_name = 'last_breathing_epoch'
    ) THEN
        RAISE EXCEPTION 'Migration failed: last_breathing_epoch counter not created';
    END IF;

    IF NOT EXISTS (
        SELECT FROM kg_api.scheduled_jobs WHERE name = 'ontology_breathing'
    ) THEN
        RAISE EXCEPTION 'Migration failed: ontology_breathing scheduled job not created';
    END IF;

    RAISE NOTICE 'Migration 047: Breathing cycle infrastructure installed successfully';
END $$;

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (47, 'breathing_scheduled_job')
ON CONFLICT (version) DO NOTHING;
