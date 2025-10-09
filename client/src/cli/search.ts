/**
 * Search and Query Commands
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../api/client';
import * as colors from './colors';
import { getConceptColor, getRelationshipColor, coloredPercentage, separator } from './colors';
import { configureColoredHelp } from './help-formatter';

const queryCommand = new Command('query')
      .description('Search for concepts using natural language')
      .argument('<query>', 'Search query text')
      .option('-l, --limit <number>', 'Maximum results', '10')
      .option('--min-similarity <number>', 'Minimum similarity score (0.0-1.0)', '0.7')
      .action(async (query, options) => {
        try {
          const client = createClientFromEnv();
          const result = await client.searchConcepts({
            query,
            limit: parseInt(options.limit),
            min_similarity: parseFloat(options.minSimilarity)
          });

          console.log('\n' + separator());
          console.log(colors.ui.title(`🔍 Searching for: ${query}`));
          console.log(separator());
          console.log(colors.status.success(`\n✓ Found ${result.count} concepts:\n`));

          result.results.forEach((concept, i) => {
            const scoreColor = getConceptColor(concept.score);
            console.log(colors.ui.bullet('●') + ' ' + colors.concept.label(`${i + 1}. ${concept.label}`));
            console.log(`   ${colors.ui.key('ID:')} ${colors.concept.id(concept.concept_id)}`);
            console.log(`   ${colors.ui.key('Similarity:')} ${coloredPercentage(concept.score)}`);
            console.log(`   ${colors.ui.key('Documents:')} ${colors.evidence.document(concept.documents.join(', '))}`);
            console.log(`   ${colors.ui.key('Evidence:')} ${colors.evidence.count(String(concept.evidence_count))} instances`);
            console.log();
          });
        } catch (error: any) {
          console.error(colors.status.error('✗ Search failed'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      });

const detailsCommand = new Command('details')
      .description('Get detailed information about a concept')
      .argument('<concept-id>', 'Concept ID to retrieve')
      .action(async (conceptId) => {
        try {
          const client = createClientFromEnv();
          const concept = await client.getConceptDetails(conceptId);

          console.log('\n' + separator());
          console.log(colors.ui.title(`📊 Concept Details: ${concept.label}`));
          console.log(separator());
          console.log(`\n${colors.ui.key('ID:')} ${colors.concept.id(concept.concept_id)}`);
          console.log(`${colors.ui.key('Search Terms:')} ${colors.concept.searchTerms(concept.search_terms.join(', '))}`);
          console.log(`${colors.ui.key('Documents:')} ${colors.evidence.document(concept.documents.join(', '))}`);

          console.log('\n' + colors.ui.header(`Evidence (${concept.instances.length} instances)`));
          console.log(separator(80, '─'));
          concept.instances.forEach((inst, i) => {
            console.log(`\n${colors.ui.bullet(`${i + 1}.`)} ${colors.evidence.document(inst.document)} ${colors.evidence.paragraph(`(para ${inst.paragraph})`)}`);
            console.log(`   ${colors.evidence.quote(`"${inst.quote}"`)}`);
          });

          if (concept.relationships.length > 0) {
            console.log('\n' + colors.ui.header(`Relationships (${concept.relationships.length})`));
            console.log(separator(80, '─'));
            concept.relationships.forEach(rel => {
              const relColor = getRelationshipColor(rel.rel_type);
              const confidence = rel.confidence ? ` ${colors.status.dim(`[${(rel.confidence * 100).toFixed(0)}%]`)}` : '';
              console.log(`  ${colors.path.arrow('→')} ${relColor(rel.rel_type)} ${colors.path.arrow('→')} ${colors.concept.label(rel.to_label)} ${colors.concept.id(`(${rel.to_id})`)}${confidence}`);
            });
          } else {
            console.log('\n' + colors.status.warning('⚠ No outgoing relationships'));
          }
          console.log();
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to get concept details'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      });

const relatedCommand = new Command('related')
      .description('Find concepts related through graph traversal')
      .argument('<concept-id>', 'Starting concept ID')
      .option('-d, --depth <number>', 'Maximum traversal depth (1-5)', '2')
      .option('-t, --types <types...>', 'Filter by relationship types')
      .action(async (conceptId, options) => {
        try {
          const client = createClientFromEnv();
          const result = await client.findRelatedConcepts({
            concept_id: conceptId,
            max_depth: parseInt(options.depth),
            relationship_types: options.types
          });

          console.log('\n' + separator());
          console.log(colors.ui.title(`🔗 Related Concepts from: ${conceptId}`));
          console.log(`${colors.ui.key('Max depth:')} ${colors.path.distance(String(result.max_depth))}`);
          console.log(separator());
          console.log(colors.status.success(`\n✓ Found ${result.count} related concepts:\n`));

          let currentDistance = -1;
          result.results.forEach(concept => {
            if (concept.distance !== currentDistance) {
              currentDistance = concept.distance;
              console.log('\n' + colors.path.distance(`Distance ${currentDistance}:`));
            }
            console.log(`  ${colors.ui.bullet('●')} ${colors.concept.label(concept.label)} ${colors.concept.id(`(${concept.concept_id})`)}`);

            // Color-code the path by relationship types
            const coloredPath = concept.path_types.map(type => getRelationshipColor(type)(type)).join(colors.path.arrow(' → '));
            console.log(`    ${colors.ui.key('Path:')} ${coloredPath}`);
          });
          console.log();
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to find related concepts'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      });

const connectCommand = new Command('connect')
      .description('Find shortest path between two concepts (accepts concept IDs or natural language queries)')
      .argument('<from>', 'Starting concept (ID or search phrase)')
      .argument('<to>', 'Target concept (ID or search phrase)')
      .option('--max-hops <number>', 'Maximum path length', '5')
      .action(async (from, to, options) => {
        try {
          const client = createClientFromEnv();

          // Auto-detect if using concept IDs (contain hyphens/underscores) or natural language
          const isFromId = from.includes('-') || from.includes('_');
          const isToId = to.includes('-') || to.includes('_');

          let result;
          let fromLabel = from;
          let toLabel = to;

          if (isFromId && isToId) {
            // Both are concept IDs - use ID-based search
            result = await client.findConnection({
              from_id: from,
              to_id: to,
              max_hops: parseInt(options.maxHops)
            });
          } else {
            // At least one is a natural language query - use search-based
            result = await client.findConnectionBySearch({
              from_query: from,
              to_query: to,
              max_hops: parseInt(options.maxHops)
            });

            // Update labels with matched concepts
            if (result.from_concept) {
              fromLabel = `${result.from_concept.label} (matched: "${from}")`;
            }
            if (result.to_concept) {
              toLabel = `${result.to_concept.label} (matched: "${to}")`;
            }
          }

          console.log('\n' + separator());
          console.log(colors.ui.title('🌉 Finding Connection'));
          console.log(separator());
          console.log(`  ${colors.ui.key('From:')} ${colors.concept.label(fromLabel)}`);
          console.log(`  ${colors.ui.key('To:')} ${colors.concept.label(toLabel)}`);
          console.log(`  ${colors.ui.key('Max hops:')} ${colors.path.hop(String(result.max_hops))}\n`);

          if (result.count === 0) {
            console.log(colors.status.warning(`⚠ No connection found within ${result.max_hops} hops`));
          } else {
            console.log(colors.status.success(`✓ Found ${result.count} path(s):\n`));

            result.paths.forEach((path, i) => {
              console.log(colors.path.distance(`Path ${i + 1}`) + colors.status.dim(` (${path.hops} hops):`));
              path.nodes.forEach((node, j) => {
                console.log(`  ${colors.path.node(node.label)} ${colors.concept.id(`(${node.id})`)}`);
                if (j < path.relationships.length) {
                  const relType = path.relationships[j];
                  const relColor = getRelationshipColor(relType);
                  console.log(`    ${colors.path.arrow('↓')} ${relColor(relType)}`);
                }
              });
              console.log();
            });
          }
          console.log(separator());
        } catch (error: any) {
          console.error(colors.status.error('✗ Failed to find connection'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      });

// Configure colored help for all search subcommands
[queryCommand, detailsCommand, relatedCommand, connectCommand].forEach(configureColoredHelp);

export const searchCommand = new Command('search')
  .description('Search for concepts and explore the graph')
  .addCommand(queryCommand)
  .addCommand(detailsCommand)
  .addCommand(relatedCommand)
  .addCommand(connectCommand);
