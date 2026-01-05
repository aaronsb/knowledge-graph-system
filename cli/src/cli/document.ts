/**
 * Document search and retrieval commands (ADR-084)
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../api/client';
import { setCommandHelp } from './help-formatter';
import * as colors from './colors';
import { coloredPercentage, separator, getRelationshipColor } from './colors';
import { Table } from '../lib/table';

/**
 * Format grounding for display - prefers API's grounding_display when available
 * Falls back to local computation from grounding_strength
 */
function formatGrounding(
  grounding: number | undefined | null,
  groundingDisplay?: string | null,
  confidenceScore?: number | null
): string {
  // Prefer API's categorical label when available
  if (groundingDisplay) {
    const confStr = confidenceScore !== undefined && confidenceScore !== null
      ? ` [${(confidenceScore * 100).toFixed(0)}% conf]`
      : '';

    // Apply color based on the display label
    const label = groundingDisplay.toLowerCase();
    if (label.includes('well-supported') || label.includes('strong')) {
      return colors.status.success(`✓ ${groundingDisplay}${confStr}`);
    } else if (label.includes('some support') || label.includes('moderate')) {
      return colors.status.warning(`⚡ ${groundingDisplay}${confStr}`);
    } else if (label.includes('contested') || label.includes('contradicted')) {
      return colors.status.error(`⚠ ${groundingDisplay}${confStr}`);
    } else if (label.includes('unclear') || label.includes('unexplored')) {
      return colors.status.dim(`◯ ${groundingDisplay}${confStr}`);
    } else {
      return colors.status.dim(`${groundingDisplay}${confStr}`);
    }
  }

  // Fallback: compute from raw grounding value
  if (grounding === undefined || grounding === null) {
    return colors.status.dim('◯ Unexplored');
  }
  const groundingValue = grounding.toFixed(3);
  const percentValue = grounding * 100;
  const groundingPercent = (Math.abs(percentValue) < 0.1 && percentValue !== 0)
    ? `≈${percentValue >= 0 ? '0' : '-0'}`
    : percentValue.toFixed(0);

  if (grounding >= 0.7) {
    return colors.status.success(`✓ Strong (${groundingValue}, ${groundingPercent}%)`);
  } else if (grounding >= 0.3) {
    return colors.status.warning(`⚡ Moderate (${groundingValue}, ${groundingPercent}%)`);
  } else if (grounding >= 0) {
    return colors.status.dim(`◯ Weak (${groundingValue}, ${groundingPercent}%)`);
  } else if (grounding >= -0.3) {
    return colors.status.warning(`⚠ Negative (${groundingValue}, ${groundingPercent}%)`);
  } else {
    return colors.status.error(`✗ Contradicted (${groundingValue}, ${groundingPercent}%)`);
  }
}

export const documentCommand = setCommandHelp(
  new Command('document'),
  'Search and retrieve documents',
  'Search for documents using semantic similarity and retrieve their content from Garage storage. Documents are aggregated from source chunks, ranked by their best matching chunk similarity (ADR-084).'
)
  .showHelpAfterError();

// Alias: kg doc
documentCommand.alias('doc');

