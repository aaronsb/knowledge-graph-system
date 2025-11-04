/**
 * Shared Help Formatter for Consistent Colored Output
 */

import { Command, Help } from 'commander';
import * as colors from './colors';

/**
 * Format description text with markdown-like syntax and colors
 * Supports:
 * - Sentences ending with periods: regular white text
 * - Sentences ending with colons: bold cyan (section headers)
 * - Text in parentheses like (ADR-xxx): dim gray
 * - Terms with special chars (/, →, -): highlighted in green
 * - Breaks long text into readable chunks
 */
function formatDescription(text: string): string {
  if (!text) return '';

  // Split into sentences by periods followed by space or end
  const sentences = text.match(/[^.!?]+[.!?]+/g) || [text];
  let output = '';
  let lineLength = 0;
  const maxLineLength = 100;

  sentences.forEach((sentence, idx) => {
    sentence = sentence.trim();
    if (!sentence) return;

    // Section headers (end with colon) - new line and bold cyan
    if (sentence.endsWith(':')) {
      if (output && !output.endsWith('\n')) output += '\n';
      output += '\x1b[1m\x1b[36m' + sentence + '\x1b[0m' + '\n';
      lineLength = 0;
      return;
    }

    // Apply inline formatting
    let formatted = sentence;

    // Highlight parenthetical references (ADR-xxx, etc.) in dim
    formatted = formatted.replace(/(\([A-Z]+[-\d]+[^)]*\))/g, '\x1b[2m$1\x1b[22m');

    // Highlight technical terms with arrows
    formatted = formatted.replace(/([a-z]+→[a-z]+)/gi, '\x1b[32m$1\x1b[39m');

    // Highlight file extensions and paths
    formatted = formatted.replace(/(\w+\/\w+)/g, '\x1b[32m$1\x1b[39m');
    formatted = formatted.replace(/(\.\w{2,4})/g, '\x1b[32m$1\x1b[39m');

    // Highlight workflow/status terms
    formatted = formatted.replace(/\b(pending|approval|processing|completed|failed|awaiting_approval|running)\b/g, '\x1b[33m$1\x1b[39m');

    // Highlight technical terms
    formatted = formatted.replace(/\b(LLM|API|REST|OAuth|PostgreSQL|Apache AGE|vector|embedding|graph|concept|chunk|ontology)\b/g, '\x1b[36m$1\x1b[39m');

    // Normal text in white (not dim)
    output += '\x1b[37m' + formatted + '\x1b[0m';

    lineLength += sentence.length;

    // Add line break after ~100 chars or every 2-3 sentences for readability
    if (lineLength > maxLineLength || (idx > 0 && idx % 2 === 0)) {
      output += '\n';
      lineLength = 0;
    } else {
      output += ' ';
    }
  });

  return output.trim();
}

/**
 * Set both a terse summary (for command listings) and detailed description (for --help)
 * @param cmd - Commander.js command
 * @param summary - Terse one-line description for command listings
 * @param description - Detailed multi-line description for --help output
 */
export function setCommandHelp(cmd: Command, summary: string, description: string): Command {
  (cmd as any)._shortDesc = summary;
  return cmd.description(description);
}

/**
 * Configure colored help for a command
 */
export function configureColoredHelp(cmd: Command): void {
  cmd.configureHelp({
    formatHelp: (command, helper) => {
      const termWidth = helper.padWidth(command, helper);
      let output = '';

      // Usage
      output += colors.ui.key('Usage: ') +
                colors.ui.value(helper.commandUsage(command).replace('Usage: ', '')) + '\n\n';

      // Description (formatted with colors and structure)
      const desc = helper.commandDescription(command);
      if (desc) {
        output += formatDescription(desc) + '\n\n';
      }

      // Arguments
      const args = helper.visibleArguments(command);
      if (args.length > 0) {
        output += colors.ui.header('Arguments') + '\n';
        args.forEach(arg => {
          const name = helper.argumentTerm(arg);
          const description = helper.argumentDescription(arg);

          // Color argument placeholders
          const coloredName = name.startsWith('<') || name.startsWith('[')
            ? colors.status.dim(name)
            : colors.ui.command(name);

          const padding = ' '.repeat(Math.max(2, termWidth - name.length + 2));
          output += '  ' + coloredName + padding + colors.status.dim(description) + '\n';
        });
        output += '\n';
      }

      // Options
      const opts = helper.visibleOptions(command);
      if (opts.length > 0) {
        output += colors.ui.header('Options') + '\n';
        opts.forEach(option => {
          const flags = helper.optionTerm(option);
          const description = helper.optionDescription(option);

          // Parse and color each component
          const parts = flags.split(/\s+/);
          const coloredParts = parts.map(part => {
            if (part.startsWith('<') && part.endsWith('>')) {
              return colors.status.dim(part);  // placeholders like <url>
            } else if (part.startsWith('[') && part.endsWith(']')) {
              return colors.status.dim(part);  // optional like [value]
            } else if (part.startsWith('-')) {
              return colors.ui.command(part);  // flags like -V or --version (forest green)
            } else {
              return part;  // commas, etc
            }
          });

          const coloredFlags = coloredParts.join(' ');
          const padding = ' '.repeat(Math.max(2, termWidth - flags.length + 2));
          output += '  ' + coloredFlags + padding + colors.status.dim(description) + '\n';
        });
        output += '\n';
      }

      // Commands
      const commands = helper.visibleCommands(command);
      if (commands.length > 0) {
        output += colors.ui.header('Commands') + '\n';
        commands.forEach(subcommand => {
          const name = helper.subcommandTerm(subcommand);
          // Use ._shortDesc if available (terse), otherwise fall back to full description
          const description = (subcommand as any)._shortDesc || helper.subcommandDescription(subcommand);

          // Parse and color command name parts
          const parts = name.split(/\s+/);
          const coloredParts = parts.map(part => {
            if (part.startsWith('[') && part.endsWith(']')) {
              return colors.status.dim(part);  // [arguments]
            } else if (part.startsWith('<') && part.endsWith('>')) {
              return colors.status.dim(part);  // <required>
            } else if (part.includes('|')) {
              // Handle aliases like "database|db"
              const aliases = part.split('|');
              return aliases.map(a => colors.ui.command(a)).join('|');
            } else {
              return colors.ui.command(part);  // command name (forest green)
            }
          });

          const coloredName = coloredParts.join(' ');
          const padding = ' '.repeat(Math.max(2, termWidth - name.length + 2));
          output += '  ' + coloredName + padding + colors.status.dim(description) + '\n';
        });
      }

      return output;
    }
  });
}
