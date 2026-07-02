-- Migration: 007_add_local_extraction_providers
-- Description: Extend AI extraction config to support local inference providers (Ollama, vLLM)
-- ADR: ADR-042 (Local LLM Inference for Concept Extraction)
-- Date: 2025-10-22

BEGIN;

-- ============================================================================
-- Extend ai_extraction_config Table for Local Providers
-- ============================================================================

-- Step 1: Drop existing CHECK constraint on provider
ALTER TABLE kg_api.ai_extraction_config
DROP CONSTRAINT IF EXISTS ai_extraction_config_provider_check;

-- Step 2: Add new CHECK constraint with local providers
ALTER TABLE kg_api.ai_extraction_config
ADD CONSTRAINT ai_extraction_config_provider_check
CHECK (provider IN ('openai', 'anthropic', 'ollama', 'vllm'));

-- Step 3: Add columns for local provider configuration
-- These are optional fields used only by local providers (ollama, vllm)

-- Ollama/vLLM base URL (e.g., http://localhost:11434, http://ollama:11434)
ALTER TABLE kg_api.ai_extraction_config
ADD COLUMN IF NOT EXISTS base_url VARCHAR(255);

-- Sampling parameters (used by local models)
ALTER TABLE kg_api.ai_extraction_config
ADD COLUMN IF NOT EXISTS temperature FLOAT DEFAULT 0.1
CHECK (temperature >= 0.0 AND temperature <= 1.0);

ALTER TABLE kg_api.ai_extraction_config
ADD COLUMN IF NOT EXISTS top_p FLOAT DEFAULT 0.9
CHECK (top_p >= 0.0 AND top_p <= 1.0);

-- GPU/CPU inference settings (future-proofing for llama.cpp direct integration)
ALTER TABLE kg_api.ai_extraction_config
ADD COLUMN IF NOT EXISTS gpu_layers INTEGER DEFAULT -1;  -- -1 = auto, 0 = CPU only, >0 = specific layer count

ALTER TABLE kg_api.ai_extraction_config
ADD COLUMN IF NOT EXISTS num_threads INTEGER DEFAULT 4;  -- CPU threads for inference

-- ============================================================================
-- Update Comments
-- ============================================================================

COMMENT ON COLUMN kg_api.ai_extraction_config.provider IS 'AI provider: openai, anthropic, ollama, or vllm';
COMMENT ON COLUMN kg_api.ai_extraction_config.base_url IS 'Base URL for local providers (e.g., http://localhost:11434 for Ollama)';
COMMENT ON COLUMN kg_api.ai_extraction_config.temperature IS 'Sampling temperature (0.0-1.0, lower = more consistent). Used by local providers.';
COMMENT ON COLUMN kg_api.ai_extraction_config.top_p IS 'Nucleus sampling threshold (0.0-1.0). Used by local providers.';
COMMENT ON COLUMN kg_api.ai_extraction_config.gpu_layers IS 'GPU layers for inference: -1 = auto, 0 = CPU only, >0 = specific layer count (llama.cpp)';
COMMENT ON COLUMN kg_api.ai_extraction_config.num_threads IS 'CPU threads for inference (used by local CPU-based providers)';

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (7, 'add_local_extraction_providers')
ON CONFLICT (version) DO NOTHING;

COMMIT;
