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
  Key,
  Users,
  Activity,
  Plus,
  Trash2,
  Copy,
  Check,
  AlertCircle,
  RefreshCw,
  RotateCw,
  User,
  Clock,
  Database,
  Server,
  Loader2,
  Eye,
  EyeOff,
  ChevronRight,
  ExternalLink,
  FileText,
} from 'lucide-react';
import { apiClient, API_BASE_URL } from '../../api/client';
import { useAuthStore } from '../../store/authStore';

// Types
interface OAuthClient {
  client_id: string;
  client_name: string;
  client_type: string;
  created_at: string;
  is_active?: boolean;
  created_by?: number | null;
  metadata?: {
    user_id?: number;
    username?: string;
    personal?: boolean;
  };
  // Derived fields (not from API directly)
  last_used?: string | null;
  token_count?: number;
}

interface UserInfo {
  id: number;
  username: string;
  role: string;
  created_at: string;
  last_login: string | null;
  disabled: boolean;
}

interface SystemStatus {
  database: {
    connected: boolean;
    postgres_version?: string;
    age_version?: string;
  };
  jobs: {
    pending: number;
    running: number;
    completed: number;
    failed: number;
  };
  storage?: {
    connected: boolean;
    bucket_count?: number;
  };
}

interface NewClientCredentials {
  client_id: string;
  client_secret: string;
  client_name: string;
  // Other fields from OAuthClientWithSecret may be present but aren't used
}

type TabType = 'account' | 'users' | 'system';

// Tab button component
const TabButton: React.FC<{
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  badge?: number;
}> = ({ active, onClick, icon, label, badge }) => (
  <button
    onClick={onClick}
    className={`
      flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors
      ${active
        ? 'bg-primary text-primary-foreground dark:bg-blue-600 dark:text-white'
        : 'text-muted-foreground hover:text-foreground hover:bg-muted dark:text-gray-400 dark:hover:text-gray-200 dark:hover:bg-gray-800'
      }
    `}
  >
    {icon}
    {label}
    {badge !== undefined && badge > 0 && (
      <span className={`
        ml-1 px-1.5 py-0.5 text-xs rounded-full
        ${active ? 'bg-white/20' : 'bg-muted-foreground/20'}
      `}>
        {badge}
      </span>
    )}
  </button>
);

// Section component
const Section: React.FC<{
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  action?: React.ReactNode;
}> = ({ title, icon, children, action }) => (
  <section className="bg-card dark:bg-gray-900 rounded-lg border border-border dark:border-gray-800 overflow-hidden">
    <div className="px-4 py-3 border-b border-border dark:border-gray-800 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className="text-muted-foreground dark:text-gray-400">{icon}</span>
        <h2 className="font-semibold text-card-foreground dark:text-gray-200">{title}</h2>
      </div>
      {action}
    </div>
    <div className="p-4">{children}</div>
  </section>
);

