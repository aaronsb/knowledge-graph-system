#!/usr/bin/env node
/**
 * Documentation Validation Script
 *
 * Checks that all CLI commands are properly documented in CLI_USAGE.md
 * and that documentation references match actual command structure.
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// ANSI colors
const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  dim: '\x1b[2m'
};

const log = {
  success: (msg) => console.log(`${colors.green}✓${colors.reset} ${msg}`),
  error: (msg) => console.log(`${colors.red}✗${colors.reset} ${msg}`),
  warn: (msg) => console.log(`${colors.yellow}⚠${colors.reset} ${msg}`),
  info: (msg) => console.log(`${colors.blue}ℹ${colors.reset} ${msg}`),
  dim: (msg) => console.log(`${colors.dim}${msg}${colors.reset}`)
};

const ROOT = path.resolve(__dirname, '../..');
const CLI_USAGE_PATH = path.join(ROOT, 'docs/guides/CLI_USAGE.md');

/**
 * Get list of all main commands from kg CLI
 */
function getMainCommands() {
  try {
    // Try kg command first, fall back to built dist if not installed
    let help;
    let usedDist = false;
    try {
      help = execSync('kg --help', { encoding: 'utf8', cwd: ROOT });
    } catch {
      // Try using dist/index.js directly
      const distPath = path.join(ROOT, 'client/dist/index.js');
      if (!fs.existsSync(distPath)) {
        throw new Error('kg CLI not installed and dist/index.js not found. Run: npm run build');
      }
      help = execSync(`node ${distPath} --help`, { encoding: 'utf8', cwd: ROOT });
      usedDist = true;
    }

    // Parse commands from help output (strip ANSI codes first)
    const cleanHelp = help.replace(/\x1b\[[0-9;]*m/g, '');
    const commandSection = cleanHelp.split('Commands')[1];
    if (!commandSection) {
      console.error('DEBUG: Could not find Commands section in help output');
      console.error('DEBUG: Used dist:', usedDist);
      return [];
    }

    const commands = [];
    const lines = commandSection.split('\n');

    for (const line of lines) {
      // Match command lines like "  health    Check API server health"
      const match = line.match(/^\s+([a-z-]+)(?:\|([a-z-]+))?\s+/);
      if (match) {
        const [, primary, alias] = match;
        // Skip help and Unix verbs
        if (!['help', 'ls', 'rm', 'cat', 'bat', 'stat'].includes(primary)) {
          commands.push({ name: primary, alias: alias || null });
        }
      }
    }

    return commands;
  } catch (error) {
    log.error('Failed to get command list from kg CLI');
    log.dim(error.message);
    return [];
  }
}

/**
 * Check if a command is documented in CLI_USAGE.md
 */
function isCommandDocumented(commandName, docContent) {
  // Look for section headers like "## 4. Job Commands"
  const patterns = [
    new RegExp(`##\\s+\\d+\\.\\s+${commandName}\\s+Command`, 'i'),
    new RegExp(`\\*\\*Command:\\*\\*\\s+\`kg ${commandName}`, 'i'),
    new RegExp(`### .*\`kg ${commandName}`, 'i')
  ];

  return patterns.some(pattern => pattern.test(docContent));
}

/**
 * Main validation function
 */
async function validateDocs() {
  console.log('\n' + '='.repeat(80));
  log.info('Documentation Validation');
  console.log('='.repeat(80) + '\n');

  // Check if CLI_USAGE.md exists
  if (!fs.existsSync(CLI_USAGE_PATH)) {
    log.error(`Documentation file not found: ${CLI_USAGE_PATH}`);
    process.exit(1);
  }

  log.success(`Found documentation: ${path.relative(ROOT, CLI_USAGE_PATH)}`);

  // Read documentation
  const docContent = fs.readFileSync(CLI_USAGE_PATH, 'utf8');

  // Get all main commands
  log.info('Scanning CLI commands...');
  const commands = getMainCommands();

  if (commands.length === 0) {
    log.error('No commands found - CLI help output could not be parsed');
    log.dim('This might be a bug in the check-docs script\n');
    process.exit(1);
  }

  log.dim(`Found ${commands.length} main commands\n`);

  // Check each command
  let undocumented = [];
  let documented = [];

  for (const cmd of commands) {
    const isDoc = isCommandDocumented(cmd.name, docContent);

    if (isDoc) {
      documented.push(cmd);
      log.success(`${cmd.name.padEnd(15)} documented`);
    } else {
      undocumented.push(cmd);
      log.error(`${cmd.name.padEnd(15)} missing documentation`);
    }
  }

  // Summary
  console.log('\n' + '─'.repeat(80));
  console.log(`\n${colors.green}Documented:${colors.reset} ${documented.length}/${commands.length}`);

  if (undocumented.length > 0) {
    console.log(`${colors.red}Undocumented:${colors.reset} ${undocumented.length}/${commands.length}\n`);
    log.error('Documentation validation failed');
    console.log('\nMissing documentation for:');
    undocumented.forEach(cmd => {
      console.log(`  - ${cmd.name}${cmd.alias ? ` (alias: ${cmd.alias})` : ''}`);
    });
    console.log();
    process.exit(1);
  } else {
    console.log(`${colors.green}Undocumented:${colors.reset} 0/${commands.length}\n`);
    log.success('All commands are documented!\n');
  }

  // Additional checks
  console.log('─'.repeat(80));
  log.info('Additional Documentation Checks\n');

  // Check for ADR-029 references
  if (docContent.includes('ADR-029')) {
    log.success('ADR-029 (CLI Theory) referenced');
  } else {
    log.warn('ADR-029 (CLI Theory) not referenced');
  }

  // Check for Unix verb router section
  if (docContent.includes('Unix Verb Router')) {
    log.success('Unix Verb Router documented');
  } else {
    log.warn('Unix Verb Router section missing');
  }

  // Check for alias documentation
  if (docContent.includes('User-Configurable Aliases')) {
    log.success('User-configurable aliases documented');
  } else {
    log.warn('User-configurable aliases not documented');
  }

  console.log('\n' + '='.repeat(80) + '\n');
}

// Run validation
validateDocs().catch(error => {
  log.error('Validation script failed');
  console.error(error);
  process.exit(1);
});
