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
  ChevronDown,
  ExternalLink,
  FileText,
  Edit2,
  KeyRound,
  UserPlus,
  X,
  Save,
  Ban,
  CheckCircle,
  Lock,
  Unlock,
  GitBranch,
  Cpu,
  BrainCircuit,
  Zap,
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
  docker: {
    running: boolean;
    container_name?: string;
    status?: string;
    ports?: string;
  };
  database_connection: {
    connected: boolean;
    uri: string;
    error?: string;
  };
  database_stats?: {
    concepts: number;
    sources: number;
    instances: number;
    relationships: number;
  };
  python_env: {
    venv_exists: boolean;
    python_version?: string;
  };
  configuration: {
    env_exists: boolean;
    anthropic_key_configured: boolean;
    openai_key_configured: boolean;
  };
}

interface NewClientCredentials {
  client_id: string;
  client_secret: string;
  client_name: string;
  // Other fields from OAuthClientWithSecret may be present but aren't used
}

interface RoleInfo {
  role_name: string;
  display_name: string;
  description: string | null;
  is_builtin: boolean;
  is_active: boolean;
  parent_role: string | null;
  created_at: string;
  created_by: string | null;
  metadata: Record<string, unknown>;
}

interface ResourceInfo {
  resource_type: string;
  description: string | null;
  parent_type: string | null;
  available_actions: string[];
  supports_scoping: boolean;
  metadata: Record<string, unknown>;
  registered_at: string;
  registered_by: string | null;
}

interface PermissionInfo {
  id: number;
  role_name: string;
  resource_type: string;
  action: string;
  scope_type: string;
  scope_id: string | null;
  scope_filter: Record<string, unknown> | null;
  granted: boolean;
  inherited_from: string | null;
  created_at: string;
  created_by: string | null;
}

