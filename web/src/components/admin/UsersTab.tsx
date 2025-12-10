/**
 * Users Tab Component
 *
 * User management for admins.
 */

import React, { useState, useEffect } from 'react';
import {
  Users,
  Key,
  RefreshCw,
  Loader2,
  UserPlus,
  Edit2,
  KeyRound,
  Trash2,
  X,
  Save,
  Ban,
  CheckCircle,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useAuthStore } from '../../store/authStore';
import { Section, OAuthClientCard, UserRow } from './components';
import type { OAuthClient, UserInfo } from './types';

interface UsersTabProps {
  onError: (error: string) => void;
  onSuccess: (message: string) => void;
}

export const UsersTab: React.FC<UsersTabProps> = ({ onError, onSuccess }) => {
  const { user, hasPermission, isPlatformAdmin } = useAuthStore();

  const canCreateUsers = hasPermission('users', 'create');
  const canEditUsers = hasPermission('users', 'write');
  const canDeleteUsers = hasPermission('users', 'delete');
  const canViewAllOAuthClients = hasPermission('oauth_clients', 'read');

  // Data states
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [allClients, setAllClients] = useState<OAuthClient[]>([]);
  const [loading, setLoading] = useState(true);

  // UI states
  const [showCreateUserModal, setShowCreateUserModal] = useState(false);
  const [newUserData, setNewUserData] = useState({ username: '', password: '', role: 'contributor' });
  const [creatingUser, setCreatingUser] = useState(false);
  const [editingUserId, setEditingUserId] = useState<number | null>(null);
  const [editUserData, setEditUserData] = useState({ role: '', disabled: false });
  const [savingUser, setSavingUser] = useState(false);
  const [deletingUserId, setDeletingUserId] = useState<number | null>(null);
  const [confirmDeleteUser, setConfirmDeleteUser] = useState<UserInfo | null>(null);
  const [resetPasswordUserId, setResetPasswordUserId] = useState<number | null>(null);
  const [newPassword, setNewPassword] = useState('');
  const [resettingPassword, setResettingPassword] = useState(false);
  const [deletingClientId, setDeletingClientId] = useState<string | null>(null);

  // Load data
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [usersData, clientsData] = await Promise.all([
        apiClient.listUsers({ limit: 100 }),
        canViewAllOAuthClients
          ? apiClient.listAllOAuthClients({ include_disabled: true })
          : Promise.resolve([]),
      ]);
      setUsers(usersData.users);
      setAllClients(clientsData);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  // User management handlers
  const handleCreateUser = async () => {
    if (!newUserData.username.trim() || !newUserData.password.trim()) return;
    setCreatingUser(true);
    try {
      await apiClient.createUser({
        username: newUserData.username.trim(),
        password: newUserData.password,
        role: newUserData.role,
      });
      onSuccess(`User '${newUserData.username}' created successfully`);
      setNewUserData({ username: '', password: '', role: 'contributor' });
      setShowCreateUserModal(false);
      const usersData = await apiClient.listUsers({ limit: 100 });
      setUsers(usersData.users);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to create user');
    } finally {
      setCreatingUser(false);
    }
  };

  const handleStartEditUser = (userInfo: UserInfo) => {
    setEditingUserId(userInfo.id);
    setEditUserData({ role: userInfo.role, disabled: userInfo.disabled });
  };

  const handleSaveUser = async () => {
    if (!editingUserId) return;
    setSavingUser(true);
    try {
      await apiClient.updateUser(editingUserId, {
        role: editUserData.role,
        disabled: editUserData.disabled,
      });
      onSuccess('User updated successfully');
      setEditingUserId(null);
      const usersData = await apiClient.listUsers({ limit: 100 });
      setUsers(usersData.users);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to update user');
    } finally {
      setSavingUser(false);
    }
  };

  const handleDeleteUser = async () => {
    if (!confirmDeleteUser) return;
    setDeletingUserId(confirmDeleteUser.id);
    try {
      await apiClient.deleteUser(confirmDeleteUser.id);
      onSuccess(`User '${confirmDeleteUser.username}' deleted`);
      setConfirmDeleteUser(null);
      const usersData = await apiClient.listUsers({ limit: 100 });
      setUsers(usersData.users);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to delete user');
    } finally {
      setDeletingUserId(null);
    }
  };

  const handleResetPassword = async () => {
    if (!resetPasswordUserId || !newPassword.trim()) return;
    setResettingPassword(true);
    try {
      const result = await apiClient.resetUserPassword(resetPasswordUserId, newPassword);
      onSuccess(result.message);
      setResetPasswordUserId(null);
      setNewPassword('');
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to reset password');
    } finally {
      setResettingPassword(false);
    }
  };

  const handleDeleteClient = async (clientId: string) => {
    setDeletingClientId(clientId);
    try {
      await apiClient.deleteOAuthClient(clientId);
      setAllClients(prev => prev.filter(c => c.client_id !== clientId));
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to delete client');
    } finally {
      setDeletingClientId(null);
    }
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
      {/* Create User Button */}
      {canCreateUsers && (
        <div className="flex justify-end mb-4">
          <button
            onClick={() => setShowCreateUserModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
          >
            <UserPlus className="w-4 h-4" />
            Create User
          </button>
        </div>
      )}

      <Section
        title="All Users"
        icon={<Users className="w-5 h-5" />}
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
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-sm text-muted-foreground border-b border-border">
                <th className="px-4 py-2 font-medium">Username</th>
                <th className="px-4 py-2 font-medium">Role</th>
                <th className="px-4 py-2 font-medium">Created</th>
                <th className="px-4 py-2 font-medium">Last Login</th>
                {(canEditUsers || canDeleteUsers) && (
                  <th className="px-4 py-2 font-medium">Actions</th>
                )}
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <UserRow
                  key={u.id}
                  user={u}
                  isCurrentUser={u.id === user?.id}
                  canEdit={canEditUsers}
                  canDelete={canDeleteUsers}
                  onEdit={handleStartEditUser}
                  onDelete={setConfirmDeleteUser}
                  onResetPassword={setResetPasswordUserId}
                />
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* All OAuth Clients */}
      {canViewAllOAuthClients && (
        <Section
          title="All OAuth Clients"
          icon={<Key className="w-5 h-5" />}
        >
          {allClients.length === 0 ? (
            <p className="text-muted-foreground text-center py-8">
              No OAuth clients registered.
            </p>
          ) : (
            <div className="space-y-3">
              {allClients.map((client) => (
                <OAuthClientCard
                  key={client.client_id}
                  client={client}
                  onDelete={handleDeleteClient}
                  isDeleting={deletingClientId === client.client_id}
                  showOwner={true}
                />
              ))}
            </div>
          )}
        </Section>
      )}

      {/* Create User Modal */}
      {showCreateUserModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card rounded-lg shadow-xl w-full max-w-md mx-4 border border-border">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <h3 className="font-semibold text-foreground flex items-center gap-2">
                <UserPlus className="w-5 h-5" />
                Create User
              </h3>
              <button
                onClick={() => {
                  setShowCreateUserModal(false);
                  setNewUserData({ username: '', password: '', role: 'contributor' });
                }}
                className="p-1 text-muted-foreground hover:text-foreground rounded"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Username
                </label>
                <input
                  type="text"
                  value={newUserData.username}
                  onChange={(e) => setNewUserData(prev => ({ ...prev, username: e.target.value }))}
                  placeholder="Enter username"
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Password
                </label>
                <input
                  type="password"
                  value={newUserData.password}
                  onChange={(e) => setNewUserData(prev => ({ ...prev, password: e.target.value }))}
                  placeholder="Minimum 8 characters"
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Role
                </label>
                <select
                  value={newUserData.role}
                  onChange={(e) => setNewUserData(prev => ({ ...prev, role: e.target.value }))}
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="read_only">Read Only</option>
                  <option value="contributor">Contributor</option>
                  <option value="curator">Curator</option>
                  <option value="admin">Admin</option>
                  {isPlatformAdmin() && <option value="platform_admin">Platform Admin</option>}
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-2 px-4 py-3 border-t border-border">
              <button
                onClick={() => {
                  setShowCreateUserModal(false);
                  setNewUserData({ username: '', password: '', role: 'contributor' });
                }}
                className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateUser}
                disabled={creatingUser || !newUserData.username.trim() || !newUserData.password.trim()}
                className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {creatingUser ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <UserPlus className="w-4 h-4" />
                )}
                Create User
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit User Modal */}
      {editingUserId && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card rounded-lg shadow-xl w-full max-w-md mx-4 border border-border">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <h3 className="font-semibold text-foreground flex items-center gap-2">
                <Edit2 className="w-5 h-5" />
                Edit User
              </h3>
              <button
                onClick={() => setEditingUserId(null)}
                className="p-1 text-muted-foreground hover:text-foreground rounded"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Username
                </label>
                <div className="px-3 py-2 bg-muted/50 border border-border rounded-lg text-muted-foreground">
                  {users.find(u => u.id === editingUserId)?.username}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Role
                </label>
                <select
                  value={editUserData.role}
                  onChange={(e) => setEditUserData(prev => ({ ...prev, role: e.target.value }))}
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="read_only">Read Only</option>
                  <option value="contributor">Contributor</option>
                  <option value="curator">Curator</option>
                  <option value="admin">Admin</option>
                  {isPlatformAdmin() && <option value="platform_admin">Platform Admin</option>}
                </select>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setEditUserData(prev => ({ ...prev, disabled: !prev.disabled }))}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors ${
                    editUserData.disabled
                      ? 'bg-destructive/10 border-destructive/30 text-destructive'
                      : 'bg-status-active/10 border-status-active/30 text-status-active'
                  }`}
                >
                  {editUserData.disabled ? (
                    <>
                      <Ban className="w-4 h-4" />
                      Account Disabled
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-4 h-4" />
                      Account Active
                    </>
                  )}
                </button>
              </div>
            </div>
            <div className="flex justify-end gap-2 px-4 py-3 border-t border-border">
              <button
                onClick={() => setEditingUserId(null)}
                className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveUser}
                disabled={savingUser}
                className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {savingUser ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete User Confirmation Dialog */}
      {confirmDeleteUser && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card rounded-lg shadow-xl w-full max-w-md mx-4 border border-border">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <h3 className="font-semibold text-destructive flex items-center gap-2">
                <Trash2 className="w-5 h-5" />
                Delete User
              </h3>
              <button
                onClick={() => setConfirmDeleteUser(null)}
                className="p-1 text-muted-foreground hover:text-foreground rounded"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4">
              <p className="text-foreground">
                Are you sure you want to delete user <strong>{confirmDeleteUser.username}</strong>?
              </p>
              <p className="text-sm text-muted-foreground mt-2">
                This action cannot be undone. All associated OAuth clients and tokens will also be deleted.
              </p>
            </div>
            <div className="flex justify-end gap-2 px-4 py-3 border-t border-border">
              <button
                onClick={() => setConfirmDeleteUser(null)}
                className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteUser}
                disabled={deletingUserId === confirmDeleteUser.id}
                className="px-4 py-2 text-sm bg-destructive text-white rounded-lg hover:bg-destructive/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {deletingUserId === confirmDeleteUser.id ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
                Delete User
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reset Password Modal */}
      {resetPasswordUserId && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card rounded-lg shadow-xl w-full max-w-md mx-4 border border-border">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <h3 className="font-semibold text-foreground flex items-center gap-2">
                <KeyRound className="w-5 h-5" />
                Reset Password
              </h3>
              <button
                onClick={() => {
                  setResetPasswordUserId(null);
                  setNewPassword('');
                }}
                className="p-1 text-muted-foreground hover:text-foreground rounded"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  User
                </label>
                <div className="px-3 py-2 bg-muted/50 border border-border rounded-lg text-muted-foreground">
                  {users.find(u => u.id === resetPasswordUserId)?.username}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  New Password
                </label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Minimum 8 characters"
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 px-4 py-3 border-t border-border">
              <button
                onClick={() => {
                  setResetPasswordUserId(null);
                  setNewPassword('');
                }}
                className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleResetPassword}
                disabled={resettingPassword || !newPassword.trim()}
                className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {resettingPassword ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <KeyRound className="w-4 h-4" />
                )}
                Reset Password
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default UsersTab;
