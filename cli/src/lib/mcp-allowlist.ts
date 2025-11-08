/**
 * MCP File Access Allowlist Manager
 *
 * ADR-062: MCP File Ingestion Security Model
 *
 * Manages path allowlist for secure file/directory ingestion from MCP server.
 * Agent-readable but not agent-writable (CLI-only configuration).
 *
 * Security Model:
 * - Fail-secure validation (blocked patterns checked first)
 * - Explicit allowlist (no access without configuration)
 * - Path resolution prevents traversal attacks (../../../)
 * - Size/count limits prevent resource exhaustion
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { minimatch } from 'minimatch';

export interface AllowlistConfig {
  version: string;
  allowed_directories: string[];
  allowed_patterns: string[];
  blocked_patterns: string[];
  max_file_size_mb: number;
  max_files_per_directory: number;
}

export interface ValidationResult {
  allowed: boolean;
  reason?: string;
  hint?: string;
}

export class McpAllowlistManager {
  private configDir: string;
  private allowlistPath: string;
  private config: AllowlistConfig | null;

  constructor() {
    // Use XDG config directory (~/.config/kg/)
    const xdgConfig = process.env.XDG_CONFIG_HOME || path.join(os.homedir(), '.config');
    this.configDir = path.join(xdgConfig, 'kg');
    this.allowlistPath = path.join(this.configDir, 'mcp-allowed-paths.json');
    this.config = this.load();
  }

  /**
   * Get allowlist file path
   */
  getAllowlistPath(): string {
    return this.allowlistPath;
  }

  /**
   * Load allowlist from disk
   */
  private load(): AllowlistConfig | null {
    try {
      if (fs.existsSync(this.allowlistPath)) {
        const data = fs.readFileSync(this.allowlistPath, 'utf-8');
        return JSON.parse(data);
      }
    } catch (error) {
      console.warn(`Warning: Failed to load allowlist from ${this.allowlistPath}:`, error);
    }

    return null;
  }

  /**
   * Get default allowlist configuration
   */
  getDefaultConfig(): AllowlistConfig {
    return {
      version: '1.0',
      allowed_directories: [],
      allowed_patterns: [
        '**/*.md',
        '**/*.txt',
        '**/*.pdf',
        '**/*.png',
        '**/*.jpg',
        '**/*.jpeg',
      ],
      blocked_patterns: [
        '**/.env',
        '**/.env.*',
        '**/.git/**',
        '**/node_modules/**',
        '**/.ssh/**',
        '**/*_history',
        '**/*.key',
        '**/*.pem',
        '**/id_rsa',
        '**/id_rsa.pub',
        '**/id_ed25519',
        '**/id_ed25519.pub',
      ],
      max_file_size_mb: 10,
      max_files_per_directory: 1000,
    };
  }

  /**
   * Initialize allowlist with default configuration
   */
  async initialize(): Promise<void> {
    // Ensure config directory exists
    if (!fs.existsSync(this.configDir)) {
      fs.mkdirSync(this.configDir, { recursive: true });
    }

    // Create default allowlist if it doesn't exist
    if (!fs.existsSync(this.allowlistPath)) {
      const defaultConfig = this.getDefaultConfig();
      fs.writeFileSync(this.allowlistPath, JSON.stringify(defaultConfig, null, 2));
      this.config = defaultConfig;
    }
  }

  /**
   * Get current allowlist configuration
   */
  getConfig(): AllowlistConfig | null {
    return this.config;
  }

  /**
   * Save allowlist configuration to disk
   */
  private save(): void {
    if (!this.config) {
      throw new Error('No configuration to save');
    }

    // Ensure config directory exists
    if (!fs.existsSync(this.configDir)) {
      fs.mkdirSync(this.configDir, { recursive: true });
    }

    fs.writeFileSync(this.allowlistPath, JSON.stringify(this.config, null, 2));
  }

  /**
   * Add allowed directory
   */
  addAllowedDirectory(dir: string): void {
    if (!this.config) {
      throw new Error('Allowlist not initialized. Run: kg mcp-config init-allowlist');
    }

    // Expand tilde
    const expandedDir = dir.startsWith('~') ? path.join(os.homedir(), dir.slice(1)) : dir;

    if (!this.config.allowed_directories.includes(expandedDir)) {
      this.config.allowed_directories.push(expandedDir);
      this.save();
    }
  }

  /**
   * Remove allowed directory
   */
  removeAllowedDirectory(dir: string): void {
    if (!this.config) {
      throw new Error('Allowlist not initialized');
    }

    const expandedDir = dir.startsWith('~') ? path.join(os.homedir(), dir.slice(1)) : dir;
    this.config.allowed_directories = this.config.allowed_directories.filter(d => d !== expandedDir);
    this.save();
  }

  /**
   * Add allowed file pattern
   */
  addAllowedPattern(pattern: string): void {
    if (!this.config) {
      throw new Error('Allowlist not initialized');
    }

    if (!this.config.allowed_patterns.includes(pattern)) {
      this.config.allowed_patterns.push(pattern);
      this.save();
    }
  }

  /**
   * Remove allowed file pattern
   */
  removeAllowedPattern(pattern: string): void {
    if (!this.config) {
      throw new Error('Allowlist not initialized');
    }

    this.config.allowed_patterns = this.config.allowed_patterns.filter(p => p !== pattern);
    this.save();
  }

  /**
   * Add blocked file pattern
   */
  addBlockedPattern(pattern: string): void {
    if (!this.config) {
      throw new Error('Allowlist not initialized');
    }

    if (!this.config.blocked_patterns.includes(pattern)) {
      this.config.blocked_patterns.push(pattern);
      this.save();
    }
  }

  /**
   * Remove blocked file pattern
   */
  removeBlockedPattern(pattern: string): void {
    if (!this.config) {
      throw new Error('Allowlist not initialized');
    }

    this.config.blocked_patterns = this.config.blocked_patterns.filter(p => p !== pattern);
    this.save();
  }

  /**
   * Expand tilde in path
   */
  private expandTilde(filePath: string): string {
    if (filePath.startsWith('~/') || filePath === '~') {
      return path.join(os.homedir(), filePath.slice(1));
    }
    return filePath;
  }

  /**
   * Validate file path against allowlist (ADR-062 fail-secure validation)
   *
   * Security checks (in order):
   * 1. Resolve to absolute path (prevents ../ attacks)
   * 2. Check blocked patterns FIRST (fail-secure)
   * 3. Must match at least one allowed directory
   * 4. Must match at least one allowed file pattern
   * 5. Check file size (if file exists)
   */
  validatePath(filePath: string): ValidationResult {
    // 0. Require allowlist configuration
    if (!this.config) {
      return {
        allowed: false,
        reason: 'Allowlist not configured',
        hint: 'Run: kg mcp-config init-allowlist',
      };
    }

    // 1. Resolve to absolute path (prevents ../../../ attacks)
    const expandedPath = this.expandTilde(filePath);
    const absolutePath = path.resolve(expandedPath);

    // 2. Check blocked patterns FIRST (fail-secure)
    for (const pattern of this.config.blocked_patterns) {
      if (minimatch(absolutePath, pattern, { dot: true })) {
        return {
          allowed: false,
          reason: `Matches blocked pattern: ${pattern}`,
          hint: 'This file type is blocked for security',
        };
      }
    }

    // 3. Must match at least one allowed directory
    let matchesAllowedDir = false;
    for (const dir of this.config.allowed_directories) {
      const expandedDir = this.expandTilde(dir);

      // Check if path starts with allowed directory or matches pattern
      if (absolutePath.startsWith(expandedDir) || minimatch(absolutePath, expandedDir, { dot: true })) {
        matchesAllowedDir = true;
        break;
      }
    }

    if (!matchesAllowedDir) {
      return {
        allowed: false,
        reason: 'Path not in any allowed directory',
        hint: `Allowed directories: ${this.config.allowed_directories.join(', ')}`,
      };
    }

    // 4. Must match at least one allowed file pattern
    let matchesPattern = false;
    for (const pattern of this.config.allowed_patterns) {
      if (minimatch(absolutePath, pattern, { dot: true })) {
        matchesPattern = true;
        break;
      }
    }

    if (!matchesPattern) {
      return {
        allowed: false,
        reason: 'File extension not allowed',
        hint: `Allowed patterns: ${this.config.allowed_patterns.join(', ')}`,
      };
    }

    // 5. Check file size (if file exists)
    try {
      if (fs.existsSync(absolutePath)) {
        const stats = fs.statSync(absolutePath);
        const sizeMB = stats.size / (1024 * 1024);

        if (sizeMB > this.config.max_file_size_mb) {
          return {
            allowed: false,
            reason: `File too large: ${sizeMB.toFixed(2)}MB (max: ${this.config.max_file_size_mb}MB)`,
          };
        }
      }
    } catch (error: any) {
      // File doesn't exist or permission error - allow validation to continue
      // Actual file operations will fail later with appropriate error
    }

    return { allowed: true };
  }

  /**
   * Validate directory path
   */
  validateDirectory(dirPath: string): ValidationResult {
    if (!this.config) {
      return {
        allowed: false,
        reason: 'Allowlist not configured',
        hint: 'Run: kg mcp-config init-allowlist',
      };
    }

    const expandedPath = this.expandTilde(dirPath);
    const absolutePath = path.resolve(expandedPath);

    // Check if directory path is allowed
    for (const dir of this.config.allowed_directories) {
      const expandedDir = this.expandTilde(dir);

      if (absolutePath.startsWith(expandedDir) || minimatch(absolutePath, expandedDir, { dot: true })) {
        return { allowed: true };
      }
    }

    return {
      allowed: false,
      reason: 'Directory not in allowed paths',
      hint: `Allowed directories: ${this.config.allowed_directories.join(', ')}`,
    };
  }
}
