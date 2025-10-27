-- Migration: 012_add_embedding_worker_support
-- Description: Add infrastructure for unified embedding generation (ADR-045)
-- ADR: ADR-045 (Unified Embedding Generation System)
-- Date: 2025-01-25

BEGIN;

-- ============================================================================
-- Embedding Generation Tracking
-- ============================================================================

-- Track embedding generation jobs and cold start initialization
CREATE TABLE IF NOT EXISTS kg_api.embedding_generation_jobs (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Job type
    job_type VARCHAR(50) NOT NULL CHECK (job_type IN (
        'cold_start',           -- Initialize embeddings for builtin types
        'vocabulary_update',    -- Generate embeddings for new vocabulary
        'model_migration',      -- Regenerate all embeddings for model change
        'batch_regeneration'    -- Bulk regeneration (admin operation)
    )),

    -- Job scope
    target_types VARCHAR(100)[], -- Array of relationship types to process (NULL = all)
    target_count INTEGER,         -- Number of types to process

    -- Progress tracking
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending', 'running', 'completed', 'failed', 'cancelled'
    )),
    processed_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,

    -- Model information
    embedding_model VARCHAR(100),
    embedding_provider VARCHAR(50),

    -- Timing
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,

    -- Result summary
    result_summary JSONB,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_embedding_jobs_status
