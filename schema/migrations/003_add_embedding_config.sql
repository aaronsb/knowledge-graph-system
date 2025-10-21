-- Migration: 003_add_embedding_config
-- Description: Add resource-aware embedding configuration table for local/remote models
-- ADR: ADR-039 (Local Embedding Service)
-- Date: 2025-10-20

BEGIN;

-- ============================================================================
-- Embedding Configuration Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS kg_api.embedding_config (
    id SERIAL PRIMARY KEY,

    -- Provider configuration
    provider VARCHAR(50) NOT NULL CHECK (provider IN ('local', 'openai')),

    -- Model configuration
    model_name VARCHAR(200) NOT NULL,
    embedding_dimensions INTEGER NOT NULL,
    precision VARCHAR(20) NOT NULL CHECK (precision IN ('float16', 'float32')),

    -- Resource allocation (for local provider)
    max_memory_mb INTEGER,
    num_threads INTEGER,
    device VARCHAR(20) CHECK (device IN ('cpu', 'cuda', 'mps')),
    batch_size INTEGER DEFAULT 8,

    -- Performance tuning
    max_seq_length INTEGER,
    normalize_embeddings BOOLEAN DEFAULT TRUE,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    active BOOLEAN DEFAULT TRUE,

    -- Only one active config at a time
    CONSTRAINT unique_active_config UNIQUE(active) WHERE active = TRUE
);

CREATE INDEX IF NOT EXISTS idx_embedding_config_active
ON kg_api.embedding_config(active) WHERE active = TRUE;

COMMENT ON TABLE kg_api.embedding_config IS 'Resource-aware embedding configuration for local and remote models - ADR-039';
COMMENT ON COLUMN kg_api.embedding_config.provider IS 'Embedding provider: local (sentence-transformers) or openai';
COMMENT ON COLUMN kg_api.embedding_config.model_name IS 'Model identifier (HuggingFace ID for local, OpenAI model name for remote)';
COMMENT ON COLUMN kg_api.embedding_config.max_memory_mb IS 'Maximum RAM allocation for local model (local provider only)';
COMMENT ON COLUMN kg_api.embedding_config.num_threads IS 'CPU threads for inference (local provider only)';
COMMENT ON COLUMN kg_api.embedding_config.device IS 'Compute device: cpu, cuda, or mps (local provider only)';
COMMENT ON COLUMN kg_api.embedding_config.batch_size IS 'Batch size for embedding generation';
COMMENT ON COLUMN kg_api.embedding_config.active IS 'Only one config can be active at a time (enforced by unique constraint)';

-- Trigger to update 'updated_at' timestamp
CREATE OR REPLACE FUNCTION kg_api.update_embedding_config_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER embedding_config_update_timestamp
    BEFORE UPDATE ON kg_api.embedding_config
    FOR EACH ROW
    EXECUTE FUNCTION kg_api.update_embedding_config_timestamp();

-- ============================================================================
-- Seed Data: Default OpenAI Configuration
-- ============================================================================

-- Insert default OpenAI configuration (allows system to work out of the box)
INSERT INTO kg_api.embedding_config (
    provider, model_name, embedding_dimensions, precision,
    max_seq_length, normalize_embeddings, updated_by, active
) VALUES (
    'openai', 'text-embedding-3-small', 1536, 'float32',
    8191, TRUE, 'system', TRUE
)
ON CONFLICT (active) WHERE active = TRUE DO NOTHING;

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (3, 'add_embedding_config')
ON CONFLICT (version) DO NOTHING;

COMMIT;