// kg document search <query>
const searchCommand = setCommandHelp(
  new Command('search'),
  'Search documents by semantic similarity',
  'Find documents that match a query using semantic search. Results show documents ranked by their best matching chunk similarity. Use --details to show full concept information for the top result.'
)
  .argument('<query>', 'Search query (natural language)')
  .option('-o, --ontology <name>', 'Filter by ontology name')
  .option('-s, --min-similarity <n>', 'Minimum similarity threshold (0-1)', '0.5')
  .option('-l, --limit <n>', 'Maximum results', '20')
  .option('-d, --details', 'Show full concept details for top result')
  .option('-j, --json', 'Output raw JSON')
  .showHelpAfterError()
  .action(async (query: string, options: {
    ontology?: string;
    minSimilarity: string;
    limit: string;
    details?: boolean;
    json?: boolean;
  }) => {
    try {
      const client = createClientFromEnv();
      const result = await client.searchDocuments({
        query,
        ontology: options.ontology,
        min_similarity: parseFloat(options.minSimilarity),
        limit: parseInt(options.limit),
      });

      if (options.json) {
        console.log(JSON.stringify(result, null, 2));
        return;
      }

      console.log();
      console.log(colors.ui.title(`🔍 Document Search: "${query}"`));
      console.log(colors.separator());

      if (result.documents.length === 0) {
        console.log(colors.status.warning('\n⚠ No documents found matching query'));
        console.log(colors.status.dim(`  Try lowering --min-similarity (currently ${options.minSimilarity})`));
        return;
      }

      console.log(colors.status.success(`\n✓ Found ${result.total_matches} document(s):\n`));

      for (let i = 0; i < result.documents.length; i++) {
        const doc = result.documents[i];
        const similarity = (doc.best_similarity * 100).toFixed(1);

        // Document header
        console.log(colors.ui.bullet(`${i + 1}.`) + ' ' + colors.ui.title(doc.filename));
        console.log(`   ${colors.ui.key('ID:')} ${colors.status.dim(doc.document_id.substring(0, 40) + '...')}`);
        console.log(`   ${colors.ui.key('Ontology:')} ${colors.ui.value(doc.ontology)}`);
        console.log(`   ${colors.ui.key('Similarity:')} ${colors.coloredPercentage(doc.best_similarity)}`);
        console.log(`   ${colors.ui.key('Sources:')} ${colors.ui.value(String(doc.source_count))} chunk(s)`);

        // Concepts
        if (doc.concept_ids.length > 0) {
          const conceptPreview = doc.concept_ids.slice(0, 3).map(id =>
            id.length > 20 ? id.substring(0, 20) + '…' : id
          ).join(', ');
          const more = doc.concept_ids.length > 3 ? ` (+${doc.concept_ids.length - 3} more)` : '';
          console.log(`   ${colors.ui.key('Concepts:')} ${colors.status.dim(conceptPreview + more)}`);
        }

        console.log();
      }

      if (result.returned < result.total_matches) {
        console.log(colors.status.dim(`  Showing ${result.returned} of ${result.total_matches} matches`));
        console.log(colors.status.dim(`  Use --limit to see more`));
      }

      // --details: Show full concept details for the top result
      if (options.details && result.documents.length > 0) {
        const topDoc = result.documents[0];
        console.log(separator());
        console.log(colors.ui.header(`Concepts: ${topDoc.filename}`));
        console.log(separator());

        // Fetch concepts for this document
        const conceptsResult = await client.getDocumentConcepts(topDoc.document_id);

        if (conceptsResult.concepts.length === 0) {
          console.log(colors.status.warning('\n⚠ No concepts found for this document'));
        } else {
          const uniqueConceptIds = [...new Set(conceptsResult.concepts.map(c => c.concept_id))];
          console.log(colors.status.dim(`\nFetching details for ${uniqueConceptIds.length} unique concepts...\n`));

          for (const [i, conceptId] of uniqueConceptIds.entries()) {
            try {
              const concept = await client.getConceptDetails(conceptId, true);

              console.log(colors.ui.bullet('●') + ' ' + colors.concept.label(`${i + 1}. ${concept.label}`));
              if (concept.description) {
                console.log(`   ${colors.status.dim(concept.description)}`);
              }
              console.log(`   ${colors.ui.key('ID:')} ${colors.concept.id(concept.concept_id)}`);
              console.log(`   ${colors.ui.key('Evidence:')} ${colors.evidence.count(String(concept.instances.length))} instances`);

              // Display grounding
              if (concept.grounding_strength !== undefined) {
                console.log(`   ${colors.ui.key('Grounding:')} ${formatGrounding(concept.grounding_strength, concept.grounding_display, concept.confidence_score)}`);
              }

              // Display sample evidence (max 2)
              if (concept.instances.length > 0) {
                console.log(`   ${colors.ui.key('Sample Evidence:')}`);
                for (const inst of concept.instances.slice(0, 2)) {
                  const truncatedQuote = inst.quote.length > 100
                    ? inst.quote.substring(0, 100) + '...'
                    : inst.quote;
                  console.log(`      ${colors.ui.bullet('•')} ${colors.evidence.document(inst.document)} ${colors.evidence.paragraph(`(para ${inst.paragraph})`)}`);
                  console.log(`         ${colors.evidence.quote(`"${truncatedQuote}"`)}`);
                }
                if (concept.instances.length > 2) {
                  console.log(`      ${colors.status.dim(`... and ${concept.instances.length - 2} more`)}`);
                }
              }

              // Display relationships (max 3)
              if (concept.relationships.length > 0) {
                console.log(`   ${colors.ui.key('Relationships:')} ${colors.status.dim(`(${concept.relationships.length})`)}`);
                for (const rel of concept.relationships.slice(0, 3)) {
                  const relColor = getRelationshipColor(rel.rel_type);
                  const confidence = rel.confidence ? ` ${colors.status.dim(`[${(rel.confidence * 100).toFixed(0)}%]`)}` : '';
                  console.log(`      ${colors.path.arrow('→')} ${relColor(rel.rel_type)} ${colors.path.arrow('→')} ${colors.concept.label(rel.to_label)}${confidence}`);
                }
                if (concept.relationships.length > 3) {
                  console.log(`      ${colors.status.dim(`... and ${concept.relationships.length - 3} more`)}`);
                }
              }

              console.log();
            } catch (err: any) {
              console.log(colors.ui.bullet('●') + ' ' + colors.status.error(`${i + 1}. Failed to load: ${conceptId}`));
              console.log(`   ${colors.status.dim(err.message)}`);
              console.log();
            }
          }
        }
      }
    } catch (error: any) {
      console.error(colors.status.error('✗ Document search failed'));
      console.error(colors.status.error(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// kg document list
const listCommand = setCommandHelp(
  new Command('list'),
  'List all documents',
  'List all documents (DocumentMeta nodes) in the knowledge graph. Filter by ontology to see documents from specific collections.'
)
  .option('-o, --ontology <name>', 'Filter by ontology name (partial match)')
  .option('-l, --limit <n>', 'Maximum documents to return', '50')
  .option('--offset <n>', 'Skip N documents (pagination)', '0')
  .option('-j, --json', 'Output raw JSON')
  .showHelpAfterError()
  .action(async (options: { ontology?: string; limit: string; offset: string; json?: boolean }) => {
    try {
      const client = createClientFromEnv();
      const result = await client.listDocuments({
        ontology: options.ontology,
        limit: parseInt(options.limit),
        offset: parseInt(options.offset),
      });

      if (options.json) {
        console.log(JSON.stringify(result, null, 2));
        return;
      }

      if (result.documents.length === 0) {
        console.log(colors.status.warning('\n⚠ No documents found'));
        if (options.ontology) {
          console.log(colors.status.dim(`  Try a different ontology filter or remove -o`));
        }
        return;
      }

      console.log('\n' + colors.ui.title('📄 Documents'));
      console.log(colors.status.dim(`  Showing ${result.documents.length} of ${result.total} documents\n`));

      const table = new Table({
        columns: [
          { header: 'Filename', field: 'filename', type: 'heading', width: 30 },
          { header: 'Ontology', field: 'ontology', type: 'text', width: 'flex' },
          { header: 'Type', field: 'content_type', type: 'text', width: 10 },
          { header: 'Sources', field: 'source_count', type: 'count', width: 8, align: 'right' },
          { header: 'Concepts', field: 'concept_count', type: 'count', width: 10, align: 'right' },
        ]
      });

      table.print(result.documents);

      if (result.total > result.documents.length) {
        console.log(colors.status.dim(`\n  Use --offset ${result.offset + result.documents.length} to see more`));
      }
    } catch (error: any) {
      console.error(colors.status.error('✗ Failed to list documents'));
      console.error(colors.status.error(error.response?.data?.detail || error.message));
      process.exit(1);
    }
  });

// kg document show <document-id>
const showCommand = setCommandHelp(
  new Command('show'),
  'Show document content',
  'Retrieve and display the full content of a document from Garage storage. Shows the original document text plus source chunks created during ingestion.'
)
  .argument('<document-id>', 'Document ID (e.g., sha256:abc123...)')
  .option('-c, --chunks', 'Show source chunks instead of full document')
  .option('-j, --json', 'Output raw JSON')
  .showHelpAfterError()
  .action(async (documentId: string, options: { chunks?: boolean; json?: boolean }) => {
    try {
      const client = createClientFromEnv();
      const result = await client.getDocumentContent(documentId);

      if (options.json) {
        console.log(JSON.stringify(result, null, 2));
        return;
      }

      console.log();
      console.log(colors.ui.header(`Document: ${documentId.substring(0, 50)}...`));
      console.log(colors.separator());
      console.log(`${colors.ui.key('Type:')} ${colors.ui.value(result.content_type)}`);
      console.log(`${colors.ui.key('Chunks:')} ${colors.ui.value(String(result.chunks.length))}`);
      console.log();

      if (options.chunks) {
        // Show chunks
        console.log(colors.ui.header('Source Chunks'));
        console.log();
        for (const chunk of result.chunks) {
          console.log(colors.ui.bullet(chunk.paragraph) + ' ' + colors.status.dim(`[${chunk.source_id}]`));
          const preview = chunk.full_text.length > 200
            ? chunk.full_text.substring(0, 200) + '...'
            : chunk.full_text;
          console.log(colors.status.dim(preview));
          console.log();
        }
      } else {
        // Show full document
        console.log(colors.ui.header('Content'));
        console.log();

        if (result.content_type === 'image') {
          if (result.content.prose) {
            console.log(result.content.prose);
          }
          if (result.content.image) {
            console.log(colors.status.dim(`\n[Image data: ${result.content.image.length} bytes base64]`));
          }
        } else {
          if (result.content.document) {
            console.log(result.content.document);
          } else if (result.content.error) {
            console.log(colors.status.error(`Error retrieving content: ${result.content.error}`));
          } else {
            console.log(colors.status.warning('No document content available'));
          }
        }
      }
    } catch (error: any) {
      if (error.response?.status === 404) {
        console.error(colors.status.error(`✗ Document not found: ${documentId}`));
      } else {
        console.error(colors.status.error(`✗ Failed to retrieve document: ${error.message}`));
        if (error.response?.data?.detail) {
          console.error(colors.status.error(error.response.data.detail));
        }
      }
      process.exit(1);
    }
  });

// kg document concepts <document-id>
const conceptsCommand = setCommandHelp(
  new Command('concepts'),
  'List concepts from a document',
  'Show all concepts extracted from a specific document. Displays concept names, IDs, and the source chunks where they appear. Use --details for full concept information including evidence and relationships.'
)
  .argument('<document-id>', 'Document ID (e.g., sha256:abc123...)')
  .option('-d, --details', 'Show full concept details (evidence, relationships, grounding)')
  .option('-j, --json', 'Output raw JSON')
  .showHelpAfterError()
  .action(async (documentId: string, options: { details?: boolean; json?: boolean }) => {
    try {
      const client = createClientFromEnv();
      const result = await client.getDocumentConcepts(documentId);

      if (options.json) {
        console.log(JSON.stringify(result, null, 2));
        return;
      }

      console.log();
      console.log(colors.ui.header(`Concepts: ${result.filename}`));
      console.log(colors.separator());
      console.log(`${colors.ui.key('Document:')} ${colors.status.dim(documentId.substring(0, 50) + '...')}`);
      console.log(`${colors.ui.key('Total:')} ${colors.ui.value(String(result.total))} concept(s)`);
      console.log();

      if (result.concepts.length === 0) {
        console.log(colors.status.warning('⚠ No concepts found for this document'));
        console.log(colors.status.dim('  The document may not have HAS_SOURCE relationships (ingested before fix)'));
        return;
      }

      if (options.details) {
        // Detailed view: fetch full details for each concept
        const uniqueConceptIds = [...new Set(result.concepts.map(c => c.concept_id))];
        console.log(colors.status.dim(`Fetching details for ${uniqueConceptIds.length} unique concepts...\n`));

        for (const [i, conceptId] of uniqueConceptIds.entries()) {
          try {
            const concept = await client.getConceptDetails(conceptId, true);

            console.log(colors.ui.bullet('●') + ' ' + colors.concept.label(`${i + 1}. ${concept.label}`));
            if (concept.description) {
              console.log(`   ${colors.status.dim(concept.description)}`);
            }
            console.log(`   ${colors.ui.key('ID:')} ${colors.concept.id(concept.concept_id)}`);
            console.log(`   ${colors.ui.key('Documents:')} ${colors.evidence.document(concept.documents.join(', '))}`);
            console.log(`   ${colors.ui.key('Evidence:')} ${colors.evidence.count(String(concept.instances.length))} instances`);

            // Display grounding
            if (concept.grounding_strength !== undefined) {
              console.log(`   ${colors.ui.key('Grounding:')} ${formatGrounding(concept.grounding_strength, concept.grounding_display, concept.confidence_score)}`);
            }

            // Display sample evidence (max 2)
            if (concept.instances.length > 0) {
              console.log(`   ${colors.ui.key('Sample Evidence:')}`);
              for (const inst of concept.instances.slice(0, 2)) {
                const truncatedQuote = inst.quote.length > 100
                  ? inst.quote.substring(0, 100) + '...'
                  : inst.quote;
                console.log(`      ${colors.ui.bullet('•')} ${colors.evidence.document(inst.document)} ${colors.evidence.paragraph(`(para ${inst.paragraph})`)}`);
                console.log(`         ${colors.evidence.quote(`"${truncatedQuote}"`)}`);
              }
              if (concept.instances.length > 2) {
                console.log(`      ${colors.status.dim(`... and ${concept.instances.length - 2} more`)}`);
              }
            }

            // Display relationships (max 5)
            if (concept.relationships.length > 0) {
              console.log(`   ${colors.ui.key('Relationships:')} ${colors.status.dim(`(${concept.relationships.length})`)}`);
              for (const rel of concept.relationships.slice(0, 5)) {
                const relColor = getRelationshipColor(rel.rel_type);
                const confidence = rel.confidence ? ` ${colors.status.dim(`[${(rel.confidence * 100).toFixed(0)}%]`)}` : '';
                console.log(`      ${colors.path.arrow('→')} ${relColor(rel.rel_type)} ${colors.path.arrow('→')} ${colors.concept.label(rel.to_label)}${confidence}`);
              }
              if (concept.relationships.length > 5) {
                console.log(`      ${colors.status.dim(`... and ${concept.relationships.length - 5} more`)}`);
              }
            }

            console.log();
          } catch (err: any) {
            console.log(colors.ui.bullet('●') + ' ' + colors.status.error(`${i + 1}. Failed to load: ${conceptId}`));
            console.log(`   ${colors.status.dim(err.message)}`);
            console.log();
          }
        }
      } else {
        // Table view (default)
        const table = new Table({
          columns: [
            { header: 'Concept', field: 'name', type: 'heading', width: 'flex' },
            { header: 'Concept ID', field: 'concept_id', type: 'concept_id', width: 28 },
            { header: 'Source', field: 'source_id', type: 'text', width: 22 },
            { header: 'Instances', field: 'instance_count', type: 'count', width: 10, align: 'right' },
          ]
        });

        const displayData = result.concepts.map(c => ({
          ...c,
          concept_id: c.concept_id.length > 26 ? c.concept_id.substring(0, 26) + '…' : c.concept_id,
          source_id: c.source_id.length > 20 ? c.source_id.substring(0, 20) + '…' : c.source_id,
        }));

        table.print(displayData);
        console.log(colors.status.dim(`\nTip: Use --details for full concept information`));
      }
    } catch (error: any) {
      if (error.response?.status === 404) {
        console.error(colors.status.error(`✗ Document not found: ${documentId}`));
      } else {
        console.error(colors.status.error(`✗ Failed to get concepts: ${error.message}`));
        if (error.response?.data?.detail) {
          console.error(colors.status.error(error.response.data.detail));
        }
      }
      process.exit(1);
    }
  });

documentCommand.addCommand(searchCommand);
documentCommand.addCommand(listCommand);
documentCommand.addCommand(showCommand);
documentCommand.addCommand(conceptsCommand);
