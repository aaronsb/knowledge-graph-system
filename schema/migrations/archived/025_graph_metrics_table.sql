-- Migration 025: Graph Metrics Table
-- Purpose: Track graph change counters to trigger periodic epistemic status measurement
-- Date: 2025-11-17
--
-- Philosophy:
-- - Vocabulary epistemic status can be cached (unlike node grounding)
-- - Only re-measure when vocabulary changes (create/delete/consolidate)
-- - Use change counters, not datetimes, to detect staleness
-- - Delta = current_counter - last_measured_counter indicates staleness

CREATE TABLE IF NOT EXISTS graph_metrics (
    metric_name VARCHAR(255) PRIMARY KEY,
    counter BIGINT NOT NULL DEFAULT 0,
    last_measured_counter BIGINT NOT NULL DEFAULT 0,
    last_measured_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

COMMENT ON TABLE graph_metrics IS 'Change counters for triggering periodic epistemic status measurement';
COMMENT ON COLUMN graph_metrics.metric_name IS 'Unique metric identifier (e.g., vocabulary_change_counter, concept_count)';
COMMENT ON COLUMN graph_metrics.counter IS 'Increments on every change (create/delete/consolidate) - never decrements';
COMMENT ON COLUMN graph_metrics.last_measured_counter IS 'Counter value when epistemic status was last measured';
COMMENT ON COLUMN graph_metrics.last_measured_at IS 'Timestamp when epistemic status was last measured';
COMMENT ON COLUMN graph_metrics.updated_at IS 'Timestamp of last counter increment';

-- Initialize core metrics
INSERT INTO graph_metrics (metric_name, counter, last_measured_counter, notes)
VALUES
    -- Vocabulary change tracking (primary trigger for epistemic status re-measurement)
    ('vocabulary_change_counter', 0, 0, 'Increments on any vocabulary type create/delete/consolidate'),
    ('vocabulary_creation_counter', 0, 0, 'New vocabulary types created'),
    ('vocabulary_deletion_counter', 0, 0, 'Vocabulary types deleted'),
    ('vocabulary_consolidation_counter', 0, 0, 'Vocabulary synonym merges/consolidations'),

    -- Concept/relationship change tracking
    ('concept_creation_counter', 0, 0, 'New concepts added to graph'),
    ('concept_deletion_counter', 0, 0, 'Concepts removed from graph'),
    ('relationship_creation_counter', 0, 0, 'New relationships/edges added'),
    ('relationship_deletion_counter', 0, 0, 'Relationships/edges removed'),

    -- Ingestion activity tracking
    ('document_ingestion_counter', 0, 0, 'Documents successfully ingested'),
    ('chunk_processing_counter', 0, 0, 'Document chunks processed'),
    ('extraction_job_counter', 0, 0, 'Extraction jobs completed'),

    -- Quality/maintenance tracking
    ('grounding_calculation_counter', 0, 0, 'Concepts with grounding calculated/updated'),
    ('epistemic_measurement_counter', 0, 0, 'Epistemic status measurements completed'),

    -- Snapshot totals (for reference, not change counters)
    ('concept_count', 0, 0, 'Current total concept count'),
    ('vocabulary_type_count', 0, 0, 'Current total vocabulary type count'),
    ('total_edges', 0, 0, 'Current total relationship count'),
    ('source_count', 0, 0, 'Current total source document count'),
    ('instance_count', 0, 0, 'Current total evidence instance count')
ON CONFLICT (metric_name) DO NOTHING;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_graph_metrics_updated_at ON graph_metrics(updated_at);

-- Function to increment any counter
CREATE OR REPLACE FUNCTION increment_counter(p_metric_name VARCHAR(255))
RETURNS void AS $$
BEGIN
    UPDATE graph_metrics
    SET counter = counter + 1,
        updated_at = CURRENT_TIMESTAMP
    WHERE metric_name = p_metric_name;

    -- Create metric if it doesn't exist
    IF NOT FOUND THEN
        INSERT INTO graph_metrics (metric_name, counter, last_measured_counter, updated_at)
        VALUES (p_metric_name, 1, 0, CURRENT_TIMESTAMP);
    END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION increment_counter IS 'Increment any metric counter and update timestamp';

-- Function to get counter delta (staleness indicator)
CREATE OR REPLACE FUNCTION get_counter_delta(p_metric_name VARCHAR(255))
RETURNS BIGINT AS $$
DECLARE
    v_delta BIGINT;
BEGIN
    SELECT (counter - last_measured_counter) INTO v_delta
    FROM graph_metrics
    WHERE metric_name = p_metric_name;

    RETURN COALESCE(v_delta, 0);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_counter_delta IS 'Get delta between current counter and last measured counter (staleness)';

-- Function to mark measurement complete (reset delta)
CREATE OR REPLACE FUNCTION mark_measurement_complete(p_metric_name VARCHAR(255))
RETURNS void AS $$
BEGIN
    UPDATE graph_metrics
    SET last_measured_counter = counter,
        last_measured_at = CURRENT_TIMESTAMP
    WHERE metric_name = p_metric_name;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION mark_measurement_complete IS 'Mark epistemic status measurement complete - resets delta to 0';

-- Function to update snapshot totals
CREATE OR REPLACE FUNCTION update_snapshot_totals()
RETURNS void AS $$
BEGIN
    -- Update concept count
    UPDATE graph_metrics
    SET counter = (SELECT COUNT(*) FROM ag_catalog.ag_vertex WHERE label = 'Concept'),
        updated_at = CURRENT_TIMESTAMP
    WHERE metric_name = 'concept_count';

    -- Update vocabulary type count
    UPDATE graph_metrics
    SET counter = (SELECT COUNT(*) FROM ag_catalog.ag_vertex WHERE label = 'VocabType'),
        updated_at = CURRENT_TIMESTAMP
    WHERE metric_name = 'vocabulary_type_count';

    -- Note: total_edges, source_count, instance_count would require similar queries
    -- but are omitted here to avoid cross-namespace queries
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_snapshot_totals IS 'Update snapshot total counters from current graph state';

-- Function to reset counter (operator task)
CREATE OR REPLACE FUNCTION reset_counter(p_metric_name VARCHAR(255))
RETURNS void AS $$
BEGIN
    UPDATE graph_metrics
    SET counter = 0,
        last_measured_counter = 0,
        last_measured_at = NULL,
        updated_at = CURRENT_TIMESTAMP
    WHERE metric_name = p_metric_name;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION reset_counter IS 'Reset counter to 0 (operator maintenance task)';

-- Function to reset all counters (operator task - use with caution)
CREATE OR REPLACE FUNCTION reset_all_counters()
RETURNS void AS $$
BEGIN
    UPDATE graph_metrics
    SET counter = 0,
        last_measured_counter = 0,
        last_measured_at = NULL,
        updated_at = CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION reset_all_counters IS 'Reset ALL counters to 0 (operator maintenance task - use with caution)';

-- ---------------------------------------------------------------------------
-- Migration Tracking
-- ---------------------------------------------------------------------------

INSERT INTO public.schema_migrations (version, name)
VALUES (25, 'graph_metrics_table')
ON CONFLICT (version) DO NOTHING;
