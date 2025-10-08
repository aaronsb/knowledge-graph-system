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

export interface KgConfig {
  username?: string;
  secret?: string;  // API key (never store password!)
  api_url?: string;
  backup_dir?: string;
  mcp?: McpConfig;
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
