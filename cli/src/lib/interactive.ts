/**
 * Interactive utilities for CLI wizard mode (ADR-089 Phase 2).
 *
 * Provides Tab-to-select input, multi-line editing, and confirmation prompts.
 */

import * as readline from 'readline';
import * as colors from '../cli/colors';

/**
 * Option for selection menus.
 */
export interface SelectOption {
  label: string;
  value: string;
  description?: string;
}

/**
 * Result from field input.
 */
export interface FieldInputResult {
  value: string;
  cancelled: boolean;
}

/**
 * Configuration for FieldInput.
 */
export interface FieldInputConfig {
  prompt: string;
  defaultValue?: string;
  required?: boolean;
  validator?: (value: string) => string | null; // Returns error message or null
  selectorProvider?: () => Promise<SelectOption[]>; // Async function to get options
}

/**
 * Create a readline interface for terminal input.
 */
function createReadline(): readline.Interface {
  return readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });
}

/**
 * Simple text input with optional default value.
 */
export async function textInput(prompt: string, defaultValue?: string): Promise<FieldInputResult> {
  return new Promise((resolve) => {
    const rl = createReadline();
    const displayPrompt = defaultValue
      ? `${prompt} [${colors.status.dim(defaultValue)}]: `
      : `${prompt}: `;

    rl.question(displayPrompt, (answer) => {
      rl.close();
      const value = answer.trim() || defaultValue || '';
      resolve({ value, cancelled: false });
    });

    // Handle Ctrl+C
    rl.on('SIGINT', () => {
      rl.close();
      resolve({ value: '', cancelled: true });
    });
  });
}

/**
 * Multi-line text input (for evidence/description).
 * Ctrl+D to finish, Ctrl+C to cancel.
 */
export async function multiLineInput(prompt: string): Promise<FieldInputResult> {
  console.log(`${prompt} (Ctrl+D to finish, Ctrl+C to cancel):`);
  console.log(colors.status.dim('─'.repeat(40)));

  return new Promise((resolve) => {
    const lines: string[] = [];
    const rl = createReadline();

    rl.on('line', (line) => {
      lines.push(line);
    });

    rl.on('close', () => {
      resolve({ value: lines.join('\n'), cancelled: false });
    });

    rl.on('SIGINT', () => {
      rl.close();
      resolve({ value: '', cancelled: true });
    });
  });
}

/**
 * Select from a list of options.
 */
export async function selectOption(
  prompt: string,
  options: SelectOption[],
  allowCancel: boolean = true
): Promise<{ selected: SelectOption | null; cancelled: boolean }> {
  console.log(`\n${prompt}`);
  console.log(colors.status.dim('─'.repeat(40)));

  for (let i = 0; i < options.length; i++) {
    const opt = options[i];
    console.log(`  ${colors.status.info((i + 1).toString() + '.')} ${opt.label}`);
    if (opt.description) {
      console.log(`     ${colors.status.dim(opt.description)}`);
    }
  }

  if (allowCancel) {
    console.log(`  ${colors.status.dim('0. Cancel')}`);
  }

  return new Promise((resolve) => {
    const rl = createReadline();
    rl.question(`\nSelect [1-${options.length}]: `, (answer) => {
      rl.close();
      const num = parseInt(answer.trim(), 10);

      if (num === 0 && allowCancel) {
        resolve({ selected: null, cancelled: true });
        return;
      }

      if (isNaN(num) || num < 1 || num > options.length) {
        console.log(colors.status.error('Invalid selection'));
        resolve({ selected: null, cancelled: false });
        return;
      }

      resolve({ selected: options[num - 1], cancelled: false });
    });

    rl.on('SIGINT', () => {
      rl.close();
      resolve({ selected: null, cancelled: true });
    });
  });
}

/**
 * Confirmation prompt with Accept/Reject/JSON options.
 */
