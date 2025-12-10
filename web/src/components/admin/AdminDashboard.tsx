/**
 * Admin Dashboard
 *
 * Platform administration interface with two access levels:
 * - Self-admin: Manage own OAuth clients (all authenticated users)
 * - Superadmin: User listing, system status (admin role only)
 */

import React, { useState, useEffect } from 'react';
import {
  Shield,
  ShieldCheck,
  Key,
  Users,
  Activity,
  AlertCircle,
  Loader2,
  CheckCircle,
} from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { TabButton } from './components';
import { AccountTab } from './AccountTab';
import { UsersTab } from './UsersTab';
import { RolesTab } from './RolesTab';
import { SystemTab } from './SystemTab';
import type { TabType } from './types';

export const AdminDashboard: React.FC = () => {
  const { isAuthenticated, permissions, hasPermission, isPlatformAdmin } = useAuthStore();

  // Permission-based access control (ADR-074)
  const canViewUsers = hasPermission('users', 'read');
  const canViewRoles = hasPermission('rbac', 'read');
  const canViewSystemStatus = hasPermission('admin', 'status');

  // Tab state
  const [activeTab, setActiveTab] = useState<TabType>('account');

  // UI states
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Clear success message after 3 seconds
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  // Not authenticated
  if (!isAuthenticated) {
    return (
      <div className="h-full flex items-center justify-center bg-background">
        <div className="text-center">
          <Shield className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-foreground">
            Authentication Required
          </h2>
          <p className="text-muted-foreground mt-2">
            Please log in to access admin settings.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-background">
      {/* Header */}
      <div className="flex-none p-4 border-b border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-primary" />
            <h1 className="text-lg font-semibold text-foreground">
              Administration
            </h1>
            {/* Platform Admin Badge (ADR-074) */}
            {isPlatformAdmin() && (
              <span className="px-2 py-0.5 text-xs rounded-full bg-purple-500/20 text-purple-400 font-medium">
                Platform Admin
              </span>
            )}
            {/* Role indicator for non-platform admins */}
            {!isPlatformAdmin() && permissions?.role && (
              <span className="px-2 py-0.5 text-xs rounded-full bg-muted text-muted-foreground">
                {permissions.role}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <TabButton
              active={activeTab === 'account'}
              onClick={() => setActiveTab('account')}
              icon={<Key className="w-4 h-4" />}
              label="Account"
            />
            {/* Users tab - requires users:read permission (ADR-074) */}
            {canViewUsers && (
              <TabButton
                active={activeTab === 'users'}
                onClick={() => setActiveTab('users')}
                icon={<Users className="w-4 h-4" />}
                label="Users"
              />
            )}
            {/* Roles tab - requires rbac:read permission (ADR-074) */}
            {canViewRoles && (
              <TabButton
                active={activeTab === 'roles'}
                onClick={() => setActiveTab('roles')}
                icon={<ShieldCheck className="w-4 h-4" />}
                label="Roles"
              />
            )}
            {/* System tab - requires admin:status permission (ADR-074) */}
            {canViewSystemStatus && (
              <TabButton
                active={activeTab === 'system'}
                onClick={() => setActiveTab('system')}
                icon={<Activity className="w-4 h-4" />}
                label="System"
              />
            )}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Error display */}
          {error && (
            <div className="p-4 bg-destructive/10 border border-destructive/30 rounded-lg flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-destructive mt-0.5" />
              <div>
                <p className="text-destructive">{error}</p>
                <button
                  onClick={() => setError(null)}
                  className="text-sm text-destructive underline mt-1"
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}

          {/* Success message */}
          {successMessage && (
            <div className="p-4 bg-status-active/10 border border-status-active/30 rounded-lg flex items-center gap-3">
              <CheckCircle className="w-5 h-5 text-status-active" />
              <p className="text-status-active">{successMessage}</p>
            </div>
          )}

          {/* Tab Content */}
          {activeTab === 'account' && (
            <AccountTab onError={setError} />
          )}

          {activeTab === 'users' && canViewUsers && (
            <UsersTab onError={setError} onSuccess={setSuccessMessage} />
          )}

          {activeTab === 'roles' && canViewRoles && (
            <RolesTab onError={setError} onSuccess={setSuccessMessage} />
          )}

          {activeTab === 'system' && canViewSystemStatus && (
            <SystemTab onError={setError} />
          )}
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;
