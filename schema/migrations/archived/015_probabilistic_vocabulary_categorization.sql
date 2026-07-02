-- ============================================================================
-- Migration 015: Probabilistic Vocabulary Categorization (ADR-047)
-- ============================================================================
-- Date: 2025-10-27
-- Description:
--   Adds fields for probabilistic category assignment using embedding similarity.
--
--   New fields:
--   - category_source: 'builtin' or 'computed' (no manual overrides)
--   - category_confidence: 0.0 to 1.0 similarity score
--   - category_scores: JSONB with full category breakdown
--   - category_ambiguous: true if runner-up score > 0.70
--
-- Related:
--   - ADR-047: Probabilistic Vocabulary Categorization
--   - ADR-044: Probabilistic Truth Convergence
--   - ADR-045: Unified Embedding Generation
-- ============================================================================

-- Add category scoring fields to relationship_vocabulary table
ALTER TABLE kg_api.relationship_vocabulary
ADD COLUMN IF NOT EXISTS category_source VARCHAR(20) DEFAULT 'builtin',
ADD COLUMN IF NOT EXISTS category_confidence FLOAT,
ADD COLUMN IF NOT EXISTS category_scores JSONB,
ADD COLUMN IF NOT EXISTS category_ambiguous BOOLEAN DEFAULT false;

-- Create indexes for category queries
CREATE INDEX IF NOT EXISTS idx_relationship_category
    ON kg_api.relationship_vocabulary(category);
CREATE INDEX IF NOT EXISTS idx_category_confidence
    ON kg_api.relationship_vocabulary(category_confidence);
CREATE INDEX IF NOT EXISTS idx_category_source
    ON kg_api.relationship_vocabulary(category_source);

-- Update existing builtin types to mark them as such
UPDATE kg_api.relationship_vocabulary
SET category_source = 'builtin'
WHERE is_builtin = TRUE AND category_source IS NULL;

-- Add comments for documentation
COMMENT ON COLUMN kg_api.relationship_vocabulary.category_source IS
    'Source of category assignment: builtin (hand-assigned) or computed (ADR-047)';
COMMENT ON COLUMN kg_api.relationship_vocabulary.category_confidence IS
    'Confidence score (0.0-1.0) for computed categories based on max similarity to seed types';
COMMENT ON COLUMN kg_api.relationship_vocabulary.category_scores IS
    'Full category similarity breakdown as JSON: {"causation": 0.85, "composition": 0.45, ...}';
COMMENT ON COLUMN kg_api.relationship_vocabulary.category_ambiguous IS
    'True if runner-up category score > 0.70 (potential multi-category type)';

-- Record migration in schema_migrations tables
-- kg_api.schema_migrations: For backup/restore compatibility (ADR-015)
INSERT INTO kg_api.schema_migrations (version, description)
VALUES (15, 'Probabilistic Vocabulary Categorization (ADR-047)')
ON CONFLICT (version) DO NOTHING;

-- public.schema_migrations: For migration tracking
INSERT INTO public.schema_migrations (version, name)
VALUES (15, 'probabilistic_vocabulary_categorization')
ON CONFLICT (version) DO NOTHING;
