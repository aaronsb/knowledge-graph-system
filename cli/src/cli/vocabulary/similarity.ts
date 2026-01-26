/**
 * Vocabulary Similarity Commands
 * Find similar/opposite types and analyze category fit (ADR-053)
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../../api/client';
import * as colors from '../colors';
import { separator } from '../colors';

export function createSimilarCommand(): Command {
  return new Command('similar')
    .description('Find similar edge types via embedding similarity (ADR-053). Shows types with highest cosine similarity - useful for synonym detection and consolidation.')
    .argument('<type>', 'Relationship type to analyze (e.g., IMPLIES)')
    .option('--limit <n>', 'Number of results to return (1-100)', '10')
    .action(async (type: string, options: { limit: string }) => {
      try {
        const client = createClientFromEnv();
        const limit = parseInt(options.limit, 10);

        if (isNaN(limit) || limit < 1 || limit > 100) {
          console.error(colors.status.error('✗ Limit must be between 1 and 100'));
          process.exit(1);
        }

        const data = await client.getSimilarTypes(type, limit, false);

        console.log('\n' + separator());
        console.log(colors.ui.title(`📊 Most Similar to ${type}`));
        console.log(separator());
        console.log();
        console.log(`${colors.ui.key('Type:')} ${type}`);
        console.log(`${colors.ui.key('Category:')} ${data.category}`);
        console.log(`${colors.ui.key('Compared:')} ${data.total_compared} types`);
        console.log();
        console.log(colors.status.dim('──────────────────────────────────────────────────────────────'));
        console.log(colors.status.dim('TYPE                      SIMILARITY  CATEGORY          USAGE'));
        console.log(colors.status.dim('──────────────────────────────────────────────────────────────'));

        for (const similar of data.similar_types) {
          const typeColor = colors.concept.label;
          const simScore = (similar.similarity * 100).toFixed(0) + '%';
          const simColor = similar.similarity >= 0.90 ? colors.status.success :
                         similar.similarity >= 0.75 ? colors.status.warning :
                         colors.status.dim;

          console.log(
            `${typeColor(similar.relationship_type.padEnd(25))} ` +
            `${simColor(simScore.padEnd(11))} ` +
            `${similar.category.padEnd(17)} ` +
            `${colors.status.dim(similar.usage_count.toString())}`
          );
        }

        console.log(colors.status.dim('──────────────────────────────────────────────────────────────'));
        console.log();
        console.log(colors.status.dim('💡 Similarity ≥90%: Strong merge candidates (ADR-052)'));
        console.log(colors.status.dim('   Similarity 75-90%: Review for potential consolidation'));

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to find similar types'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

export function createOppositeCommand(): Command {
  return new Command('opposite')
    .description('Find opposite (least similar) edge types via embedding similarity (ADR-053). Shows types with lowest cosine similarity.')
    .argument('<type>', 'Relationship type to analyze (e.g., IMPLIES)')
    .option('--limit <n>', 'Number of results to return (1-100)', '5')
    .action(async (type: string, options: { limit: string }) => {
      try {
        const client = createClientFromEnv();
        const limit = parseInt(options.limit, 10);

        if (isNaN(limit) || limit < 1 || limit > 100) {
          console.error(colors.status.error('✗ Limit must be between 1 and 100'));
          process.exit(1);
        }

        const data = await client.getSimilarTypes(type, limit, true);

        console.log('\n' + separator());
        console.log(colors.ui.title(`📊 Least Similar to ${type} (Opposites)`));
        console.log(separator());
        console.log();
        console.log(`${colors.ui.key('Type:')} ${type}`);
        console.log(`${colors.ui.key('Category:')} ${data.category}`);
        console.log(`${colors.ui.key('Compared:')} ${data.total_compared} types`);
        console.log();
        console.log(colors.status.dim('──────────────────────────────────────────────────────────────'));
        console.log(colors.status.dim('TYPE                      SIMILARITY  CATEGORY          USAGE'));
        console.log(colors.status.dim('──────────────────────────────────────────────────────────────'));

        for (const similar of data.similar_types) {
          const typeColor = colors.concept.label;
          const simScore = (similar.similarity * 100).toFixed(0) + '%';

          console.log(
            `${typeColor(similar.relationship_type.padEnd(25))} ` +
            `${colors.status.dim(simScore.padEnd(11))} ` +
            `${similar.category.padEnd(17)} ` +
            `${colors.status.dim(similar.usage_count.toString())}`
          );
        }

        console.log(colors.status.dim('──────────────────────────────────────────────────────────────'));

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to find opposite types'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

export function createSearchCommand(): Command {
  return new Command('search')
    .description('Search for vocabulary terms by natural language query. Useful when creating edges to find the best relationship type.')
    .argument('<query>', 'Natural language search term (e.g., "prevents", "leads to", "causes")')
    .option('--limit <n>', 'Number of results to return (1-20)', '5')
    .option('--json', 'Output as JSON for scripting')
    .action(async (query: string, options: { limit: string; json?: boolean }) => {
      try {
        const client = createClientFromEnv();
        const limit = Math.min(parseInt(options.limit, 10) || 5, 20);

        // Use the similar types endpoint with the query
        // This works because the API accepts any term and compares embeddings
        const data = await client.getSimilarTypes(query.toUpperCase().replace(/\s+/g, '_'), limit, false);

        if (options.json) {
          console.log(JSON.stringify({
            query,
            results: data.similar_types.map((t: any) => ({
              term: t.relationship_type,
              similarity: t.similarity,
              category: t.category,
              usage_count: t.usage_count,
            })),
          }, null, 2));
          return;
        }

        console.log();
        console.log(colors.ui.title(`🔍 Vocabulary Search: "${query}"`));
        console.log(separator());
        console.log();

        if (!data.similar_types || data.similar_types.length === 0) {
          console.log(colors.status.warning('No matching vocabulary terms found.'));
          console.log();
          console.log(colors.status.dim('To create a new term, use:'));
          console.log(colors.status.dim(`  kg edge create --type ${query.toUpperCase().replace(/\s+/g, '_')} --create-vocab`));
          return;
        }

        for (let i = 0; i < data.similar_types.length; i++) {
          const t = data.similar_types[i];
          const simScore = (t.similarity * 100).toFixed(0) + '%';
          const simColor = t.similarity >= 0.90 ? colors.status.success :
                          t.similarity >= 0.75 ? colors.status.warning :
                          colors.status.dim;

          console.log(
            `  ${colors.status.info((i + 1).toString() + '.')} ` +
            `${colors.concept.label(t.relationship_type.padEnd(25))} ` +
            `${simColor(simScore.padEnd(8))} ` +
            `${colors.status.dim(t.category)}`
          );
        }

        console.log();
        console.log(colors.status.dim('Use: kg edge create --type <TERM> ...'));

      } catch (error: any) {
        // If the term doesn't exist, the API might return an error
        // In that case, try to search concepts instead
        console.error(colors.status.error('✗ Search failed'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

export function createAnalyzeCommand(): Command {
  return new Command('analyze')
    .description('Detailed analysis of vocabulary type for quality assurance (ADR-053). Shows category fit and potential miscategorization.')
    .argument('<type>', 'Relationship type to analyze (e.g., STORES)')
    .action(async (type: string) => {
      try {
        const client = createClientFromEnv();
        const data = await client.analyzeVocabularyType(type);

        console.log('\n' + separator(64, '═'));
        console.log(colors.ui.title(`🔍 Vocabulary Analysis: ${type}`));
        console.log(separator(64, '═'));
        console.log();
        console.log(`${colors.ui.key('Category:')} ${data.category}`);
        console.log(`${colors.ui.key('Category Fit:')} ${(data.category_fit * 100).toFixed(0)}%`);

        if (data.potential_miscategorization) {
          console.log();
          console.log(colors.status.warning('⚠️  Potential Miscategorization Detected'));
          console.log(colors.status.dim(`   ${data.suggestion}`));
        } else {
          console.log(colors.status.success('\n✓ Category assignment looks good'));
        }

        console.log();
        console.log(colors.status.dim('────────────────────────────────────────────────────────────────'));
        console.log(colors.ui.header('Most Similar in Same Category:'));
        console.log(colors.status.dim('────────────────────────────────────────────────────────────────'));

        if (data.most_similar_same_category.length > 0) {
          for (const similar of data.most_similar_same_category) {
            const simScore = (similar.similarity * 100).toFixed(0) + '%';
            console.log(
              `  ${colors.concept.label(similar.relationship_type.padEnd(25))} ` +
              `${colors.status.success(simScore.padEnd(6))} ` +
              `${colors.status.dim(`(${similar.usage_count} uses)`)}`
            );
          }
        } else {
          console.log(colors.status.dim('  No other types in this category'));
        }

        console.log();
        console.log(colors.status.dim('────────────────────────────────────────────────────────────────'));
        console.log(colors.ui.header('Most Similar in Other Categories:'));
        console.log(colors.status.dim('────────────────────────────────────────────────────────────────'));

        if (data.most_similar_other_categories.length > 0) {
          for (const similar of data.most_similar_other_categories) {
            const simScore = (similar.similarity * 100).toFixed(0) + '%';
            console.log(
              `  ${colors.concept.label(similar.relationship_type.padEnd(25))} ` +
              `${colors.status.warning(simScore.padEnd(6))} ` +
              `${colors.status.dim(similar.category.padEnd(15))} ` +
              `${colors.status.dim(`(${similar.usage_count} uses)`)}`
            );
          }
        } else {
          console.log(colors.status.dim('  No similar types in other categories'));
        }

        console.log(separator(64, '═'));

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to analyze type'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}
