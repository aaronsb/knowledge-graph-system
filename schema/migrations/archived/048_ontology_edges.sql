-- ===========================================================================
-- Migration 048: Ontology-to-Ontology Edge Types (ADR-200 Phase 5)
-- ===========================================================================
-- Date: 2026-01-31
-- Related: ADR-200 (Annealing Ontologies, Phase 5)
--
-- Introduces three edge types between Ontology nodes:
--   OVERLAPS:     bidirectional — significant concept overlap between domains
--   SPECIALIZES:  directional  — A is a coherent subset of B
--   GENERALIZES:  directional  — A is a superset of B (inverse of SPECIALIZES)
--
-- Edge properties:
--   source:               'annealing_worker' | 'manual'
--   score:                affinity strength (0.0-1.0)
--   shared_concept_count: number of concepts in common
--   computed_at_epoch:    global epoch when computed
--
-- Derived edges (source='annealing_worker') are refreshed each annealing
-- cycle — stale edges are removed if affinity drops below threshold.
-- Manual edges (source='manual') persist unless explicitly deleted.
--
-- No Cypher DDL is needed for edge types in Apache AGE — edges are created
-- dynamically by MERGE statements. This migration adds tracking metrics
-- and documents the schema contract.
-- ===========================================================================

-- Track ontology edge refresh cycles
INSERT INTO public.graph_metrics (metric_name, counter, last_measured_counter, notes)
VALUES ('ontology_edge_refresh_counter', 0, 0, 'Number of ontology edge refresh cycles completed')
ON CONFLICT (metric_name) DO NOTHING;

-- Add annealing option for edge derivation thresholds
INSERT INTO kg_api.annealing_options (key, value, description) VALUES
    ('overlap_threshold',     '0.1',  'Minimum affinity score to create an OVERLAPS edge'),
    ('specializes_threshold', '0.3',  'Minimum asymmetry ratio for SPECIALIZES/GENERALIZES edges'),
    ('derive_edges',          'true', 'Whether annealing cycles should derive ontology-to-ontology edges')
ON CONFLICT (key) DO NOTHING;

-- ===========================================================================
-- Verification
-- ===========================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM public.graph_metrics WHERE metric_name = 'ontology_edge_refresh_counter'
    ) THEN
        RAISE EXCEPTION 'Migration failed: ontology_edge_refresh_counter not created';
    END IF;

    IF NOT EXISTS (
        SELECT FROM kg_api.annealing_options WHERE key = 'overlap_threshold'
    ) THEN
        RAISE EXCEPTION 'Migration failed: edge threshold options not seeded';
    END IF;

    RAISE NOTICE 'Migration 048: Ontology edge types infrastructure installed successfully';
END $$;

-- ===========================================================================
-- Record Migration
-- ===========================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (48, 'ontology_edges')
ON CONFLICT (version) DO NOTHING;
