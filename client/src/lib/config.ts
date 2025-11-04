/**
 * Configuration Manager for kg CLI
 *
 * Manages user configuration stored at ~/.config/kg/config.json
 *
 * ADR-054: OAuth 2.0 Authentication
 * - All authentication uses personal OAuth clients (GitHub CLI-style)
 * - Client credentials (client_id + client_secret) are long-lived
 * - Fresh access tokens obtained on-demand via client credentials grant
 * - JWT support removed (OAuth-only)
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
  // ADR-054: OAuth 2.0 Client Credentials (Personal OAuth Client)
  oauth_client_id?: string;        // OAuth client ID (kg-cli-username-random)
  oauth_client_secret?: string;    // OAuth client secret (hashed on server)
  oauth_client_name?: string;      // Client name for display
  oauth_scopes?: string[];         // OAuth scopes granted
  oauth_created_at?: string;       // ISO 8601 timestamp

  // Metadata
  token_type?: string;             // Always "bearer"
  username?: string;               // Cached username
  role?: string;                   // Cached role
}

export interface DisplayConfig {
  // ADR-057: Terminal image display with chafa
  enableChafa?: boolean;           // Enable inline terminal image display (default: true if chafa installed)
  chafaWidth?: number;             // Terminal width for image display (default: auto)
  chafaScale?: number;             // Scale factor 0.0-1.0 (e.g., 0.3 for 1/3 width, default: 0.3)
  chafaAlign?: 'left' | 'center' | 'right';  // Image alignment (default: left)
  chafaColors?: '256' | '16' | '2' | 'full';  // Color mode (default: 256)
}

export interface SearchConfig {
  // ADR-057: Search command display defaults
  showEvidence?: boolean;          // Show evidence quotes by default in search results (default: true)
  showImages?: boolean;            // Display images inline by default in search results (default: true)
}

export interface KgConfig {
  username?: string;
  secret?: string;  // API key (never store password!)
  api_url?: string;
  backup_dir?: string;
  auto_approve?: boolean;  // ADR-014: Auto-approve all jobs by default
  auth?: AuthTokenConfig;   // ADR-054: OAuth 2.0 client credentials
  mcp?: McpConfig;
  aliases?: Record<string, string[]>;  // ADR-029: User-configurable command aliases
  display?: DisplayConfig;  // ADR-057: Display preferences
  search?: SearchConfig;    // ADR-057: Search command defaults
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
      },
      // ADR-057: Display and search defaults
      display: {
        enableChafa: true,   // Enable chafa if available
        chafaScale: 0.3,     // Default to 1/3 terminal width
        chafaAlign: 'left',  // Default to left alignment
        chafaColors: '256'   // Default to 256 colors for best compatibility
      },
      search: {
        showEvidence: true,  // Show evidence quotes by default
        showImages: true     // Display images inline by default
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
   * Store OAuth client credentials (ADR-054 - personal OAuth clients)
   *
   * Stores long-lived client_id + client_secret for client credentials grant.
   * This is the preferred authentication method for CLI tools.
   *
   * @param credentials OAuth client credentials
   */
  storeOAuthCredentials(credentials: {
    client_id: string;
    client_secret: string;
    client_name: string;
    scopes: string[];
    created_at: string;
    username?: string;
  }): void {
    this.set('auth.oauth_client_id', credentials.client_id);
    this.set('auth.oauth_client_secret', credentials.client_secret);
    this.set('auth.oauth_client_name', credentials.client_name);
    this.set('auth.oauth_scopes', credentials.scopes);
    this.set('auth.oauth_created_at', credentials.created_at);
    this.set('auth.token_type', 'bearer');

    if (credentials.username) {
      this.set('auth.username', credentials.username);
      this.set('username', credentials.username);  // Backwards compatibility
    }

    // Clear any legacy fields
    this.delete('auth.token');
    this.delete('auth.access_token');
    this.delete('auth.refresh_token');
    this.delete('auth.expires_at');
    this.delete('auth.client_id');
    this.delete('auth.scope');
  }

  /**
   * Get OAuth client credentials (ADR-054)
   *
   * @returns OAuth client credentials or null if not stored
   */
  getOAuthCredentials(): {
    client_id: string;
    client_secret: string;
    client_name: string;
    scopes: string[];
    created_at: string;
    username?: string;
  } | null {
    const clientId = this.get('auth.oauth_client_id');
    const clientSecret = this.get('auth.oauth_client_secret');

    if (!clientId || !clientSecret) {
      return null;
    }

    return {
      client_id: clientId,
      client_secret: clientSecret,
      client_name: this.get('auth.oauth_client_name') || 'kg-cli',
      scopes: this.get('auth.oauth_scopes') || [],
      created_at: this.get('auth.oauth_created_at') || new Date().toISOString(),
      username: this.get('auth.username')
    };
  }


  /**
   * Clear authentication token
   */
  clearAuthToken(): void {
    this.delete('auth');
  }

  /**
   * Check if user is authenticated (has OAuth client credentials)
   *
   * OAuth client credentials are long-lived and do not expire.
   * Fresh access tokens are obtained on-demand via client credentials grant.
   *
   * @returns true if user has OAuth client credentials
   */
  isAuthenticated(): boolean {
    return this.getOAuthCredentials() !== null;
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

  // ========== Display Methods (ADR-057) ==========

  /**
   * Check if chafa terminal image display is enabled
   * If not explicitly set, defaults to true (will check for chafa availability at runtime)
   *
   * @returns true if chafa display is enabled in config
   */
  isChafaEnabled(): boolean {
    return this.config.display?.enableChafa ?? true;
  }

  /**
   * Enable or disable chafa terminal image display
   *
   * @param enabled Whether to enable chafa
   */
  setChafaEnabled(enabled: boolean): void {
    if (!this.config.display) {
      this.config.display = {};
    }
    this.config.display.enableChafa = enabled;
    this.save();
  }

  /**
   * Get chafa display width
   *
   * @returns Width in characters, or undefined for auto-sizing
   */
  getChafaWidth(): number | undefined {
    return this.config.display?.chafaWidth;
  }

  /**
   * Set chafa display width
   *
   * @param width Width in characters (undefined for auto)
   */
  setChafaWidth(width: number | undefined): void {
    if (!this.config.display) {
      this.config.display = {};
    }
    this.config.display.chafaWidth = width;
    this.save();
  }

  /**
   * Get chafa color mode
   *
   * @returns Color mode ('256', '16', '2', or 'full')
   */
  getChafaColors(): '256' | '16' | '2' | 'full' {
    return this.config.display?.chafaColors ?? '256';
  }

  /**
   * Set chafa color mode
   *
   * @param colors Color mode
   */
  setChafaColors(colors: '256' | '16' | '2' | 'full'): void {
    if (!this.config.display) {
      this.config.display = {};
    }
    this.config.display.chafaColors = colors;
    this.save();
  }

  /**
   * Get chafa scale factor
   *
   * @returns Scale factor (0.0-1.0, e.g., 0.3 for 1/3 width)
   */
  getChafaScale(): number {
    return this.config.display?.chafaScale ?? 0.3;
  }

  /**
   * Set chafa scale factor
   *
   * @param scale Scale factor (0.0-1.0)
   */
  setChafaScale(scale: number): void {
    if (!this.config.display) {
      this.config.display = {};
    }
    this.config.display.chafaScale = scale;
    this.save();
  }

  /**
   * Get chafa alignment
   *
   * @returns Alignment ('left', 'center', or 'right')
   */
  getChafaAlign(): 'left' | 'center' | 'right' {
    return this.config.display?.chafaAlign ?? 'left';
  }

  /**
   * Set chafa alignment
   *
   * @param align Alignment
   */
  setChafaAlign(align: 'left' | 'center' | 'right'): void {
    if (!this.config.display) {
      this.config.display = {};
    }
    this.config.display.chafaAlign = align;
    this.save();
  }

  // ========== Search Methods (ADR-057) ==========

  /**
   * Check if search should show evidence by default
   * Defaults to true for rich terminal experience
   *
   * @returns true if evidence should be shown by default
   */
  getSearchShowEvidence(): boolean {
    return this.config.search?.showEvidence ?? true;
  }

  /**
   * Set whether search should show evidence by default
   *
   * @param enabled Whether to show evidence by default
   */
  setSearchShowEvidence(enabled: boolean): void {
    if (!this.config.search) {
      this.config.search = {};
    }
    this.config.search.showEvidence = enabled;
    this.save();
  }

  /**
   * Check if search should show images by default
   * Defaults to true for rich terminal experience
   *
   * @returns true if images should be shown by default
   */
  getSearchShowImages(): boolean {
    return this.config.search?.showImages ?? true;
  }

  /**
   * Set whether search should show images by default
   *
   * @param enabled Whether to show images by default
   */
  setSearchShowImages(enabled: boolean): void {
    if (!this.config.search) {
      this.config.search = {};
    }
    this.config.search.showImages = enabled;
    this.save();
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
