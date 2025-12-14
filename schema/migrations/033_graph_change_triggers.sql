-- Migration 033: Graph Metrics Snapshot Refresh
-- Purpose: Provide reliable graph change detection for projection cache invalidation
-- Date: 2025-12-13
-- Related: ADR-079 (Projection Artifact Storage)
--
-- Background: We initially attempted to use PostgreSQL triggers to track graph
-- changes incrementally. However, Apache AGE's Cypher operations bypass PostgreSQL's
-- trigger mechanism entirely - AGE uses internal C functions that directly manipulate
-- tables without firing row-level triggers.
--
-- Solution: Snapshot-based change detection
--   - Periodically refresh counters from actual COUNT(*) queries
--   - Compare current counts to stored counts to detect changes
--   - Simple, reliable, and AGE-compatible
--   - ~1-2ms per COUNT(*) query - negligible overhead
--
-- Counter Categories:
--   A. SNAPSHOT COUNTERS (refreshed by refresh_graph_metrics):
--      - concept_count, vocabulary_type_count, total_edges, source_count, instance_count
--      - graph_change_counter: composite checksum for cache invalidation
--
--   B. ACTIVITY COUNTERS (application-incremented, still work):
--      - document_ingestion_counter, epistemic_measurement_counter
--      - vocabulary_consolidation_counter
--
-- Usage:
--   - Call refresh_graph_metrics() after ingestion jobs complete
--   - Call refresh_graph_metrics() periodically for background sync
--   - Compare graph_change_counter to stored value for cache invalidation
--
-- IDEMPOTENCY: This migration can safely be run multiple times:
--   - Functions use CREATE OR REPLACE
--   - INSERT uses ON CONFLICT DO NOTHING
--   - Counter updates are idempotent (same counts → same values)

BEGIN;

-- ============================================================================
-- STEP 1: Add unified graph change counter (for ADR-079 projection caching)
-- ============================================================================

INSERT INTO graph_metrics (metric_name, counter, last_measured_counter, notes)
VALUES ('graph_change_counter', 0, 0, 'Composite counter for cache invalidation - sum of all graph objects (ADR-079)')
ON CONFLICT (metric_name) DO NOTHING;

-- ============================================================================
-- STEP 2: Create comprehensive snapshot refresh function
-- ============================================================================

CREATE OR REPLACE FUNCTION public.refresh_graph_metrics()
RETURNS TABLE(metric_name TEXT, old_value BIGINT, new_value BIGINT, changed BOOLEAN) AS $$
DECLARE
    v_concept_count BIGINT;
    v_edge_count BIGINT;
    v_vocab_type_count BIGINT;
    v_vocab_category_count BIGINT;
    v_source_count BIGINT;
    v_instance_count BIGINT;
    v_document_count BIGINT;
    v_graph_change_counter BIGINT;
    v_old_value BIGINT;