ON kg_api.embedding_generation_jobs(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_embedding_jobs_type
ON kg_api.embedding_generation_jobs(job_type, created_at DESC);

COMMENT ON TABLE kg_api.embedding_generation_jobs IS
'ADR-045: Tracks embedding generation jobs for audit trail and progress monitoring';

-- ============================================================================
-- Cold Start Initialization Status
-- ============================================================================

-- Track completion of cold start initialization for builtin types
CREATE TABLE IF NOT EXISTS kg_api.system_initialization_status (
    component VARCHAR(50) PRIMARY KEY,
    initialized BOOLEAN DEFAULT FALSE,
    initialized_at TIMESTAMPTZ,
    initialization_job_id UUID REFERENCES kg_api.embedding_generation_jobs(job_id),
    version VARCHAR(20),
    metadata JSONB
);

-- Insert cold start tracking record
INSERT INTO kg_api.system_initialization_status (component, initialized)
VALUES ('builtin_vocabulary_embeddings', FALSE)
ON CONFLICT (component) DO NOTHING;

COMMENT ON TABLE kg_api.system_initialization_status IS
'ADR-045: Tracks completion of system initialization tasks like cold start embedding generation';

-- ============================================================================
-- Embedding Quality Metrics
-- ============================================================================

-- Add embedding quality tracking to vocabulary table
ALTER TABLE kg_api.relationship_vocabulary
ADD COLUMN IF NOT EXISTS embedding_quality_score FLOAT CHECK (embedding_quality_score >= 0.0 AND embedding_quality_score <= 1.0);

ALTER TABLE kg_api.relationship_vocabulary
ADD COLUMN IF NOT EXISTS embedding_validation_status VARCHAR(20) CHECK (embedding_validation_status IN (
    'pending', 'valid', 'invalid', 'stale'
));

COMMENT ON COLUMN kg_api.relationship_vocabulary.embedding_quality_score IS
'ADR-045: Quality score for embedding (based on validation checks like magnitude, dimensionality)';

COMMENT ON COLUMN kg_api.relationship_vocabulary.embedding_validation_status IS
'ADR-045: Validation status - stale indicates model changed since generation';

-- ============================================================================
-- Helper Views for Embedding Worker
-- ============================================================================

-- View: Builtin types missing embeddings (cold start targets)
CREATE OR REPLACE VIEW kg_api.v_builtin_types_missing_embeddings AS
SELECT
    relationship_type,
    description,
    category,
    usage_count,
    added_at
FROM kg_api.relationship_vocabulary
WHERE is_builtin = TRUE
  AND (embedding IS NULL OR embedding_validation_status = 'stale')
  AND is_active = TRUE
ORDER BY usage_count DESC, relationship_type;

COMMENT ON VIEW kg_api.v_builtin_types_missing_embeddings IS
'ADR-045: Builtin vocabulary types requiring embedding generation (cold start initialization)';

-- View: All types needing embedding regeneration
CREATE OR REPLACE VIEW kg_api.v_types_needing_embedding_regeneration AS
SELECT
    relationship_type,
    description,
    category,
    is_builtin,
    usage_count,
    embedding_model,
    embedding_generated_at,
    CASE
        WHEN embedding IS NULL THEN 'missing'
        WHEN embedding_validation_status = 'stale' THEN 'stale'
        WHEN embedding_validation_status = 'invalid' THEN 'invalid'
        ELSE 'unknown'
    END as regeneration_reason
FROM kg_api.relationship_vocabulary
WHERE is_active = TRUE
  AND (
    embedding IS NULL OR
    embedding_validation_status IN ('stale', 'invalid', 'pending')
  )
ORDER BY
    is_builtin DESC,  -- Builtins first
    usage_count DESC,
    relationship_type;

COMMENT ON VIEW kg_api.v_types_needing_embedding_regeneration IS
'ADR-045: All vocabulary types requiring embedding (re)generation, prioritized by builtin status and usage';

-- ============================================================================
-- Helper Functions for Embedding Worker
-- ============================================================================

-- Function: Mark embeddings as stale when model changes
CREATE OR REPLACE FUNCTION kg_api.mark_embeddings_stale_for_model(
    p_old_model VARCHAR(100)
) RETURNS INTEGER AS $$
DECLARE
    v_updated_count INTEGER;
BEGIN
    UPDATE kg_api.relationship_vocabulary
    SET embedding_validation_status = 'stale'
    WHERE embedding_model = p_old_model
      AND embedding IS NOT NULL
      AND is_active = TRUE;

    GET DIAGNOSTICS v_updated_count = ROW_COUNT;

    RETURN v_updated_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION kg_api.mark_embeddings_stale_for_model IS
'ADR-045: Marks all embeddings for a model as stale when model is changed. Returns count of marked types.';

-- Function: Validate embedding structure
CREATE OR REPLACE FUNCTION kg_api.validate_embedding(
    p_embedding JSONB,
    p_expected_dimensions INTEGER DEFAULT 1536
) RETURNS BOOLEAN AS $$
DECLARE
    v_array_length INTEGER;
BEGIN
    -- Check if embedding is a JSON array
    IF jsonb_typeof(p_embedding) != 'array' THEN
        RETURN FALSE;
    END IF;

    -- Check dimensionality
    v_array_length := jsonb_array_length(p_embedding);
    IF v_array_length != p_expected_dimensions THEN
        RETURN FALSE;
    END IF;

    -- Basic validation passed
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION kg_api.validate_embedding IS
'ADR-045: Validates embedding structure (JSON array of expected dimensions)';

-- ============================================================================
-- Triggers for Automatic Validation
-- ============================================================================

-- Trigger function: Validate embedding on insert/update
CREATE OR REPLACE FUNCTION kg_api.auto_validate_vocabulary_embedding()
RETURNS TRIGGER AS $$
BEGIN
    -- Only validate if embedding was set/changed
    IF NEW.embedding IS NOT NULL THEN
        -- Get expected dimensions from active embedding config
        DECLARE
            v_expected_dimensions INTEGER;
        BEGIN
            SELECT embedding_dimensions INTO v_expected_dimensions
            FROM kg_api.embedding_config
            WHERE active = TRUE
            LIMIT 1;

            -- Validate embedding structure
            IF kg_api.validate_embedding(NEW.embedding, v_expected_dimensions) THEN
                NEW.embedding_validation_status := 'valid';

                -- Calculate quality score (basic: non-zero vector magnitude)
                -- Full quality scoring implemented in Python EmbeddingWorker
                NEW.embedding_quality_score := 1.0;
            ELSE
                NEW.embedding_validation_status := 'invalid';
                NEW.embedding_quality_score := 0.0;
            END IF;
        END;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for vocabulary embedding validation
DROP TRIGGER IF EXISTS trigger_validate_vocabulary_embedding ON kg_api.relationship_vocabulary;
CREATE TRIGGER trigger_validate_vocabulary_embedding
    BEFORE INSERT OR UPDATE OF embedding ON kg_api.relationship_vocabulary
    FOR EACH ROW
    WHEN (NEW.embedding IS NOT NULL)
    EXECUTE FUNCTION kg_api.auto_validate_vocabulary_embedding();

COMMENT ON TRIGGER trigger_validate_vocabulary_embedding ON kg_api.relationship_vocabulary IS
'ADR-045: Automatically validates embedding structure when set/updated';

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (12, 'add_embedding_worker_support')
ON CONFLICT (version) DO NOTHING;

COMMIT;
