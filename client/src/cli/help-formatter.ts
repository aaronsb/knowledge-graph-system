/**
 * Shared Help Formatter for Consistent Colored Output
 */

import { Command, Help } from 'commander';
import * as colors from './colors';

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

      // Description
      const desc = helper.commandDescription(command);
      if (desc) {
        output += colors.status.dim(desc) + '\n\n';
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
          const description = helper.subcommandDescription(subcommand);

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
