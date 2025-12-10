/**
 * Roles Tab Component
 *
 * RBAC role and permission management for admins.
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  ShieldCheck,
  FileText,
  RefreshCw,
  Loader2,
  Plus,
  ChevronRight,
  ChevronDown,
  GitBranch,
  Trash2,
  X,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useAuthStore } from '../../store/authStore';
import { Section } from './components';
import type { RoleInfo, ResourceInfo, PermissionInfo } from './types';

interface RolesTabProps {
  onError: (error: string) => void;
  onSuccess: (message: string) => void;
}

export const RolesTab: React.FC<RolesTabProps> = ({ onError, onSuccess }) => {
  const { hasPermission } = useAuthStore();

  const canCreateRoles = hasPermission('rbac', 'create');
  const canEditRoles = hasPermission('rbac', 'write');
  const canDeleteRoles = hasPermission('rbac', 'delete');

  // Data states
  const [roles, setRoles] = useState<RoleInfo[]>([]);
  const [resources, setResources] = useState<ResourceInfo[]>([]);
  const [rolePermissions, setRolePermissions] = useState<PermissionInfo[]>([]);
  const [loading, setLoading] = useState(true);

  // UI states
  const [showCreateRoleModal, setShowCreateRoleModal] = useState(false);
  const [newRoleData, setNewRoleData] = useState({ role_name: '', display_name: '', description: '', parent_role: '' });
  const [creatingRole, setCreatingRole] = useState(false);
  const [confirmDeleteRole, setConfirmDeleteRole] = useState<RoleInfo | null>(null);
  const [deletingRole, setDeletingRole] = useState(false);
  const [expandedRoles, setExpandedRoles] = useState<Set<string>>(new Set());
  const [showResourcesPanel, setShowResourcesPanel] = useState(false);
  // Track which permission dropdown is open: "roleName:resourceType" or null
  const [openPermissionDropdown, setOpenPermissionDropdown] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close permission dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setOpenPermissionDropdown(null);
      }
    };

    if (openPermissionDropdown) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [openPermissionDropdown]);

  // Load data
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [rolesData, resourcesData] = await Promise.all([
        apiClient.listRoles(),
        apiClient.listResources(),
      ]);
      setRoles(rolesData);
      setResources(resourcesData);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const loadRolePermissions = async (roleName: string) => {
    try {
      const permissions = await apiClient.listPermissions({ role_name: roleName });
      setRolePermissions(permissions);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to load role permissions');
    }
  };

  const handleCreateRole = async () => {
    if (!newRoleData.role_name.trim() || !newRoleData.display_name.trim()) return;
    setCreatingRole(true);
    try {
      await apiClient.createRole({
        role_name: newRoleData.role_name.trim().toLowerCase().replace(/\s+/g, '_'),
        display_name: newRoleData.display_name.trim(),
        description: newRoleData.description.trim() || undefined,
        parent_role: newRoleData.parent_role || undefined,
      });
      onSuccess(`Role '${newRoleData.display_name}' created successfully`);
      setNewRoleData({ role_name: '', display_name: '', description: '', parent_role: '' });
      setShowCreateRoleModal(false);
      const rolesData = await apiClient.listRoles();
      setRoles(rolesData);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to create role');
    } finally {
      setCreatingRole(false);
    }
  };

  const handleDeleteRole = async () => {
    if (!confirmDeleteRole) return;
    setDeletingRole(true);
    try {
      await apiClient.deleteRole(confirmDeleteRole.role_name);
      onSuccess(`Role '${confirmDeleteRole.display_name}' deleted`);
      setConfirmDeleteRole(null);
      const rolesData = await apiClient.listRoles();
      setRoles(rolesData);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to delete role');
    } finally {
      setDeletingRole(false);
    }
  };

  const handleGrantPermission = async (roleName: string, resourceType: string, action: string) => {
    try {
      await apiClient.grantPermission({
        role_name: roleName,
        resource_type: resourceType,
        action: action,
      });
      onSuccess(`Permission granted: ${resourceType}:${action}`);
      await loadRolePermissions(roleName);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to grant permission');
    }
  };

  const handleRevokePermission = async (permissionId: number, roleName: string) => {
    try {
      await apiClient.revokePermission(permissionId);
      onSuccess('Permission revoked');
      await loadRolePermissions(roleName);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to revoke permission');
    }
  };

  const toggleRoleExpanded = (roleName: string) => {
    const newExpanded = new Set(expandedRoles);
    if (newExpanded.has(roleName)) {
      newExpanded.delete(roleName);
    } else {
      newExpanded.add(roleName);
      loadRolePermissions(roleName);
    }
    setExpandedRoles(newExpanded);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    );
  }

  return (
    <>
      {/* Create Role Button */}
      {canCreateRoles && (
        <div className="flex justify-between items-center mb-4">
          <button
            onClick={() => setShowCreateRoleModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Create Role
          </button>
          <button
            onClick={() => setShowResourcesPanel(!showResourcesPanel)}
            className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors"
          >
            <FileText className="w-4 h-4" />
            {showResourcesPanel ? 'Hide' : 'Show'} Resources
          </button>
        </div>
      )}

      {/* Resources Panel */}
      {showResourcesPanel && (
        <Section
          title="Available Resources"
          icon={<FileText className="w-5 h-5" />}
        >
          <p className="text-sm text-muted-foreground mb-4">
            Resources and actions that can be granted to roles.
          </p>
          <div className="space-y-2">
            {resources.map((resource) => (
              <div
                key={resource.resource_type}
                className="p-3 bg-muted/50 rounded-lg"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <span className="font-medium text-foreground">
                      {resource.resource_type}
                    </span>
                    {resource.description && (
                      <p className="text-sm text-muted-foreground mt-0.5">
                        {resource.description}
                      </p>
                    )}
                  </div>
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {resource.available_actions.map((action) => (
                    <span
                      key={action}
                      className="px-2 py-0.5 text-xs bg-primary/10 text-primary rounded"
                    >
                      {action}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Roles List */}
      <Section
        title="Roles"
        icon={<ShieldCheck className="w-5 h-5" />}
        action={
          <button
            onClick={loadData}
            className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        }
      >
        <div className="space-y-2">
          {roles.map((role) => (
            <div
              key={role.role_name}
              className="border border-border rounded-lg overflow-hidden"
            >
              {/* Role Header */}
              <div
                className={`p-4 cursor-pointer hover:bg-muted/50 transition-colors ${
                  expandedRoles.has(role.role_name) ? 'bg-muted/30' : ''
                }`}
                onClick={() => toggleRoleExpanded(role.role_name)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <button className="p-0.5">
                      {expandedRoles.has(role.role_name) ? (
                        <ChevronDown className="w-4 h-4 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-muted-foreground" />
                      )}
                    </button>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-foreground">
                          {role.display_name}
                        </span>
                        <span className="text-xs text-muted-foreground font-mono">
                          ({role.role_name})
                        </span>
                        {role.is_builtin && (
                          <span className="px-1.5 py-0.5 text-xs rounded bg-purple-500/20 text-purple-400">
                            built-in
                          </span>
                        )}
                        {!role.is_active && (
                          <span className="px-1.5 py-0.5 text-xs rounded bg-destructive/20 text-destructive">
                            inactive
                          </span>
                        )}
                      </div>
                      {role.description && (
                        <p className="text-sm text-muted-foreground mt-1">
                          {role.description}
                        </p>
                      )}
                      {role.parent_role && (
                        <div className="flex items-center gap-1 mt-1 text-xs text-muted-foreground">
                          <GitBranch className="w-3 h-3" />
                          <span>inherits from</span>
                          <span className="font-medium">{role.parent_role}</span>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                    {canDeleteRoles && !role.is_builtin && (
                      <button
                        onClick={() => setConfirmDeleteRole(role)}
                        className="p-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded transition-colors"
                        title="Delete role"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Role Permissions (Expanded) */}
              {expandedRoles.has(role.role_name) && (
                <div className="border-t border-border p-4 bg-muted/20">
                  <h4 className="text-sm font-medium text-foreground mb-3">
                    Permissions
                  </h4>
                  {rolePermissions.filter(p => p.role_name === role.role_name).length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      {role.parent_role
                        ? `Inherits all permissions from ${role.parent_role}`
                        : 'No direct permissions assigned'}
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {/* Group permissions by resource */}
                      {Object.entries(
                        rolePermissions
                          .filter(p => p.role_name === role.role_name)
                          .reduce((acc, p) => {
                            if (!acc[p.resource_type]) acc[p.resource_type] = [];
                            acc[p.resource_type].push(p);
                            return acc;
                          }, {} as Record<string, PermissionInfo[]>)
                      ).map(([resourceType, perms]) => (
                        <div key={resourceType} className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-medium text-foreground min-w-[120px]">
                            {resourceType}:
                          </span>
                          {perms.map((p) => (
                            <span
                              key={p.id}
                              className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded ${
                                p.inherited_from
                                  ? 'bg-muted text-muted-foreground'
                                  : 'bg-status-active/20 text-status-active'
                              }`}
                            >
                              {p.action}
                              {p.inherited_from && (
                                <span className="text-muted-foreground">
                                  (from {p.inherited_from})
                                </span>
                              )}
                              {canEditRoles && !p.inherited_from && (
                                <button
                                  onClick={() => handleRevokePermission(p.id, role.role_name)}
                                  className="ml-1 hover:text-destructive"
                                  title="Revoke permission"
                                >
                                  <X className="w-3 h-3" />
                                </button>
                              )}
                            </span>
                          ))}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Add Permission */}
                  {canEditRoles && (
                    <div className="mt-4 pt-4 border-t border-border pb-32">
                      <h5 className="text-xs font-medium text-muted-foreground mb-2">
                        Grant Permission
                      </h5>
                      <div className="flex flex-wrap gap-2">
                        {resources.map((resource) => {
                          const dropdownKey = `${role.role_name}:${resource.resource_type}`;
                          const isOpen = openPermissionDropdown === dropdownKey;
                          return (
                            <div
                              key={resource.resource_type}
                              className="relative"
                              ref={isOpen ? dropdownRef : null}
                            >
                              <button
                                onClick={() => setOpenPermissionDropdown(isOpen ? null : dropdownKey)}
                                className={`px-2 py-1 text-xs rounded transition-colors ${
                                  isOpen
                                    ? 'bg-primary text-primary-foreground'
                                    : 'bg-muted hover:bg-muted/80'
                                }`}
                              >
                                {resource.resource_type}
                              </button>
                              {isOpen && (
                                <div className="absolute left-0 top-full mt-1 z-10 bg-card border border-border rounded shadow-lg p-2 min-w-[120px]">
                                  {resource.available_actions.map((action) => {
                                    const hasPermission = rolePermissions.some(
                                      p => p.role_name === role.role_name &&
                                           p.resource_type === resource.resource_type &&
                                           p.action === action
                                    );
                                    return (
                                      <button
                                        key={action}
                                        onClick={() => {
                                          handleGrantPermission(role.role_name, resource.resource_type, action);
                                          setOpenPermissionDropdown(null);
                                        }}
                                        disabled={hasPermission}
                                        className={`block w-full text-left px-2 py-1 text-xs rounded ${
                                          hasPermission
                                            ? 'text-muted-foreground cursor-not-allowed'
                                            : 'hover:bg-muted'
                                        }`}
                                      >
                                        {action}
                                        {hasPermission && ' ✓'}
                                      </button>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </Section>

      {/* Create Role Modal */}
      {showCreateRoleModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card rounded-lg shadow-xl w-full max-w-md mx-4 border border-border">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <h3 className="font-semibold text-foreground flex items-center gap-2">
                <ShieldCheck className="w-5 h-5" />
                Create Custom Role
              </h3>
              <button
                onClick={() => {
                  setShowCreateRoleModal(false);
                  setNewRoleData({ role_name: '', display_name: '', description: '', parent_role: '' });
                }}
                className="p-1 text-muted-foreground hover:text-foreground rounded"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Role Name (ID) <span className="text-destructive">*</span>
                </label>
                <input
                  type="text"
                  value={newRoleData.role_name}
                  onChange={(e) => setNewRoleData({ ...newRoleData, role_name: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_') })}
                  placeholder="e.g., data_analyst"
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                />
                <p className="text-xs text-muted-foreground mt-1">Lowercase letters, numbers, and underscores only</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Display Name <span className="text-destructive">*</span>
                </label>
                <input
                  type="text"
                  value={newRoleData.display_name}
                  onChange={(e) => setNewRoleData({ ...newRoleData, display_name: e.target.value })}
                  placeholder="e.g., Data Analyst"
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Description
                </label>
                <textarea
                  value={newRoleData.description}
                  onChange={(e) => setNewRoleData({ ...newRoleData, description: e.target.value })}
                  placeholder="Describe the role's purpose..."
                  rows={2}
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Parent Role (Inherits Permissions)
                </label>
                <select
                  value={newRoleData.parent_role}
                  onChange={(e) => setNewRoleData({ ...newRoleData, parent_role: e.target.value })}
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="">No parent (standalone role)</option>
                  {roles.filter(r => r.is_active).map(role => (
                    <option key={role.role_name} value={role.role_name}>
                      {role.display_name} ({role.role_name})
                    </option>
                  ))}
                </select>
                <p className="text-xs text-muted-foreground mt-1">
                  Child roles inherit all permissions from their parent
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-2 px-4 py-3 border-t border-border">
              <button
                onClick={() => {
                  setShowCreateRoleModal(false);
                  setNewRoleData({ role_name: '', display_name: '', description: '', parent_role: '' });
                }}
                className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateRole}
                disabled={creatingRole || !newRoleData.role_name.trim() || !newRoleData.display_name.trim()}
                className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {creatingRole ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Plus className="w-4 h-4" />
                )}
                Create Role
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Role Confirmation Modal */}
      {confirmDeleteRole && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card rounded-lg shadow-xl w-full max-w-md mx-4 border border-border">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <h3 className="font-semibold text-destructive flex items-center gap-2">
                <Trash2 className="w-5 h-5" />
                Delete Role
              </h3>
              <button
                onClick={() => setConfirmDeleteRole(null)}
                className="p-1 text-muted-foreground hover:text-foreground rounded"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 space-y-3">
              <p className="text-foreground">
                Are you sure you want to delete the role <strong>&quot;{confirmDeleteRole.display_name}&quot;</strong>?
              </p>
              <div className="p-3 bg-status-warning/10 border border-status-warning/20 rounded-lg">
                <p className="text-sm text-status-warning">
                  <strong>Warning:</strong> This will remove all permission assignments for this role.
                  Users assigned to this role will lose those permissions.
                </p>
              </div>
              {confirmDeleteRole.is_builtin && (
                <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-lg">
                  <p className="text-sm text-destructive">
                    <strong>Note:</strong> This is a built-in role. Deleting it may affect system functionality.
                  </p>
                </div>
              )}
            </div>
            <div className="flex justify-end gap-2 px-4 py-3 border-t border-border">
              <button
                onClick={() => setConfirmDeleteRole(null)}
                className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteRole}
                disabled={deletingRole}
                className="px-4 py-2 text-sm bg-destructive text-white rounded-lg hover:bg-destructive/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {deletingRole ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
                Delete Role
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default RolesTab;
