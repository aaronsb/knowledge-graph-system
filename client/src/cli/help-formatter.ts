/**
 * Shared Help Formatter for Consistent Colored Output
 */

import { Command, Help } from 'commander';
import * as colors from './colors';
import ansis from 'ansis';

/**
 * Format description text with markdown-like syntax and colors using ansis
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
      output += ansis.bold.cyan(sentence) + '\n';
      lineLength = 0;
      return;
    }

    // Apply inline formatting
    let formatted = sentence;

    // Highlight parenthetical references (ADR-xxx, etc.) in dim
    formatted = formatted.replace(/(\([A-Z]+[-\d]+[^)]*\))/g, (match) => ansis.dim(match));

    // Highlight technical terms with arrows
    formatted = formatted.replace(/([a-z]+→[a-z]+)/gi, (match) => ansis.green(match));

    // Highlight file extensions and paths
    formatted = formatted.replace(/(\w+\/\w+)/g, (match) => ansis.green(match));
    formatted = formatted.replace(/(\.\w{2,4})/g, (match) => ansis.green(match));

    // Highlight workflow/status terms
    formatted = formatted.replace(/\b(pending|approval|processing|completed|failed|awaiting_approval|running)\b/g,
      (match) => ansis.yellow(match));

    // Highlight technical terms
    formatted = formatted.replace(/\b(LLM|API|REST|OAuth|PostgreSQL|Apache AGE|vector|embedding|graph|concept|chunk|ontology)\b/g,
      (match) => ansis.cyan(match));

    // Normal text in white (not dim)
    output += ansis.white(formatted);

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
 * Wrap text to fit within a specific width, indenting continuation lines
 * Uses ansis.strip() to measure actual text length without color codes
 * @param text - Text to wrap (may include ANSI color codes)
 * @param maxWidth - Maximum width for each line
 * @param indent - Indentation for continuation lines
 */
function wrapText(text: string, maxWidth: number, indent: string = ''): string {
  const words = text.split(' ');
  const lines: string[] = [];
  let currentLine = '';

  for (const word of words) {
    const testLine = currentLine ? currentLine + ' ' + word : word;
    const testLineStripped = ansis.strip(testLine);

    if (testLineStripped.length <= maxWidth) {
      currentLine = testLine;
    } else {
      if (currentLine) {
        lines.push(currentLine);
      }
      currentLine = word;
    }
  }

  if (currentLine) {
    lines.push(currentLine);
  }

  // Join with newline + indent for continuation lines
  return lines.map((line, idx) => idx === 0 ? line : indent + line).join('\n');
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
      const availableWidth = process.stdout.columns || 100;
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
          const leftColumnWidth = 2 + name.length + padding.length; // 2 for indent
          const descWidth = availableWidth - leftColumnWidth;
          const wrappedDesc = wrapText(
            colors.status.dim(description),
            descWidth,
            ' '.repeat(leftColumnWidth)
          );
          output += '  ' + coloredName + padding + wrappedDesc + '\n';
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
          const leftColumnWidth = 2 + flags.length + padding.length;
          const descWidth = availableWidth - leftColumnWidth;
          const wrappedDesc = wrapText(
            colors.status.dim(description),
            descWidth,
            ' '.repeat(leftColumnWidth)
          );
          output += '  ' + coloredFlags + padding + wrappedDesc + '\n';
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
          const leftColumnWidth = 2 + name.length + padding.length;
          const descWidth = availableWidth - leftColumnWidth;
          const wrappedDesc = wrapText(
            colors.status.dim(description),
            descWidth,
            ' '.repeat(leftColumnWidth)
          );
          output += '  ' + coloredName + padding + wrappedDesc + '\n';
        });
      }

      return output;
    }
  });
}
