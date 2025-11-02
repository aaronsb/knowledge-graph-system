-- Migration 022: OAuth 2.0 Client Management
-- ADR-054: OAuth 2.0 Client Management for Multi-Client Authentication
-- Date: 2025-11-02
-- Description: Implements OAuth 2.0 flows (Authorization Code + PKCE, Device Authorization Grant, Client Credentials)

BEGIN;

-- =============================================================================
-- PART 1: CREATE NEW OAUTH TABLES
-- =============================================================================

-- Table 1: OAuth Clients (Registered client applications)
CREATE TABLE IF NOT EXISTS kg_auth.oauth_clients (
    client_id VARCHAR(255) PRIMARY KEY,
    client_secret_hash VARCHAR(255),  -- bcrypt hash, NULL for public clients
    client_name VARCHAR(255) NOT NULL,
    client_type VARCHAR(50) NOT NULL CHECK (client_type IN ('public', 'confidential')),
    grant_types TEXT[] NOT NULL,  -- Allowed grant types
    redirect_uris TEXT[],  -- For authorization code flow
    scopes TEXT[],  -- Allowed scopes
    is_active BOOLEAN DEFAULT true,
    created_by INTEGER REFERENCES kg_auth.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

COMMENT ON TABLE kg_auth.oauth_clients IS 'OAuth 2.0 client applications registered to use the API';
COMMENT ON COLUMN kg_auth.oauth_clients.client_type IS 'public = no client secret (CLI, web apps), confidential = has client secret (MCP server)';
COMMENT ON COLUMN kg_auth.oauth_clients.grant_types IS 'Allowed OAuth grant types: authorization_code, urn:ietf:params:oauth:grant-type:device_code, client_credentials, refresh_token';

-- Table 2: OAuth Authorization Codes (Temporary codes for authorization code flow)
CREATE TABLE IF NOT EXISTS kg_auth.oauth_authorization_codes (
    code VARCHAR(255) PRIMARY KEY,
    client_id VARCHAR(255) NOT NULL REFERENCES kg_auth.oauth_clients(client_id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES kg_auth.users(id) ON DELETE CASCADE,
    redirect_uri TEXT NOT NULL,
    scopes TEXT[],
    code_challenge VARCHAR(255),  -- PKCE
    code_challenge_method VARCHAR(10) CHECK (code_challenge_method IN ('S256', 'plain')),
    expires_at TIMESTAMPTZ NOT NULL,  -- 10 minutes from creation
    used BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE kg_auth.oauth_authorization_codes IS 'Temporary authorization codes for OAuth Authorization Code flow (web apps)';
COMMENT ON COLUMN kg_auth.oauth_authorization_codes.code_challenge IS 'PKCE code challenge (hash of code verifier)';
COMMENT ON COLUMN kg_auth.oauth_authorization_codes.expires_at IS 'Authorization codes expire in 10 minutes';

-- Table 3: OAuth Device Codes (Device authorization codes for CLI flow)
CREATE TABLE IF NOT EXISTS kg_auth.oauth_device_codes (
    device_code VARCHAR(255) PRIMARY KEY,
    user_code VARCHAR(50) UNIQUE NOT NULL,  -- Human-friendly: ABCD-1234
    client_id VARCHAR(255) NOT NULL REFERENCES kg_auth.oauth_clients(client_id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES kg_auth.users(id) ON DELETE CASCADE,  -- NULL until authorized
    scopes TEXT[],
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'authorized', 'denied', 'expired')),
    expires_at TIMESTAMPTZ NOT NULL,  -- 10 minutes from creation
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE kg_auth.oauth_device_codes IS 'Device authorization codes for OAuth Device Authorization Grant flow (CLI tools)';
COMMENT ON COLUMN kg_auth.oauth_device_codes.user_code IS 'Human-friendly code displayed to user (e.g., ABCD-1234)';
COMMENT ON COLUMN kg_auth.oauth_device_codes.device_code IS 'Long code used by device for polling';
COMMENT ON COLUMN kg_auth.oauth_device_codes.expires_at IS 'Device codes expire in 10 minutes';

-- Table 4: OAuth Access Tokens (Issued access tokens)
CREATE TABLE IF NOT EXISTS kg_auth.oauth_access_tokens (
    token_hash VARCHAR(255) PRIMARY KEY,
    client_id VARCHAR(255) NOT NULL REFERENCES kg_auth.oauth_clients(client_id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES kg_auth.users(id) ON DELETE CASCADE,  -- NULL for client_credentials grant
    scopes TEXT[],
    expires_at TIMESTAMPTZ NOT NULL,  -- 1 hour from creation
    revoked BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE kg_auth.oauth_access_tokens IS 'OAuth access tokens issued to clients';
COMMENT ON COLUMN kg_auth.oauth_access_tokens.token_hash IS 'SHA256 hash of the actual token (tokens are not stored in plaintext)';
COMMENT ON COLUMN kg_auth.oauth_access_tokens.user_id IS 'NULL for client_credentials grant (machine-to-machine), set for user-delegated grants';
COMMENT ON COLUMN kg_auth.oauth_access_tokens.expires_at IS 'Access tokens expire in 1 hour';

-- Table 5: OAuth Refresh Tokens (Long-lived refresh tokens)
CREATE TABLE IF NOT EXISTS kg_auth.oauth_refresh_tokens (
    token_hash VARCHAR(255) PRIMARY KEY,
    client_id VARCHAR(255) NOT NULL REFERENCES kg_auth.oauth_clients(client_id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES kg_auth.users(id) ON DELETE CASCADE,
    scopes TEXT[],
    access_token_hash VARCHAR(255) REFERENCES kg_auth.oauth_access_tokens(token_hash) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,  -- 7-30 days based on client type
    revoked BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used TIMESTAMPTZ
);

COMMENT ON TABLE kg_auth.oauth_refresh_tokens IS 'OAuth refresh tokens for long-lived sessions';
COMMENT ON COLUMN kg_auth.oauth_refresh_tokens.expires_at IS 'Refresh tokens expire in 7 days (CLI) or 30 days (web)';
COMMENT ON COLUMN kg_auth.oauth_refresh_tokens.last_used IS 'Updated when refresh token is used to obtain new access token';

-- =============================================================================
-- PART 2: RENAME EXISTING TABLE
-- =============================================================================

-- Rename oauth_tokens to clarify it stores tokens FROM external providers (not issued by us)
ALTER TABLE IF EXISTS kg_auth.oauth_tokens RENAME TO oauth_external_provider_tokens;

COMMENT ON TABLE kg_auth.oauth_external_provider_tokens IS
  'OAuth tokens FROM external providers (Google, GitHub, etc.) - not tokens issued by our system';

-- =============================================================================
-- PART 3: DROP LEGACY TABLES
-- =============================================================================

-- Drop API keys table (replaced by OAuth)
DROP TABLE IF EXISTS kg_auth.api_keys CASCADE;

-- =============================================================================
-- PART 4: CREATE INDEXES FOR PERFORMANCE
-- =============================================================================

-- OAuth Clients indexes
CREATE INDEX IF NOT EXISTS idx_oauth_clients_active ON kg_auth.oauth_clients(is_active);
CREATE INDEX IF NOT EXISTS idx_oauth_clients_created_by ON kg_auth.oauth_clients(created_by);

-- OAuth Authorization Codes indexes
CREATE INDEX IF NOT EXISTS idx_oauth_auth_codes_client_id ON kg_auth.oauth_authorization_codes(client_id);
CREATE INDEX IF NOT EXISTS idx_oauth_auth_codes_user_id ON kg_auth.oauth_authorization_codes(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_auth_codes_expires_at ON kg_auth.oauth_authorization_codes(expires_at);
CREATE INDEX IF NOT EXISTS idx_oauth_auth_codes_used ON kg_auth.oauth_authorization_codes(used);

-- OAuth Device Codes indexes
CREATE INDEX IF NOT EXISTS idx_oauth_device_codes_client_id ON kg_auth.oauth_device_codes(client_id);
CREATE INDEX IF NOT EXISTS idx_oauth_device_codes_user_id ON kg_auth.oauth_device_codes(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_device_codes_status ON kg_auth.oauth_device_codes(status);
CREATE INDEX IF NOT EXISTS idx_oauth_device_codes_expires_at ON kg_auth.oauth_device_codes(expires_at);

-- OAuth Access Tokens indexes
CREATE INDEX IF NOT EXISTS idx_oauth_access_tokens_client_id ON kg_auth.oauth_access_tokens(client_id);
CREATE INDEX IF NOT EXISTS idx_oauth_access_tokens_user_id ON kg_auth.oauth_access_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_access_tokens_expires_at ON kg_auth.oauth_access_tokens(expires_at);
CREATE INDEX IF NOT EXISTS idx_oauth_access_tokens_revoked ON kg_auth.oauth_access_tokens(revoked);

-- OAuth Refresh Tokens indexes
CREATE INDEX IF NOT EXISTS idx_oauth_refresh_tokens_client_id ON kg_auth.oauth_refresh_tokens(client_id);
CREATE INDEX IF NOT EXISTS idx_oauth_refresh_tokens_user_id ON kg_auth.oauth_refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_refresh_tokens_expires_at ON kg_auth.oauth_refresh_tokens(expires_at);
CREATE INDEX IF NOT EXISTS idx_oauth_refresh_tokens_revoked ON kg_auth.oauth_refresh_tokens(revoked);
CREATE INDEX IF NOT EXISTS idx_oauth_refresh_tokens_access_token ON kg_auth.oauth_refresh_tokens(access_token_hash);

-- =============================================================================
-- PART 5: SEED BUILTIN CLIENTS
-- =============================================================================

-- Insert the three builtin OAuth clients
-- Note: For kg-mcp (confidential client), client_secret must be generated separately via CLI
INSERT INTO kg_auth.oauth_clients (client_id, client_name, client_type, grant_types, redirect_uris, scopes, metadata)
VALUES
  -- 1. Knowledge Graph CLI (public client, device flow)
  (
    'kg-cli',
    'Knowledge Graph CLI',
    'public',
    ARRAY['urn:ietf:params:oauth:grant-type:device_code', 'refresh_token'],
    NULL,
    ARRAY['read:*', 'write:*'],
    '{"description": "Official CLI tool for knowledge graph operations", "builtin": true}'::jsonb
  ),

  -- 2. Knowledge Graph Visualizer (public client, authorization code flow)
  (
    'kg-viz',
    'Knowledge Graph Visualizer',
    'public',
    ARRAY['authorization_code', 'refresh_token'],
    ARRAY['http://localhost:3000/callback', 'https://viz.kg.example.com/callback'],
    ARRAY['read:*', 'write:*'],
    '{"description": "Web-based graph visualization interface", "builtin": true}'::jsonb
  ),

  -- 3. Knowledge Graph MCP Server (confidential client, client credentials flow)
  (
    'kg-mcp',
    'Knowledge Graph MCP Server',
    'confidential',
    ARRAY['client_credentials'],
    NULL,
    ARRAY['read:*', 'write:*'],
    '{"description": "Model Context Protocol server for AI assistants", "builtin": true}'::jsonb
  )
ON CONFLICT (client_id) DO NOTHING;

-- =============================================================================
-- MIGRATION VERIFICATION
-- =============================================================================

DO $$
BEGIN
    -- Check that all 5 new OAuth tables exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'kg_auth' AND table_name = 'oauth_clients'
    ) THEN
        RAISE EXCEPTION 'Migration failed: oauth_clients table not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'kg_auth' AND table_name = 'oauth_authorization_codes'
    ) THEN
        RAISE EXCEPTION 'Migration failed: oauth_authorization_codes table not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'kg_auth' AND table_name = 'oauth_device_codes'
    ) THEN
        RAISE EXCEPTION 'Migration failed: oauth_device_codes table not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'kg_auth' AND table_name = 'oauth_access_tokens'
    ) THEN
        RAISE EXCEPTION 'Migration failed: oauth_access_tokens table not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'kg_auth' AND table_name = 'oauth_refresh_tokens'
    ) THEN
        RAISE EXCEPTION 'Migration failed: oauth_refresh_tokens table not created';
    END IF;

    -- Check that table was renamed
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'kg_auth' AND table_name = 'oauth_tokens'
    ) THEN
        RAISE EXCEPTION 'Migration failed: oauth_tokens table still exists (should be renamed)';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'kg_auth' AND table_name = 'oauth_external_provider_tokens'
    ) THEN
        RAISE WARNING 'oauth_external_provider_tokens table does not exist (may not have existed before)';
    END IF;

    -- Check that api_keys table was dropped
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'kg_auth' AND table_name = 'api_keys'
    ) THEN
        RAISE EXCEPTION 'Migration failed: api_keys table still exists (should be dropped)';
    END IF;

    -- Check that builtin clients were seeded
    IF (SELECT COUNT(*) FROM kg_auth.oauth_clients WHERE client_id IN ('kg-cli', 'kg-viz', 'kg-mcp')) < 3 THEN
        RAISE EXCEPTION 'Migration failed: builtin OAuth clients not seeded';
    END IF;

    RAISE NOTICE 'Migration 022 completed successfully';
    RAISE NOTICE '  ✓ Created 5 new OAuth tables';
    RAISE NOTICE '  ✓ Renamed oauth_tokens → oauth_external_provider_tokens';
    RAISE NOTICE '  ✓ Dropped api_keys table';
    RAISE NOTICE '  ✓ Added performance indexes';
    RAISE NOTICE '  ✓ Seeded 3 builtin clients (kg-cli, kg-viz, kg-mcp)';
    RAISE NOTICE '';
    RAISE NOTICE 'OAuth clients registered:';
    RAISE NOTICE '  - kg-cli: Device Authorization Grant (for CLI)';
    RAISE NOTICE '  - kg-viz: Authorization Code + PKCE (for web app)';
    RAISE NOTICE '  - kg-mcp: Client Credentials (for MCP server)';
    RAISE NOTICE '';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '  1. Generate client secret for kg-mcp: kg admin oauth clients rotate-secret kg-mcp';
    RAISE NOTICE '  2. Implement OAuth API endpoints (Phase 2)';
    RAISE NOTICE '  3. Update kg CLI to use device flow (Phase 3)';
    RAISE NOTICE '  4. Remove legacy /auth/login endpoint';
END $$;

-- =============================================================================
-- RECORD MIGRATION
-- =============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (22, 'oauth_client_management')
ON CONFLICT (version) DO NOTHING;

COMMIT;
