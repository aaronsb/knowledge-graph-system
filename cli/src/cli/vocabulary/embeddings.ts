/**
 * Vocabulary Embedding Commands
 * Generate embeddings and manage category assignments (ADR-047)
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../../api/client';
import * as colors from '../colors';
import { coloredCount, separator } from '../colors';

export function createGenerateEmbeddingsCommand(): Command {
  return new Command('generate-embeddings')
    .description('Generate vector embeddings for vocabulary types (required for consolidation and categorization).')
    .option('--force', 'Regenerate ALL embeddings regardless of existing state')
    .option('--all', 'Process all active types (not just missing)')
    .action(async (options) => {
      try {
        const client = createClientFromEnv();

        const forceRegenerate = options.force || false;
        const onlyMissing = !options.all;

        let modeDescription = '';
        if (forceRegenerate) {
          modeDescription = colors.status.warning('ALL vocabulary types (force regenerate)');
        } else if (onlyMissing) {
          modeDescription = colors.ui.value('vocabulary types WITHOUT embeddings (default)');
        } else {
          modeDescription = colors.ui.value('all active vocabulary types');
        }

        console.log('\n' + separator());
        console.log(colors.ui.title('🔄 Generating Vocabulary Embeddings'));
        console.log(separator());
        console.log(`\n  ${colors.ui.key('Mode:')} ${modeDescription}`);

        // Fetch active embedding config to show correct provider
        const embeddingConfig = await client.getEmbeddingConfig();
        const providerName = embeddingConfig.provider === 'openai' ? 'OpenAI' :
                             embeddingConfig.provider === 'local' ? 'local embeddings' :
                             embeddingConfig.provider;
        const modelInfo = embeddingConfig.model ? ` (${embeddingConfig.model})` : '';
        console.log('\n' + colors.status.dim(`  Generating embeddings via ${providerName}${modelInfo}...`));

        const result = await client.generateVocabularyEmbeddings(
          forceRegenerate,
          onlyMissing
        );

        console.log('\n' + separator());
        if (result.success) {
          console.log(colors.status.success('✓ Embedding generation completed successfully'));
        } else {
          console.log(colors.status.warning('⚠️  Embedding generation completed with failures'));
        }
        console.log(`  ${colors.stats.label('Generated:')} ${coloredCount(result.generated)}`);
        console.log(`  ${colors.stats.label('Skipped:')} ${coloredCount(result.skipped)}`);
        if (result.failed > 0) {
          console.log(`  ${colors.stats.label('Failed:')} ${colors.status.error(result.failed.toString())}`);
        } else {
          console.log(`  ${colors.stats.label('Failed:')} ${coloredCount(result.failed)}`);
        }
        console.log('\n' + separator());

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to generate embeddings'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

export function createCategoryScoresCommand(): Command {
  return new Command('category-scores')
    .description('Show category similarity scores for a specific relationship type (ADR-047).')
    .argument('<type>', 'Relationship type to analyze (e.g., CAUSES, ENABLES)')
    .action(async (relationshipType: string) => {
      try {
        const client = createClientFromEnv();
        const result = await client.getCategoryScores(relationshipType);

        console.log('\n' + separator());
        console.log(colors.ui.title(`📊 Category Scores: ${colors.getRelationshipColor(relationshipType)(relationshipType)}`));
        console.log(separator());

        console.log(`\n${colors.stats.section('Assignment')}`);
        console.log(`  ${colors.stats.label('Category:')} ${colors.ui.value(result.category)}`);

        const confPercent = (result.confidence * 100).toFixed(0);
        let confColor = colors.status.dim;
        if (result.confidence >= 0.70) confColor = colors.status.success;
        else if (result.confidence >= 0.50) confColor = colors.status.warning;
        else confColor = colors.status.error;

        console.log(`  ${colors.stats.label('Confidence:')} ${confColor(confPercent + '%')}`);
        console.log(`  ${colors.stats.label('Ambiguous:')} ${result.ambiguous ? colors.status.warning('Yes') : colors.status.success('No')}`);

        if (result.ambiguous && result.runner_up_category) {
          const runnerUpPercent = (result.runner_up_score * 100).toFixed(0);
          console.log(`  ${colors.stats.label('Runner-up:')} ${colors.ui.value(result.runner_up_category)} (${runnerUpPercent}%)`);
        }

        console.log(`\n${colors.stats.section('Similarity to Category Seeds')}`);

        const sortedScores = Object.entries(result.scores)
          .sort((a: any, b: any) => b[1] - a[1]);

        for (const [category, score] of sortedScores) {
          const scoreNum = score as number;
          const percent = (scoreNum * 100).toFixed(0).padStart(3);
          const barLength = Math.round(scoreNum * 20);
          const bar = '█'.repeat(barLength);

          const catDisplay = category === result.category
            ? colors.status.success(category.padEnd(15))
            : colors.ui.value(category.padEnd(15));

          console.log(`  ${catDisplay} ${percent}%  ${bar}`);
        }

        console.log('\n' + separator());

      } catch (error: any) {
        if (error.response?.status === 404) {
          console.error(colors.status.error(`✗ Relationship type not found: ${relationshipType}`));
          console.error(colors.status.dim('  Make sure the type exists and has an embedding'));
        } else {
          console.error(colors.status.error('✗ Failed to get category scores'));
          console.error(colors.status.error(error.response?.data?.detail || error.message));
        }
        process.exit(1);
      }
    });
}

export function createRefreshCategoriesCommand(): Command {
  return new Command('refresh-categories')
    .description('Refresh category assignments for vocabulary types using latest embeddings (ADR-047, ADR-053).')
    .option('--computed-only', 'Refresh only types with category_source=computed')
    .action(async (options) => {
      try {
        const client = createClientFromEnv();
        const onlyComputed = options.computedOnly || false;

        console.log('\n' + separator());
        console.log(colors.ui.title('🔄 Refreshing Category Assignments'));
        console.log(separator());

        const modeDesc = onlyComputed
          ? 'computed categories only (category_source=computed)'
          : 'all active types (default)';
        console.log(`\n  ${colors.ui.key('Mode:')} ${colors.ui.value(modeDesc)}`);
        console.log(colors.status.dim('\n  Computing category scores via embedding similarity...'));

        const result = await client.refreshCategories(onlyComputed);

        console.log('\n' + separator());
        console.log(colors.status.success('✓ Category refresh completed'));
        console.log(`  ${colors.stats.label('Refreshed:')} ${coloredCount(result.refreshed_count)}`);
        console.log(`  ${colors.stats.label('Skipped:')} ${coloredCount(result.skipped_count)}`);

        if (result.failed_count > 0) {
          console.log(`  ${colors.stats.label('Failed:')} ${colors.status.error(result.failed_count.toString())}`);
        } else {
          console.log(`  ${colors.stats.label('Failed:')} ${coloredCount(result.failed_count)}`);
        }

        if (result.assignments && result.assignments.length > 0) {
          const sampleSize = Math.min(5, result.assignments.length);
          console.log(`\n${colors.stats.section(`Sample Results (${sampleSize} of ${result.assignments.length})`)}`);

          for (let i = 0; i < sampleSize; i++) {
            const assignment = result.assignments[i];
            const confPercent = (assignment.confidence * 100).toFixed(0);
            const ambiguous = assignment.ambiguous ? colors.status.warning(' ⚠') : '';
            console.log(
              `  ${colors.getRelationshipColor(assignment.relationship_type)(assignment.relationship_type.padEnd(25))} → ` +
              `${colors.ui.value(assignment.category.padEnd(12))} (${confPercent}%)${ambiguous}`
            );
          }
        }

        console.log('\n' + separator());

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to refresh categories'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}
