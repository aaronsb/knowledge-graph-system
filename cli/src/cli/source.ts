/**
 * Source document retrieval commands (ADR-081)
 */

import { Command } from 'commander';
import * as fs from 'fs';
import * as path from 'path';
import { createClientFromEnv } from '../api/client';
import { setCommandHelp } from './help-formatter';
import * as colors from './colors';
import { Table } from '../lib/table';

export const sourceCommand = setCommandHelp(
  new Command('source'),
  'Manage source documents',
  'Retrieve and manage source documents stored in Garage. Source documents are the original files ingested into the knowledge graph, preserved for model evolution and re-extraction (ADR-081).'
)
  .showHelpAfterError();

// kg source list
const listCommand = setCommandHelp(
  new Command('list'),
  'List source nodes',
  'List source nodes (chunks) in the graph. Sources are chunks of ingested documents. Filter by ontology name to see sources from specific documents.'
)
  .option('-o, --ontology <name>', 'Filter by ontology/document name (partial match)')
  .option('-l, --limit <n>', 'Maximum sources to return', '50')
  .option('--offset <n>', 'Skip N sources (pagination)', '0')
  .option('-j, --json', 'Output raw JSON')
  .showHelpAfterError()
  .action(async (options: { ontology?: string; limit: string; offset: string; json?: boolean }) => {
    try {
      const client = createClientFromEnv();
      const result = await client.listSources({
        ontology: options.ontology,
        limit: parseInt(options.limit),
        offset: parseInt(options.offset),
      });

      if (options.json) {
        console.log(JSON.stringify(result, null, 2));
        return;
      }

      if (result.sources.length === 0) {
        console.log(colors.status.warning('\n⚠ No sources found'));
        if (options.ontology) {
          console.log(colors.status.dim(`  Try a different ontology filter or remove -o`));
        }
        return;
      }

      console.log('\n' + colors.ui.title('📄 Sources'));
      console.log(colors.status.dim(`  Showing ${result.sources.length} of ${result.total} sources\n`));

      const table = new Table({
        columns: [
          { header: 'Source ID', field: 'source_id', type: 'concept_id', width: 24 },
          { header: 'Document', field: 'document', type: 'heading', width: 'flex' },
          { header: 'Para', field: 'paragraph', type: 'count', width: 6, align: 'right' },
          { header: 'Type', field: 'content_type', type: 'text', width: 8 },
          { header: 'Garage', field: 'has_garage_key', type: 'text', width: 8,
            customFormat: (val: boolean) => val ? colors.status.success('✓') : colors.status.dim('—') },
        ]
      });

      const displayData = result.sources.map(s => ({
        ...s,
        source_id: s.source_id.length > 22 ? s.source_id.substring(0, 22) + '…' : s.source_id,
        content_type: s.content_type || 'text',
      }));

      table.print(displayData);

      if (result.total > result.sources.length) {
        console.log(colors.status.dim(`\n  Use --offset ${result.offset + result.sources.length} to see more`));
      }
    } catch (error: any) {
      console.error(colors.status.error('✗ Failed to list sources'));
      console.error(colors.status.error(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// kg source get <source-id>
const getCommand = setCommandHelp(
  new Command('get'),
  'Retrieve original document from Garage',
  'Download the original source document from Garage storage. This returns the complete document as it was before chunking, not individual chunks. Useful for verification, re-processing, or archival. Output goes to stdout by default (for piping) or to a file with -o.'
)
  .argument('<source-id>', 'Source ID (e.g., sha256:abc123_chunk1)')
  .option('-o, --output <file>', 'Save to file instead of stdout')
  .option('-m, --metadata', 'Show source metadata instead of content')
  .showHelpAfterError()
  .action(async (sourceId: string, options: { output?: string; metadata?: boolean }) => {
    try {
      const client = createClientFromEnv();

      if (options.metadata) {
        // Show metadata
        const metadata = await client.getSourceMetadata(sourceId);
        console.log(JSON.stringify(metadata, null, 2));
        return;
      }

      // Fetch document
      const buffer = await client.getSourceDocument(sourceId);

      if (options.output) {
        // Save to file
        const outputPath = path.resolve(options.output);
        fs.writeFileSync(outputPath, buffer);
        console.error(colors.status.success(`✓ Saved ${buffer.length} bytes to ${outputPath}`));
      } else {
        // Write to stdout (for piping)
        process.stdout.write(buffer);
      }
    } catch (error: any) {
      if (error.response?.status === 404) {
        console.error(colors.status.error(`✗ Source not found or no document: ${sourceId}`));
        console.error(colors.status.dim('  The source may predate ADR-081 or have no garage_key.'));
      } else {
        console.error(colors.status.error(`✗ Failed to retrieve document: ${error.message}`));
      }
      process.exit(1);
    }
  });

// kg source info <source-id>
const infoCommand = setCommandHelp(
  new Command('info'),
  'Show source metadata',
  'Display metadata for a source node including document name, paragraph number, content type, garage_key, and embedding status.'
)
  .argument('<source-id>', 'Source ID')
  .showHelpAfterError()
  .action(async (sourceId: string) => {
    try {
      const client = createClientFromEnv();
      const metadata = await client.getSourceMetadata(sourceId);

      console.log(colors.ui.header(`Source: ${sourceId}`));
      console.log();
      console.log(`${colors.ui.key('Document:')} ${colors.ui.value(metadata.document)}`);
      console.log(`${colors.ui.key('Paragraph:')} ${colors.ui.value(String(metadata.paragraph))}`);
      if (metadata.content_type) {
        console.log(`${colors.ui.key('Type:')} ${colors.ui.value(metadata.content_type)}`);
      }
      if (metadata.file_path) {
        console.log(`${colors.ui.key('File:')} ${colors.status.dim(metadata.file_path)}`);
      }
      console.log();

      // ADR-081 fields
      console.log(colors.ui.header('Storage (ADR-081)'));
      if (metadata.garage_key) {
        console.log(`${colors.ui.key('Garage Key:')} ${colors.status.dim(metadata.garage_key)}`);
      } else {
        console.log(`${colors.ui.key('Garage Key:')} ${colors.status.warning('none (predates ADR-081)')}`);
      }
      if (metadata.content_hash) {
        console.log(`${colors.ui.key('Content Hash:')} ${colors.status.dim(metadata.content_hash.substring(0, 16) + '...')}`);
      }
      if (metadata.chunk_index !== undefined && metadata.chunk_index !== null) {
        console.log(`${colors.ui.key('Chunk:')} ${colors.ui.value(String(metadata.chunk_index))}`);
      }
      if (metadata.char_offset_start !== undefined && metadata.char_offset_end !== undefined) {
        console.log(`${colors.ui.key('Offsets:')} ${colors.ui.value(`${metadata.char_offset_start}-${metadata.char_offset_end}`)}`);
      }
      console.log();

      console.log(colors.ui.header('Embeddings'));
      console.log(`  Text: ${metadata.has_text_embedding ? colors.status.success('yes') : colors.status.dim('no')}`);
      console.log(`  Visual: ${metadata.has_visual_embedding ? colors.status.success('yes') : colors.status.dim('no')}`);
      console.log();
      console.log(colors.ui.header('Content Preview'));
      const preview = metadata.full_text.length > 200
        ? metadata.full_text.substring(0, 200) + '...'
        : metadata.full_text;
      console.log(colors.status.dim(preview));
    } catch (error: any) {
      if (error.response?.status === 404) {
        console.error(colors.status.error(`✗ Source not found: ${sourceId}`));
      } else {
        console.error(colors.status.error(`✗ Failed to get source info: ${error.message}`));
      }
      process.exit(1);
    }
  });

sourceCommand.addCommand(listCommand);
sourceCommand.addCommand(getCommand);
sourceCommand.addCommand(infoCommand);