BEGIN
    -- Get current counts (fast parallel-safe queries)
    SELECT COUNT(*) INTO v_concept_count FROM knowledge_graph."Concept";
    SELECT COUNT(*) INTO v_edge_count FROM knowledge_graph._ag_label_edge;
    SELECT COUNT(*) INTO v_vocab_type_count FROM knowledge_graph."VocabType";
    SELECT COUNT(*) INTO v_vocab_category_count FROM knowledge_graph."VocabCategory";
    SELECT COUNT(*) INTO v_source_count FROM knowledge_graph."Source";
    SELECT COUNT(*) INTO v_instance_count FROM knowledge_graph."Instance";
    SELECT COUNT(*) INTO v_document_count FROM knowledge_graph."DocumentMeta";

    -- Compute unified graph change counter (sum of all objects)
    v_graph_change_counter := v_concept_count + v_edge_count + v_vocab_type_count +
                              v_vocab_category_count + v_source_count + v_instance_count +
                              v_document_count;

    -- Update concept_count
    SELECT counter INTO v_old_value FROM public.graph_metrics WHERE public.graph_metrics.metric_name = 'concept_count';
    UPDATE public.graph_metrics SET counter = v_concept_count, updated_at = CURRENT_TIMESTAMP
    WHERE public.graph_metrics.metric_name = 'concept_count';
    metric_name := 'concept_count'; old_value := v_old_value; new_value := v_concept_count;
    changed := (v_old_value IS DISTINCT FROM v_concept_count); RETURN NEXT;

    -- Update total_edges
    SELECT counter INTO v_old_value FROM public.graph_metrics WHERE public.graph_metrics.metric_name = 'total_edges';
    UPDATE public.graph_metrics SET counter = v_edge_count, updated_at = CURRENT_TIMESTAMP
    WHERE public.graph_metrics.metric_name = 'total_edges';
    metric_name := 'total_edges'; old_value := v_old_value; new_value := v_edge_count;
    changed := (v_old_value IS DISTINCT FROM v_edge_count); RETURN NEXT;

    -- Update vocabulary_type_count
    SELECT counter INTO v_old_value FROM public.graph_metrics WHERE public.graph_metrics.metric_name = 'vocabulary_type_count';
    UPDATE public.graph_metrics SET counter = v_vocab_type_count, updated_at = CURRENT_TIMESTAMP
    WHERE public.graph_metrics.metric_name = 'vocabulary_type_count';
    metric_name := 'vocabulary_type_count'; old_value := v_old_value; new_value := v_vocab_type_count;
    changed := (v_old_value IS DISTINCT FROM v_vocab_type_count); RETURN NEXT;

    -- Update source_count
    SELECT counter INTO v_old_value FROM public.graph_metrics WHERE public.graph_metrics.metric_name = 'source_count';
    UPDATE public.graph_metrics SET counter = v_source_count, updated_at = CURRENT_TIMESTAMP
    WHERE public.graph_metrics.metric_name = 'source_count';
    metric_name := 'source_count'; old_value := v_old_value; new_value := v_source_count;
    changed := (v_old_value IS DISTINCT FROM v_source_count); RETURN NEXT;

    -- Update instance_count
    SELECT counter INTO v_old_value FROM public.graph_metrics WHERE public.graph_metrics.metric_name = 'instance_count';
    UPDATE public.graph_metrics SET counter = v_instance_count, updated_at = CURRENT_TIMESTAMP
    WHERE public.graph_metrics.metric_name = 'instance_count';
    metric_name := 'instance_count'; old_value := v_old_value; new_value := v_instance_count;
    changed := (v_old_value IS DISTINCT FROM v_instance_count); RETURN NEXT;

    -- Update graph_change_counter (unified counter for cache invalidation)
    SELECT counter INTO v_old_value FROM public.graph_metrics WHERE public.graph_metrics.metric_name = 'graph_change_counter';
    UPDATE public.graph_metrics SET counter = v_graph_change_counter, updated_at = CURRENT_TIMESTAMP
    WHERE public.graph_metrics.metric_name = 'graph_change_counter';
    metric_name := 'graph_change_counter'; old_value := v_old_value; new_value := v_graph_change_counter;
    changed := (v_old_value IS DISTINCT FROM v_graph_change_counter); RETURN NEXT;

    -- Also update the legacy creation counters to match current state
    -- (These were meant to be trigger-incremented but AGE bypasses triggers)
    UPDATE public.graph_metrics SET counter = v_concept_count, updated_at = CURRENT_TIMESTAMP
    WHERE public.graph_metrics.metric_name = 'concept_creation_counter';

    UPDATE public.graph_metrics SET counter = v_edge_count, updated_at = CURRENT_TIMESTAMP
    WHERE public.graph_metrics.metric_name = 'relationship_creation_counter';

    UPDATE public.graph_metrics SET counter = v_vocab_type_count, updated_at = CURRENT_TIMESTAMP
    WHERE public.graph_metrics.metric_name = 'vocabulary_creation_counter';

    UPDATE public.graph_metrics SET counter = v_vocab_type_count + v_vocab_category_count, updated_at = CURRENT_TIMESTAMP
    WHERE public.graph_metrics.metric_name = 'vocabulary_change_counter';
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION public.refresh_graph_metrics IS
'Refreshes all graph metrics from current counts. Call after ingestion or periodically.
Returns table showing which metrics changed. Safe to call repeatedly (idempotent).
Used for ADR-079 projection cache invalidation.';

