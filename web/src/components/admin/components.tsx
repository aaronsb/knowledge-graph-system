/**
 * Admin Shared Components
 *
 * Reusable UI components for admin tabs.
 */

import React, { useState } from 'react';
import {
  Clock,
  Activity,
  Key,
  User,
  Trash2,
  RotateCw,
  Loader2,
  Copy,
  Check,
  Eye,
  EyeOff,
  ChevronRight,
  Server,
  Edit2,
  KeyRound,
} from 'lucide-react';
import { API_BASE_URL } from '../../api/client';
import type { OAuthClient, NewClientCredentials, UserInfo } from './types';

// Tab button component
export const TabButton: React.FC<{
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
        : 'text-muted-foreground hover:text-foreground hover:bg-muted'
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
export const Section: React.FC<{
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  action?: React.ReactNode;
}> = ({ title, icon, children, action }) => (
  <section className="bg-card rounded-lg border border-border overflow-hidden">
    <div className="px-4 py-3 border-b border-border flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className="text-muted-foreground">{icon}</span>
        <h2 className="font-semibold text-card-foreground">{title}</h2>
      </div>
      {action}
    </div>
    <div className="p-4">{children}</div>
  </section>
);

// Info Card component
export const InfoCard: React.FC<{
  icon: React.ReactNode;
  label: string;
  value: string | number;
  subValue?: string;
}> = ({ icon, label, value, subValue }) => (
  <div className="p-4 bg-muted/50 rounded-lg">
    <div className="flex items-center gap-2 text-muted-foreground mb-1">
      {icon}
      <span className="text-sm">{label}</span>
    </div>
    <div className="text-2xl font-bold text-foreground">{value}</div>
    {subValue && (
      <div className="text-xs text-muted-foreground mt-1">{subValue}</div>
    )}
  </div>
);

// Status Badge
export const StatusBadge: React.FC<{
  connected: boolean;
  label: string;
}> = ({ connected, label }) => (
  <div className={`
    flex items-center gap-2 px-3 py-2 rounded-lg
    ${connected
      ? 'bg-status-active/10 text-status-active'
      : 'bg-destructive/10 text-destructive'
    }
  `}>
    <span className={`w-2 h-2 rounded-full ${connected ? 'bg-status-active' : 'bg-destructive'}`} />
    {label}
  </div>
);

// Format date helper
export const formatDate = (dateStr: string | null) => {
  if (!dateStr) return 'Never';
  return new Date(dateStr).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
};

export const formatDateTime = (dateStr: string | null) => {
  if (!dateStr) return 'Never';
  return new Date(dateStr).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

// OAuth Client Card
export const OAuthClientCard: React.FC<{
  client: OAuthClient;
  onDelete: (clientId: string) => void;
  onRotate?: (clientId: string) => void;
  isDeleting: boolean;
  isRotating?: boolean;
  showOwner?: boolean;
}> = ({ client, onDelete, onRotate, isDeleting, isRotating, showOwner }) => {
  const [confirmDelete, setConfirmDelete] = useState(false);

  const ownerUsername = client.metadata?.username;

  return (
    <div className="p-4 bg-muted/50 rounded-lg border border-border">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-medium text-foreground">
              {client.client_name}
            </h3>
            <span className="px-2 py-0.5 text-xs rounded-full bg-primary/10 text-primary">
              {client.client_type}
            </span>
            {client.is_active === false && (
              <span className="px-2 py-0.5 text-xs rounded-full bg-destructive/20 text-destructive">
                inactive
              </span>
            )}
          </div>
          <div className="mt-1 text-sm text-muted-foreground font-mono">
            {client.client_id}
          </div>
          <div className="mt-2 flex flex-wrap gap-4 text-xs text-muted-foreground">
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
                className="px-2 py-1 text-xs bg-destructive text-white rounded hover:bg-destructive/90 disabled:opacity-50"
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
                className="p-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded transition-colors"
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
export const NewClientCredentialsDisplay: React.FC<{
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
                <code className="flex-1 px-3 py-2 bg-white dark:bg-gray-900 rounded border border-status-active/30 text-sm font-mono overflow-x-auto">
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
                <code className="flex-1 px-3 py-2 bg-white dark:bg-gray-900 rounded border border-status-active/30 text-sm font-mono overflow-x-auto">
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
            <div className="mt-3 p-3 bg-white dark:bg-gray-900 rounded-lg border border-status-active/30 space-y-4 w-full max-w-full overflow-hidden">
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
                <div className="overflow-x-auto rounded bg-muted max-w-full">
                  <pre className="p-3 text-xs font-mono text-foreground whitespace-pre w-max">
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
                <div className="overflow-x-auto rounded bg-muted max-w-full">
                  <pre className="p-3 text-xs font-mono text-foreground whitespace-pre w-max">
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
              className="px-3 py-1.5 text-sm bg-status-active text-white rounded hover:bg-status-active/90 transition-colors"
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
export const UserRow: React.FC<{
  user: UserInfo;
  isCurrentUser: boolean;
  canEdit?: boolean;
  canDelete?: boolean;
  onEdit?: (user: UserInfo) => void;
  onDelete?: (user: UserInfo) => void;
  onResetPassword?: (userId: number) => void;
}> = ({ user, isCurrentUser, canEdit, canDelete, onEdit, onDelete, onResetPassword }) => {
  const showActions = (canEdit || canDelete) && !isCurrentUser;

  return (
    <tr className={`border-b border-border last:border-0 ${isCurrentUser ? 'bg-primary/5' : ''}`}>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="font-medium text-foreground">
            {user.username}
          </span>
          {isCurrentUser && (
            <span className="px-1.5 py-0.5 text-xs rounded bg-primary/20 text-primary">
              you
            </span>
          )}
          {user.disabled && (
            <span className="px-1.5 py-0.5 text-xs rounded bg-destructive/20 text-destructive">
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
      <td className="px-4 py-3 text-sm text-muted-foreground">
        {formatDateTime(user.created_at)}
      </td>
      <td className="px-4 py-3 text-sm text-muted-foreground">
        {formatDateTime(user.last_login)}
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
                className="p-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded transition-colors"
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
