/**
 * Search and Query Commands
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../api/client';
import * as colors from './colors';
import { getConceptColor, getRelationshipColor, coloredPercentage, separator } from './colors';
import { configureColoredHelp } from './help-formatter';

/**
 * Format grounding strength for display (ADR-044)
 */
function formatGroundingStrength(grounding: number): string {
  const groundingPercent = (grounding * 100).toFixed(0);
  const groundingValue = grounding.toFixed(3);

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

const queryCommand = new Command('query')
      .description('Search for concepts using natural language')
      .showHelpAfterError()
      .argument('<query>', 'Search query text')
      .option('-l, --limit <number>', 'Maximum results', '10')
      .option('--min-similarity <number>', 'Minimum similarity score (0.0-1.0)', '0.7')
      .option('--show-evidence', 'Show sample evidence quotes from source text')
      .option('--no-grounding', 'Disable grounding strength calculation (faster)')
      .option('--json', 'Output raw JSON instead of formatted text')
      .action(async (query, options) => {
        try {
          const client = createClientFromEnv();
          const includeEvidence = options.showEvidence || false;
          const includeGrounding = options.grounding !== false; // Default: true

          const result = await client.searchConcepts({
            query,
            limit: parseInt(options.limit),
            min_similarity: parseFloat(options.minSimilarity),
            include_evidence: includeEvidence,
            include_grounding: includeGrounding
          });

          // JSON output mode
          if (options.json) {
            console.log(JSON.stringify(result, null, 2));
            return;
          }

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

            // Display grounding strength if available (ADR-044)
            if (concept.grounding_strength !== undefined && concept.grounding_strength !== null) {
              console.log(`   ${colors.ui.key('Grounding:')} ${formatGroundingStrength(concept.grounding_strength)}`);
            }

            // Display sample evidence if requested
            if (includeEvidence && concept.sample_evidence && concept.sample_evidence.length > 0) {
              console.log(`   ${colors.ui.key('Sample Evidence:')}`);
              concept.sample_evidence.forEach((inst, idx) => {
                const truncatedQuote = inst.quote.length > 100
                  ? inst.quote.substring(0, 100) + '...'
                  : inst.quote;
                console.log(`      ${colors.ui.bullet(`${idx + 1}.`)} ${colors.evidence.document(inst.document)} ${colors.evidence.paragraph(`(para ${inst.paragraph})`)}`);
                console.log(`         ${colors.evidence.quote(`"${truncatedQuote}"`)}`);
              });
            }

            console.log();
          });

          // Show hint if additional results available below threshold
          if (result.below_threshold_count && result.below_threshold_count > 0 && result.suggested_threshold) {
            const thresholdPercent = (result.suggested_threshold * 100).toFixed(0);
            console.log(colors.status.warning(`💡 ${result.below_threshold_count} additional concept${result.below_threshold_count > 1 ? 's' : ''} available at ${thresholdPercent}% threshold`));
            console.log(colors.status.dim(`   Try: kg search query "${query}" --min-similarity ${result.suggested_threshold}\n`));
          }
        } catch (error: any) {
          console.error(colors.status.error('✗ Search failed'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
          process.exit(1);
        }
      });

const detailsCommand = new Command('details')
      .description('Get detailed information about a concept')
      .showHelpAfterError()
      .argument('<concept-id>', 'Concept ID to retrieve')
      .option('--no-grounding', 'Disable grounding strength calculation (faster)')
      .option('--json', 'Output raw JSON instead of formatted text')
      .action(async (conceptId, options) => {
        try {
          const client = createClientFromEnv();
          const includeGrounding = options.grounding !== false; // Default: true
          const concept = await client.getConceptDetails(conceptId, includeGrounding);

          // JSON output mode
          if (options.json) {
            console.log(JSON.stringify(concept, null, 2));
            return;
          }

          console.log('\n' + separator());
          console.log(colors.ui.title(`📊 Concept Details: ${concept.label}`));
          console.log(separator());
          console.log(`\n${colors.ui.key('ID:')} ${colors.concept.id(concept.concept_id)}`);
          console.log(`${colors.ui.key('Search Terms:')} ${colors.concept.searchTerms(concept.search_terms.join(', '))}`);
          console.log(`${colors.ui.key('Documents:')} ${colors.evidence.document(concept.documents.join(', '))}`);

          // Display grounding strength if available (ADR-044)
          if (concept.grounding_strength !== undefined && concept.grounding_strength !== null) {
            console.log(`${colors.ui.key('Grounding:')} ${formatGroundingStrength(concept.grounding_strength)}`);
          }

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
      .showHelpAfterError()
      .argument('<concept-id>', 'Starting concept ID')
      .option('-d, --depth <number>', 'Maximum traversal depth (1-5)', '2')
      .option('-t, --types <types...>', 'Filter by relationship types')
      .option('--json', 'Output raw JSON instead of formatted text')
      .action(async (conceptId, options) => {
        try {
          const client = createClientFromEnv();
          const result = await client.findRelatedConcepts({
            concept_id: conceptId,
            max_depth: parseInt(options.depth),
            relationship_types: options.types
          });

          // JSON output mode
          if (options.json) {
            console.log(JSON.stringify(result, null, 2));
            return;
          }

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
      .description('Find shortest path between two concepts using IDs or semantic phrase matching')
      .showHelpAfterError()
      .argument('<from>', 'Starting concept (exact ID or descriptive phrase - e.g., "licensing issues" not "licensing")')
      .argument('<to>', 'Target concept (exact ID or descriptive phrase - use 2-3 word phrases for best results)')
      .option('--max-hops <number>', 'Maximum path length', '5')
      .option('--min-similarity <number>', 'Semantic similarity threshold for phrase matching (default 50% - lower for broader matches)', '0.5')
      .option('--show-evidence', 'Show sample evidence quotes for each concept in paths')
      .option('--no-grounding', 'Disable grounding strength calculation (faster)')
      .option('--json', 'Output raw JSON instead of formatted text')
      .addHelpText('after', `
Examples:
  $ kg search connect concept-id-123 concept-id-456
  $ kg search connect "licensing issues" "AGE benefits"
  $ kg search connect "Apache AGE" "graph database" --min-similarity 0.3
  $ kg search connect "my concept" "another concept" --show-evidence

Notes:
  - Generic single words ("features", "issues") may not match well
  - Use specific 2-3 word phrases for better semantic matching
  - Lower --min-similarity (e.g., 0.3) to find weaker concept matches
  - Error messages suggest threshold adjustments when near-misses exist
      `)
      .action(async (from, to, options) => {
        try {
          const client = createClientFromEnv();
          const includeEvidence = options.showEvidence || false;
          const includeGrounding = options.grounding !== false; // Default: true

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
              max_hops: parseInt(options.maxHops),
              include_evidence: includeEvidence,
              include_grounding: includeGrounding
            });
          } else {
            // At least one is a natural language query - use search-based
            result = await client.findConnectionBySearch({
              from_query: from,
              to_query: to,
              max_hops: parseInt(options.maxHops),
              threshold: parseFloat(options.minSimilarity),
              include_evidence: includeEvidence,
              include_grounding: includeGrounding
            });

            // Update labels with matched concepts
            if (result.from_concept) {
              fromLabel = `${result.from_concept.label} (matched: "${from}")`;
            }
            if (result.to_concept) {
              toLabel = `${result.to_concept.label} (matched: "${to}")`;
            }
          }

          // JSON output mode
          if (options.json) {
            console.log(JSON.stringify(result, null, 2));
            return;
          }

          console.log('\n' + separator());
          console.log(colors.ui.title('🌉 Finding Connection'));
          console.log(separator());
          console.log(`  ${colors.ui.key('From:')} ${colors.concept.label(fromLabel)}`);
          if ('from_similarity' in result && result.from_similarity) {
            console.log(`        ${colors.ui.key('Match:')} ${coloredPercentage(result.from_similarity)}`);
          }
          console.log(`  ${colors.ui.key('To:')} ${colors.concept.label(toLabel)}`);
          if ('to_similarity' in result && result.to_similarity) {
            console.log(`        ${colors.ui.key('Match:')} ${coloredPercentage(result.to_similarity)}`);
          }
          console.log(`  ${colors.ui.key('Max hops:')} ${colors.path.hop(String(result.max_hops))}\n`);

          if (result.count === 0) {
            console.log(colors.status.warning(`⚠ No connection found within ${result.max_hops} hops`));
          } else {
            console.log(colors.status.success(`✓ Found ${result.count} path(s):\n`));

            result.paths.forEach((path, i) => {
              console.log(colors.path.distance(`Path ${i + 1}`) + colors.status.dim(` (${path.hops} hops):`));
              path.nodes.forEach((node, j) => {
                console.log(`  ${colors.path.node(node.label)} ${colors.concept.id(`(${node.id})`)}`);

                // Display grounding strength if available (ADR-044)
                if (includeGrounding && node.grounding_strength !== undefined && node.grounding_strength !== null) {
                  console.log(`     ${colors.ui.key('Grounding:')} ${formatGroundingStrength(node.grounding_strength)}`);
                }

                // Display sample evidence if requested
                if (includeEvidence && node.sample_evidence && node.sample_evidence.length > 0) {
                  console.log(`     ${colors.ui.key('Evidence:')}`);
                  node.sample_evidence.forEach((inst, idx) => {
                    const truncatedQuote = inst.quote.length > 80
                      ? inst.quote.substring(0, 80) + '...'
                      : inst.quote;
                    console.log(`        ${colors.ui.bullet(`${idx + 1}.`)} ${colors.evidence.document(inst.document)} ${colors.evidence.paragraph(`(para ${inst.paragraph})`)}`);
                    console.log(`           ${colors.evidence.quote(`"${truncatedQuote}"`)}`);
                  });
                }

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
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  .addCommand(queryCommand)
  .addCommand(detailsCommand)
  .addCommand(relatedCommand)
  .addCommand(connectCommand);
