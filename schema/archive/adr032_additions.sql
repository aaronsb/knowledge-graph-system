-- =============================================================================
-- AUTOMATIC EDGE VOCABULARY EXPANSION (ADR-032)
-- =============================================================================

-- Add embedding storage to existing relationship_vocabulary table
ALTER TABLE kg_api.relationship_vocabulary
ADD COLUMN IF NOT EXISTS embedding vector(1536),  -- OpenAI ada-002 dimension (1536)
ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(100),  -- Track model used
ADD COLUMN IF NOT EXISTS embedding_generated_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_vocab_embedding_model ON kg_api.relationship_vocabulary(embedding_model)
WHERE embedding IS NOT NULL;

COMMENT ON COLUMN kg_api.relationship_vocabulary.embedding IS 'Cached embedding vector for synonym detection (ADR-032)';
COMMENT ON COLUMN kg_api.relationship_vocabulary.embedding_model IS 'Model used to generate embedding (e.g., text-embedding-ada-002)';

-- Vocabulary History (detailed change tracking)
CREATE TABLE IF NOT EXISTS kg_api.vocabulary_history (
    id SERIAL PRIMARY KEY,
    relationship_type VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL CHECK (action IN ('added', 'merged', 'pruned', 'deprecated', 'reactivated')),
    performed_by VARCHAR(100) NOT NULL,
    performed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    target_type VARCHAR(100),  -- For merges: what it merged into
    reason TEXT,
    metadata JSONB,  -- value_score, similarity, affected_edges, etc.
    aggressiveness NUMERIC(4,3),  -- Aggressiveness at time of action
    zone VARCHAR(20),  -- Zone at time of action (safe/active/critical/emergency)
    vocab_size_before INTEGER,  -- Size before action
    vocab_size_after INTEGER   -- Size after action
);

CREATE INDEX IF NOT EXISTS idx_vocab_history_type ON kg_api.vocabulary_history(relationship_type);
CREATE INDEX IF NOT EXISTS idx_vocab_history_action ON kg_api.vocabulary_history(action);
CREATE INDEX IF NOT EXISTS idx_vocab_history_performed_at ON kg_api.vocabulary_history(performed_at DESC);
CREATE INDEX IF NOT EXISTS idx_vocab_history_performed_by ON kg_api.vocabulary_history(performed_by);

COMMENT ON TABLE kg_api.vocabulary_history IS 'Detailed vocabulary change tracking with context (ADR-032)';

-- Pruning Recommendations (pending actions)
CREATE TABLE IF NOT EXISTS kg_api.pruning_recommendations (
    id SERIAL PRIMARY KEY,
    relationship_type VARCHAR(100) NOT NULL,
    target_type VARCHAR(100),  -- For merges: preserve this type
    action_type VARCHAR(50) NOT NULL CHECK (action_type IN ('merge', 'prune', 'deprecate', 'skip')),
    review_level VARCHAR(20) NOT NULL CHECK (review_level IN ('none', 'ai', 'human')),
    reasoning TEXT NOT NULL,
    similarity NUMERIC(4,3),  -- For merges: synonym similarity score
    value_score NUMERIC(10,2),  -- From vocabulary scoring
    metadata JSONB,  -- Full context (edge_count, bridges, trends, etc.)
    status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'executed', 'expired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by VARCHAR(100),
    reviewer_notes TEXT,
    executed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ  -- Auto-expire old recommendations
);

CREATE INDEX IF NOT EXISTS idx_pruning_recs_type ON kg_api.pruning_recommendations(relationship_type);
CREATE INDEX IF NOT EXISTS idx_pruning_recs_status ON kg_api.pruning_recommendations(status);
CREATE INDEX IF NOT EXISTS idx_pruning_recs_review_level ON kg_api.pruning_recommendations(review_level);
CREATE INDEX IF NOT EXISTS idx_pruning_recs_created_at ON kg_api.pruning_recommendations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pruning_recs_expires_at ON kg_api.pruning_recommendations(expires_at)
WHERE expires_at IS NOT NULL;

COMMENT ON TABLE kg_api.pruning_recommendations IS 'Pending vocabulary management actions (merges, prunes, deprecations) - ADR-032';
COMMENT ON COLUMN kg_api.pruning_recommendations.review_level IS 'Approval level: none (auto-execute), ai (AI-approved), human (needs curator)';

-- Vocabulary Configuration (system settings)
CREATE TABLE IF NOT EXISTS kg_api.vocabulary_config (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by VARCHAR(100)
);

-- Seed default configuration
INSERT INTO kg_api.vocabulary_config (key, value, description, updated_by)
VALUES
    ('vocab_min', '30', 'Minimum vocabulary size (protected core types)', 'system'),
    ('vocab_max', '90', 'Maximum vocabulary size (soft limit)', 'system'),
    ('vocab_emergency', '200', 'Emergency threshold (aggressive pruning)', 'system'),
    ('aggressiveness_profile', 'aggressive', 'Bezier curve profile for pruning aggressiveness', 'system'),
    ('pruning_mode', 'hitl', 'Decision mode: naive, hitl, aitl', 'system'),
    ('embedding_model', 'text-embedding-ada-002', 'OpenAI model for embeddings', 'system'),
    ('auto_expand_enabled', 'false', 'Enable automatic vocabulary expansion', 'system'),
    ('synonym_threshold_strong', '0.90', 'Strong synonym threshold (auto-merge)', 'system'),
    ('synonym_threshold_moderate', '0.70', 'Moderate synonym threshold (review)', 'system'),
    ('low_value_threshold', '1.0', 'Value score threshold for pruning consideration', 'system')
ON CONFLICT (key) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_vocab_config_updated_at ON kg_api.vocabulary_config(updated_at DESC);

COMMENT ON TABLE kg_api.vocabulary_config IS 'System configuration for automatic vocabulary management (ADR-032)';

-- Function to expire old recommendations
CREATE OR REPLACE FUNCTION expire_old_recommendations(days_threshold INTEGER DEFAULT 7)
RETURNS INTEGER AS $$
DECLARE
    expired_count INTEGER;
BEGIN
    UPDATE kg_api.pruning_recommendations
    SET status = 'expired'
    WHERE status = 'pending'
      AND created_at < NOW() - (days_threshold || ' days')::INTERVAL
      AND expires_at IS NULL;  -- Only expire if no explicit expiry set
    
    GET DIAGNOSTICS expired_count = ROW_COUNT;
    RETURN expired_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION expire_old_recommendations IS 'Expire pending recommendations older than threshold (ADR-032)';

