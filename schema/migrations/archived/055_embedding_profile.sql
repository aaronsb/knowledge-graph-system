-- Migration: 055_embedding_profile
-- Description: Unified embedding profile with text + image model slots
-- ADR: ADR-039 (Local Embedding Service) + Embedding Profile Abstraction
-- Date: 2026-02-10
--
-- Rationale:
-- The embedding_config table only tracked text embedding models. Image embeddings
-- were hardcoded to Nomic Vision v1.5. We need a unified profile that covers
-- both text and image embedding models with a vector_space compatibility tag.
--
-- A "profile" is the atomic unit: create, export, import, activate, regenerate.
-- Each profile has two slots (text model + image model) and a vector_space tag.
-- For multimodal models, both slots point to the same model (multimodal=true).

-- ============================================================================
-- New Table: kg_api.embedding_profile (idempotent via IF NOT EXISTS)
-- ============================================================================

CREATE TABLE IF NOT EXISTS kg_api.embedding_profile (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    vector_space VARCHAR(100) NOT NULL,      -- compatibility key (e.g. 'nomic-v1.5', 'siglip2-base')
    multimodal BOOLEAN DEFAULT FALSE,        -- true = text config serves both text and image roles

    -- Text model slot
    text_provider VARCHAR(50) NOT NULL,
    text_model_name VARCHAR(200) NOT NULL,
    text_loader VARCHAR(50) NOT NULL,        -- 'sentence-transformers', 'transformers', 'api'
    text_revision VARCHAR(200),              -- HuggingFace commit hash / version tag
    text_dimensions INTEGER NOT NULL,
    text_precision VARCHAR(20) DEFAULT 'float16',
    text_trust_remote_code BOOLEAN DEFAULT FALSE,

    -- Image model slot (nullable for text-only profiles)
    image_provider VARCHAR(50),
    image_model_name VARCHAR(200),
    image_loader VARCHAR(50),
    image_revision VARCHAR(200),
    image_dimensions INTEGER,
    image_precision VARCHAR(20) DEFAULT 'float16',
    image_trust_remote_code BOOLEAN DEFAULT FALSE,

    -- Resource allocation (shared -- one device for all local models)
    device VARCHAR(20) DEFAULT 'cpu',
    max_memory_mb INTEGER,
    num_threads INTEGER,
    batch_size INTEGER DEFAULT 8,
    max_seq_length INTEGER,
    normalize_embeddings BOOLEAN DEFAULT TRUE,

    -- Lifecycle
    active BOOLEAN DEFAULT FALSE,
    delete_protected BOOLEAN DEFAULT FALSE,
    change_protected BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),

    -- Constraints
    CONSTRAINT chk_text_loader CHECK (
        text_loader IN ('sentence-transformers', 'transformers', 'api')
    ),
    CONSTRAINT chk_image_loader CHECK (
        image_loader IN ('sentence-transformers', 'transformers', 'api')
        OR image_loader IS NULL
    ),
    CONSTRAINT chk_multimodal_no_image CHECK (
        -- If multimodal, image columns must be NULL (text config serves both)
        NOT multimodal OR (
            image_provider IS NULL
            AND image_model_name IS NULL
            AND image_loader IS NULL
            AND image_dimensions IS NULL
        )
    ),
    CONSTRAINT chk_image_dimensions_match CHECK (
        -- If not multimodal and image columns are present, text_dimensions = image_dimensions
        multimodal
        OR image_dimensions IS NULL
        OR text_dimensions = image_dimensions
    )
);

-- Only one active profile at a time
CREATE UNIQUE INDEX IF NOT EXISTS idx_embedding_profile_unique_active
ON kg_api.embedding_profile(active) WHERE active = TRUE;

COMMENT ON TABLE kg_api.embedding_profile IS 'Unified embedding profile with text + image model slots. Replaces embedding_config.';
COMMENT ON COLUMN kg_api.embedding_profile.vector_space IS 'Compatibility key — profiles with same vector_space produce comparable embeddings';
COMMENT ON COLUMN kg_api.embedding_profile.multimodal IS 'When true, the text model also handles image embeddings (e.g. SigLIP 2)';
COMMENT ON COLUMN kg_api.embedding_profile.text_loader IS 'How to load text model: sentence-transformers, transformers (AutoModel), or api';
COMMENT ON COLUMN kg_api.embedding_profile.image_loader IS 'How to load image model: sentence-transformers, transformers (AutoModel), or api';

-- ============================================================================
-- Auto-update trigger (idempotent via CREATE OR REPLACE + IF NOT EXISTS)
-- ============================================================================

CREATE OR REPLACE FUNCTION kg_api.update_embedding_profile_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'embedding_profile_update_timestamp'
    ) THEN
        CREATE TRIGGER embedding_profile_update_timestamp
            BEFORE UPDATE ON kg_api.embedding_profile
            FOR EACH ROW
            EXECUTE FUNCTION kg_api.update_embedding_profile_timestamp();
    END IF;
END $$;

