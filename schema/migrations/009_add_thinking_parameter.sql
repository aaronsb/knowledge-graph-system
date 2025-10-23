-- Migration: 009_add_thinking_parameter
-- Description: Add enable_thinking parameter for Ollama reasoning models
-- ADR: ADR-042 (Local LLM Inference for Concept Extraction)
-- Date: 2025-10-23
--
-- Rationale:
-- Ollama 0.12.x+ supports a "think" parameter for reasoning models (deepseek-r1, qwen3, gpt-oss).
-- When enabled, models can think before responding (slower but potentially higher quality).
-- When disabled, models output directly (faster, clean JSON).
--
-- This parameter should be configurable per extraction config, not globally via .env.

BEGIN;

-- ============================================================================
-- Add enable_thinking Column
-- ============================================================================

ALTER TABLE kg_api.ai_extraction_config
ADD COLUMN IF NOT EXISTS enable_thinking BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN kg_api.ai_extraction_config.enable_thinking IS 'Enable thinking mode for reasoning models (Ollama 0.12.x+): deepseek-r1, qwen3, gpt-oss. False = faster direct output, True = slower but may improve quality.';

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (9, 'add_thinking_parameter')
ON CONFLICT (version) DO NOTHING;

COMMIT;
