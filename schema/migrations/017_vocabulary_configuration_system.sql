-- Migration 017: Vocabulary Configuration System
-- Adds aggressiveness profiles table for Bezier curve parameters
-- Updates vocabulary thresholds (vocab_emergency: 200 → 300)

-- ============================================================================
-- Update Existing Vocabulary Configuration
-- ============================================================================

-- Update vocab_emergency threshold from 200 to 300
UPDATE kg_api.vocabulary_config
SET value = '300', description = 'Hard limit - blocks new additions (EMERGENCY threshold, increased from 200)'
WHERE key = 'vocab_emergency';

-- Add consolidation threshold if not exists
INSERT INTO kg_api.vocabulary_config (key, value, description, updated_by) VALUES
    ('consolidation_similarity_threshold', '0.90', 'Minimum similarity for auto-merge (0.0-1.0)', 'system')
ON CONFLICT (key) DO NOTHING;

-- ============================================================================
-- Aggressiveness Profiles Table
-- ============================================================================

-- Table already created from previous migration attempt, ensure it has correct structure
-- If it doesn't exist, CREATE TABLE IF NOT EXISTS will create it

CREATE TABLE IF NOT EXISTS kg_api.aggressiveness_profiles (
    profile_name VARCHAR(50) PRIMARY KEY,
    control_x1 FLOAT NOT NULL CHECK (control_x1 >= 0.0 AND control_x1 <= 1.0),
    control_y1 FLOAT NOT NULL,
    control_x2 FLOAT NOT NULL CHECK (control_x2 >= 0.0 AND control_x2 <= 1.0),
    control_y2 FLOAT NOT NULL,
    description TEXT,
    is_builtin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Seed builtin aggressiveness profiles
-- Based on aggressiveness_curve.py:AGGRESSIVENESS_CURVES
INSERT INTO kg_api.aggressiveness_profiles (profile_name, control_x1, control_y1, control_x2, control_y2, description, is_builtin) VALUES
    ('linear', 0.0, 0.0, 1.0, 1.0, 'Constant rate increase. Predictable, good for testing.', TRUE),
    ('ease', 0.25, 0.1, 0.25, 1.0, 'CSS default. Balanced acceleration.', TRUE),
    ('ease-in', 0.42, 0.0, 1.0, 1.0, 'Slow start, fast end. Gradual then sharp.', TRUE),
    ('ease-out', 0.0, 0.0, 0.58, 1.0, 'Fast start, slow end. Sharp then gradual.', TRUE),
    ('ease-in-out', 0.42, 0.0, 0.58, 1.0, 'Smooth S-curve. Balanced transitions.', TRUE),
    ('aggressive', 0.1, 0.0, 0.9, 1.0, 'RECOMMENDED: Stay passive until 75%, then sharp acceleration. Best for production - avoids premature optimization.', TRUE),
    ('gentle', 0.5, 0.5, 0.5, 0.5, 'Very gradual. Good for high-churn environments.', TRUE),
    ('exponential', 0.7, 0.0, 0.84, 0.0, 'Explosive near limit. Use when capacity is strict.', TRUE)
ON CONFLICT (profile_name) DO NOTHING;

-- ============================================================================
-- Helper Functions
-- ============================================================================

-- Drop existing function to avoid parameter name conflicts
DROP FUNCTION IF EXISTS kg_api.get_vocab_config(VARCHAR, TEXT);

-- Function to get vocabulary config value
CREATE FUNCTION kg_api.get_vocab_config(lookup_key VARCHAR, fallback TEXT DEFAULT NULL)
RETURNS TEXT AS $$
DECLARE
    result TEXT;
BEGIN
    SELECT value INTO result
    FROM kg_api.vocabulary_config
    WHERE key = lookup_key;

    IF result IS NULL THEN
        RETURN fallback;
    END IF;

    RETURN result;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION kg_api.get_vocab_config IS 'Retrieve vocabulary configuration value with optional fallback';

-- Function to get aggressiveness profile
CREATE OR REPLACE FUNCTION kg_api.get_aggressiveness_profile(profile VARCHAR)
RETURNS TABLE (
    profile_name VARCHAR,
    control_x1 FLOAT,
    control_y1 FLOAT,
    control_x2 FLOAT,
    control_y2 FLOAT,
    description TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.profile_name,
        p.control_x1,
        p.control_y1,
        p.control_x2,
        p.control_y2,
        p.description
    FROM kg_api.aggressiveness_profiles p
    WHERE p.profile_name = profile;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION kg_api.get_aggressiveness_profile IS 'Retrieve Bezier curve parameters for aggressiveness profile';

-- ============================================================================
-- Update Triggers
-- ============================================================================

-- Create trigger function for aggressiveness_profiles if not exists
CREATE OR REPLACE FUNCTION kg_api.update_aggressiveness_profiles_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop and recreate trigger to ensure it's attached correctly
DROP TRIGGER IF EXISTS aggressiveness_profiles_update_timestamp ON kg_api.aggressiveness_profiles;
CREATE TRIGGER aggressiveness_profiles_update_timestamp
    BEFORE UPDATE ON kg_api.aggressiveness_profiles
    FOR EACH ROW
    EXECUTE FUNCTION kg_api.update_aggressiveness_profiles_timestamp();

-- Create trigger function to prevent deletion of builtin profiles
CREATE OR REPLACE FUNCTION kg_api.prevent_builtin_profile_deletion()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.is_builtin = TRUE THEN
        RAISE EXCEPTION 'Cannot delete builtin aggressiveness profile: %', OLD.profile_name;
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

-- Drop and recreate trigger to ensure it's attached correctly
DROP TRIGGER IF EXISTS prevent_builtin_aggressiveness_profile_deletion ON kg_api.aggressiveness_profiles;
CREATE TRIGGER prevent_builtin_aggressiveness_profile_deletion
    BEFORE DELETE ON kg_api.aggressiveness_profiles
    FOR EACH ROW
    EXECUTE FUNCTION kg_api.prevent_builtin_profile_deletion();

-- ============================================================================
-- Indexes
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_aggressiveness_profiles_builtin
    ON kg_api.aggressiveness_profiles(is_builtin);

-- ============================================================================
-- Grants
-- ============================================================================

GRANT SELECT ON kg_api.vocabulary_config TO PUBLIC;
GRANT SELECT ON kg_api.aggressiveness_profiles TO PUBLIC;
