#!/usr/bin/env -S node --use-system-ca
/**
 * Knowledge Graph CLI - Entry Point
 *
 * Main CLI tool for interacting with the knowledge graph API.
 * For MCP server mode, use the separate kg-mcp-server executable.
 */

import { program } from 'commander';
import { registerCommands } from './cli/commands.js';

// Run CLI
registerCommands(program).then(() => {
  program.parse();
});
