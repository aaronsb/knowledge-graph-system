/**
 * Help Commands - Including dynamic command map introspection
 */

import { Command } from 'commander';
import * as colors from './colors';
import { setCommandHelp } from './help-formatter';

/**
 * Calculate the maximum visible width needed for command names at each depth
 * Returns a map of depth -> max width needed for that level
 */
function calculateColumnWidths(cmd: Command, depth: number = 0, widths: Map<number, number> = new Map()): Map<number, number> {
  const name = cmd.name();
  // Calculate visible width (indent + connector + name)
  const indentWidth = depth === 0 ? 0 : (depth - 1) * 2 + 3; // "  " per level + "├─ "
  const currentWidth = indentWidth + name.length;

  const existingMax = widths.get(depth) || 0;
  widths.set(depth, Math.max(existingMax, currentWidth));

  cmd.commands.forEach((subcmd: Command) => {
    calculateColumnWidths(subcmd, depth + 1, widths);
  });

  return widths;
}

/**
 * Get the maximum width across all depths (for consistent alignment)
 */
function getMaxColumnWidth(cmd: Command): number {
  const widths = calculateColumnWidths(cmd);
  let maxWidth = 0;
  widths.forEach((width) => {
    maxWidth = Math.max(maxWidth, width);
  });
  // Add some padding and cap at reasonable width
  return Math.min(maxWidth + 2, 35);
}

/**
 * Recursively build command tree structure with aligned descriptions
 */
function buildCommandTree(cmd: Command, depth: number = 0, maxWidth: number = 30): string[] {
  const lines: string[] = [];

  // Get command name and description
  const name = cmd.name();

  // Format based on depth
  if (depth === 0) {
    lines.push(colors.ui.title(`${name}`));
  }

  // Get subcommands
  const subcommands = cmd.commands;

  subcommands.forEach((subcmd: Command, i: number) => {
    const isLast = i === subcommands.length - 1;

    // Add blank line before top-level commands with subcommands for visual separation
    if (subcmd.commands.length > 0 && i > 0) {
      lines.push('│');
    }

    const subLines = buildCommandTreeWithConnectors(subcmd, depth + 1, isLast, '', maxWidth);
    lines.push(...subLines);
  });

  return lines;
}

/**
 * Build command tree with proper box-drawing connectors and aligned descriptions
 */
function buildCommandTreeWithConnectors(
  cmd: Command,
  depth: number,
  isLast: boolean,
  inheritedIndent: string,
  maxWidth: number
): string[] {
  const lines: string[] = [];
  const connector = isLast ? '└─' : '├─';
  const continuation = isLast ? '  ' : '│ ';

  const name = cmd.name();
  const desc = cmd.description() || '';
  // Get first sentence/line of description
  const fullDesc = desc.split('.')[0].split('\n')[0];

  // Calculate visual width for padding
  const linePrefix = `${inheritedIndent}${connector} `;
  const visualWidth = linePrefix.length + name.length;
  const padding = Math.max(1, maxWidth - visualWidth);

  // Calculate available width for description based on terminal width
  const terminalWidth = process.stdout.columns || 120;
  const descStartCol = maxWidth + 1; // Where description starts
  const availableForDesc = Math.max(20, terminalWidth - descStartCol - 2);

  // Truncate description only if it exceeds available space
  const shortDesc = fullDesc.length > availableForDesc
    ? fullDesc.substring(0, availableForDesc - 1) + '…'
    : fullDesc;

  const cmdName = colors.concept.label(name);
  const cmdDesc = shortDesc ? colors.status.dim(' '.repeat(padding) + shortDesc) : '';
  lines.push(`${linePrefix}${cmdName}${cmdDesc}`);

  // Get subcommands
  const subcommands = cmd.commands;
  const newIndent = `${inheritedIndent}${continuation}`;

  subcommands.forEach((subcmd: Command, i: number) => {
    const isLastSub = i === subcommands.length - 1;
    const subLines = buildCommandTreeWithConnectors(subcmd, depth + 1, isLastSub, newIndent, maxWidth);
    lines.push(...subLines);
  });

  return lines;
}

