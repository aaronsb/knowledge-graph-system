/**
 * Admin Dashboard Types
 *
 * Shared type definitions for admin components.
 */

export interface OAuthClient {
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
  last_used?: string | null;
  token_count?: number;
}

export interface UserInfo {
  id: number;
  username: string;
  role: string;
  created_at: string;
  last_login: string | null;
  disabled: boolean;
}

export interface SystemStatus {
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

export interface NewClientCredentials {
  client_id: string;
  client_secret: string;
  client_name: string;
}

export interface RoleInfo {
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

export interface ResourceInfo {
  resource_type: string;
  description: string | null;
  parent_type: string | null;
  available_actions: string[];
  supports_scoping: boolean;
  metadata: Record<string, unknown>;
  registered_at: string;
  registered_by: string | null;
}

export interface PermissionInfo {
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

export interface EmbeddingConfig {
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
}

export interface ExtractionConfig {
  provider: string;
  model: string;
  supports_vision: boolean;
  supports_json_mode: boolean;
  max_tokens: number;
  rate_limit_config?: {
    max_concurrent_requests: number;
    max_retries: number;
  };
}

export interface ApiKeyInfo {
  provider: string;
  configured: boolean;
  validation_status: string | null;
  masked_key: string | null;
  last_validated_at: string | null;
}

export interface SchedulerStatus {
  jobs_by_status: Record<string, number>;
  last_cleanup: string | null;
  next_cleanup: string | null;
}

export type TabType = 'account' | 'users' | 'roles' | 'system';
