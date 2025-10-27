-- Migration: 009_add_thinking_mode
-- Description: Add thinking_mode parameter for Ollama reasoning models
-- ADR: ADR-042 (Local LLM Inference for Concept Extraction)
-- Date: 2025-10-23
--
-- Rationale:
-- Ollama 0.12.x+ supports a "think" parameter for reasoning models (deepseek-r1, qwen3, gpt-oss).
-- Unified thinking mode interface: "off", "low", "medium", "high"
-- Model-specific behavior handled by provider:
--   - GPT-OSS: "off" → "low", "low/medium/high" → pass through
--   - Standard models: "off" → false, "low/medium/high" → true
--   - DeepSeek-R1, Qwen3: Similar to GPT-OSS (may support levels)
--
-- This provides consistent user interface while handling model quirks internally.
-- This parameter is configurable per extraction config, not globally via .env.

BEGIN;

-- ============================================================================
-- Add thinking_mode Column
-- ============================================================================

ALTER TABLE kg_api.ai_extraction_config
ADD COLUMN IF NOT EXISTS thinking_mode VARCHAR(20) DEFAULT 'off'
CHECK (thinking_mode IN ('off', 'low', 'medium', 'high'));

COMMENT ON COLUMN kg_api.ai_extraction_config.thinking_mode IS
'Thinking mode for reasoning models (Ollama 0.12.x+): off, low, medium, high.
GPT-OSS: off=low, others pass through. Standard models: off=disabled, low/medium/high=enabled.';

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (9, 'add_thinking_mode')
ON CONFLICT (version) DO NOTHING;

COMMIT;
