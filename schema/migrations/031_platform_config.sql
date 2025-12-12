-- Migration: 031_platform_config
-- Description: Platform lifecycle configuration for operator-as-control-plane pattern
-- Date: 2025-12-11
--
-- Stores platform mode choices (dev/prod, GPU mode) so the operator can
-- restart the system with the same configuration without re-prompting.
-- Inspired by Kubernetes operator pattern where the control plane remembers
-- desired state and reconciles actual state to match.

-- Platform configuration key-value store
CREATE TABLE IF NOT EXISTS kg_api.platform_config (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by VARCHAR(100) DEFAULT 'system'
);

-- Add comment
COMMENT ON TABLE kg_api.platform_config IS 'Platform lifecycle configuration for operator control plane (ADR-061)';

-- Insert default configuration
INSERT INTO kg_api.platform_config (key, value, description) VALUES
    ('dev_mode', 'false', 'Enable development mode with hot reload (true/false)'),
    ('gpu_mode', 'auto', 'GPU acceleration mode: auto, nvidia, mac, cpu'),
    ('initialized_at', '', 'Timestamp of initial quickstart setup'),
    ('initialized_by', '', 'How platform was initialized (quickstart/manual)'),
    ('compose_files', '', 'Comma-separated list of compose files used')
ON CONFLICT (key) DO NOTHING;

-- Function to update platform config with timestamp
CREATE OR REPLACE FUNCTION kg_api.set_platform_config(
    p_key VARCHAR(100),
    p_value TEXT,
    p_updated_by VARCHAR(100) DEFAULT 'system'
) RETURNS VOID AS $$
BEGIN
    INSERT INTO kg_api.platform_config (key, value, updated_at, updated_by)
    VALUES (p_key, p_value, NOW(), p_updated_by)
    ON CONFLICT (key) DO UPDATE SET
        value = EXCLUDED.value,
        updated_at = NOW(),
        updated_by = EXCLUDED.updated_by;
END;
$$ LANGUAGE plpgsql;

-- Function to get platform config value
CREATE OR REPLACE FUNCTION kg_api.get_platform_config(p_key VARCHAR(100))
RETURNS TEXT AS $$
DECLARE
    v_value TEXT;
BEGIN
    SELECT value INTO v_value FROM kg_api.platform_config WHERE key = p_key;
    RETURN v_value;
END;
$$ LANGUAGE plpgsql;
