-- Migration 054: Add delete action to sources resource
-- Enables document-level deletion via DELETE /documents/{document_id}
--
-- Required for FUSE filesystem integration where users can `rm` individual documents.
-- Also needed for any client that calls the document delete API endpoint.

-- Skip if already applied
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.schema_migrations WHERE version = 54) THEN
        RAISE NOTICE 'Migration 054 already applied, skipping';
        RETURN;
    END IF;

    -- Add 'delete' to sources available_actions
    UPDATE kg_auth.resources
    SET available_actions = ARRAY['read', 'delete']
    WHERE resource_type = 'sources'
      AND NOT ('delete' = ANY(available_actions));

    -- Grant sources:delete to admin role
    INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
    SELECT 'admin', 'sources', 'delete', 'global', TRUE
    WHERE NOT EXISTS (
        SELECT 1 FROM kg_auth.role_permissions
        WHERE role_name = 'admin' AND resource_type = 'sources' AND action = 'delete'
    );

    -- Grant sources:delete to platform_admin role
    INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
    SELECT 'platform_admin', 'sources', 'delete', 'global', TRUE
    WHERE NOT EXISTS (
        SELECT 1 FROM kg_auth.role_permissions
        WHERE role_name = 'platform_admin' AND resource_type = 'sources' AND action = 'delete'
    );

    RAISE NOTICE 'Migration 054: Added sources:delete permission for admin and platform_admin';
END $$;

-- ===========================================================================
-- Record Migration
-- ===========================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (54, 'sources_delete_permission')
ON CONFLICT (version) DO NOTHING;
