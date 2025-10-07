#!/usr/bin/env node
/**
 * Knowledge Graph Client - Entry Point
 *
 * Unified client that can run as:
 * 1. CLI tool (default)
 * 2. MCP server (when MCP_SERVER_MODE=true)
 */

import { program } from 'commander';

// Detect mode
if (process.env.MCP_SERVER_MODE === 'true') {
  // MCP server mode (Phase 2)
  console.error('MCP server mode not implemented yet (Phase 2)');
  process.exit(1);
} else {
  // CLI mode
  import('./cli/commands').then(({ registerCommands }) => {
    registerCommands(program);
    program.parse();
  });
}