/**
 * Count total commands recursively
 */
function countCommands(cmd: Command): number {
  let count = 1; // Count this command
  cmd.commands.forEach((subcmd: Command) => {
    count += countCommands(subcmd);
  });
  return count;
}

/**
 * Create the help command with commandmap subcommand
 */
export function createHelpCommand(program: Command): Command {
  const helpCommand = setCommandHelp(
    new Command('help'),
    'Get help on any command (try: kg help help)',
    'Get help on commands and explore the full CLI command structure. Use "kg help <command>" for specific help, or "kg help help" to see help utilities like commandmap.'
  )
    .showHelpAfterError();

  // kg help commandmap - introspective tree of all commands
  const commandmapSubcommand = setCommandHelp(
    new Command('commandmap'),
    'Show full command tree',
    'Display an introspective tree of all CLI commands and subcommands'
  )
    .alias('map')
    .alias('tree')
    .option('--flat', 'Show flat list instead of tree')
    .option('--json', 'Output as JSON')
    .showHelpAfterError()
    .action((options: { flat?: boolean; json?: boolean }) => {
      const totalCommands = countCommands(program);

      if (options.json) {
        // JSON output for scripting
        const buildJsonTree = (cmd: Command): object => ({
          name: cmd.name(),
          description: cmd.description() || undefined,
          aliases: cmd.aliases().length > 0 ? cmd.aliases() : undefined,
          subcommands: cmd.commands.length > 0
            ? cmd.commands.map((c: Command) => buildJsonTree(c))
            : undefined
        });
        console.log(JSON.stringify(buildJsonTree(program), null, 2));
        return;
      }

      if (options.flat) {
        // Flat list of all commands
        console.log('\n' + colors.ui.title('CLI Command List'));
        console.log(colors.status.dim(`${totalCommands} commands total\n`));

        const collectCommands = (cmd: Command, prefix: string = ''): string[] => {
          const results: string[] = [];
          const fullName = prefix ? `${prefix} ${cmd.name()}` : cmd.name();
          if (prefix) { // Skip root
            results.push(fullName);
          }
          cmd.commands.forEach((subcmd: Command) => {
            results.push(...collectCommands(subcmd, fullName));
          });
          return results;
        };

        const allCommands = collectCommands(program);
        allCommands.sort().forEach(cmd => {
          console.log(`  ${colors.concept.label(cmd)}`);
        });
        console.log();
        return;
      }

      // Tree view (default)
      console.log('\n' + colors.ui.title('CLI Command Map'));
      console.log(colors.status.dim(`${totalCommands} commands total\n`));

      // Calculate optimal column width for aligned descriptions
      const maxWidth = getMaxColumnWidth(program);
      const lines = buildCommandTree(program, 0, maxWidth);
      lines.forEach(line => console.log(line));

      console.log('\n' + colors.status.dim('Use "kg <command> --help" for details on any command'));
      console.log();
    });

  helpCommand.addCommand(commandmapSubcommand);

  // kg help <topic> - show help for a specific topic/command
  helpCommand
    .argument('[command...]', 'Command path to get help for (e.g., "search connect")')
    .action((commandPath: string[]) => {
      if (!commandPath || commandPath.length === 0) {
        // Show general help
        program.outputHelp();
        return;
      }

      // Find the command by path
      let current: Command = program;
      for (const part of commandPath) {
        const found = current.commands.find((c: Command) =>
          c.name() === part || c.aliases().includes(part)
        );
        if (!found) {
          console.error(colors.status.error(`✗ Unknown command: ${commandPath.join(' ')}`));
          console.error(colors.status.dim(`  Try: kg help commandmap`));
          process.exit(1);
        }
        current = found;
      }

      // Show help for the found command
      current.outputHelp();
    });

  return helpCommand;
}
