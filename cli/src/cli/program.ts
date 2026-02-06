/**
 * Program Commands (ADR-500)
 *
 * CLI commands for managing GraphProgram notarization.
 * Programs are validated (notarized) server-side before storage.
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../api/client';
import * as colors from './colors';
import { separator } from './colors';
import { Table } from '../lib/table';
import { setCommandHelp } from './help-formatter';
import * as fs from 'fs';

export const programCommand = setCommandHelp(
  new Command('program'),
  'Manage graph programs',
  'Validate, store, and retrieve GraphProgram ASTs (ADR-500). Programs are notarized server-side to ensure safety before execution.'
)
  .alias('prog')
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  .addCommand(
    new Command('validate')
      .description('Validate a program without storing it (dry run)')
      .argument('<file>', 'JSON file path (use - for stdin)')
      .action(async (file) => {
        try {
          const program = await readProgramJson(file);
          const client = createClientFromEnv();
          const result = await client.validateProgram(program);

          if (result.valid) {
            console.log(colors.status.success('\n  ✓ Program is valid'));
          } else {
            console.log(colors.status.error('\n  ✗ Program is invalid'));
          }

          if (result.errors.length > 0) {
            console.log('\n' + colors.stats.section('Errors'));
            for (const err of result.errors) {
              const loc = err.statement !== null && err.statement !== undefined
                ? `stmt ${err.statement}`
                : 'program';
              console.log(
                `  ${colors.status.error(`[${err.rule_id}]`)} ${colors.status.dim(loc)}: ${err.message}`
              );
            }
          }

          if (result.warnings.length > 0) {
            console.log('\n' + colors.stats.section('Warnings'));
            for (const warn of result.warnings) {
              const loc = warn.statement !== null && warn.statement !== undefined
                ? `stmt ${warn.statement}`
                : 'program';
              console.log(
                `  ${colors.status.warning(`[${warn.rule_id}]`)} ${colors.status.dim(loc)}: ${warn.message}`
              );
            }
          }

          console.log();
          if (!result.valid) process.exit(1);

        } catch (error: any) {
          console.error(colors.status.error('Failed to validate program'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('create')
      .description('Notarize and store a program')
      .argument('<file>', 'JSON file path (use - for stdin)')
      .option('-n, --name <name>', 'Program name')
      .action(async (file, options) => {
        try {
          const program = await readProgramJson(file);
          const client = createClientFromEnv();
          const result = await client.createProgram(program, options.name);

          console.log(colors.status.success(
            `\n  Notarized program "${result.name}" (ID ${result.id})`
          ));
          console.log(`  ${colors.stats.label('Created:')} ${result.created_at}`);
          console.log(`  ${colors.stats.label('Statements:')} ${result.program.statements.length}`);
          console.log();

        } catch (error: any) {
          if (error.response?.status === 400) {
            const detail = error.response.data.detail;
            console.error(colors.status.error('\n  ✗ Program validation failed'));
            if (detail?.validation?.errors) {
              for (const err of detail.validation.errors) {
                const loc = err.statement !== null && err.statement !== undefined
                  ? `stmt ${err.statement}`
                  : 'program';
                console.error(
                  `  ${colors.status.error(`[${err.rule_id}]`)} ${colors.status.dim(loc)}: ${err.message}`
                );
              }
            }
            console.error();
          } else {
            console.error(colors.status.error('Failed to create program'));
            console.error(colors.status.error(error.response?.data?.detail || error.message));
          }
          process.exit(1);
        }
      })
  )
  .addCommand(
    new Command('show')
      .description('Show a notarized program')
      .argument('<id>', 'Program ID')
      .option('--json', 'Output raw JSON')
      .action(async (id, options) => {
        try {
          const client = createClientFromEnv();
          const result = await client.getProgram(parseInt(id));

          if (options.json) {
            console.log(JSON.stringify(result, null, 2));
            return;
          }

          console.log('\n' + separator());
          console.log(colors.ui.title(`Program ${result.id}`));
          console.log(separator());

          console.log(`\n  ${colors.stats.label('Name:')} ${result.name}`);
          console.log(`  ${colors.stats.label('Owner:')} ${result.owner_id ?? colors.status.dim('(system)')}`);
          console.log(`  ${colors.stats.label('Version:')} ${result.program.version}`);
          console.log(`  ${colors.stats.label('Statements:')} ${result.program.statements.length}`);
          console.log(`  ${colors.stats.label('Created:')} ${result.created_at}`);
          console.log(`  ${colors.stats.label('Updated:')} ${result.updated_at}`);

          if (result.program.metadata?.description) {
            console.log(`  ${colors.stats.label('Description:')} ${result.program.metadata.description}`);
          }

          console.log('\n' + colors.stats.section('Statements'));
          console.log(separator(80, '─'));

          for (let i = 0; i < result.program.statements.length; i++) {
            const stmt = result.program.statements[i];
            const label = stmt.label ? ` ${colors.status.dim(`(${stmt.label})`)}` : '';
            const op = stmt.operation;

            if (op.type === 'cypher') {
              console.log(`  ${colors.concept.label(`[${i}]`)} ${stmt.op} ${colors.ui.key('cypher')}${label}`);
              console.log(`      ${colors.status.dim(op.query)}`);
            } else if (op.type === 'api') {
              console.log(`  ${colors.concept.label(`[${i}]`)} ${stmt.op} ${colors.ui.key('api')} ${op.endpoint}${label}`);
            } else if (op.type === 'conditional') {
              console.log(`  ${colors.concept.label(`[${i}]`)} ${stmt.op} ${colors.ui.key('conditional')}${label}`);
            }
          }

          console.log(separator(80, '─'));
          console.log();

        } catch (error: any) {
          if (error.response?.status === 404) {
            console.error(colors.status.error(`Program not found: ${id}`));
          } else if (error.response?.status === 403) {
            console.error(colors.status.error('Access denied to this program'));
          } else {
            console.error(colors.status.error('Failed to get program'));
            console.error(colors.status.error(error.response?.data?.detail || error.message));
          }
          process.exit(1);
        }
      })
  );


/**
 * Read a GraphProgram JSON from file or stdin.
 */
async function readProgramJson(filePath: string): Promise<Record<string, any>> {
  let content: string;

  if (filePath === '-') {
    // Read from stdin
    content = await new Promise<string>((resolve, reject) => {
      let data = '';
      process.stdin.setEncoding('utf8');
      process.stdin.on('data', (chunk) => { data += chunk; });
      process.stdin.on('end', () => resolve(data));
      process.stdin.on('error', reject);
    });
  } else {
    if (!fs.existsSync(filePath)) {
      throw new Error(`File not found: ${filePath}`);
    }
    content = fs.readFileSync(filePath, 'utf8');
  }

  try {
    return JSON.parse(content);
  } catch {
    throw new Error('Invalid JSON in program file');
  }
}