// OAuth Client Card
const OAuthClientCard: React.FC<{
  client: OAuthClient;
  onDelete: (clientId: string) => void;
  onRotate?: (clientId: string) => void;
  isDeleting: boolean;
  isRotating?: boolean;
  showOwner?: boolean;
}> = ({ client, onDelete, onRotate, isDeleting, isRotating, showOwner }) => {
  const [confirmDelete, setConfirmDelete] = useState(false);

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  // Get owner username from metadata
  const ownerUsername = client.metadata?.username;

  return (
    <div className="p-4 bg-muted/50 dark:bg-gray-800/50 rounded-lg border border-border dark:border-gray-700">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-medium text-foreground dark:text-gray-200">
              {client.client_name}
            </h3>
            <span className="px-2 py-0.5 text-xs rounded-full bg-primary/10 text-primary dark:bg-blue-900/50 dark:text-blue-300">
              {client.client_type}
            </span>
            {client.is_active === false && (
              <span className="px-2 py-0.5 text-xs rounded-full bg-red-100 text-red-600 dark:bg-red-900/50 dark:text-red-300">
                inactive
              </span>
            )}
          </div>
          <div className="mt-1 text-sm text-muted-foreground dark:text-gray-400 font-mono">
            {client.client_id}
          </div>
          <div className="mt-2 flex flex-wrap gap-4 text-xs text-muted-foreground dark:text-gray-500">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              Created {formatDate(client.created_at)}
            </span>
            {client.last_used && (
              <span className="flex items-center gap-1">
                <Activity className="w-3 h-3" />
                Last used {formatDate(client.last_used)}
              </span>
            )}
            {client.token_count !== undefined && (
              <span className="flex items-center gap-1">
                <Key className="w-3 h-3" />
                {client.token_count} active token{client.token_count !== 1 ? 's' : ''}
              </span>
            )}
            {showOwner && ownerUsername && (
              <span className="flex items-center gap-1">
                <User className="w-3 h-3" />
                {ownerUsername}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1">
          {confirmDelete ? (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setConfirmDelete(false)}
                className="px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
                disabled={isDeleting}
              >
                Cancel
              </button>
              <button
                onClick={() => onDelete(client.client_id)}
                className="px-2 py-1 text-xs bg-red-500 text-white rounded hover:bg-red-600 disabled:opacity-50"
                disabled={isDeleting}
              >
                {isDeleting ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Delete'}
              </button>
            </div>
          ) : (
            <>
              {onRotate && client.client_type === 'confidential' && (
                <button
                  onClick={() => onRotate(client.client_id)}
                  disabled={isRotating}
                  className="p-1.5 text-muted-foreground hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors disabled:opacity-50"
                  title="Rotate secret"
                >
                  {isRotating ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <RotateCw className="w-4 h-4" />
                  )}
                </button>
              )}
              <button
                onClick={() => setConfirmDelete(true)}
                className="p-1.5 text-muted-foreground hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                title="Delete client"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

// New Client Credentials Display
const NewClientCredentialsDisplay: React.FC<{
  credentials: NewClientCredentials;
  onDismiss: () => void;
}> = ({ credentials, onDismiss }) => {
  const [copied, setCopied] = useState<'id' | 'secret' | 'json' | 'cli' | null>(null);
  const [showSecret, setShowSecret] = useState(false);
  const [showMcpConfig, setShowMcpConfig] = useState(false);

  const copyToClipboard = async (text: string, type: 'id' | 'secret' | 'json' | 'cli') => {
    await navigator.clipboard.writeText(text);
    setCopied(type);
    setTimeout(() => setCopied(null), 2000);
  };

  // Generate MCP config JSON (Claude Desktop format)
  const mcpJsonConfig = JSON.stringify({
    "knowledge-graph": {
      command: "kg-mcp-server",
      env: {
        KG_OAUTH_CLIENT_ID: credentials.client_id,
        KG_OAUTH_CLIENT_SECRET: credentials.client_secret,
        KG_API_URL: API_BASE_URL
      }
    }
  }, null, 2);

  // Generate claude CLI command
  const claudeCliCommand = `claude mcp add knowledge-graph kg-mcp-server \\
  --env KG_OAUTH_CLIENT_ID=${credentials.client_id} \\
  --env KG_OAUTH_CLIENT_SECRET=${credentials.client_secret} \\
  --env KG_API_URL=${API_BASE_URL} \\
  -s local`;

  return (
    <div className="p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg overflow-hidden">
      <div className="flex items-start gap-3 min-w-0">
        <Check className="w-5 h-5 text-green-600 dark:text-green-400 mt-0.5 flex-shrink-0" />
        <div className="flex-1 min-w-0 overflow-hidden">
          <h3 className="font-medium text-green-800 dark:text-green-300">
            Client Created: {credentials.client_name}
          </h3>
          <p className="text-sm text-green-700 dark:text-green-400 mt-1">
            Save these credentials now - the secret will not be shown again.
          </p>

          <div className="mt-4 space-y-3">
            <div>
              <label className="text-xs font-medium text-green-700 dark:text-green-400">Client ID</label>
              <div className="flex items-center gap-2 mt-1">
                <code className="flex-1 px-3 py-2 bg-white dark:bg-gray-800 rounded border border-green-200 dark:border-green-700 text-sm font-mono overflow-x-auto">
                  {credentials.client_id}
                </code>
                <button
                  onClick={() => copyToClipboard(credentials.client_id, 'id')}
                  className="p-2 hover:bg-green-100 dark:hover:bg-green-800/50 rounded transition-colors"
                  title="Copy Client ID"
                >
                  {copied === 'id' ? (
                    <Check className="w-4 h-4 text-green-600" />
                  ) : (
                    <Copy className="w-4 h-4 text-green-600" />
                  )}
                </button>
              </div>
            </div>

            <div>
              <label className="text-xs font-medium text-green-700 dark:text-green-400">Client Secret</label>
              <div className="flex items-center gap-2 mt-1">
                <code className="flex-1 px-3 py-2 bg-white dark:bg-gray-800 rounded border border-green-200 dark:border-green-700 text-sm font-mono overflow-x-auto">
                  {showSecret ? credentials.client_secret : '••••••••••••••••••••••••'}
                </code>
                <button
                  onClick={() => setShowSecret(!showSecret)}
                  className="p-2 hover:bg-green-100 dark:hover:bg-green-800/50 rounded transition-colors"
                  title={showSecret ? "Hide Secret" : "Show Secret"}
                >
                  {showSecret ? (
                    <EyeOff className="w-4 h-4 text-green-600" />
                  ) : (
                    <Eye className="w-4 h-4 text-green-600" />
                  )}
                </button>
                <button
                  onClick={() => copyToClipboard(credentials.client_secret, 'secret')}
                  className="p-2 hover:bg-green-100 dark:hover:bg-green-800/50 rounded transition-colors"
                  title="Copy Client Secret"
                >
                  {copied === 'secret' ? (
                    <Check className="w-4 h-4 text-green-600" />
                  ) : (
                    <Copy className="w-4 h-4 text-green-600" />
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* MCP Config Toggle */}
          <button
            onClick={() => setShowMcpConfig(!showMcpConfig)}
            className="mt-4 flex items-center gap-2 text-sm text-green-700 dark:text-green-400 hover:text-green-800 dark:hover:text-green-300"
          >
            <Server className="w-4 h-4" />
            {showMcpConfig ? 'Hide' : 'Show'} MCP Server Config
            <ChevronRight className={`w-4 h-4 transition-transform ${showMcpConfig ? 'rotate-90' : ''}`} />
          </button>

          {/* MCP Config Panel */}
          {showMcpConfig && (
            <div className="mt-3 p-3 bg-white dark:bg-gray-800 rounded-lg border border-green-200 dark:border-green-700 space-y-4 w-full max-w-full overflow-hidden">
              {/* Claude Desktop JSON Config */}
              <div className="w-full max-w-full">
                <div className="flex items-center justify-between mb-2 gap-2">
                  <label className="text-xs font-medium text-green-700 dark:text-green-400 truncate">
                    Claude Desktop Config
                  </label>
                  <button
                    onClick={() => copyToClipboard(mcpJsonConfig, 'json')}
                    className="flex-shrink-0 flex items-center gap-1 px-2 py-1 text-xs bg-green-100 dark:bg-green-800/50 text-green-700 dark:text-green-300 rounded hover:bg-green-200 dark:hover:bg-green-700/50 transition-colors"
                  >
                    {copied === 'json' ? (
                      <>
                        <Check className="w-3 h-3" />
                        Copied!
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" />
                        Copy JSON
                      </>
                    )}
                  </button>
                </div>
                <div className="overflow-x-auto rounded bg-gray-50 dark:bg-gray-900 max-w-full">
                  <pre className="p-3 text-xs font-mono text-gray-800 dark:text-gray-200 whitespace-pre w-max">
                    {mcpJsonConfig}
                  </pre>
                </div>
              </div>

              {/* Claude CLI Command */}
              <div className="w-full max-w-full">
                <div className="flex items-center justify-between mb-2 gap-2">
                  <label className="text-xs font-medium text-green-700 dark:text-green-400 truncate">
                    Claude CLI Command
                  </label>
                  <button
                    onClick={() => copyToClipboard(claudeCliCommand, 'cli')}
                    className="flex-shrink-0 flex items-center gap-1 px-2 py-1 text-xs bg-green-100 dark:bg-green-800/50 text-green-700 dark:text-green-300 rounded hover:bg-green-200 dark:hover:bg-green-700/50 transition-colors"
                  >
                    {copied === 'cli' ? (
                      <>
                        <Check className="w-3 h-3" />
                        Copied!
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" />
                        Copy Command
                      </>
                    )}
                  </button>
                </div>
                <div className="overflow-x-auto rounded bg-gray-50 dark:bg-gray-900 max-w-full">
                  <pre className="p-3 text-xs font-mono text-gray-800 dark:text-gray-200 whitespace-pre w-max">
                    {claudeCliCommand}
                  </pre>
                </div>
              </div>

              <p className="text-xs text-green-600 dark:text-green-500">
                Add to your Claude Desktop config file or use the CLI command to set up MCP server access.
              </p>
            </div>
          )}

          <div className="mt-4 flex gap-2">
            <button
              onClick={onDismiss}
              className="px-3 py-1.5 text-sm bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// User Row
const UserRow: React.FC<{
  user: UserInfo;
  isCurrentUser: boolean;
}> = ({ user, isCurrentUser }) => {
  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Never';
    return new Date(dateStr).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <tr className={`border-b border-border dark:border-gray-800 last:border-0 ${isCurrentUser ? 'bg-primary/5 dark:bg-blue-900/10' : ''}`}>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="font-medium text-foreground dark:text-gray-200">
            {user.username}
          </span>
          {isCurrentUser && (
            <span className="px-1.5 py-0.5 text-xs rounded bg-primary/20 text-primary dark:bg-blue-900/50 dark:text-blue-300">
              you
            </span>
          )}
          {user.disabled && (
            <span className="px-1.5 py-0.5 text-xs rounded bg-red-100 text-red-600 dark:bg-red-900/50 dark:text-red-300">
              disabled
            </span>
          )}
        </div>
      </td>
      <td className="px-4 py-3">
        <span className={`
          px-2 py-0.5 text-xs rounded-full
          ${user.role === 'platform_admin'
            ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-300 font-medium'
            : user.role === 'admin'
            ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300'
            : user.role === 'curator'
            ? 'bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300'
            : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
          }
        `}>
          {user.role}
        </span>
      </td>
      <td className="px-4 py-3 text-sm text-muted-foreground dark:text-gray-400">
        {formatDate(user.created_at)}
      </td>
      <td className="px-4 py-3 text-sm text-muted-foreground dark:text-gray-400">
        {formatDate(user.last_login)}
      </td>
    </tr>
  );
};

// Status Badge
const StatusBadge: React.FC<{
  connected: boolean;
  label: string;
}> = ({ connected, label }) => (
  <div className={`
    flex items-center gap-2 px-3 py-2 rounded-lg
    ${connected
      ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300'
      : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300'
    }
  `}>
    <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
    {label}
  </div>
);

export const AdminDashboard: React.FC = () => {
  const { user, isAuthenticated, permissions, hasPermission, isPlatformAdmin } = useAuthStore();

  // Permission-based access control (ADR-074)
  // Instead of role equality, check actual permissions
  const canViewUsers = hasPermission('users', 'read');
  const canViewAllOAuthClients = hasPermission('oauth_clients', 'read');
  const canViewSystemStatus = hasPermission('admin', 'status');

  // Legacy compatibility - keep isAdmin for now but base it on having admin-level permissions
  const isAdmin = canViewUsers || canViewSystemStatus;

  // Tab state
  const [activeTab, setActiveTab] = useState<TabType>('account');

  // Data states
  const [myClients, setMyClients] = useState<OAuthClient[]>([]);
  const [allClients, setAllClients] = useState<OAuthClient[]>([]);
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [dbStats, setDbStats] = useState<any>(null);

  // UI states
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creatingClient, setCreatingClient] = useState(false);
  const [newClientName, setNewClientName] = useState('');
  const [newCredentials, setNewCredentials] = useState<NewClientCredentials | null>(null);
  const [deletingClientId, setDeletingClientId] = useState<string | null>(null);
  const [rotatingClientId, setRotatingClientId] = useState<string | null>(null);

  // Load data based on active tab (ADR-074: permission-based)
  useEffect(() => {
    if (!isAuthenticated) return;

    const loadData = async () => {
      setLoading(true);
      setError(null);

      try {
        if (activeTab === 'account') {
          const clients = await apiClient.getMyOAuthClients();
          setMyClients(clients);
        } else if (activeTab === 'users' && canViewUsers) {
          const [usersData, clientsData] = await Promise.all([
            apiClient.listUsers({ limit: 100 }),
            canViewAllOAuthClients
              ? apiClient.listAllOAuthClients({ include_disabled: true })
              : Promise.resolve([]),
          ]);
          setUsers(usersData.users);
          setAllClients(clientsData);
        } else if (activeTab === 'system' && canViewSystemStatus) {
          const [status, stats] = await Promise.all([
            apiClient.getSystemStatus().catch(() => null),
            apiClient.getDatabaseStats().catch(() => null),
          ]);
          setSystemStatus(status);
          setDbStats(stats);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [activeTab, isAuthenticated, canViewUsers, canViewAllOAuthClients, canViewSystemStatus]);

  // Create new client
  const handleCreateClient = async () => {
    if (!newClientName.trim()) return;

    setCreatingClient(true);
    try {
      const result = await apiClient.createPersonalOAuthClient({
        client_name: newClientName.trim(),
      });
      setNewCredentials(result);
      setNewClientName('');
      // Refresh list
      const clients = await apiClient.getMyOAuthClients();
      setMyClients(clients);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create client');
    } finally {
      setCreatingClient(false);
    }
  };

  // Delete client
  const handleDeleteClient = async (clientId: string, isPersonal: boolean) => {
    setDeletingClientId(clientId);
    try {
      if (isPersonal) {
        await apiClient.deletePersonalOAuthClient(clientId);
        setMyClients(prev => prev.filter(c => c.client_id !== clientId));
      } else {
        await apiClient.deleteOAuthClient(clientId);
        setAllClients(prev => prev.filter(c => c.client_id !== clientId));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete client');
    } finally {
      setDeletingClientId(null);
    }
  };

  // Rotate client secret
  const handleRotateSecret = async (clientId: string) => {
    setRotatingClientId(clientId);
    try {
      const result = await apiClient.rotatePersonalOAuthClientSecret(clientId);
      // Show new credentials with MCP config helper
      setNewCredentials({
        client_id: result.client_id,
        client_name: result.client_name || clientId,
        client_secret: result.client_secret,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to rotate secret');
    } finally {
      setRotatingClientId(null);
    }
  };

  // Not authenticated
  if (!isAuthenticated) {
    return (
      <div className="h-full flex items-center justify-center bg-background dark:bg-gray-950">
        <div className="text-center">
          <Shield className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-foreground dark:text-gray-200">
            Authentication Required
          </h2>
          <p className="text-muted-foreground dark:text-gray-400 mt-2">
            Please log in to access admin settings.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-background dark:bg-gray-950">
      {/* Header */}
      <div className="flex-none p-4 border-b border-border dark:border-gray-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-primary dark:text-blue-400" />
            <h1 className="text-lg font-semibold text-foreground dark:text-gray-100">
              Administration
            </h1>
            {/* Platform Admin Badge (ADR-074) */}
            {isPlatformAdmin() && (
              <span className="px-2 py-0.5 text-xs rounded-full bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-300 font-medium">
                Platform Admin
              </span>
            )}
            {/* Role indicator for non-platform admins */}
            {!isPlatformAdmin() && permissions?.role && (
              <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400">
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
              badge={myClients.length}
            />
            {/* Users tab - requires users:read permission (ADR-074) */}
            {canViewUsers && (
              <TabButton
                active={activeTab === 'users'}
                onClick={() => setActiveTab('users')}
                icon={<Users className="w-4 h-4" />}
                label="Users"
                badge={users.length}
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
            <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 mt-0.5" />
              <div>
                <p className="text-red-800 dark:text-red-300">{error}</p>
                <button
                  onClick={() => setError(null)}
                  className="text-sm text-red-600 dark:text-red-400 underline mt-1"
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}

          {/* Loading state */}
          {loading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-primary animate-spin" />
            </div>
          )}

          {/* Account Tab */}
          {!loading && activeTab === 'account' && (
            <>
              {/* New credentials display */}
              {newCredentials && (
                <NewClientCredentialsDisplay
                  credentials={newCredentials}
                  onDismiss={() => setNewCredentials(null)}
                />
              )}

              {/* Create new client */}
              <Section
                title="Create OAuth Client"
                icon={<Plus className="w-5 h-5" />}
              >
                <p className="text-sm text-muted-foreground dark:text-gray-400 mb-4">
                  Create a personal OAuth client for CLI tools, scripts, or other applications.
                  Each client gets its own credentials for secure API access.
                </p>
                <div className="flex gap-3">
                  <input
                    type="text"
                    value={newClientName}
                    onChange={(e) => setNewClientName(e.target.value)}
                    placeholder="Client name (e.g., 'My Laptop CLI')"
                    className="flex-1 px-3 py-2 bg-muted dark:bg-gray-800 border border-border dark:border-gray-700 rounded-lg text-foreground dark:text-gray-200 placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary dark:focus:ring-blue-500"
                    onKeyDown={(e) => e.key === 'Enter' && handleCreateClient()}
                  />
                  <button
                    onClick={handleCreateClient}
                    disabled={creatingClient || !newClientName.trim()}
                    className="px-4 py-2 bg-primary text-primary-foreground dark:bg-blue-600 dark:text-white rounded-lg hover:bg-primary/90 dark:hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                  >
                    {creatingClient ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Plus className="w-4 h-4" />
                    )}
                    Create
                  </button>
                </div>
              </Section>

              {/* My clients */}
              <Section
                title="My OAuth Clients"
                icon={<Key className="w-5 h-5" />}
                action={
                  <button
                    onClick={async () => {
                      setLoading(true);
                      const clients = await apiClient.getMyOAuthClients();
                      setMyClients(clients);
                      setLoading(false);
                    }}
                    className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
                    title="Refresh"
                  >
                    <RefreshCw className="w-4 h-4" />
                  </button>
                }
              >
                {myClients.length === 0 ? (
                  <p className="text-muted-foreground dark:text-gray-400 text-center py-8">
                    No OAuth clients yet. Create one above to get started.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {myClients.map((client) => (
                      <OAuthClientCard
                        key={client.client_id}
                        client={client}
                        onDelete={(id) => handleDeleteClient(id, true)}
                        onRotate={handleRotateSecret}
                        isDeleting={deletingClientId === client.client_id}
                        isRotating={rotatingClientId === client.client_id}
                      />
                    ))}
                  </div>
                )}
              </Section>
            </>
          )}

          {/* Users Tab - requires users:read permission (ADR-074) */}
          {!loading && activeTab === 'users' && canViewUsers && (
            <>
              <Section
                title="All Users"
                icon={<Users className="w-5 h-5" />}
                action={
                  <button
                    onClick={async () => {
                      setLoading(true);
                      const data = await apiClient.listUsers({ limit: 100 });
                      setUsers(data.users);
                      setLoading(false);
                    }}
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
                      <tr className="text-left text-sm text-muted-foreground dark:text-gray-400 border-b border-border dark:border-gray-800">
                        <th className="px-4 py-2 font-medium">Username</th>
                        <th className="px-4 py-2 font-medium">Role</th>
                        <th className="px-4 py-2 font-medium">Created</th>
                        <th className="px-4 py-2 font-medium">Last Login</th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.map((u) => (
                        <UserRow
                          key={u.id}
                          user={u}
                          isCurrentUser={u.id === user?.id}
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
              </Section>

              {/* All OAuth Clients - requires oauth_clients:read permission (ADR-074) */}
              {canViewAllOAuthClients && (
                <Section
                  title="All OAuth Clients"
                  icon={<Key className="w-5 h-5" />}
                >
                  {allClients.length === 0 ? (
                    <p className="text-muted-foreground dark:text-gray-400 text-center py-8">
                      No OAuth clients registered.
                    </p>
                  ) : (
                    <div className="space-y-3">
                      {allClients.map((client) => (
                        <OAuthClientCard
                          key={client.client_id}
                          client={client}
                          onDelete={(id) => handleDeleteClient(id, false)}
                          isDeleting={deletingClientId === client.client_id}
                          showOwner={true}
                        />
                      ))}
                    </div>
                  )}
                </Section>
              )}
            </>
          )}

          {/* System Tab - requires admin:status permission (ADR-074) */}
          {!loading && activeTab === 'system' && canViewSystemStatus && (
            <>
              <Section
                title="System Status"
                icon={<Server className="w-5 h-5" />}
                action={
                  <button
                    onClick={async () => {
                      setLoading(true);
                      const [status, stats] = await Promise.all([
                        apiClient.getSystemStatus().catch(() => null),
                        apiClient.getDatabaseStats().catch(() => null),
                      ]);
                      setSystemStatus(status);
                      setDbStats(stats);
                      setLoading(false);
                    }}
                    className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
                    title="Refresh"
                  >
                    <RefreshCw className="w-4 h-4" />
                  </button>
                }
              >
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  <StatusBadge
                    connected={systemStatus?.database?.connected ?? false}
                    label={systemStatus?.database?.connected ? 'Database Connected' : 'Database Offline'}
                  />
                  <StatusBadge
                    connected={systemStatus?.storage?.connected ?? false}
                    label={systemStatus?.storage?.connected ? 'Storage Connected' : 'Storage Offline'}
                  />
                </div>

                {systemStatus?.database && (
                  <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                    {systemStatus.database.postgres_version && (
                      <div>
                        <span className="text-muted-foreground dark:text-gray-400">PostgreSQL:</span>
                        <span className="ml-2 font-mono text-foreground dark:text-gray-200">
                          {systemStatus.database.postgres_version}
                        </span>
                      </div>
                    )}
                    {systemStatus.database.age_version && (
                      <div>
                        <span className="text-muted-foreground dark:text-gray-400">Apache AGE:</span>
                        <span className="ml-2 font-mono text-foreground dark:text-gray-200">
                          {systemStatus.database.age_version}
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </Section>

              <Section
                title="Database Statistics"
                icon={<Database className="w-5 h-5" />}
              >
                {dbStats ? (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="p-4 bg-muted/50 dark:bg-gray-800/50 rounded-lg">
                      <div className="text-2xl font-bold text-foreground dark:text-gray-200">
                        {dbStats.nodes?.Concept?.toLocaleString() ?? 0}
                      </div>
                      <div className="text-sm text-muted-foreground dark:text-gray-400">Concepts</div>
                    </div>
                    <div className="p-4 bg-muted/50 dark:bg-gray-800/50 rounded-lg">
                      <div className="text-2xl font-bold text-foreground dark:text-gray-200">
                        {dbStats.nodes?.Source?.toLocaleString() ?? 0}
                      </div>
                      <div className="text-sm text-muted-foreground dark:text-gray-400">Sources</div>
                    </div>
                    <div className="p-4 bg-muted/50 dark:bg-gray-800/50 rounded-lg">
                      <div className="text-2xl font-bold text-foreground dark:text-gray-200">
                        {dbStats.nodes?.Instance?.toLocaleString() ?? 0}
                      </div>
                      <div className="text-sm text-muted-foreground dark:text-gray-400">Instances</div>
                    </div>
                    <div className="p-4 bg-muted/50 dark:bg-gray-800/50 rounded-lg">
                      <div className="text-2xl font-bold text-foreground dark:text-gray-200">
                        {dbStats.relationships?.total?.toLocaleString() ?? 0}
                      </div>
                      <div className="text-sm text-muted-foreground dark:text-gray-400">Relationships</div>
                    </div>
                  </div>
                ) : (
                  <p className="text-muted-foreground dark:text-gray-400 text-center py-8">
                    Unable to load database statistics.
                  </p>
                )}
              </Section>

              <Section
                title="Job Queue"
                icon={<Activity className="w-5 h-5" />}
              >
                {systemStatus?.jobs ? (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg">
                      <div className="text-2xl font-bold text-yellow-700 dark:text-yellow-300">
                        {systemStatus.jobs.pending}
                      </div>
                      <div className="text-sm text-yellow-600 dark:text-yellow-400">Pending</div>
                    </div>
                    <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                      <div className="text-2xl font-bold text-blue-700 dark:text-blue-300">
                        {systemStatus.jobs.running}
                      </div>
                      <div className="text-sm text-blue-600 dark:text-blue-400">Running</div>
                    </div>
                    <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                      <div className="text-2xl font-bold text-green-700 dark:text-green-300">
                        {systemStatus.jobs.completed}
                      </div>
                      <div className="text-sm text-green-600 dark:text-green-400">Completed</div>
                    </div>
                    <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
                      <div className="text-2xl font-bold text-red-700 dark:text-red-300">
                        {systemStatus.jobs.failed}
                      </div>
                      <div className="text-sm text-red-600 dark:text-red-400">Failed</div>
                    </div>
                  </div>
                ) : (
                  <p className="text-muted-foreground dark:text-gray-400 text-center py-8">
                    Unable to load job queue status.
                  </p>
                )}
              </Section>

              <Section
                title="API Documentation"
                icon={<FileText className="w-5 h-5" />}
              >
                <p className="text-sm text-muted-foreground dark:text-gray-400 mb-4">
                  Interactive API documentation for developers and integrations.
                </p>
                <div className="flex flex-wrap gap-3">
                  <a
                    href={`${API_BASE_URL}/docs`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 px-4 py-2 bg-muted dark:bg-gray-800 hover:bg-muted/80 dark:hover:bg-gray-700 rounded-lg transition-colors text-foreground dark:text-gray-200"
                  >
                    <FileText className="w-4 h-4" />
                    Swagger UI
                    <ExternalLink className="w-3 h-3 text-muted-foreground" />
                  </a>
                  <a
                    href={`${API_BASE_URL}/redoc`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 px-4 py-2 bg-muted dark:bg-gray-800 hover:bg-muted/80 dark:hover:bg-gray-700 rounded-lg transition-colors text-foreground dark:text-gray-200"
                  >
                    <FileText className="w-4 h-4" />
                    ReDoc
                    <ExternalLink className="w-3 h-3 text-muted-foreground" />
                  </a>
                </div>
                <p className="mt-3 text-xs text-muted-foreground dark:text-gray-500">
                  API: {API_BASE_URL}
                </p>
              </Section>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;