type TabType = 'account' | 'users' | 'roles' | 'system';

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
        ? 'bg-primary text-primary-foreground'
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
  <section className="bg-card rounded-lg border border-border dark:border-gray-800 overflow-hidden">
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
    <div className="p-4 bg-muted/50/50 rounded-lg border border-border dark:border-gray-700">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-medium text-foreground dark:text-gray-200">
              {client.client_name}
            </h3>
            <span className="px-2 py-0.5 text-xs rounded-full bg-primary/10 text-primary">
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
                  className="p-1.5 text-muted-foreground hover:text-status-info hover:bg-status-info/10 rounded transition-colors disabled:opacity-50"
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
    <div className="p-4 bg-status-active/10 border border-status-active/30 rounded-lg overflow-hidden">
      <div className="flex items-start gap-3 min-w-0">
        <Check className="w-5 h-5 text-status-active mt-0.5 flex-shrink-0" />
        <div className="flex-1 min-w-0 overflow-hidden">
          <h3 className="font-medium text-status-active">
            Client Created: {credentials.client_name}
          </h3>
          <p className="text-sm text-status-active mt-1">
            Save these credentials now - the secret will not be shown again.
          </p>

          <div className="mt-4 space-y-3">
            <div>
              <label className="text-xs font-medium text-status-active">Client ID</label>
              <div className="flex items-center gap-2 mt-1">
                <code className="flex-1 px-3 py-2 bg-white rounded border border-status-active/30 text-sm font-mono overflow-x-auto">
                  {credentials.client_id}
                </code>
                <button
                  onClick={() => copyToClipboard(credentials.client_id, 'id')}
                  className="p-2 hover:bg-status-active/20 rounded transition-colors"
                  title="Copy Client ID"
                >
                  {copied === 'id' ? (
                    <Check className="w-4 h-4 text-status-active" />
                  ) : (
                    <Copy className="w-4 h-4 text-status-active" />
                  )}
                </button>
              </div>
            </div>

            <div>
              <label className="text-xs font-medium text-status-active">Client Secret</label>
              <div className="flex items-center gap-2 mt-1">
                <code className="flex-1 px-3 py-2 bg-white rounded border border-status-active/30 text-sm font-mono overflow-x-auto">
                  {showSecret ? credentials.client_secret : '••••••••••••••••••••••••'}
                </code>
                <button
                  onClick={() => setShowSecret(!showSecret)}
                  className="p-2 hover:bg-status-active/20 rounded transition-colors"
                  title={showSecret ? "Hide Secret" : "Show Secret"}
                >
                  {showSecret ? (
                    <EyeOff className="w-4 h-4 text-status-active" />
                  ) : (
                    <Eye className="w-4 h-4 text-status-active" />
                  )}
                </button>
                <button
                  onClick={() => copyToClipboard(credentials.client_secret, 'secret')}
                  className="p-2 hover:bg-status-active/20 rounded transition-colors"
                  title="Copy Client Secret"
                >
                  {copied === 'secret' ? (
                    <Check className="w-4 h-4 text-status-active" />
                  ) : (
                    <Copy className="w-4 h-4 text-status-active" />
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* MCP Config Toggle */}
          <button
            onClick={() => setShowMcpConfig(!showMcpConfig)}
            className="mt-4 flex items-center gap-2 text-sm text-status-active hover:text-status-active"
          >
            <Server className="w-4 h-4" />
            {showMcpConfig ? 'Hide' : 'Show'} MCP Server Config
            <ChevronRight className={`w-4 h-4 transition-transform ${showMcpConfig ? 'rotate-90' : ''}`} />
          </button>

          {/* MCP Config Panel */}
          {showMcpConfig && (
            <div className="mt-3 p-3 bg-white rounded-lg border border-status-active/30 space-y-4 w-full max-w-full overflow-hidden">
              {/* Claude Desktop JSON Config */}
              <div className="w-full max-w-full">
                <div className="flex items-center justify-between mb-2 gap-2">
                  <label className="text-xs font-medium text-status-active truncate">
                    Claude Desktop Config
                  </label>
                  <button
                    onClick={() => copyToClipboard(mcpJsonConfig, 'json')}
                    className="flex-shrink-0 flex items-center gap-1 px-2 py-1 text-xs bg-status-active/20 text-status-active rounded hover:bg-status-active/30 transition-colors"
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
                <div className="overflow-x-auto rounded bg-gray-50 max-w-full">
                  <pre className="p-3 text-xs font-mono text-gray-800 dark:text-gray-200 whitespace-pre w-max">
                    {mcpJsonConfig}
                  </pre>
                </div>
              </div>

              {/* Claude CLI Command */}
              <div className="w-full max-w-full">
                <div className="flex items-center justify-between mb-2 gap-2">
                  <label className="text-xs font-medium text-status-active truncate">
                    Claude CLI Command
                  </label>
                  <button
                    onClick={() => copyToClipboard(claudeCliCommand, 'cli')}
                    className="flex-shrink-0 flex items-center gap-1 px-2 py-1 text-xs bg-status-active/20 text-status-active rounded hover:bg-status-active/30 transition-colors"
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
                <div className="overflow-x-auto rounded bg-gray-50 max-w-full">
                  <pre className="p-3 text-xs font-mono text-gray-800 dark:text-gray-200 whitespace-pre w-max">
                    {claudeCliCommand}
                  </pre>
                </div>
              </div>

              <p className="text-xs text-status-active">
                Add to your Claude Desktop config file or use the CLI command to set up MCP server access.
              </p>
            </div>
          )}

          <div className="mt-4 flex gap-2">
            <button
              onClick={onDismiss}
              className="px-3 py-1.5 text-sm bg-status-active text-white rounded hover:bg-status-active transition-colors"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// User Row with actions
const UserRow: React.FC<{
  user: UserInfo;
  isCurrentUser: boolean;
  canEdit?: boolean;
  canDelete?: boolean;
  onEdit?: (user: UserInfo) => void;
  onDelete?: (user: UserInfo) => void;
  onResetPassword?: (userId: number) => void;
}> = ({ user, isCurrentUser, canEdit, canDelete, onEdit, onDelete, onResetPassword }) => {
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

  const showActions = (canEdit || canDelete) && !isCurrentUser;

  return (
    <tr className={`border-b border-border dark:border-gray-800 last:border-0 ${isCurrentUser ? 'bg-primary/5' : ''}`}>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="font-medium text-foreground dark:text-gray-200">
            {user.username}
          </span>
          {isCurrentUser && (
            <span className="px-1.5 py-0.5 text-xs rounded bg-primary/20 text-primary">
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
            ? 'bg-status-warning/20 text-status-warning font-medium'
            : user.role === 'admin'
            ? 'bg-status-info/20 text-status-info'
            : user.role === 'curator'
            ? 'bg-status-active/20 text-status-active'
            : user.role === 'contributor'
            ? 'bg-primary/20 text-primary'
            : 'bg-purple-500/20 text-purple-400'
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
      {showActions && (
        <td className="px-4 py-3">
          <div className="flex items-center gap-1">
            {canEdit && onEdit && (
              <button
                onClick={() => onEdit(user)}
                className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
                title="Edit user"
              >
                <Edit2 className="w-4 h-4" />
              </button>
            )}
            {canEdit && onResetPassword && (
              <button
                onClick={() => onResetPassword(user.id)}
                className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
                title="Reset password"
              >
                <KeyRound className="w-4 h-4" />
              </button>
            )}
            {canDelete && onDelete && (
              <button
                onClick={() => onDelete(user)}
                className="p-1.5 text-muted-foreground hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                title="Delete user"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </div>
        </td>
      )}
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
      ? 'bg-status-active/10 text-status-active'
      : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300'
    }
  `}>
    <span className={`w-2 h-2 rounded-full ${connected ? 'bg-status-active' : 'bg-red-500'}`} />
    {label}
  </div>
);

export const AdminDashboard: React.FC = () => {
  const { user, isAuthenticated, permissions, hasPermission, isPlatformAdmin } = useAuthStore();

  // Permission-based access control (ADR-074)
  // Instead of role equality, check actual permissions
  const canViewUsers = hasPermission('users', 'read');
  const canCreateUsers = hasPermission('users', 'create');
  const canEditUsers = hasPermission('users', 'write');
  const canDeleteUsers = hasPermission('users', 'delete');
  const canViewAllOAuthClients = hasPermission('oauth_clients', 'read');
  const canViewSystemStatus = hasPermission('admin', 'status');

  // RBAC permissions
  const canViewRoles = hasPermission('rbac', 'read');
  const canCreateRoles = hasPermission('rbac', 'create');
  const canEditRoles = hasPermission('rbac', 'write');
  const canDeleteRoles = hasPermission('rbac', 'delete');

  // Legacy compatibility - keep isAdmin for now but base it on having admin-level permissions
  const isAdmin = canViewUsers || canViewSystemStatus || canViewRoles;

  // Tab state
  const [activeTab, setActiveTab] = useState<TabType>('account');

  // Data states
  const [myClients, setMyClients] = useState<OAuthClient[]>([]);
  const [allClients, setAllClients] = useState<OAuthClient[]>([]);
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [dbStats, setDbStats] = useState<any>(null);
  const [schedulerStatus, setSchedulerStatus] = useState<{
    jobs_by_status: Record<string, number>;
    last_cleanup: string | null;
    next_cleanup: string | null;
  } | null>(null);

  // AI Configuration states
  const [embeddingConfigs, setEmbeddingConfigs] = useState<Array<{
    id: number;
    provider: string;
    model_name: string;
    embedding_dimensions: number;
    precision: string;
    device: string | null;
    active: boolean;
    delete_protected: boolean;
    change_protected: boolean;
    updated_at: string;
    updated_by: string;
  }>>([]);
  const [extractionConfig, setExtractionConfig] = useState<{
    provider: string;
    model: string;
    supports_vision: boolean;
    supports_json_mode: boolean;
    max_tokens: number;
    rate_limit_config?: {
      max_concurrent_requests: number;
      max_retries: number;
    };
  } | null>(null);
  const [apiKeys, setApiKeys] = useState<Array<{
    provider: string;
    configured: boolean;
    validation_status: string | null;
    masked_key: string | null;
    last_validated_at: string | null;
  }>>([]);

  // RBAC data states
  const [roles, setRoles] = useState<RoleInfo[]>([]);
  const [resources, setResources] = useState<ResourceInfo[]>([]);
  const [rolePermissions, setRolePermissions] = useState<PermissionInfo[]>([]);

  // UI states
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creatingClient, setCreatingClient] = useState(false);
  const [newClientName, setNewClientName] = useState('');
  const [newCredentials, setNewCredentials] = useState<NewClientCredentials | null>(null);
  const [deletingClientId, setDeletingClientId] = useState<string | null>(null);
  const [rotatingClientId, setRotatingClientId] = useState<string | null>(null);

  // User management states
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
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // RBAC management states
  const [showCreateRoleModal, setShowCreateRoleModal] = useState(false);
  const [newRoleData, setNewRoleData] = useState({ role_name: '', display_name: '', description: '', parent_role: '' });
  const [creatingRole, setCreatingRole] = useState(false);
  const [editingRole, setEditingRole] = useState<RoleInfo | null>(null);
  const [savingRole, setSavingRole] = useState(false);
  const [confirmDeleteRole, setConfirmDeleteRole] = useState<RoleInfo | null>(null);
  const [deletingRole, setDeletingRole] = useState(false);
  const [expandedRoles, setExpandedRoles] = useState<Set<string>>(new Set());
  const [showResourcesPanel, setShowResourcesPanel] = useState(false);

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
        } else if (activeTab === 'roles' && canViewRoles) {
          const [rolesData, resourcesData] = await Promise.all([
            apiClient.listRoles(),
            apiClient.listResources(),
          ]);
          setRoles(rolesData);
          setResources(resourcesData);
        } else if (activeTab === 'system' && canViewSystemStatus) {
          const [status, stats, scheduler, embeddings, extraction, keys] = await Promise.all([
            apiClient.getSystemStatus().catch(() => null),
            apiClient.getDatabaseStats().catch(() => null),
            apiClient.getSchedulerStatus().catch(() => null),
            apiClient.listEmbeddingConfigs().catch(() => []),
            apiClient.getExtractionConfig().catch(() => null),
            apiClient.listApiKeys().catch(() => []),
          ]);
          setSystemStatus(status);
          setDbStats(stats);
          setSchedulerStatus(scheduler);
          setEmbeddingConfigs(embeddings);
          setExtractionConfig(extraction);
          setApiKeys(keys);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [activeTab, isAuthenticated, canViewUsers, canViewAllOAuthClients, canViewRoles, canViewSystemStatus]);

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
      setSuccessMessage(`User '${newUserData.username}' created successfully`);
      setNewUserData({ username: '', password: '', role: 'contributor' });
      setShowCreateUserModal(false);
      // Refresh users list
      const usersData = await apiClient.listUsers({ limit: 100 });
      setUsers(usersData.users);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create user');
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
      setSuccessMessage('User updated successfully');
      setEditingUserId(null);
      // Refresh users list
      const usersData = await apiClient.listUsers({ limit: 100 });
      setUsers(usersData.users);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update user');
    } finally {
      setSavingUser(false);
    }
  };

  const handleDeleteUser = async () => {
    if (!confirmDeleteUser) return;
    setDeletingUserId(confirmDeleteUser.id);
    try {
      await apiClient.deleteUser(confirmDeleteUser.id);
      setSuccessMessage(`User '${confirmDeleteUser.username}' deleted`);
      setConfirmDeleteUser(null);
      // Refresh users list
      const usersData = await apiClient.listUsers({ limit: 100 });
      setUsers(usersData.users);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete user');
    } finally {
      setDeletingUserId(null);
    }
  };

  const handleResetPassword = async () => {
    if (!resetPasswordUserId || !newPassword.trim()) return;
    setResettingPassword(true);
    try {
      const result = await apiClient.resetUserPassword(resetPasswordUserId, newPassword);
      setSuccessMessage(result.message);
      setResetPasswordUserId(null);
      setNewPassword('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset password');
    } finally {
      setResettingPassword(false);
    }
  };

  // Role management handlers
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
      setSuccessMessage(`Role '${newRoleData.display_name}' created successfully`);
      setNewRoleData({ role_name: '', display_name: '', description: '', parent_role: '' });
      setShowCreateRoleModal(false);
      // Refresh roles list
      const rolesData = await apiClient.listRoles();
      setRoles(rolesData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create role');
    } finally {
      setCreatingRole(false);
    }
  };

  const handleDeleteRole = async () => {
    if (!confirmDeleteRole) return;
    setDeletingRole(true);
    try {
      await apiClient.deleteRole(confirmDeleteRole.role_name);
      setSuccessMessage(`Role '${confirmDeleteRole.display_name}' deleted`);
      setConfirmDeleteRole(null);
      // Refresh roles list
      const rolesData = await apiClient.listRoles();
      setRoles(rolesData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete role');
    } finally {
      setDeletingRole(false);
    }
  };

  const loadRolePermissions = async (roleName: string) => {
    try {
      const permissions = await apiClient.listPermissions({ role_name: roleName });
      setRolePermissions(permissions);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load role permissions');
    }
  };

  const handleGrantPermission = async (roleName: string, resourceType: string, action: string) => {
    try {
      await apiClient.grantPermission({
        role_name: roleName,
        resource_type: resourceType,
        action: action,
      });
      setSuccessMessage(`Permission granted: ${resourceType}:${action}`);
      // Refresh permissions for this role
      await loadRolePermissions(roleName);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to grant permission');
    }
  };

  const handleRevokePermission = async (permissionId: number, roleName: string) => {
    try {
      await apiClient.revokePermission(permissionId);
      setSuccessMessage('Permission revoked');
      // Refresh permissions for this role
      await loadRolePermissions(roleName);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to revoke permission');
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

  // Get role hierarchy for display
  const getRoleHierarchy = (role: RoleInfo): string[] => {
    const hierarchy: string[] = [role.role_name];
    let current = role;
    while (current.parent_role) {
      hierarchy.push(current.parent_role);
      const parent = roles.find(r => r.role_name === current.parent_role);
      if (!parent) break;
      current = parent;
    }
    return hierarchy.reverse();
  };

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
    <div className="h-full flex flex-col bg-background">
      {/* Header */}
      <div className="flex-none p-4 border-b border-border dark:border-gray-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-primary" />
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
              <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600 dark:text-gray-400">
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
            {/* Roles tab - requires rbac:read permission (ADR-074) */}
            {canViewRoles && (
              <TabButton
                active={activeTab === 'roles'}
                onClick={() => setActiveTab('roles')}
                icon={<ShieldCheck className="w-4 h-4" />}
                label="Roles"
                badge={roles.length}
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

          {/* Success message */}
          {successMessage && (
            <div className="p-4 bg-status-active/10 border border-status-active/30 rounded-lg flex items-center gap-3">
              <CheckCircle className="w-5 h-5 text-status-active" />
              <p className="text-status-active">{successMessage}</p>
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
                    className="flex-1 px-3 py-2 bg-muted border border-border dark:border-gray-700 rounded-lg text-foreground dark:text-gray-200 placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary dark:focus:ring-blue-500"
                    onKeyDown={(e) => e.key === 'Enter' && handleCreateClient()}
                  />
                  <button
                    onClick={handleCreateClient}
                    disabled={creatingClient || !newClientName.trim()}
                    className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
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

          {/* Roles Tab - requires rbac:read permission (ADR-074) */}
          {!loading && activeTab === 'roles' && canViewRoles && (
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
                  <p className="text-sm text-muted-foreground dark:text-gray-400 mb-4">
                    Resources and actions that can be granted to roles.
                  </p>
                  <div className="space-y-2">
                    {resources.map((resource) => (
                      <div
                        key={resource.resource_type}
                        className="p-3 bg-muted/50/50 rounded-lg"
                      >
                        <div className="flex items-start justify-between">
                          <div>
                            <span className="font-medium text-foreground dark:text-gray-200">
                              {resource.resource_type}
                            </span>
                            {resource.description && (
                              <p className="text-sm text-muted-foreground dark:text-gray-400 mt-0.5">
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
                    onClick={async () => {
                      setLoading(true);
                      const rolesData = await apiClient.listRoles();
                      setRoles(rolesData);
                      setLoading(false);
                    }}
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
                      className="border border-border dark:border-gray-700 rounded-lg overflow-hidden"
                    >
                      {/* Role Header */}
                      <div
                        className={`p-4 cursor-pointer hover:bg-muted/50 dark:hover:bg-gray-800/50 transition-colors ${
                          expandedRoles.has(role.role_name) ? 'bg-muted/30/30' : ''
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
                                <span className="font-medium text-foreground dark:text-gray-200">
                                  {role.display_name}
                                </span>
                                <span className="text-xs text-muted-foreground dark:text-gray-500 font-mono">
                                  ({role.role_name})
                                </span>
                                {role.is_builtin && (
                                  <span className="px-1.5 py-0.5 text-xs rounded bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-300">
                                    built-in
                                  </span>
                                )}
                                {!role.is_active && (
                                  <span className="px-1.5 py-0.5 text-xs rounded bg-red-100 text-red-600 dark:bg-red-900/50 dark:text-red-300">
                                    inactive
                                  </span>
                                )}
                              </div>
                              {role.description && (
                                <p className="text-sm text-muted-foreground dark:text-gray-400 mt-1">
                                  {role.description}
                                </p>
                              )}
                              {role.parent_role && (
                                <div className="flex items-center gap-1 mt-1 text-xs text-muted-foreground dark:text-gray-500">
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
                                className="p-1.5 text-muted-foreground hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
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
                        <div className="border-t border-border dark:border-gray-700 p-4 bg-muted/20/20">
                          <h4 className="text-sm font-medium text-foreground dark:text-gray-300 mb-3">
                            Permissions
                          </h4>
                          {rolePermissions.filter(p => p.role_name === role.role_name).length === 0 ? (
                            <p className="text-sm text-muted-foreground dark:text-gray-400">
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
                                  <span className="text-sm font-medium text-foreground dark:text-gray-300 min-w-[120px]">
                                    {resourceType}:
                                  </span>
                                  {perms.map((p) => (
                                    <span
                                      key={p.id}
                                      className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded ${
                                        p.inherited_from
                                          ? 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                                          : 'bg-status-active/20 text-status-active'
                                      }`}
                                    >
                                      {p.action}
                                      {p.inherited_from && (
                                        <span className="text-gray-400 dark:text-gray-500">
                                          (from {p.inherited_from})
                                        </span>
                                      )}
                                      {canEditRoles && !p.inherited_from && (
                                        <button
                                          onClick={() => handleRevokePermission(p.id, role.role_name)}
                                          className="ml-1 hover:text-red-600"
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
                            <div className="mt-4 pt-4 border-t border-border dark:border-gray-700">
                              <h5 className="text-xs font-medium text-muted-foreground dark:text-gray-400 mb-2">
                                Grant Permission
                              </h5>
                              <div className="flex flex-wrap gap-2">
                                {resources.map((resource) => (
                                  <div key={resource.resource_type} className="relative group">
                                    <button className="px-2 py-1 text-xs bg-muted rounded hover:bg-muted/80 dark:hover:bg-gray-700 transition-colors">
                                      {resource.resource_type}
                                    </button>
                                    <div className="absolute left-0 top-full mt-1 hidden group-hover:block z-10 bg-card border border-border dark:border-gray-700 rounded shadow-lg p-2 min-w-[120px]">
                                      {resource.available_actions.map((action) => {
                                        const hasPermission = rolePermissions.some(
                                          p => p.role_name === role.role_name &&
                                               p.resource_type === resource.resource_type &&
                                               p.action === action
                                        );
                                        return (
                                          <button
                                            key={action}
                                            onClick={() => handleGrantPermission(role.role_name, resource.resource_type, action)}
                                            disabled={hasPermission}
                                            className={`block w-full text-left px-2 py-1 text-xs rounded ${
                                              hasPermission
                                                ? 'text-muted-foreground cursor-not-allowed'
                                                : 'hover:bg-muted dark:hover:bg-gray-800'
                                            }`}
                                          >
                                            {action}
                                            {hasPermission && ' ✓'}
                                          </button>
                                        );
                                      })}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </Section>
            </>
          )}

          {/* System Tab - requires admin:status permission (ADR-074) */}
          {!loading && activeTab === 'system' && canViewSystemStatus && (
            <>
              <Section
                title="System Config"
                icon={<Server className="w-5 h-5" />}
                action={
                  <button
                    onClick={async () => {
                      setLoading(true);
                      const [status, stats, scheduler, embeddings, extraction, keys] = await Promise.all([
                        apiClient.getSystemStatus().catch(() => null),
                        apiClient.getDatabaseStats().catch(() => null),
                        apiClient.getSchedulerStatus().catch(() => null),
                        apiClient.listEmbeddingConfigs().catch(() => []),
                        apiClient.getExtractionConfig().catch(() => null),
                        apiClient.listApiKeys().catch(() => []),
                      ]);
                      setSystemStatus(status);
                      setDbStats(stats);
                      setSchedulerStatus(scheduler);
                      setEmbeddingConfigs(embeddings);
                      setExtractionConfig(extraction);
                      setApiKeys(keys);
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
                    connected={systemStatus?.database_connection?.connected ?? false}
                    label={systemStatus?.database_connection?.connected ? 'Database Connected' : 'Database Offline'}
                  />
                  <StatusBadge
                    connected={systemStatus?.docker?.running ?? false}
                    label={systemStatus?.docker?.running ? 'Container Running' : 'Container Offline'}
                  />
                </div>

                {systemStatus && (
                  <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                    {systemStatus.python_env?.python_version && (
                      <div>
                        <span className="text-muted-foreground dark:text-gray-400">Python:</span>
                        <span className="ml-2 font-mono text-foreground dark:text-gray-200">
                          {systemStatus.python_env.python_version}
                        </span>
                      </div>
                    )}
                    {systemStatus.docker?.status && (
                      <div>
                        <span className="text-muted-foreground dark:text-gray-400">Docker:</span>
                        <span className="ml-2 font-mono text-foreground dark:text-gray-200">
                          {systemStatus.docker.status}
                        </span>
                      </div>
                    )}
                    {systemStatus.configuration && (
                      <>
                        <div>
                          <span className="text-muted-foreground dark:text-gray-400">OpenAI Key:</span>
                          <span className={`ml-2 font-mono ${systemStatus.configuration.openai_key_configured ? 'text-status-active' : 'text-red-600 dark:text-red-400'}`}>
                            {systemStatus.configuration.openai_key_configured ? 'Configured' : 'Not Set'}
                          </span>
                        </div>
                        <div>
                          <span className="text-muted-foreground dark:text-gray-400">Anthropic Key:</span>
                          <span className={`ml-2 font-mono ${systemStatus.configuration.anthropic_key_configured ? 'text-status-active' : 'text-red-600 dark:text-red-400'}`}>
                            {systemStatus.configuration.anthropic_key_configured ? 'Configured' : 'Not Set'}
                          </span>
                        </div>
                      </>
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
                    <div className="p-4 bg-muted/50/50 rounded-lg">
                      <div className="text-2xl font-bold text-foreground dark:text-gray-200">
                        {(dbStats.nodes?.concepts ?? 0).toLocaleString()}
                      </div>
                      <div className="text-sm text-muted-foreground dark:text-gray-400">Concepts</div>
                    </div>
                    <div className="p-4 bg-muted/50/50 rounded-lg">
                      <div className="text-2xl font-bold text-foreground dark:text-gray-200">
                        {(dbStats.nodes?.sources ?? 0).toLocaleString()}
                      </div>
                      <div className="text-sm text-muted-foreground dark:text-gray-400">Sources</div>
                    </div>
                    <div className="p-4 bg-muted/50/50 rounded-lg">
                      <div className="text-2xl font-bold text-foreground dark:text-gray-200">
                        {(dbStats.nodes?.instances ?? 0).toLocaleString()}
                      </div>
                      <div className="text-sm text-muted-foreground dark:text-gray-400">Instances</div>
                    </div>
                    <div className="p-4 bg-muted/50/50 rounded-lg">
                      <div className="text-2xl font-bold text-foreground dark:text-gray-200">
                        {(dbStats.relationships?.total ?? 0).toLocaleString()}
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
                {schedulerStatus?.jobs_by_status ? (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="p-4 bg-status-warning/10 rounded-lg">
                      <div className="text-2xl font-bold text-status-warning">
                        {(schedulerStatus.jobs_by_status.pending ?? 0) + (schedulerStatus.jobs_by_status.awaiting_approval ?? 0)}
                      </div>
                      <div className="text-sm text-status-warning">Pending</div>
                    </div>
                    <div className="p-4 bg-status-info/20 rounded-lg">
                      <div className="text-2xl font-bold text-status-info">
                        {schedulerStatus.jobs_by_status.processing ?? 0}
                      </div>
                      <div className="text-sm text-status-info">Running</div>
                    </div>
                    <div className="p-4 bg-status-active/10 rounded-lg">
                      <div className="text-2xl font-bold text-status-active">
                        {schedulerStatus.jobs_by_status.completed ?? 0}
                      </div>
                      <div className="text-sm text-status-active">Completed</div>
                    </div>
                    <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
                      <div className="text-2xl font-bold text-red-700 dark:text-red-300">
                        {schedulerStatus.jobs_by_status.failed ?? 0}
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
                    className="flex items-center gap-2 px-4 py-2 bg-muted hover:bg-muted/80 dark:hover:bg-gray-700 rounded-lg transition-colors text-foreground dark:text-gray-200"
                  >
                    <FileText className="w-4 h-4" />
                    Swagger UI
                    <ExternalLink className="w-3 h-3 text-muted-foreground" />
                  </a>
                  <a
                    href={`${API_BASE_URL}/redoc`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 px-4 py-2 bg-muted hover:bg-muted/80 dark:hover:bg-gray-700 rounded-lg transition-colors text-foreground dark:text-gray-200"
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

              {/* Embedding Profiles Section */}
              <Section
                title="Embedding Profiles"
                icon={<Cpu className="w-5 h-5" />}
              >
                <p className="text-sm text-muted-foreground dark:text-gray-400 mb-4">
                  Vector embedding model configurations for semantic search.
                </p>
                {embeddingConfigs.length > 0 ? (
                  <div className="space-y-3">
                    {embeddingConfigs.map((config) => (
                      <div
                        key={config.id}
                        className={`p-4 rounded-lg border ${
                          config.active
                            ? 'bg-status-active/10 border-status-active/30'
                            : 'bg-muted/50/50 border-border dark:border-gray-700'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            {config.active ? (
                              <span className="px-2 py-0.5 bg-green-100 dark:bg-green-900/50 text-status-active text-xs font-medium rounded">
                                ACTIVE
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 text-xs font-medium rounded">
                                Inactive
                              </span>
                            )}
                            <span className="font-medium text-foreground dark:text-gray-200">
                              Config {config.id}
                            </span>
                            {config.delete_protected && (
                              <Lock className="w-3 h-3 text-status-warning" title="Delete protected" />
                            )}
                            {config.change_protected && (
                              <Shield className="w-3 h-3 text-status-info" title="Change protected" />
                            )}
                          </div>
                        </div>
                        <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                          <div>
                            <span className="text-muted-foreground dark:text-gray-400">Provider:</span>
                            <span className="ml-1 text-foreground dark:text-gray-200">{config.provider}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground dark:text-gray-400">Model:</span>
                            <span className="ml-1 text-foreground dark:text-gray-200 font-mono text-xs">{config.model_name}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground dark:text-gray-400">Dims:</span>
                            <span className="ml-1 text-foreground dark:text-gray-200">{config.embedding_dimensions}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground dark:text-gray-400">Device:</span>
                            <span className="ml-1 text-foreground dark:text-gray-200">{config.device ?? 'cloud'}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-muted-foreground dark:text-gray-400 text-center py-4">
                    No embedding configurations found.
                  </p>
                )}
                <p className="mt-3 text-xs text-muted-foreground dark:text-gray-500">
                  Use <code className="bg-muted dark:bg-gray-700 px-1 rounded">kg admin embedding</code> to manage profiles
                </p>
              </Section>

              {/* Extraction Config Section */}
              <Section
                title="AI Extraction"
                icon={<BrainCircuit className="w-5 h-5" />}
              >
                <p className="text-sm text-muted-foreground dark:text-gray-400 mb-4">
                  LLM provider for concept extraction from documents.
                </p>
                {extractionConfig ? (
                  <div className="p-4 bg-muted/50/50 rounded-lg border border-border dark:border-gray-700">
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                      <div>
                        <span className="text-muted-foreground dark:text-gray-400">Provider:</span>
                        <span className="ml-2 font-medium text-foreground dark:text-gray-200 capitalize">{extractionConfig.provider}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground dark:text-gray-400">Model:</span>
                        <span className="ml-2 font-mono text-foreground dark:text-gray-200">{extractionConfig.model}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground dark:text-gray-400">Max Tokens:</span>
                        <span className="ml-2 text-foreground dark:text-gray-200">{extractionConfig.max_tokens?.toLocaleString()}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground dark:text-gray-400">Vision:</span>
                        <span className={`ml-2 ${extractionConfig.supports_vision ? 'text-status-active' : 'text-gray-500'}`}>
                          {extractionConfig.supports_vision ? 'Yes' : 'No'}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground dark:text-gray-400">JSON Mode:</span>
                        <span className={`ml-2 ${extractionConfig.supports_json_mode ? 'text-status-active' : 'text-gray-500'}`}>
                          {extractionConfig.supports_json_mode ? 'Yes' : 'No'}
                        </span>
                      </div>
                      {extractionConfig.rate_limit_config && (
                        <div>
                          <span className="text-muted-foreground dark:text-gray-400">Concurrency:</span>
                          <span className="ml-2 text-foreground dark:text-gray-200">
                            {extractionConfig.rate_limit_config.max_concurrent_requests} / {extractionConfig.rate_limit_config.max_retries} retries
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <p className="text-muted-foreground dark:text-gray-400 text-center py-4">
                    No extraction configuration found.
                  </p>
                )}
                <p className="mt-3 text-xs text-muted-foreground dark:text-gray-500">
                  Use <code className="bg-muted dark:bg-gray-700 px-1 rounded">kg admin extraction</code> to configure
                </p>
              </Section>

              {/* API Keys Section */}
              <Section
                title="API Keys"
                icon={<Key className="w-5 h-5" />}
              >
                <p className="text-sm text-muted-foreground dark:text-gray-400 mb-4">
                  API keys for AI providers (encrypted at rest).
                </p>
                {apiKeys.length > 0 ? (
                  <div className="space-y-2">
                    {apiKeys.map((key) => (
                      <div
                        key={key.provider}
                        className="flex items-center justify-between p-3 bg-muted/50/50 rounded-lg border border-border dark:border-gray-700"
                      >
                        <div className="flex items-center gap-3">
                          <span className="font-medium text-foreground dark:text-gray-200 capitalize w-24">
                            {key.provider}
                          </span>
                          {key.configured ? (
                            <>
                              {key.validation_status === 'valid' ? (
                                <span className="flex items-center gap-1 text-status-active text-sm">
                                  <CheckCircle className="w-4 h-4" />
                                  Valid
                                </span>
                              ) : (
                                <span className="flex items-center gap-1 text-status-warning text-sm">
                                  <AlertCircle className="w-4 h-4" />
                                  {key.validation_status ?? 'Unknown'}
                                </span>
                              )}
                              {key.masked_key && (
                                <span className="text-xs text-muted-foreground dark:text-gray-500 font-mono">
                                  {key.masked_key}
                                </span>
                              )}
                            </>
                          ) : (
                            <span className="text-muted-foreground dark:text-gray-500 text-sm">
                              Not configured
                            </span>
                          )}
                        </div>
                        {key.last_validated_at && (
                          <span className="text-xs text-muted-foreground dark:text-gray-500">
                            Validated: {new Date(key.last_validated_at).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-muted-foreground dark:text-gray-400 text-center py-4">
                    No API keys configured.
                  </p>
                )}
                <p className="mt-3 text-xs text-muted-foreground dark:text-gray-500">
                  Use <code className="bg-muted dark:bg-gray-700 px-1 rounded">kg admin keys</code> to manage keys
                </p>
              </Section>
            </>
          )}
        </div>
      </div>

      {/* Create User Modal */}
      {showCreateUserModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card rounded-lg shadow-xl w-full max-w-md mx-4 border border-border dark:border-gray-700">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border dark:border-gray-700">
              <h3 className="font-semibold text-foreground dark:text-gray-200 flex items-center gap-2">
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
                <label className="block text-sm font-medium text-foreground dark:text-gray-300 mb-1">
                  Username
                </label>
                <input
                  type="text"
                  value={newUserData.username}
                  onChange={(e) => setNewUserData(prev => ({ ...prev, username: e.target.value }))}
                  placeholder="Enter username"
                  className="w-full px-3 py-2 bg-muted border border-border dark:border-gray-700 rounded-lg text-foreground dark:text-gray-200 placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary dark:focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground dark:text-gray-300 mb-1">
                  Password
                </label>
                <input
                  type="password"
                  value={newUserData.password}
                  onChange={(e) => setNewUserData(prev => ({ ...prev, password: e.target.value }))}
                  placeholder="Minimum 8 characters"
                  className="w-full px-3 py-2 bg-muted border border-border dark:border-gray-700 rounded-lg text-foreground dark:text-gray-200 placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary dark:focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground dark:text-gray-300 mb-1">
                  Role
                </label>
                <select
                  value={newUserData.role}
                  onChange={(e) => setNewUserData(prev => ({ ...prev, role: e.target.value }))}
                  className="w-full px-3 py-2 bg-muted border border-border dark:border-gray-700 rounded-lg text-foreground dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary dark:focus:ring-blue-500"
                >
                  <option value="read_only">Read Only</option>
                  <option value="contributor">Contributor</option>
                  <option value="curator">Curator</option>
                  <option value="admin">Admin</option>
                  {isPlatformAdmin() && <option value="platform_admin">Platform Admin</option>}
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-2 px-4 py-3 border-t border-border dark:border-gray-700">
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
          <div className="bg-card rounded-lg shadow-xl w-full max-w-md mx-4 border border-border dark:border-gray-700">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border dark:border-gray-700">
              <h3 className="font-semibold text-foreground dark:text-gray-200 flex items-center gap-2">
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
                <label className="block text-sm font-medium text-foreground dark:text-gray-300 mb-1">
                  Username
                </label>
                <div className="px-3 py-2 bg-muted/50/50 border border-border dark:border-gray-700 rounded-lg text-muted-foreground dark:text-gray-400">
                  {users.find(u => u.id === editingUserId)?.username}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground dark:text-gray-300 mb-1">
                  Role
                </label>
                <select
                  value={editUserData.role}
                  onChange={(e) => setEditUserData(prev => ({ ...prev, role: e.target.value }))}
                  className="w-full px-3 py-2 bg-muted border border-border dark:border-gray-700 rounded-lg text-foreground dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary dark:focus:ring-blue-500"
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
                      ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800 text-red-700 dark:text-red-300'
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
            <div className="flex justify-end gap-2 px-4 py-3 border-t border-border dark:border-gray-700">
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
          <div className="bg-card rounded-lg shadow-xl w-full max-w-md mx-4 border border-border dark:border-gray-700">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border dark:border-gray-700">
              <h3 className="font-semibold text-red-600 dark:text-red-400 flex items-center gap-2">
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
              <p className="text-foreground dark:text-gray-300">
                Are you sure you want to delete user <strong>{confirmDeleteUser.username}</strong>?
              </p>
              <p className="text-sm text-muted-foreground dark:text-gray-400 mt-2">
                This action cannot be undone. All associated OAuth clients and tokens will also be deleted.
              </p>
            </div>
            <div className="flex justify-end gap-2 px-4 py-3 border-t border-border dark:border-gray-700">
              <button
                onClick={() => setConfirmDeleteUser(null)}
                className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteUser}
                disabled={deletingUserId === confirmDeleteUser.id}
                className="px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
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
          <div className="bg-card rounded-lg shadow-xl w-full max-w-md mx-4 border border-border dark:border-gray-700">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border dark:border-gray-700">
              <h3 className="font-semibold text-foreground dark:text-gray-200 flex items-center gap-2">
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
                <label className="block text-sm font-medium text-foreground dark:text-gray-300 mb-1">
                  User
                </label>
                <div className="px-3 py-2 bg-muted/50/50 border border-border dark:border-gray-700 rounded-lg text-muted-foreground dark:text-gray-400">
                  {users.find(u => u.id === resetPasswordUserId)?.username}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground dark:text-gray-300 mb-1">
                  New Password
                </label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Minimum 8 characters"
                  className="w-full px-3 py-2 bg-muted border border-border dark:border-gray-700 rounded-lg text-foreground dark:text-gray-200 placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary dark:focus:ring-blue-500"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 px-4 py-3 border-t border-border dark:border-gray-700">
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

      {/* Create Role Modal */}
      {showCreateRoleModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card rounded-lg shadow-xl w-full max-w-md mx-4 border border-border dark:border-gray-700">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border dark:border-gray-700">
              <h3 className="font-semibold text-foreground dark:text-gray-200 flex items-center gap-2">
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
                <label className="block text-sm font-medium text-foreground dark:text-gray-300 mb-1">
                  Role Name (ID) <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={newRoleData.role_name}
                  onChange={(e) => setNewRoleData({ ...newRoleData, role_name: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_') })}
                  placeholder="e.g., data_analyst"
                  className="w-full px-3 py-2 bg-muted border border-border dark:border-gray-700 rounded-lg text-foreground dark:text-gray-200 placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary dark:focus:ring-blue-500"
                />
                <p className="text-xs text-muted-foreground mt-1">Lowercase letters, numbers, and underscores only</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground dark:text-gray-300 mb-1">
                  Display Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={newRoleData.display_name}
                  onChange={(e) => setNewRoleData({ ...newRoleData, display_name: e.target.value })}
                  placeholder="e.g., Data Analyst"
                  className="w-full px-3 py-2 bg-muted border border-border dark:border-gray-700 rounded-lg text-foreground dark:text-gray-200 placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary dark:focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground dark:text-gray-300 mb-1">
                  Description
                </label>
                <textarea
                  value={newRoleData.description}
                  onChange={(e) => setNewRoleData({ ...newRoleData, description: e.target.value })}
                  placeholder="Describe the role's purpose..."
                  rows={2}
                  className="w-full px-3 py-2 bg-muted border border-border dark:border-gray-700 rounded-lg text-foreground dark:text-gray-200 placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary dark:focus:ring-blue-500 resize-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground dark:text-gray-300 mb-1">
                  Parent Role (Inherits Permissions)
                </label>
                <select
                  value={newRoleData.parent_role}
                  onChange={(e) => setNewRoleData({ ...newRoleData, parent_role: e.target.value })}
                  className="w-full px-3 py-2 bg-muted border border-border dark:border-gray-700 rounded-lg text-foreground dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary dark:focus:ring-blue-500"
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
            <div className="flex justify-end gap-2 px-4 py-3 border-t border-border dark:border-gray-700">
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
          <div className="bg-card rounded-lg shadow-xl w-full max-w-md mx-4 border border-border dark:border-gray-700">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border dark:border-gray-700">
              <h3 className="font-semibold text-red-600 dark:text-red-400 flex items-center gap-2">
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
              <p className="text-foreground dark:text-gray-200">
                Are you sure you want to delete the role <strong>&quot;{confirmDeleteRole.display_name}&quot;</strong>?
              </p>
              <div className="p-3 bg-status-warning/10 border border-status-warning/20 rounded-lg">
                <p className="text-sm text-status-warning">
                  <strong>Warning:</strong> This will remove all permission assignments for this role.
                  Users assigned to this role will lose those permissions.
                </p>
              </div>
              {confirmDeleteRole.is_builtin && (
                <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                  <p className="text-sm text-red-800 dark:text-red-200">
                    <strong>Note:</strong> This is a built-in role. Deleting it may affect system functionality.
                  </p>
                </div>
              )}
            </div>
            <div className="flex justify-end gap-2 px-4 py-3 border-t border-border dark:border-gray-700">
              <button
                onClick={() => setConfirmDeleteRole(null)}
                className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteRole}
                disabled={deletingRole}
                className="px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
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
    </div>
  );
};

export default AdminDashboard;
