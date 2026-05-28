-- Migration 071: Open-registration feature flag (ADR-400, internet-hardening #431)
--
-- POST /auth/register historically honored a client-supplied role and was always
-- open. Two hardening controls land together:
--   1. The route now ignores any client-supplied role and forces 'read_only'
--      (privilege escalation fix — handled in api/app/routes/auth.py).
--   2. This flag lets an internet-facing deployment turn open self-registration
--      off without a code change. Defaults to 'true' so existing dev/standalone
--      installs keep current behavior; operators harden by setting it 'false'.
--
-- Read via kg_api.get_platform_config('registration_enabled') (added in 031).
-- A missing/non-'false' value is treated as enabled, so absence never locks out
-- registration in environments that skipped this migration.

BEGIN;

INSERT INTO kg_api.platform_config (key, value, description) VALUES
    ('registration_enabled', 'true', 'Allow open self-registration via POST /auth/register (true/false). Set false for internet-facing deployments; elevated roles are assigned only through the users:create-gated admin path.')
ON CONFLICT (key) DO NOTHING;

INSERT INTO public.schema_migrations (version, name)
VALUES (71, 'registration_enabled_flag')
ON CONFLICT (version) DO NOTHING;

COMMIT;
