-- Migration 072: Grant admin oauth_clients:write (ADR-400, internet-hardening #441)
--
-- Migration 028 intended admin to have "full access" to oauth_clients (its own
-- comment says so) but seeded only read/create/delete — omitting write. As a
-- result a plain admin could create and delete OAuth clients but NOT modify
-- them: PATCH /oauth/clients/{id}, POST /oauth/clients/{id}/rotate-secret and
-- DELETE /oauth/tokens/{hash} all check oauth_clients:write, so only
-- platform_admin passed. That asymmetry is an accidental lockout, not a
-- deliberate boundary. Seed the missing grant so admin's client management is
-- consistent (create + read + write + delete).
--
-- platform_admin already holds all four (028); read_only/contributor/curator
-- hold none — unchanged.

BEGIN;

INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
SELECT 'admin', 'oauth_clients', 'write', 'global', TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM kg_auth.role_permissions
    WHERE role_name = 'admin'
      AND resource_type = 'oauth_clients'
      AND action = 'write'
      AND scope_type = 'global'
);

INSERT INTO public.schema_migrations (version, name)
VALUES (72, 'admin_oauth_clients_write')
ON CONFLICT (version) DO NOTHING;

COMMIT;