export async function confirmAction(
  message: string,
  options: {
    allowJson?: boolean;
    acceptLabel?: string;
    rejectLabel?: string;
  } = {}
): Promise<'accept' | 'reject' | 'json' | 'cancelled'> {
  const acceptKey = options.acceptLabel || 'Accept';
  const rejectKey = options.rejectLabel || 'Reject';

  console.log();
  console.log(message);
  console.log();

  let promptText = `[${colors.status.success('A')}]${acceptKey}  [${colors.status.error('R')}]${rejectKey}`;
  if (options.allowJson) {
    promptText += `  [${colors.status.info('J')}]SON export`;
  }
  console.log(promptText);

  return new Promise((resolve) => {
    const rl = createReadline();

    // Read single character
    if (process.stdin.isTTY) {
      process.stdin.setRawMode(true);
    }
    process.stdin.resume();
    process.stdin.once('data', (key) => {
      if (process.stdin.isTTY) {
        process.stdin.setRawMode(false);
      }
      rl.close();

      const char = key.toString().toLowerCase();

      if (char === '\u0003') { // Ctrl+C
        resolve('cancelled');
        return;
      }

      if (char === 'a' || char === 'y') {
        console.log(colors.status.success('Accepted'));
        resolve('accept');
      } else if (char === 'r' || char === 'n') {
        console.log(colors.status.error('Rejected'));
        resolve('reject');
      } else if (char === 'j' && options.allowJson) {
        console.log(colors.status.info('JSON export'));
        resolve('json');
      } else {
        console.log(colors.status.warning('Invalid input'));
        resolve('reject');
      }
    });

    rl.on('SIGINT', () => {
      if (process.stdin.isTTY) {
        process.stdin.setRawMode(false);
      }
      rl.close();
      resolve('cancelled');
    });
  });
}

/**
 * Simple yes/no confirmation.
 */
export async function confirmYesNo(prompt: string, defaultYes: boolean = false): Promise<boolean> {
  return new Promise((resolve) => {
    const rl = createReadline();
    const hint = defaultYes ? '[Y/n]' : '[y/N]';
    rl.question(`${prompt} ${hint}: `, (answer) => {
      rl.close();
      const normalized = answer.trim().toLowerCase();

      if (normalized === '') {
        resolve(defaultYes);
        return;
      }

      resolve(normalized === 'y' || normalized === 'yes');
    });

    rl.on('SIGINT', () => {
      rl.close();
      resolve(false);
    });
  });
}

/**
 * Build ASCII diagram for concept creation confirmation.
 */
export function buildConceptDiagram(
  concept: { label: string; isNew: boolean },
  connections: Array<{ label: string; conceptId: string; relationshipType: string }>
): string {
  const lines: string[] = [];
  const boxWidth = Math.max(concept.label.length + 4, 24);

  // Main concept box
  lines.push('┌' + '─'.repeat(boxWidth) + '┐');
  lines.push('│' + concept.label.padStart((boxWidth + concept.label.length) / 2).padEnd(boxWidth) + '│');
  lines.push('│' + (concept.isNew ? '(new concept)' : '(existing)').padStart((boxWidth + 13) / 2).padEnd(boxWidth) + '│');
  lines.push('└' + '─'.repeat(boxWidth / 2) + '┬' + '─'.repeat(boxWidth - boxWidth / 2 - 1) + '┘');

  // Connections
  for (const conn of connections) {
    lines.push(' '.repeat(boxWidth / 2 + 1) + '│');
    lines.push(' '.repeat(boxWidth / 2 + 1) + '│ ' + conn.relationshipType);
    lines.push(' '.repeat(boxWidth / 2 + 1) + '▼');
    lines.push('┌' + '─'.repeat(boxWidth) + '┐');
    lines.push('│' + conn.label.padStart((boxWidth + conn.label.length) / 2).padEnd(boxWidth) + '│');
    lines.push('│' + `(${conn.conceptId})`.padStart((boxWidth + conn.conceptId.length + 2) / 2).padEnd(boxWidth) + '│');
    lines.push('└' + '─'.repeat(boxWidth) + '┘');
  }

  return lines.join('\n');
}

/**
 * Display a spinner while an async operation runs.
 */
export async function withSpinner<T>(
  message: string,
  operation: () => Promise<T>
): Promise<T> {
  const frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
  let frameIndex = 0;
  let running = true;

  // Start spinner
  const interval = setInterval(() => {
    if (running) {
      process.stdout.write(`\r${colors.status.info(frames[frameIndex])} ${message}`);
      frameIndex = (frameIndex + 1) % frames.length;
    }
  }, 80);

  try {
    const result = await operation();
    running = false;
    clearInterval(interval);
    process.stdout.write(`\r${colors.status.success('✓')} ${message}\n`);
    return result;
  } catch (error) {
    running = false;
    clearInterval(interval);
    process.stdout.write(`\r${colors.status.error('✗')} ${message}\n`);
    throw error;
  }
}
