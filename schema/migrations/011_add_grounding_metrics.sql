-- Migration: 011_add_grounding_metrics
-- Description: Add grounding-aware metrics to vocabulary table for ADR-044/046
-- ADR: ADR-046 (Grounding-Aware Vocabulary Management)
-- Date: 2025-01-25

BEGIN;

-- ============================================================================
-- Grounding Metrics for Relationship Vocabulary
-- ============================================================================

-- Add grounding contribution metric (0.0-1.0)
-- Measures how much this edge type affects truth convergence across all concepts
ALTER TABLE kg_api.relationship_vocabulary
ADD COLUMN IF NOT EXISTS grounding_contribution FLOAT CHECK (grounding_contribution >= 0.0 AND grounding_contribution <= 1.0);

-- Track when grounding metrics were last calculated
ALTER TABLE kg_api.relationship_vocabulary
ADD COLUMN IF NOT EXISTS last_grounding_calculated TIMESTAMPTZ;

-- Average confidence score across all edges of this type
ALTER TABLE kg_api.relationship_vocabulary
ADD COLUMN IF NOT EXISTS avg_confidence FLOAT CHECK (avg_confidence >= 0.0 AND avg_confidence <= 1.0);

-- Semantic diversity score (measures how consistently this type is used)
-- Higher = more diverse usage contexts, Lower = more specialized/consistent usage
ALTER TABLE kg_api.relationship_vocabulary
ADD COLUMN IF NOT EXISTS semantic_diversity FLOAT CHECK (semantic_diversity >= 0.0 AND semantic_diversity <= 1.0);

-- Add comments
COMMENT ON COLUMN kg_api.relationship_vocabulary.grounding_contribution IS
'ADR-046: Measures impact on concept grounding strength (0.0-1.0). Higher values indicate this edge type significantly affects truth convergence.';

COMMENT ON COLUMN kg_api.relationship_vocabulary.last_grounding_calculated IS
'ADR-046: Timestamp when grounding metrics were last recalculated. Enables staleness detection.';

COMMENT ON COLUMN kg_api.relationship_vocabulary.avg_confidence IS
'ADR-046: Average confidence score across all edges of this type. Helps identify low-quality edge types.';

COMMENT ON COLUMN kg_api.relationship_vocabulary.semantic_diversity IS
'ADR-046: Semantic diversity score (0.0-1.0). High diversity may indicate overly broad type; low diversity may indicate well-defined type.';

-- ============================================================================
-- Indexes for Grounding Queries
-- ============================================================================

-- Index for finding high-impact edge types by grounding contribution
CREATE INDEX IF NOT EXISTS idx_vocab_grounding_contribution
ON kg_api.relationship_vocabulary(grounding_contribution DESC NULLS LAST)
WHERE grounding_contribution IS NOT NULL;

-- Index for finding stale metrics that need recalculation
CREATE INDEX IF NOT EXISTS idx_vocab_grounding_staleness
ON kg_api.relationship_vocabulary(last_grounding_calculated ASC NULLS FIRST)
WHERE is_active = TRUE;

-- ============================================================================
-- Synonym Cluster Tracking Table
-- ============================================================================

-- Track groups of synonymous edge types discovered through embedding similarity
CREATE TABLE IF NOT EXISTS kg_api.synonym_clusters (
    cluster_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Representative type (usually the one with highest usage_count)
    representative_type VARCHAR(100) REFERENCES kg_api.relationship_vocabulary(relationship_type),

    -- Member types (array of edge types in this cluster)
    member_types VARCHAR(100)[],

    -- Average embedding similarity within cluster
    avg_similarity FLOAT CHECK (avg_similarity >= 0.0 AND avg_similarity <= 1.0),

    -- Cluster quality metrics
    cluster_size INTEGER,
    total_usage_count INTEGER, -- Sum of usage_count across all members

    -- Metadata
    detected_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    detection_method VARCHAR(50) DEFAULT 'embedding_similarity',

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    merge_recommended BOOLEAN DEFAULT FALSE,
    merge_completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_synonym_clusters_active
ON kg_api.synonym_clusters(is_active) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_synonym_clusters_merge_recommended
ON kg_api.synonym_clusters(merge_recommended) WHERE merge_recommended = TRUE AND is_active = TRUE;

COMMENT ON TABLE kg_api.synonym_clusters IS
'ADR-046: Tracks groups of synonymous edge types discovered through embedding-based semantic similarity (threshold > 0.85)';

COMMENT ON COLUMN kg_api.synonym_clusters.representative_type IS
'The canonical type to use when merging cluster members. Usually has highest usage_count or is builtin.';

COMMENT ON COLUMN kg_api.synonym_clusters.avg_similarity IS
'Average cosine similarity between all pairs of member embeddings. Higher values indicate stronger synonym relationship.';

-- ============================================================================
-- Helper Function: Calculate Grounding Contribution for Single Type
-- ============================================================================

-- This is a placeholder function that will be implemented in the EmbeddingWorker
-- It calculates how much a given edge type contributes to grounding across all concepts
CREATE OR REPLACE FUNCTION kg_api.calculate_type_grounding_contribution(
    p_relationship_type VARCHAR(100)
) RETURNS FLOAT AS $$
DECLARE
    v_contribution FLOAT;
BEGIN
    -- Placeholder implementation
    -- Full implementation in Python (EmbeddingWorker.calculate_grounding_contribution)
    -- This function is here for documentation and future SQL-based optimization

    -- For now, return NULL to indicate calculation needed
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION kg_api.calculate_type_grounding_contribution IS
'ADR-046: Calculates grounding contribution for a relationship type. Currently implemented in Python EmbeddingWorker.';

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (11, 'add_grounding_metrics')
ON CONFLICT (version) DO NOTHING;

COMMIT;
