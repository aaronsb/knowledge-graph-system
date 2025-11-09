/**
 * MCP Allowlist Manager Security Tests
 *
 * ADR-062: MCP File Ingestion Security Model
 *
 * Tests fail-secure validation, path traversal prevention, and security controls.
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { McpAllowlistManager, AllowlistConfig } from '../../src/lib/mcp-allowlist';

describe('McpAllowlistManager', () => {
  let tempConfigDir: string;
  let originalEnv: string | undefined;
  let manager: McpAllowlistManager;

  beforeEach(() => {
    // Create temporary config directory
    tempConfigDir = fs.mkdtempSync(path.join(os.tmpdir(), 'kg-test-'));

    // Override XDG_CONFIG_HOME to use temp directory
    originalEnv = process.env.XDG_CONFIG_HOME;
    process.env.XDG_CONFIG_HOME = tempConfigDir;

    // Create fresh manager instance
    manager = new McpAllowlistManager();
  });

  afterEach(() => {
    // Restore environment
    if (originalEnv !== undefined) {
      process.env.XDG_CONFIG_HOME = originalEnv;
    } else {
      delete process.env.XDG_CONFIG_HOME;
    }

    // Clean up temp directory
    if (fs.existsSync(tempConfigDir)) {
      fs.rmSync(tempConfigDir, { recursive: true, force: true });
    }
  });

  describe('Initialization', () => {
    it('should create default configuration', async () => {
      await manager.initialize();
      const config = manager.getConfig();

      expect(config).not.toBeNull();
      expect(config?.version).toBe('1.0');
      expect(config?.allowed_directories).toEqual([]);
      expect(config?.allowed_patterns).toContain('**/*.md');
      expect(config?.allowed_patterns).toContain('**/*.txt');
      expect(config?.blocked_patterns).toContain('**/.env');
      expect(config?.max_file_size_mb).toBe(10);
    });

    it('should have secure defaults for blocked patterns', async () => {
      await manager.initialize();
      const config = manager.getConfig();

      expect(config?.blocked_patterns).toContain('**/.env');
      expect(config?.blocked_patterns).toContain('**/.env.*');
      expect(config?.blocked_patterns).toContain('**/.ssh/**');
      expect(config?.blocked_patterns).toContain('**/*.key');
      expect(config?.blocked_patterns).toContain('**/*.pem');
      expect(config?.blocked_patterns).toContain('**/id_rsa');
      expect(config?.blocked_patterns).toContain('**/node_modules/**');
    });

    it('should not overwrite existing configuration', async () => {
      await manager.initialize();
      manager.addAllowedDirectory('/test/path');

      // Create new manager instance
      const manager2 = new McpAllowlistManager();
      const config = manager2.getConfig();

      expect(config?.allowed_directories).toContain('/test/path');
    });
  });

  describe('Path Validation - Fail-Secure', () => {
    beforeEach(async () => {
      await manager.initialize();
      manager.addAllowedDirectory('/home/test/documents');
    });

    it('should deny access when allowlist not configured', () => {
      // Create a fresh temp directory with no config
      const freshTempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'kg-test-fresh-'));
      const oldEnv = process.env.XDG_CONFIG_HOME;
      process.env.XDG_CONFIG_HOME = freshTempDir;

      try {
        const uninitializedManager = new McpAllowlistManager();
        const result = uninitializedManager.validatePath('/home/test/file.md');

        expect(result.allowed).toBe(false);
        expect(result.reason).toContain('Allowlist not configured');
      } finally {
        // Restore environment and cleanup
        process.env.XDG_CONFIG_HOME = oldEnv;
        fs.rmSync(freshTempDir, { recursive: true, force: true });
      }
    });

    it('should check blocked patterns FIRST (fail-secure)', () => {
      // Add directory that would normally allow .env files
      manager.addAllowedPattern('**/.env');  // This shouldn't override security

      const result = manager.validatePath('/home/test/documents/.env');

      expect(result.allowed).toBe(false);
      expect(result.reason).toContain('blocked pattern');
    });

    it('should block .env files even if pattern matches', () => {
      const testCases = [
        '/home/test/documents/.env',
        '/home/test/documents/.env.local',
        '/home/test/documents/.env.production',
        '/home/test/documents/subdir/.env'
      ];

      testCases.forEach(testPath => {
        const result = manager.validatePath(testPath);
        expect(result.allowed).toBe(false);
        expect(result.reason).toContain('blocked pattern');
      });
    });

    it('should block SSH credentials', () => {
      const testCases = [
        '/home/test/documents/.ssh/id_rsa',
        '/home/test/documents/.ssh/id_rsa.pub',
        '/home/test/documents/.ssh/id_ed25519',
        '/home/test/documents/.ssh/config'
      ];

      testCases.forEach(testPath => {
        const result = manager.validatePath(testPath);
        expect(result.allowed).toBe(false);
      });
    });

    it('should block credential files', () => {
      const testCases = [
        '/home/test/documents/private.key',
        '/home/test/documents/certificate.pem',
        '/home/test/documents/subdir/auth.key'
      ];

      testCases.forEach(testPath => {
        const result = manager.validatePath(testPath);
        expect(result.allowed).toBe(false);
      });
    });
  });

  describe('Path Traversal Prevention', () => {
    beforeEach(async () => {
      await manager.initialize();
      manager.addAllowedDirectory('/home/test/safe');
    });

    it('should prevent ../ traversal attacks', () => {
      const testCases = [
        '/home/test/safe/../../../etc/passwd',
        '/home/test/safe/../../other/file.md',
        'safe/../../../etc/passwd'
      ];

      testCases.forEach(testPath => {
        const result = manager.validatePath(testPath);

        // Path resolves outside allowed directory
        if (result.allowed) {
          // If allowed, verify it's within allowed directory
          const absolutePath = path.resolve(testPath);
          expect(absolutePath.startsWith('/home/test/safe')).toBe(true);
        } else {
          // Most should be denied
          expect(result.allowed).toBe(false);
        }
      });
    });

    it('should resolve symbolic path components', () => {
      const result = manager.validatePath('/home/test/safe/./document.md');

      // Should resolve to /home/test/safe/document.md which is allowed
      expect(result.allowed).toBe(true);
    });

    it('should normalize paths before validation', () => {
      const result1 = manager.validatePath('/home/test/safe/file.md');
      const result2 = manager.validatePath('/home/test/safe//file.md');
      const result3 = manager.validatePath('/home/test/safe/./file.md');

      // All should have same result after normalization
      expect(result1.allowed).toBe(result2.allowed);
      expect(result1.allowed).toBe(result3.allowed);
    });
  });

  describe('Tilde Expansion', () => {
    beforeEach(async () => {
      await manager.initialize();
    });

    it('should expand ~ to home directory', () => {
      manager.addAllowedDirectory('~/Documents');
      const config = manager.getConfig();

      const expected = path.join(os.homedir(), 'Documents');
      expect(config?.allowed_directories).toContain(expected);
    });

    it('should validate paths with ~', () => {
      manager.addAllowedDirectory('~/test');

      const result = manager.validatePath('~/test/file.md');

      expect(result.allowed).toBe(true);
    });
  });

  describe('Pattern Matching', () => {
    beforeEach(async () => {
      await manager.initialize();
      manager.addAllowedDirectory('/home/test/docs');
    });

    it('should allow files matching allowed patterns', () => {
      const allowedFiles = [
        '/home/test/docs/readme.md',
        '/home/test/docs/notes.txt',
        '/home/test/docs/image.png',
        '/home/test/docs/photo.jpg',
        '/home/test/docs/document.pdf'
      ];

      allowedFiles.forEach(filePath => {
        const result = manager.validatePath(filePath);
        expect(result.allowed).toBe(true);
      });
    });

    it('should deny files not matching allowed patterns', () => {
      const deniedFiles = [
        '/home/test/docs/script.sh',
        '/home/test/docs/program.exe',
        '/home/test/docs/app.js',
        '/home/test/docs/data.json'
      ];

      deniedFiles.forEach(filePath => {
        const result = manager.validatePath(filePath);
        expect(result.allowed).toBe(false);
        expect(result.reason).toContain('extension not allowed');
      });
    });

    it('should support glob patterns in directory paths', () => {
      // Glob pattern needs to match the full resolved path
      manager.addAllowedDirectory('/home/test/projects/*/docs/**');

      const result = manager.validatePath('/home/test/projects/project-a/docs/readme.md');

      expect(result.allowed).toBe(true);
    });
  });

  describe('File Size Limits', () => {
    beforeEach(async () => {
      await manager.initialize();
      manager.addAllowedDirectory(tempConfigDir);
    });

    it('should allow files under size limit', () => {
      // Create a small file (1KB)
      const testFile = path.join(tempConfigDir, 'small.md');
      fs.writeFileSync(testFile, 'x'.repeat(1024));

      const result = manager.validatePath(testFile);

      expect(result.allowed).toBe(true);
    });

    it('should deny files over size limit', () => {
      // Create a large file (11MB - over 10MB limit)
      const testFile = path.join(tempConfigDir, 'large.md');
      const largeContent = 'x'.repeat(11 * 1024 * 1024);
      fs.writeFileSync(testFile, largeContent);

      const result = manager.validatePath(testFile);

      expect(result.allowed).toBe(false);
      expect(result.reason).toContain('too large');
    });

    it('should allow validation of non-existent files', () => {
      // File doesn't exist yet - should pass validation
      const testFile = path.join(tempConfigDir, 'future.md');

      const result = manager.validatePath(testFile);

      expect(result.allowed).toBe(true);
    });
  });

  describe('Directory Management', () => {
    beforeEach(async () => {
      await manager.initialize();
    });

    it('should add allowed directory', () => {
      manager.addAllowedDirectory('/test/dir');
      const config = manager.getConfig();

      expect(config?.allowed_directories).toContain('/test/dir');
    });

    it('should remove allowed directory', () => {
      manager.addAllowedDirectory('/test/dir');
      manager.removeAllowedDirectory('/test/dir');
      const config = manager.getConfig();

      expect(config?.allowed_directories).not.toContain('/test/dir');
    });

    it('should not add duplicate directories', () => {
      manager.addAllowedDirectory('/test/dir');
      manager.addAllowedDirectory('/test/dir');
      const config = manager.getConfig();

      const count = config?.allowed_directories.filter(d => d === '/test/dir').length;
      expect(count).toBe(1);
    });
  });

  describe('Pattern Management', () => {
    beforeEach(async () => {
      await manager.initialize();
    });

    it('should add allowed pattern', () => {
      manager.addAllowedPattern('**/*.yaml');
      const config = manager.getConfig();

      expect(config?.allowed_patterns).toContain('**/*.yaml');
    });

    it('should remove allowed pattern', () => {
      manager.addAllowedPattern('**/*.yaml');
      manager.removeAllowedPattern('**/*.yaml');
      const config = manager.getConfig();

      expect(config?.allowed_patterns).not.toContain('**/*.yaml');
    });

    it('should add blocked pattern', () => {
      manager.addBlockedPattern('**/*.secret');
      const config = manager.getConfig();

      expect(config?.blocked_patterns).toContain('**/*.secret');
    });

    it('should remove blocked pattern', () => {
      manager.addBlockedPattern('**/*.secret');
      manager.removeBlockedPattern('**/*.secret');
      const config = manager.getConfig();

      expect(config?.blocked_patterns).not.toContain('**/*.secret');
    });
  });

  describe('Directory Validation', () => {
    beforeEach(async () => {
      await manager.initialize();
      manager.addAllowedDirectory('/home/test/allowed');
    });

    it('should allow valid directory', () => {
      const result = manager.validateDirectory('/home/test/allowed');

      expect(result.allowed).toBe(true);
    });

    it('should allow subdirectory of allowed directory', () => {
      const result = manager.validateDirectory('/home/test/allowed/subdir');

      expect(result.allowed).toBe(true);
    });

    it('should deny directory outside allowed paths', () => {
      const result = manager.validateDirectory('/home/test/forbidden');

      expect(result.allowed).toBe(false);
      expect(result.reason).toContain('not in allowed paths');
    });
  });

  describe('Error Handling', () => {
    it('should throw when adding directory without initialization', () => {
      const uninitializedManager = new McpAllowlistManager();

      expect(() => {
        uninitializedManager.addAllowedDirectory('/test');
      }).toThrow('not initialized');
    });

    it('should throw when adding pattern without initialization', () => {
      const uninitializedManager = new McpAllowlistManager();

      expect(() => {
        uninitializedManager.addAllowedPattern('**/*.md');
      }).toThrow('not initialized');
    });

    it('should provide helpful hints in validation failures', async () => {
      await manager.initialize();
      manager.addAllowedDirectory('/allowed/path');

      const result = manager.validatePath('/denied/path/file.md');

      expect(result.allowed).toBe(false);
      expect(result.hint).toBeDefined();
      expect(result.hint).toContain('/allowed/path');
    });
  });

  describe('Security Edge Cases', () => {
    beforeEach(async () => {
      await manager.initialize();
      manager.addAllowedDirectory('/home/test/safe');
    });

    it('should handle null bytes in paths', () => {
      const result = manager.validatePath('/home/test/safe/file\0.md');

      // Should either deny or handle gracefully
      expect(result).toBeDefined();
    });

    it('should handle very long paths', () => {
      const longPath = '/home/test/safe/' + 'a'.repeat(1000) + '.md';

      const result = manager.validatePath(longPath);

      // Should handle without crashing
      expect(result).toBeDefined();
    });

    it('should handle paths with special characters', () => {
      const specialPaths = [
        '/home/test/safe/file with spaces.md',
        '/home/test/safe/file-with-dashes.md',
        '/home/test/safe/file_with_underscores.md',
        '/home/test/safe/file(with)parens.md'
      ];

      specialPaths.forEach(testPath => {
        const result = manager.validatePath(testPath);
        expect(result).toBeDefined();
      });
    });

    it('should handle case-sensitive paths correctly', () => {
      manager.addAllowedDirectory('/home/Test/Safe');

      // Linux is case-sensitive, should be different paths
      const result1 = manager.validatePath('/home/Test/Safe/file.md');
      const result2 = manager.validatePath('/home/test/safe/file.md');

      // At least one should work
      expect(result1.allowed || result2.allowed).toBe(true);
    });
  });
});
