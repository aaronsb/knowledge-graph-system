-- ===========================================================================
-- Migration 068: Annealing Pressure History (#249, ADR-206 §Phase 3)
-- ===========================================================================
-- Date: 2026-05-26
-- Related: ADR-206 (ADJUST_CONTROL self-regulation), ADR-200 §9 (Resolution Limit)
--
-- Persists one row per annealing cycle capturing the ecological snapshot
-- and Bezier-derived pressure score / per-control recommendations. The
-- web UI reads the most recent row for the "current state" panel and
-- (when wired) the trailing rows for a trend chart.
--
-- Retention: indefinite for now — one row per cycle is cheap. A future
-- migration can add a TTL purge if the table grows beyond useful.
-- ===========================================================================

CREATE TABLE IF NOT EXISTS kg_api.annealing_pressure_history (
    id SERIAL PRIMARY KEY,
    epoch INT NOT NULL,
    total_ontologies INT NOT NULL,
    total_concepts INT NOT NULL,
    avg_concepts_per_ontology DOUBLE PRECISION NOT NULL,
    pressure_score DOUBLE PRECISION NOT NULL CHECK (pressure_score >= 0.0 AND pressure_score <= 1.0),
    pressure_zone VARCHAR(20) NOT NULL,
    pressure_recommendation JSONB NOT NULL DEFAULT '{}'::jsonb,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE kg_api.annealing_pressure_history IS
    'One row per annealing cycle: ecological snapshot + Bezier pressure '
    'read-out (#249, ADR-206 §Phase 3). Drives the web admin "pressure" '
    'panel and the future trend chart.';

-- Time-series reads always go newest-first.
CREATE INDEX IF NOT EXISTS idx_annealing_pressure_history_recorded_at
    ON kg_api.annealing_pressure_history(recorded_at DESC);

-- Epoch-based lookups (correlate snapshots with proposal cohorts).
CREATE INDEX IF NOT EXISTS idx_annealing_pressure_history_epoch
    ON kg_api.annealing_pressure_history(epoch DESC);

-- ===========================================================================
-- Verification
-- ===========================================================================
DO $$
BEGIN
    -- Table exists with expected columns
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'kg_api'
          AND table_name = 'annealing_pressure_history'
    ) THEN
        RAISE EXCEPTION 'Migration 068 failed: annealing_pressure_history not created';
    END IF;

    -- pressure_score CHECK rejects out-of-range
    BEGIN
        INSERT INTO kg_api.annealing_pressure_history
            (epoch, total_ontologies, total_concepts, avg_concepts_per_ontology,
             pressure_score, pressure_zone)
        VALUES (0, 0, 0, 0.0, 1.5, 'probe');
        DELETE FROM kg_api.annealing_pressure_history WHERE pressure_zone = 'probe';
        RAISE EXCEPTION 'Migration 068 failed: pressure_score > 1.0 was admitted';
    EXCEPTION WHEN check_violation THEN
        -- expected
        NULL;
    END;

    -- Probe-insert a valid row, confirm it lands, then clean up
    INSERT INTO kg_api.annealing_pressure_history
        (epoch, total_ontologies, total_concepts, avg_concepts_per_ontology,
         pressure_score, pressure_zone, pressure_recommendation)
    VALUES (0, 0, 0, 0.0, 0.0, '__probe__', '{"probe": true}'::jsonb);
    DELETE FROM kg_api.annealing_pressure_history WHERE pressure_zone = '__probe__';

    RAISE NOTICE 'Migration 068: annealing pressure history installed';
END $$;

-- ===========================================================================
-- Record Migration
-- ===========================================================================
INSERT INTO public.schema_migrations (version, name)
VALUES (68, 'annealing_pressure_history')
ON CONFLICT (version) DO NOTHING;
