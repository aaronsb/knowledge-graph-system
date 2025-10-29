-- Migration 020: Track Authenticated Users in Jobs
-- Convert jobs.client_id from TEXT to INTEGER and link to kg_auth.users
--
-- Context:
-- - Previously jobs used client_id TEXT with placeholder value "anonymous"
-- - Now jobs should track the authenticated user from JWT tokens
-- - Leverages existing kg_auth.users table (id SERIAL PRIMARY KEY)
-- - Admin user is id=1 for simplicity (no UUIDs needed)
--
-- Changes:
-- 1. Ensure admin user exists with id=1
-- 2. Convert client_id TEXT → INTEGER (map "anonymous" → 1)
-- 3. Add foreign key to kg_auth.users
-- 4. Rename client_id → user_id for clarity
--
-- Related: Authentication system (ADR-027, ADR-028)

BEGIN;

-- Step 1: Ensure admin user exists with predictable id=1
-- (Safe with ON CONFLICT - won't override if already exists)
INSERT INTO kg_auth.users (id, username, password_hash, primary_role, created_at)
VALUES (
    1,
    'admin',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5oCDxDO1b5tZK',  -- password: 'admin' (CHANGE IN PRODUCTION!)
    'admin',
    NOW()
)
ON CONFLICT (id) DO NOTHING;

-- Reset sequence to ensure next user gets id > 1
SELECT setval('kg_auth.users_id_seq', (SELECT COALESCE(MAX(id), 1) FROM kg_auth.users));

-- Step 2: Add temporary column for integer user IDs
ALTER TABLE kg_api.jobs
    ADD COLUMN user_id INTEGER;

-- Step 3: Migrate existing data
-- Map all "anonymous" entries to admin user (id=1)
-- Any other values also map to admin (cleanup weird data)
UPDATE kg_api.jobs
SET user_id = 1;

-- Step 4: Make user_id NOT NULL and add foreign key
ALTER TABLE kg_api.jobs
    ALTER COLUMN user_id SET NOT NULL,
    ADD CONSTRAINT fk_jobs_user FOREIGN KEY (user_id) REFERENCES kg_auth.users(id);

-- Step 5: Drop old client_id column
ALTER TABLE kg_api.jobs
    DROP COLUMN client_id;

-- Step 6: Add index for performance (user's jobs lookup)
CREATE INDEX idx_jobs_user_id ON kg_api.jobs(user_id);

-- Add comment for documentation
COMMENT ON COLUMN kg_api.jobs.user_id IS 'User who submitted the job (FK to kg_auth.users.id)';

COMMIT;
