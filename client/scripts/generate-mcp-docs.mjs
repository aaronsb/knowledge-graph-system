#!/usr/bin/env node
/**
 * MCP Server Documentation Generator
 *
 * Generates markdown documentation from MCP tool schemas.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { DocWriter } from './doc-utils.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Format JSON schema for documentation
 */
function formatSchema(schema, indent = 0) {
  const ind = '  '.repeat(indent);
  const lines = [];

  if (schema.type === 'object' && schema.properties) {
    Object.entries(schema.properties).forEach(([key, prop]) => {
      const required = schema.required?.includes(key) ? ' **(required)**' : '';
      const description = prop.description || '';
      const type = prop.type || 'any';

      lines.push(`${ind}- \`${key}\` (\`${type}\`)${required} - ${description}`);

      if (prop.enum) {
        lines.push(`${ind}  - Allowed values: ${prop.enum.map(v => `\`${v}\``).join(', ')}`);
      }

      if (prop.default !== undefined) {
        lines.push(`${ind}  - Default: \`${JSON.stringify(prop.default)}\``);
      }

      if (prop.properties) {
        lines.push(formatSchema(prop, indent + 1));
      }
    });
  }

  return lines.join('\n');
}

/**
 * Generate markdown for a tool
 */
function generateToolMarkdown(tool) {
  const md = [];

  md.push(`### ${tool.name}\n`);
  md.push(`${tool.description}\n`);

  // Input Schema
  if (tool.inputSchema && tool.inputSchema.properties) {
    md.push('**Parameters:**\n');
    md.push(formatSchema(tool.inputSchema));
    md.push('');
  }

  // Examples
  if (tool.examples && tool.examples.length > 0) {
    md.push('**Examples:**\n');
    tool.examples.forEach(ex => {
      md.push('```json');
      md.push(JSON.stringify(ex, null, 2));
      md.push('```\n');
    });
  }

  md.push('---\n');

  return md.join('\n');
}

/**
 * Extract tool definitions from mcp-server.ts source
 */
async function extractToolsFromSource() {
  const sourcePath = path.join(__dirname, '../src/mcp-server.ts');
  const source = fs.readFileSync(sourcePath, 'utf-8');

  // Parse tool definitions (they're in ListToolsRequestHandler)
  // This is a simple regex-based parser - could be improved with proper AST parsing
  const toolsMatch = source.match(/return\s*\{[\s\S]*?tools:\s*\[([\s\S]*?)\]/m);

  if (!toolsMatch) {
    throw new Error('Could not find tools array in mcp-server.ts');
  }

  const toolsSource = toolsMatch[1];

  // Extract each tool object
  const tools = [];
  const toolRegex = /\{[\s\S]*?name:\s*['"`]([^'"`]+)['"`][\s\S]*?description:\s*[`]([^`]+)[`][\s\S]*?inputSchema:\s*(\{[\s\S]*?\}),?\s*\}/g;

  let match;
  while ((match = toolRegex.exec(toolsSource)) !== null) {
    const [_, name, description, schemaStr] = match;

    // Parse the schema (it's JavaScript object notation)
    let inputSchema;
    try {
      // Use a safer eval in a controlled context (only for static tool definitions)
      inputSchema = eval(`(${schemaStr})`);
    } catch (err) {
      console.warn(`Warning: Could not parse schema for ${name}`);
      inputSchema = { type: 'object', properties: {} };
    }

    tools.push({ name, description, inputSchema });
  }

  return tools;
}

/**
 * Main
 */
async function main() {
  console.log('🔍 Generating MCP Server documentation...\n');

  // Extract tools from source
  const tools = await extractToolsFromSource();
  console.log(`📋 Found ${tools.length} MCP tools\n`);

  // Create output directory
  const outDir = path.join(__dirname, '../../docs/reference/mcp');
  fs.mkdirSync(outDir, { recursive: true });

  // Create smart writer to avoid git churn
  const writer = new DocWriter();

  // Generate index
  const index = [];
  index.push('# MCP Server Tool Reference (Auto-Generated)\n');
  index.push('> **Auto-Generated Documentation**');
  index.push('> ');
  index.push('> Generated from MCP server tool schemas.');
  index.push(`> Last updated: ${new Date().toISOString().split('T')[0]}\n`);
  index.push('---\n');

  // Overview
  index.push('## Overview\n');
  index.push('The Knowledge Graph MCP server provides tools for Claude Desktop to interact with the knowledge graph.');
  index.push('These tools enable semantic search, concept exploration, and graph traversal directly from Claude.\n');
  index.push('---\n');

  // TOC
  index.push('## Available Tools\n');
  tools.forEach(tool => {
    index.push(`- [\`${tool.name}\`](#${tool.name.replace(/_/g, '-')}) - ${tool.description}`);
  });
  index.push('\n---\n');

  // Tool sections
  tools.forEach(tool => {
    index.push(generateToolMarkdown(tool));
  });

  // Write index
  writer.write(path.join(outDir, 'README.md'), index.join('\n'));
  console.log(`✅ Generated: docs/reference/mcp/README.md`);

  // Generate individual tool files
  tools.forEach(tool => {
    const toolDir = path.join(outDir, tool.name);
    fs.mkdirSync(toolDir, { recursive: true });

    const toolMd = [
      `# ${tool.name}\n`,
      '> Auto-generated from MCP tool schema\n',
      generateToolMarkdown(tool)
    ];

    writer.write(
      path.join(toolDir, 'README.md'),
      toolMd.join('\n')
    );
  });

  console.log(`✅ Generated ${tools.length} tool files`);
  writer.printStats();
  console.log('\n📂 View docs at: docs/reference/mcp/\n');
  console.log('✨ Done!');
}

main().catch(err => {
  console.error('❌ Error:', err);
  process.exit(1);
});
