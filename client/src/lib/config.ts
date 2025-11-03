/**
 * Configuration Manager for kg CLI
 *
 * Manages user configuration stored at ~/.config/kg/config.json
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export interface McpToolConfig {
  enabled: boolean;
  description?: string;
}

export interface McpConfig {
  enabled: boolean;
  tools: Record<string, McpToolConfig>;
}

export interface AuthTokenConfig {
  token?: string;           // Legacy JWT access token (ADR-027, deprecated)
  token_type?: string;      // Token type (usually "bearer")
  expires_at?: number;      // Unix timestamp (seconds)
  username?: string;        // Cached username from token
  role?: string;            // Cached role from token

  // ADR-054: OAuth 2.0 token fields
  access_token?: string;    // OAuth access token
  refresh_token?: string;   // OAuth refresh token (for device flow)
  client_id?: string;       // OAuth client ID (kg-cli, kg-mcp, etc.)
  scope?: string;           // Space-separated OAuth scopes
}

export interface KgConfig {
  username?: string;
  secret?: string;  // API key (never store password!)
  api_url?: string;
  backup_dir?: string;
  auto_approve?: boolean;  // ADR-014: Auto-approve all jobs by default
  auth?: AuthTokenConfig;   // ADR-027: JWT token storage
  mcp?: McpConfig;
  aliases?: Record<string, string[]>;  // ADR-029: User-configurable command aliases
}

export class ConfigManager {
  private configDir: string;
  private configPath: string;
  private config: KgConfig;

  constructor() {
    // Use XDG config directory (~/.config/kg/)
    const xdgConfig = process.env.XDG_CONFIG_HOME || path.join(os.homedir(), '.config');
    this.configDir = path.join(xdgConfig, 'kg');
    this.configPath = path.join(this.configDir, 'config.json');
    this.config = this.load();
  }

  /**
   * Get configuration directory path
   */
  getConfigDir(): string {
    return this.configDir;
  }

  /**
   * Get configuration file path
   */
  getConfigPath(): string {
    return this.configPath;
  }

  /**
   * Load configuration from disk
   */
  private load(): KgConfig {
    try {
      if (fs.existsSync(this.configPath)) {
        const data = fs.readFileSync(this.configPath, 'utf-8');
        return JSON.parse(data);
      }
    } catch (error) {
      console.warn(`Warning: Failed to load config from ${this.configPath}:`, error);
    }

    // Return default config
    return this.getDefaultConfig();
  }

  /**
   * Get default configuration
   */
  private getDefaultConfig(): KgConfig {
    return {
      api_url: 'http://localhost:8000',
      backup_dir: path.join(os.homedir(), '.local', 'share', 'kg', 'backups'),
      auto_approve: false,  // ADR-014: Require manual approval by default
      mcp: {
        enabled: true,
        tools: {
          search_concepts: { enabled: true, description: 'Search for concepts using natural language' },
          get_concept_details: { enabled: true, description: 'Get detailed information about a concept' },
          find_related_concepts: { enabled: true, description: 'Find concepts related through graph traversal' },
          find_connection: { enabled: true, description: 'Find shortest path between concepts' },
          ingest_document: { enabled: true, description: 'Ingest a document into the knowledge graph' },
          list_ontologies: { enabled: true, description: 'List all ontologies' },
          get_database_stats: { enabled: true, description: 'Get database statistics' }
        }
      },
      // ADR-029: Command aliases for shell compatibility
      // Example: zsh users with 'alias cat=bat' can use this to prevent expansion conflicts
      aliases: {
        cat: ['bat']  // Allow 'kg bat' as alias for 'kg cat' (handles zsh cat→bat expansion)
      }
    };
  }

  /**
   * Save configuration to disk
   */
  save(): void {
    try {
      // Ensure config directory exists
      if (!fs.existsSync(this.configDir)) {
        fs.mkdirSync(this.configDir, { recursive: true });
      }

      // Write config file
      fs.writeFileSync(
        this.configPath,
        JSON.stringify(this.config, null, 2),
        'utf-8'
      );
    } catch (error) {
      throw new Error(`Failed to save config to ${this.configPath}: ${error}`);
    }
  }

  /**
   * Get entire configuration
   */
  getAll(): KgConfig {
    return { ...this.config };
  }

  /**
   * Get a configuration value by key (supports nested keys with dot notation)
   */
  get(key: string): any {
    const keys = key.split('.');
    let value: any = this.config;

    for (const k of keys) {
      if (value && typeof value === 'object' && k in value) {
        value = value[k];
      } else {
        return undefined;
      }
    }

    return value;
  }

  /**
   * Set a configuration value by key (supports nested keys with dot notation)
   */
  set(key: string, value: any): void {
    const keys = key.split('.');
    const lastKey = keys.pop()!;
    let obj: any = this.config;

    // Navigate to the nested object
    for (const k of keys) {
      if (!(k in obj) || typeof obj[k] !== 'object') {
        obj[k] = {};
      }
      obj = obj[k];
    }

    obj[lastKey] = value;
    this.save();
  }

  /**
   * Delete a configuration key
   */
  delete(key: string): void {
    const keys = key.split('.');
    const lastKey = keys.pop()!;
    let obj: any = this.config;

    // Navigate to the nested object
    for (const k of keys) {
      if (!(k in obj) || typeof obj[k] !== 'object') {
        return; // Key doesn't exist
      }
      obj = obj[k];
    }

    delete obj[lastKey];
    this.save();
  }

  /**
   * Enable an MCP tool
   */
  enableMcpTool(toolName: string): void {
    if (!this.config.mcp) {
      this.config.mcp = { enabled: true, tools: {} };
    }

    if (!this.config.mcp.tools[toolName]) {
      this.config.mcp.tools[toolName] = { enabled: true };
    } else {
      this.config.mcp.tools[toolName].enabled = true;
    }

    this.save();
  }

  /**
   * Disable an MCP tool
   */
  disableMcpTool(toolName: string): void {
    if (!this.config.mcp) {
      this.config.mcp = { enabled: true, tools: {} };
    }

    if (!this.config.mcp.tools[toolName]) {
      this.config.mcp.tools[toolName] = { enabled: false };
    } else {
      this.config.mcp.tools[toolName].enabled = false;
    }

    this.save();
  }

  /**
   * Get MCP tool status
   */
  getMcpToolStatus(toolName: string): boolean {
    return this.config.mcp?.tools?.[toolName]?.enabled ?? false;
  }

  /**
   * List all MCP tools
   */
  listMcpTools(): Record<string, McpToolConfig> {
    return this.config.mcp?.tools ?? {};
  }

  /**
   * Check if config file exists
   */
  exists(): boolean {
    return fs.existsSync(this.configPath);
  }

  /**
   * Initialize config with defaults and save
   */
  init(): void {
    if (!this.exists()) {
      this.config = this.getDefaultConfig();
      this.save();
    }
  }

  /**
   * Reset configuration to defaults
   */
  reset(): void {
    this.config = this.getDefaultConfig();
    this.save();
  }

  /**
   * Get API URL (from config or environment variable)
   */
  getApiUrl(): string {
    return process.env.KG_API_URL || this.config.api_url || 'http://localhost:8000';
  }

  /**
   * Get client ID (from config or environment variable)
   */
  getClientId(): string | undefined {
    return process.env.KG_CLIENT_ID || this.config.username;
  }

  /**
   * Get API key/secret (from config or environment variable)
   */
  getApiKey(): string | undefined {
    return process.env.KG_API_KEY || this.config.secret;
  }

  /**
   * Get backup directory (expands ~ to home directory)
   */
  getBackupDir(): string {
    const dir = this.config.backup_dir || path.join(os.homedir(), '.local', 'share', 'kg', 'backups');
    return dir.replace(/^~/, os.homedir());
  }

  /**
   * Ensure backup directory exists
   */
  ensureBackupDir(): string {
    const dir = this.getBackupDir();
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    return dir;
  }

  /**
   * Get auto-approve setting (ADR-014)
   */
  getAutoApprove(): boolean {
    return this.config.auto_approve ?? false;
  }

  /**
   * Set auto-approve setting (ADR-014)
   */
  setAutoApprove(value: boolean): void {
    this.config.auto_approve = value;
    this.save();
  }

  // ========== Authentication Methods (ADR-027, updated by ADR-054) ==========

  /**
   * Store OAuth 2.0 token (ADR-054)
   *
   * @param tokenInfo OAuth token information
   */
  storeOAuthToken(tokenInfo: {
    access_token: string;
    token_type: string;
    expires_at: number;
    refresh_token?: string;
    client_id: string;
    scope: string;
    username?: string;
    role?: string;
  }): void {
    this.set('auth.access_token', tokenInfo.access_token);
    this.set('auth.token_type', tokenInfo.token_type);
    this.set('auth.expires_at', tokenInfo.expires_at);
    this.set('auth.client_id', tokenInfo.client_id);
    this.set('auth.scope', tokenInfo.scope);

    if (tokenInfo.refresh_token) {
      this.set('auth.refresh_token', tokenInfo.refresh_token);
    }

    if (tokenInfo.username) {
      this.set('auth.username', tokenInfo.username);
      this.set('username', tokenInfo.username);  // Backwards compatibility
    }

    if (tokenInfo.role) {
      this.set('auth.role', tokenInfo.role);
    }

    // Clear legacy JWT token field
    this.delete('auth.token');
  }

  /**
   * Store authentication token (Legacy JWT, ADR-027 - deprecated)
   *
   * @deprecated Use storeOAuthToken() instead (ADR-054)
   * @param tokenInfo Token information including access token, expiration, user details
   */
  storeAuthToken(tokenInfo: {
    access_token: string;
    token_type: string;
    expires_at: number;
    username: string;
    role: string;
  }): void {
    this.set('auth.token', tokenInfo.access_token);
    this.set('auth.token_type', tokenInfo.token_type);
    this.set('auth.expires_at', tokenInfo.expires_at);
    this.set('auth.username', tokenInfo.username);
    this.set('auth.role', tokenInfo.role);

    // Also update top-level username for backwards compatibility
    this.set('username', tokenInfo.username);
  }

  /**
   * Retrieve OAuth 2.0 token (ADR-054)
   *
   * @returns OAuth token information or null if not authenticated
   */
  getOAuthToken(): {
    access_token: string;
    token_type: string;
    expires_at: number;
    refresh_token?: string;
    client_id: string;
    scope: string;
    username?: string;
    role?: string;
  } | null {
    const accessToken = this.get('auth.access_token');
    const clientId = this.get('auth.client_id');

    if (!accessToken || !clientId) {
      return null;
    }

    return {
      access_token: accessToken,
      token_type: this.get('auth.token_type') || 'Bearer',
      expires_at: this.get('auth.expires_at') || 0,
      refresh_token: this.get('auth.refresh_token'),
      client_id: clientId,
      scope: this.get('auth.scope') || '',
      username: this.get('auth.username'),
      role: this.get('auth.role')
    };
  }

  /**
   * Retrieve authentication token (supports both OAuth and legacy JWT)
   *
   * Returns OAuth token if available, otherwise falls back to legacy JWT.
   *
   * @returns Token information or null if not authenticated
   */
  getAuthToken(): {
    access_token: string;
    token_type: string;
    expires_at: number;
    username: string;
    role: string;
  } | null {
    // Try OAuth token first (ADR-054)
    const oauthToken = this.getOAuthToken();
    if (oauthToken) {
      return {
        access_token: oauthToken.access_token,
        token_type: oauthToken.token_type,
        expires_at: oauthToken.expires_at,
        username: oauthToken.username || '',
        role: oauthToken.role || ''
      };
    }

    // Fall back to legacy JWT token (ADR-027)
    const token = this.get('auth.token');
    if (!token) {
      return null;
    }

    return {
      access_token: token,
      token_type: this.get('auth.token_type') || 'bearer',
      expires_at: this.get('auth.expires_at') || 0,
      username: this.get('auth.username') || '',
      role: this.get('auth.role') || ''
    };
  }

  /**
   * Clear authentication token
   */
  clearAuthToken(): void {
    this.delete('auth');
  }

  /**
   * Check if user is authenticated (has valid, non-expired token)
   *
   * @returns true if user has a valid token
   */
  isAuthenticated(): boolean {
    const tokenInfo = this.getAuthToken();
    if (!tokenInfo) {
      return false;
    }

    const now = Math.floor(Date.now() / 1000);
    const BUFFER_SECONDS = 5 * 60;  // 5-minute buffer

    return tokenInfo.expires_at > now + BUFFER_SECONDS;
  }

  // ========== Alias Methods (ADR-029) ==========

  /**
   * Get command aliases from config
   *
   * @returns Record mapping command names to their aliases
   */
  getAliases(): Record<string, string[]> {
    return this.config.aliases ?? {};
  }

  /**
   * Get aliases for a specific command
   *
   * @param commandName Name of the command
   * @returns Array of aliases for this command
   */
  getCommandAliases(commandName: string): string[] {
    return this.config.aliases?.[commandName] ?? [];
  }

  /**
   * Add an alias for a command
   *
   * @param commandName Name of the command
   * @param alias Alias to add
   */
  addAlias(commandName: string, alias: string): void {
    if (!this.config.aliases) {
      this.config.aliases = {};
    }

    if (!this.config.aliases[commandName]) {
      this.config.aliases[commandName] = [];
    }

    if (!this.config.aliases[commandName].includes(alias)) {
      this.config.aliases[commandName].push(alias);
      this.save();
    }
  }

  /**
   * Remove an alias for a command
   *
   * @param commandName Name of the command
   * @param alias Alias to remove
   */
  removeAlias(commandName: string, alias: string): void {
    if (!this.config.aliases?.[commandName]) {
      return;
    }

    const index = this.config.aliases[commandName].indexOf(alias);
    if (index !== -1) {
      this.config.aliases[commandName].splice(index, 1);

      // Clean up empty arrays
      if (this.config.aliases[commandName].length === 0) {
        delete this.config.aliases[commandName];
      }

      this.save();
    }
  }
}

/**
 * Global config instance
 */
let globalConfig: ConfigManager | null = null;

/**
 * Get or create global config instance
 */
export function getConfig(): ConfigManager {
  if (!globalConfig) {
    globalConfig = new ConfigManager();
  }
  return globalConfig;
}
