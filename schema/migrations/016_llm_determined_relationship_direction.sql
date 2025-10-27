-- ============================================================================
-- Migration 016: LLM-Determined Relationship Direction Semantics (ADR-049)
-- ============================================================================
-- Date: 2025-10-27
-- Description:
--   Adds direction_semantics field for LLM-determined relationship directionality.
--
--   New field:
--   - direction_semantics: 'outward' | 'inward' | 'bidirectional' | NULL
--     NULL = not yet determined (LLM decides on first use)
--
--   Three direction values:
--   - outward: from → to (from acts on to, e.g., ENABLES, CAUSES)
--   - inward:  from ← to (from receives from to, e.g., RESULTS_FROM, MEASURED_BY)
--   - bidirectional: symmetric (e.g., SIMILAR_TO, COMPETES_WITH)
--
-- Related:
--   - ADR-049: LLM-Determined Relationship Direction Semantics
--   - ADR-047: Probabilistic Vocabulary Categorization
--   - ADR-048: Vocabulary Metadata as First-Class Graph
-- ============================================================================

-- Add direction_semantics field to relationship_vocabulary table
ALTER TABLE kg_api.relationship_vocabulary
ADD COLUMN IF NOT EXISTS direction_semantics VARCHAR(20) DEFAULT NULL;

-- Create index for direction queries
CREATE INDEX IF NOT EXISTS idx_direction_semantics
    ON kg_api.relationship_vocabulary(direction_semantics);

-- Add comment for documentation
COMMENT ON COLUMN kg_api.relationship_vocabulary.direction_semantics IS
    'LLM-determined direction: outward (from→to), inward (from←to), bidirectional (symmetric). NULL = not yet determined by LLM.';

-- NOTE: We deliberately do NOT pre-populate seed types with direction.
-- Following ADR-049 emergent pattern: LLM decides direction on first use,
-- even for seed types. This maintains consistency with ADR-047 (emergent categories).

-- Record migration in schema_migrations tables
-- kg_api.schema_migrations: For backup/restore compatibility (ADR-015)
INSERT INTO kg_api.schema_migrations (version, description)
VALUES (16, 'LLM-Determined Relationship Direction Semantics (ADR-049)')
ON CONFLICT (version) DO NOTHING;

-- public.schema_migrations: For migration tracking
INSERT INTO public.schema_migrations (version, name)
VALUES (16, 'llm_determined_relationship_direction')
ON CONFLICT (version) DO NOTHING;