-- ============================================================================
-- STEP 3: Simple function to check if graph changed (for cache invalidation)
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_graph_snapshot()
RETURNS TABLE(
    concepts BIGINT,
    edges BIGINT,
    sources BIGINT,
    vocab_types BIGINT,
    total_objects BIGINT
) AS $$
BEGIN
    RETURN QUERY SELECT
        (SELECT COUNT(*) FROM knowledge_graph."Concept"),
        (SELECT COUNT(*) FROM knowledge_graph._ag_label_edge),
        (SELECT COUNT(*) FROM knowledge_graph."Source"),
        (SELECT COUNT(*) FROM knowledge_graph."VocabType"),
        (SELECT COUNT(*) FROM knowledge_graph."Concept") +
        (SELECT COUNT(*) FROM knowledge_graph._ag_label_edge) +
        (SELECT COUNT(*) FROM knowledge_graph."Source") +
        (SELECT COUNT(*) FROM knowledge_graph."VocabType") +
        (SELECT COUNT(*) FROM knowledge_graph."VocabCategory") +
        (SELECT COUNT(*) FROM knowledge_graph."Instance") +
        (SELECT COUNT(*) FROM knowledge_graph."DocumentMeta");
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION public.get_graph_snapshot IS
'Returns current graph object counts. Use total_objects to compare against stored
projection artifact metadata for cache invalidation. Fast (~5ms).';

-- ============================================================================
-- STEP 4: Keep update_graph_snapshot_totals for backwards compatibility
-- ============================================================================

CREATE OR REPLACE FUNCTION public.update_graph_snapshot_totals()
RETURNS void AS $$
BEGIN
    -- Just call the new comprehensive function
    PERFORM public.refresh_graph_metrics();
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION public.update_graph_snapshot_totals IS
'DEPRECATED: Use refresh_graph_metrics() instead. Kept for backwards compatibility.';

-- ============================================================================
-- STEP 5: Initialize counters from current graph state
-- ============================================================================

-- Run initial refresh to populate all counters
SELECT public.refresh_graph_metrics();

-- ============================================================================
-- STEP 6: Add helpful view for monitoring
-- ============================================================================

CREATE OR REPLACE VIEW public.graph_metrics_summary AS
SELECT
    metric_name,
    counter,
    last_measured_counter,
    (counter - last_measured_counter) AS delta_since_last_measure,
    updated_at,
    CASE
        WHEN metric_name LIKE '%_count' THEN 'snapshot'
        WHEN metric_name = 'graph_change_counter' THEN 'snapshot'
        WHEN metric_name IN ('document_ingestion_counter', 'chunk_processing_counter',
                            'extraction_job_counter', 'grounding_calculation_counter',
                            'epistemic_measurement_counter', 'vocabulary_consolidation_counter') THEN 'activity'
        ELSE 'legacy_structure'
    END AS counter_type,
    notes
FROM public.graph_metrics
ORDER BY counter_type, metric_name;

COMMENT ON VIEW public.graph_metrics_summary IS
'Summary view of all graph metrics. snapshot counters are refreshed by refresh_graph_metrics().
activity counters are incremented by application code. legacy_structure counters are kept
in sync with snapshots (AGE bypasses PostgreSQL triggers).';

-- ============================================================================
-- STEP 7: Clean up debug table if it exists (from trigger testing)
-- ============================================================================

DROP TABLE IF EXISTS public.trigger_debug_log;

-- ============================================================================
-- Migration Tracking
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (33, 'graph_change_triggers')
ON CONFLICT (version) DO NOTHING;

COMMIT;
