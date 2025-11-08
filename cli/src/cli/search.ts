/**
 * Search and Query Commands
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../api/client';
import * as colors from './colors';
import { getConceptColor, getRelationshipColor, coloredPercentage, separator } from './colors';
import { configureColoredHelp, setCommandHelp } from './help-formatter';
import { getConfig } from '../lib/config';
import {
  isChafaAvailable,
  displayImageBufferWithChafa,
  saveImageToFile,
  detectImageFormat,
  printChafaInstallInstructions
} from '../lib/terminal-images';
import * as nodePath from 'path';

/**
 * Format grounding strength for display (ADR-044)
 */
function formatGroundingStrength(grounding: number): string {
  const groundingValue = grounding.toFixed(3);
  const percentValue = grounding * 100;

  // Use ≈ symbol when value is very close to zero but not exactly zero
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

const queryCommand = setCommandHelp(
  new Command('query'),
  'Search concepts by semantic similarity',
  'Search for concepts using vector similarity (embeddings) - use specific phrases for best results'
)
      .showHelpAfterError()
      .argument('<query>', 'Natural language search query (2-3 words work best)')
      .option('-l, --limit <number>', 'Maximum number of results to return', '10')
      .option('--min-similarity <number>', 'Minimum similarity score (0.0-1.0, default 0.7=70%, lower to 0.5 for broader matches)', '0.7')
      .option('--no-evidence', 'Hide evidence quotes (shown by default)')
      .option('--no-images', 'Hide inline image display (shown by default if chafa installed)')
      .option('--no-grounding', 'Disable grounding strength calculation (ADR-044 probabilistic truth convergence) for faster results')
      .option('--download <directory>', 'Download images to specified directory instead of displaying inline')
      .option('--json', 'Output raw JSON instead of formatted text for scripting')
      .action(async (query, options) => {
        try {
          const client = createClientFromEnv();
          const config = getConfig();

          // Use config defaults, allow CLI flags to override
          // Commander.js --no-evidence flag sets options.evidence to false
          const includeEvidence = options.evidence !== undefined ? options.evidence : config.getSearchShowEvidence();
          const shouldShowImages = options.images !== undefined ? options.images : config.getSearchShowImages();
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

          for (const [i, concept] of result.results.entries()) {
            const scoreColor = getConceptColor(concept.score);
            console.log(colors.ui.bullet('●') + ' ' + colors.concept.label(`${i + 1}. ${concept.label}`));
            if (concept.description) {
              console.log(`   ${colors.status.dim(concept.description)}`);
            }
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
              for (const [idx, inst] of concept.sample_evidence.entries()) {
                const truncatedQuote = inst.quote.length > 100
                  ? inst.quote.substring(0, 100) + '...'
                  : inst.quote;
                console.log(`      ${colors.ui.bullet(`${idx + 1}.`)} ${colors.evidence.document(inst.document)} ${colors.evidence.paragraph(`(para ${inst.paragraph})`)}`);
                console.log(`         ${colors.evidence.quote(`"${truncatedQuote}"`)}`);

                // ADR-057: Handle images if available
                if (inst.has_image && inst.source_id) {
                  const downloadDir = options.download;

                  if (downloadDir) {
                    // Download mode
                    try {
                      console.log(colors.status.dim(`         📥 Downloading image from ${inst.source_id}...`));
                      const imageBuffer = await client.getSourceImage(inst.source_id);
                      const extension = detectImageFormat(imageBuffer);
                      const filename = `${inst.source_id}${extension}`;
                      const outputPath = nodePath.join(downloadDir, filename);

                      if (saveImageToFile(imageBuffer, outputPath)) {
                        console.log(colors.status.success(`         ✓ Saved to ${outputPath}`));
                      }
                    } catch (error: any) {
                      console.log(colors.status.error(`         ✗ Failed to download image: ${error.message}`));
                    }
                  } else if (shouldShowImages && config.isChafaEnabled()) {
                    // Display mode
                    if (isChafaAvailable()) {
                      try {
                        console.log(colors.status.dim(`         🖼️  Displaying image from ${inst.source_id}...`));
                        const imageBuffer = await client.getSourceImage(inst.source_id);
                        const extension = detectImageFormat(imageBuffer);
                        await displayImageBufferWithChafa(imageBuffer, extension, {
                          width: config.getChafaWidth(),
                          scale: config.getChafaScale(),
                          align: config.getChafaAlign(),
                          colors: config.getChafaColors()
                        });
                      } catch (error: any) {
                        console.log(colors.status.error(`         ✗ Failed to display image: ${error.message}`));
                      }
                    } else {
                      console.log(colors.status.warning(`         🖼️  Image available (source: ${inst.source_id})`));
                      printChafaInstallInstructions();
                    }
                  } else {
                    // Just indicate image is available
                    console.log(colors.status.dim(`         🖼️  Image available (use --show-images to display or --download <dir> to save)`));
                  }
                }
              }
            }

            console.log();
          }

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

const detailsCommand = setCommandHelp(
  new Command('details'),
  'Get full details for a concept',
  'Get comprehensive details for a concept: all evidence, relationships, sources, and grounding strength'
)
      .showHelpAfterError()
      .argument('<concept-id>', 'Concept ID to retrieve (from search results)')
      .option('--no-grounding', 'Disable grounding strength calculation (ADR-044 probabilistic truth convergence) for faster results')
      .option('--json', 'Output raw JSON instead of formatted text for scripting')
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
          if (concept.description) {
            console.log(`${colors.ui.key('Description:')} ${colors.status.dim(concept.description)}`);
          }
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

const relatedCommand = setCommandHelp(
  new Command('related'),
  'Find related concepts by graph traversal',
  'Find concepts related through graph traversal (breadth-first search) - groups results by distance'
)
      .showHelpAfterError()
      .argument('<concept-id>', 'Starting concept ID for traversal')
      .option('-d, --depth <number>', 'Maximum traversal depth in hops (1-2 fast, 3-4 moderate, 5 slow)', '2')
      .option('-t, --types <types...>', 'Filter by relationship types (IMPLIES, ENABLES, SUPPORTS, etc. - see kg vocab list)')
      .option('--json', 'Output raw JSON instead of formatted text for scripting')
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

const connectCommand = setCommandHelp(
  new Command('connect'),
  'Find paths between two concepts',
  'Find shortest path between two concepts using IDs or semantic phrase matching'
)
      .showHelpAfterError()
      .argument('<from>', 'Starting concept (exact ID or descriptive phrase - e.g., "licensing issues" not "licensing")')
      .argument('<to>', 'Target concept (exact ID or descriptive phrase - use 2-3 word phrases for best results)')
      .option('--max-hops <number>', 'Maximum path length', '5')
      .option('--min-similarity <number>', 'Semantic similarity threshold for phrase matching (default 50% - lower for broader matches)', '0.5')
      .option('--no-evidence', 'Hide evidence quotes (shown by default)')
      .option('--no-images', 'Hide inline image display (shown by default if chafa installed)')
      .option('--no-grounding', 'Disable grounding strength calculation (faster)')
      .option('--download <directory>', 'Download images to specified directory instead of displaying inline')
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
          const config = getConfig();

          // Use config defaults, allow CLI flags to override
          const includeEvidence = options.evidence !== undefined ? options.evidence : config.getSearchShowEvidence();
          const shouldShowImages = options.images !== undefined ? options.images : config.getSearchShowImages();
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

            for (const [i, path] of result.paths.entries()) {
              console.log(colors.path.distance(`Path ${i + 1}`) + colors.status.dim(` (${path.hops} hops):`));
              for (const [j, node] of path.nodes.entries()) {
                console.log(`  ${colors.path.node(node.label)} ${colors.concept.id(`(${node.id})`)}`);
                if (node.description) {
                  console.log(`     ${colors.status.dim(node.description)}`);
                }

                // Display grounding strength if available (ADR-044)
                if (includeGrounding && node.grounding_strength !== undefined && node.grounding_strength !== null) {
                  console.log(`     ${colors.ui.key('Grounding:')} ${formatGroundingStrength(node.grounding_strength)}`);
                }

                // Display sample evidence if requested
                if (includeEvidence && node.sample_evidence && node.sample_evidence.length > 0) {
                  console.log(`     ${colors.ui.key('Evidence:')}`);
                  for (const [idx, inst] of node.sample_evidence.entries()) {
                    const truncatedQuote = inst.quote.length > 80
                      ? inst.quote.substring(0, 80) + '...'
                      : inst.quote;
                    console.log(`        ${colors.ui.bullet(`${idx + 1}.`)} ${colors.evidence.document(inst.document)} ${colors.evidence.paragraph(`(para ${inst.paragraph})`)}`);
                    console.log(`           ${colors.evidence.quote(`"${truncatedQuote}"`)}`);

                    // ADR-057: Handle images if available
                    if (inst.has_image && inst.source_id) {
                      const downloadDir = options.download;

                      if (downloadDir) {
                        // Download mode
                        try {
                          console.log(colors.status.dim(`           📥 Downloading image from ${inst.source_id}...`));
                          const imageBuffer = await client.getSourceImage(inst.source_id);
                          const extension = detectImageFormat(imageBuffer);
                          const filename = `${inst.source_id}${extension}`;
                          const outputPath = nodePath.join(downloadDir, filename);

                          if (saveImageToFile(imageBuffer, outputPath)) {
                            console.log(colors.status.success(`           ✓ Saved to ${outputPath}`));
                          }
                        } catch (error: any) {
                          console.log(colors.status.error(`           ✗ Failed to download image: ${error.message}`));
                        }
                      } else if (shouldShowImages && config.isChafaEnabled()) {
                        // Display mode
                        if (isChafaAvailable()) {
                          try {
                            console.log(colors.status.dim(`           🖼️  Displaying image from ${inst.source_id}...`));
                            const imageBuffer = await client.getSourceImage(inst.source_id);
                            const extension = detectImageFormat(imageBuffer);
                            await displayImageBufferWithChafa(imageBuffer, extension, {
                              width: config.getChafaWidth(),
                              scale: config.getChafaScale(),
                              align: config.getChafaAlign(),
                              colors: config.getChafaColors()
                            });
                          } catch (error: any) {
                            console.log(colors.status.error(`           ✗ Failed to display image: ${error.message}`));
                          }
                        } else {
                          console.log(colors.status.warning(`           🖼️  Image available (source: ${inst.source_id})`));
                          printChafaInstallInstructions();
                        }
                      } else {
                        // Just indicate image is available
                        console.log(colors.status.dim(`           🖼️  Image available (use --show-images to display or --download <dir> to save)`));
                      }
                    }
                  }
                }

                if (j < path.relationships.length) {
                  const relType = path.relationships[j];
                  const relColor = getRelationshipColor(relType);
                  console.log(`    ${colors.path.arrow('↓')} ${relColor(relType)}`);
                }
              }
              console.log();
            }
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

export const searchCommand = setCommandHelp(
  new Command('search'),
  'Search and explore the knowledge graph',
  'Search and explore the knowledge graph using vector similarity, graph traversal, and path finding'
)
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  .addCommand(queryCommand)
  .addCommand(detailsCommand)
  .addCommand(relatedCommand)
  .addCommand(connectCommand);
