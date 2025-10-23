-- Migration: 008_add_nomic_embedding_preset
-- Description: Add nomic-embed-text-v1.5 as a pre-configured local embedding option
-- ADR: ADR-039 (Local Embedding Service)
-- Date: 2025-10-22
--
-- Rationale:
-- nomic-ai/nomic-embed-text-v1.5 is a high-quality, cost-free local embedding model
-- that provides comparable performance to OpenAI embeddings. This migration adds
-- a ready-to-use preset configuration that users can activate with a single command.
--
-- Model Specifications:
-- - Model: nomic-ai/nomic-embed-text-v1.5 (HuggingFace)
-- - Dimensions: 768 (Matryoshka embeddings support 64-768)
-- - Context: 8K tokens
-- - Size: ~275MB disk, ~400MB RAM when loaded
-- - Performance: Comparable to text-embedding-3-small
-- - Cost: Free (local inference)
--
-- Usage:
--   kg admin embedding activate --id <id>  # Activate this preset
--   OR manually activate via API: PUT /admin/embedding/config

BEGIN;

-- ============================================================================
-- Insert Nomic Embedding Preset Configuration
-- ============================================================================

-- Insert nomic-embed-text-v1.5 preset (inactive by default)
-- Users can activate this config to switch to local embeddings
INSERT INTO kg_api.embedding_config (
    provider,
    model_name,
    embedding_dimensions,
    precision,
    max_memory_mb,
    num_threads,
    device,
    batch_size,
    max_seq_length,
    normalize_embeddings,
    updated_by,
    active,
    delete_protected,
    change_protected
) VALUES (
    'local',                                -- Provider: local inference via sentence-transformers
    'nomic-ai/nomic-embed-text-v1.5',      -- HuggingFace model ID
    768,                                     -- Embedding dimensions (Matryoshka: 64-768)
    'float16',                               -- Precision (float16 recommended for speed/memory)
    512,                                     -- Max memory: 512MB (model uses ~400MB, leaves headroom)
    4,                                       -- CPU threads: 4 (adjust based on hardware)
    'cpu',                                   -- Device: CPU by default (change to 'cuda' or 'mps' if GPU available)
    8,                                       -- Batch size: 8 (balance between speed and memory)
    8192,                                    -- Max sequence length: 8K tokens
    TRUE,                                    -- Normalize embeddings: TRUE (standard practice)
    'system',                                -- Created by: system (preset)
    FALSE,                                   -- Active: FALSE (inactive by default, user activates)
    FALSE,                                   -- Delete protected: FALSE (users can delete if needed)
    FALSE                                    -- Change protected: FALSE (users can modify settings)
)
ON CONFLICT DO NOTHING;  -- Skip if already exists (safe for re-running migration)

-- ============================================================================
-- Update Comments
-- ============================================================================

COMMENT ON TABLE kg_api.embedding_config IS 'Resource-aware embedding configuration for local and remote models - ADR-039. Includes preset for nomic-embed-text-v1.5.';

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (8, 'add_nomic_embedding_preset')
ON CONFLICT (version) DO NOTHING;

COMMIT;

-- ============================================================================
-- Post-Migration Instructions
-- ============================================================================
--
-- To activate the nomic embedding preset:
--   1. List all configs:     kg admin embedding list
--   2. Find the nomic config ID
--   3. Activate it:          kg admin embedding activate --id <id>
--   OR use the API:          PUT /admin/embedding/config
--
-- To verify the active config:
--   kg admin embedding status
--
-- To modify the preset (e.g., use GPU instead of CPU):
--   kg admin embedding set \
--     --provider local \
--     --model "nomic-ai/nomic-embed-text-v1.5" \
--     --dimensions 768 \
--     --device cuda \
--     --threads 8 \
--     --batch-size 16
--
-- Note: Changing embedding dimensions (768 → 1536 or vice versa) requires
-- re-embedding all existing concepts. See ADR-039 for migration procedures.