-- ============================================================================
-- Update vocabulary validation trigger to use embedding_profile
-- (replaces function from migration 012 that referenced embedding_config)
-- ============================================================================

CREATE OR REPLACE FUNCTION kg_api.auto_validate_vocabulary_embedding()
RETURNS TRIGGER AS $$
BEGIN
    -- Only validate if embedding was set/changed
    IF NEW.embedding IS NOT NULL THEN
        -- Get expected dimensions from active embedding profile
        DECLARE
            v_expected_dimensions INTEGER;
        BEGIN
            SELECT text_dimensions INTO v_expected_dimensions
            FROM kg_api.embedding_profile
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

-- ============================================================================
-- Migrate data + rename legacy table + seed profiles
-- Guarded: skips entirely if migration already recorded
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.schema_migrations WHERE version = 55) THEN
        RAISE NOTICE 'Migration 055 already applied, skipping';
        RETURN;
    END IF;

    -- Migrate from embedding_config if it still exists (not yet renamed)
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'kg_api' AND table_name = 'embedding_config'
    ) THEN
        -- 1. Migrate nomic local config → Nomic v1.5 profile
        INSERT INTO kg_api.embedding_profile (
            name, vector_space, multimodal,
            text_provider, text_model_name, text_loader, text_revision,
            text_dimensions, text_precision, text_trust_remote_code,
            image_provider, image_model_name, image_loader, image_revision,
            image_dimensions, image_precision, image_trust_remote_code,
            device, max_memory_mb, num_threads, batch_size,
            max_seq_length, normalize_embeddings,
            active, delete_protected, change_protected,
            updated_by
        )
        SELECT
            'Nomic v1.5',                            -- name
            'nomic-v1.5',                            -- vector_space
            FALSE,                                   -- multimodal (separate text + image models)
            ec.provider,                             -- text_provider
            ec.model_name,                           -- text_model_name
            'sentence-transformers',                 -- text_loader
            NULL,                                    -- text_revision
            ec.embedding_dimensions,                 -- text_dimensions
            ec.precision,                            -- text_precision
            TRUE,                                    -- text_trust_remote_code (required for nomic)
            'local',                                 -- image_provider
            'nomic-ai/nomic-embed-vision-v1.5',     -- image_model_name
            'transformers',                          -- image_loader
            NULL,                                    -- image_revision
            768,                                     -- image_dimensions (same as text for nomic)
            'float16',                               -- image_precision
            TRUE,                                    -- image_trust_remote_code
            ec.device,                               -- device
            ec.max_memory_mb,                        -- max_memory_mb
            ec.num_threads,                          -- num_threads
            ec.batch_size,                           -- batch_size
            ec.max_seq_length,                       -- max_seq_length
            ec.normalize_embeddings,                 -- normalize_embeddings
            ec.active,                               -- active (preserve active state)
            ec.delete_protected,                     -- delete_protected
            ec.change_protected,                     -- change_protected
            'migration-055'                          -- updated_by
        FROM kg_api.embedding_config ec
        WHERE ec.provider = 'local'
          AND ec.model_name = 'nomic-ai/nomic-embed-text-v1.5'
        LIMIT 1;

        -- 2. Migrate OpenAI config → OpenAI Small profile
        INSERT INTO kg_api.embedding_profile (
            name, vector_space, multimodal,
            text_provider, text_model_name, text_loader, text_revision,
            text_dimensions, text_precision, text_trust_remote_code,
            device, batch_size, max_seq_length, normalize_embeddings,
            active, delete_protected, change_protected,
            updated_by
        )
        SELECT
            'OpenAI Small',                          -- name
            'openai-v3',                             -- vector_space
            FALSE,                                   -- multimodal
            ec.provider,                             -- text_provider (openai)
            ec.model_name,                           -- text_model_name
            'api',                                   -- text_loader
            NULL,                                    -- text_revision
            ec.embedding_dimensions,                 -- text_dimensions
            ec.precision,                            -- text_precision
            FALSE,                                   -- text_trust_remote_code
            ec.device,                               -- device
            ec.batch_size,                           -- batch_size
            ec.max_seq_length,                       -- max_seq_length
            ec.normalize_embeddings,                 -- normalize_embeddings
            ec.active,                               -- active (preserve active state)
            ec.delete_protected,                     -- delete_protected
            ec.change_protected,                     -- change_protected
            'migration-055'                          -- updated_by
        FROM kg_api.embedding_config ec
        WHERE ec.provider = 'openai'
          AND ec.model_name = 'text-embedding-3-small'
        LIMIT 1;

        -- Rename old table for safe rollback
        ALTER TABLE kg_api.embedding_config RENAME TO embedding_config_legacy;
        ALTER INDEX IF EXISTS idx_embedding_config_unique_active
            RENAME TO idx_embedding_config_legacy_unique_active;

        RAISE NOTICE 'Migrated embedding_config → embedding_profile';
    END IF;

    RAISE NOTICE 'Migration 055: embedding_profile table ready';
END $$;

-- ===========================================================================
-- Record Migration
-- ===========================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (55, 'embedding_profile')
ON CONFLICT (version) DO NOTHING;
