#!/usr/bin/env node
/**
 * Simple CLI Documentation Generator
 *
 * Directly imports command definitions to avoid execution issues.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { DocWriter } from './doc-utils.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Extract metadata from a Commander.js Command
 */
function extractMetadata(cmd) {
  return {
    name: cmd.name(),
    aliases: cmd.aliases(),
    description: cmd.description(),
    arguments: cmd.registeredArguments?.map(arg => ({
      name: arg.name(),
      required: arg.required,
      description: arg.description || ''
    })) || [],
    options: cmd.options?.map(opt => ({
      flags: opt.flags,
      description: opt.description,
      defaultValue: opt.defaultValue
    })) || [],
    commands: cmd.commands?.filter(subcmd => !subcmd.name().startsWith('help'))
      .map(subcmd => extractMetadata(subcmd)) || []
  };
}

/**
 * Generate markdown
 */
function generateMarkdown(cmd, depth = 2) {
  const md = [];
  const h = '#'.repeat(depth);

  const fullName = cmd.aliases.length > 0
    ? `${cmd.name} (${cmd.aliases.join(', ')})`
    : cmd.name;

  md.push(`${h} ${fullName}\n`);

  if (cmd.description) {
    md.push(`${cmd.description}\n`);
  }

  // Usage
  md.push('**Usage:**\n```bash');
  const args = cmd.arguments.map(arg =>
    arg.required ? `<${arg.name}>` : `[${arg.name}]`
  ).join(' ');
  md.push(`kg ${cmd.name}${args ? ' ' + args : ' [options]'}`);
  md.push('```\n');

  // Arguments
  if (cmd.arguments.length > 0) {
    md.push('**Arguments:**\n');
    cmd.arguments.forEach(arg => {
      md.push(`- \`<${arg.name}>\` - ${arg.description || (arg.required ? 'Required' : 'Optional')}`);
    });
    md.push('');
  }

  // Options
  if (cmd.options.length > 0) {
    md.push('**Options:**\n');
    md.push('| Option | Description | Default |');
    md.push('|--------|-------------|---------|');
    cmd.options.forEach(opt => {
      const def = opt.defaultValue !== undefined ? `\`${JSON.stringify(opt.defaultValue)}\`` : '-';
      md.push(`| \`${opt.flags}\` | ${opt.description} | ${def} |`);
    });
    md.push('');
  }

  // Subcommands
  if (cmd.commands.length > 0) {
    md.push('**Subcommands:**\n');
    cmd.commands.forEach(sub => {
      const aliases = sub.aliases.length > 0 ? ` (\`${sub.aliases.join('`, `')}\`)` : '';
      md.push(`- \`${sub.name}\`${aliases} - ${sub.description}`);
    });
    md.push('\n---\n');

    cmd.commands.forEach(sub => {
      md.push(generateMarkdown(sub, depth + 1));
    });
  }

  return md.join('\n');
}

/**
 * Main
 */
async function main() {
  console.log('🔍 Generating CLI documentation (simple mode)...\n');

  // Import command definitions directly
  const modules = [
    { name: 'health', path: '../dist/cli/health.js' },
    { name: 'config', path: '../dist/cli/config.js' },
    { name: 'ingest', path: '../dist/cli/ingest.js' },
    { name: 'jobs', path: '../dist/cli/jobs.js' },
    { name: 'search', path: '../dist/cli/search.js' },
    { name: 'database', path: '../dist/cli/database.js' },
    { name: 'ontology', path: '../dist/cli/ontology.js' },
    { name: 'vocabulary', path: '../dist/cli/vocabulary.js' },
    { name: 'admin', path: '../dist/cli/admin.js' },
  ];

  const commands = [];

  for (const mod of modules) {
    try {
      const imported = await import(mod.path);
      const cmdExport = imported[`${mod.name}Command`] || imported.default || imported[mod.name + 'Cmd'];

      if (cmdExport) {
        commands.push(extractMetadata(cmdExport));
        console.log(`✓ Loaded ${mod.name}`);
      } else {
        console.log(`⚠ Could not find command export in ${mod.name}`);
      }
    } catch (err) {
      console.log(`✗ Failed to import ${mod.name}:`, err.message);
    }
  }

  console.log(`\n📋 Extracted ${commands.length} commands\n`);

  // Create output directory
  const outDir = path.join(__dirname, '../../docs/reference/cli');
  fs.mkdirSync(outDir, { recursive: true });

  // Create smart writer to track stats and avoid git churn
  const writer = new DocWriter();

  // Generate index
  const index = [];
  index.push('# CLI Command Reference (Auto-Generated)\n');
  index.push('> **Auto-Generated Documentation**');
  index.push('> ');
  index.push('> Generated from CLI source code.');
  index.push(`> Last updated: ${new Date().toISOString().split('T')[0]}\n`);
  index.push('---\n');

  // TOC
  index.push('## Commands\n');
  commands.forEach(cmd => {
    const aliases = cmd.aliases.length > 0 ? ` (${cmd.aliases.join(', ')})` : '';
    index.push(`- [\`${cmd.name}\`${aliases}](#${cmd.name}) - ${cmd.description}`);
  });
  index.push('\n---\n');

  // Command sections
  commands.forEach(cmd => {
    index.push(generateMarkdown(cmd, 2));
    index.push('');
  });

  writer.write(path.join(outDir, 'README.md'), index.join('\n'));
  console.log(`✅ Generated: docs/reference/cli/README.md`);

  // Individual files (flat structure)
  commands.forEach(cmd => {
    writer.write(
      path.join(outDir, `${cmd.name}.md`),
      `# kg ${cmd.name}\n\n> Auto-generated\n\n${generateMarkdown(cmd, 2)}`
    );
  });

  console.log(`✅ Generated ${commands.length} command files`);
  writer.printStats();
  console.log('\n📂 View docs at: docs/reference/cli/\n');
  console.log('✨ Done!');
}

main().catch(err => {
  console.error('❌ Error:', err);
  process.exit(1);
});
