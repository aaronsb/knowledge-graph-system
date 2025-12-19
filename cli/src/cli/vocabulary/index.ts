/**
 * Vocabulary Management Commands (ADR-032)
 * Consolidated entry point for all vocabulary subcommands
 */

import { Command } from 'commander';
import { setCommandHelp } from '../help-formatter';

// Import command factories from split modules
import { createStatusCommand, createListCommand } from './status';
import { createConsolidateCommand, createMergeCommand } from './consolidate';
import { createGenerateEmbeddingsCommand, createCategoryScoresCommand, createRefreshCategoriesCommand } from './embeddings';
import { createSimilarCommand, createOppositeCommand, createAnalyzeCommand } from './similarity';
import { createConfigCommand } from './config';
import { createProfilesCommand } from './profiles';
import { createEpistemicStatusCommand } from './epistemic';
import { createSyncCommand } from './sync';

export const vocabularyCommand = setCommandHelp(
  new Command('vocabulary'),
  'Vocabulary management and consolidation',
  'Edge vocabulary management and consolidation. Manages relationship types between concepts including builtin types (30 predefined), custom types (LLM-extracted from documents), categories (semantic groupings), consolidation (AI-assisted merging via AITL - ADR-032), and auto-categorization (probabilistic via embeddings - ADR-047). Features zone-based management (GREEN/WATCH/DANGER/EMERGENCY) and LLM-determined relationship direction (ADR-049).'
)
  .alias('vocab')
  .showHelpAfterError('(add --help for additional information)')
  .showSuggestionAfterError()
  // Core status and list
  .addCommand(createStatusCommand())
  .addCommand(createListCommand())
  // Consolidation workflow
  .addCommand(createConsolidateCommand())
  .addCommand(createMergeCommand())
  // Embeddings and categorization
  .addCommand(createGenerateEmbeddingsCommand())
  .addCommand(createCategoryScoresCommand())
  .addCommand(createRefreshCategoriesCommand())
  // Similarity analysis
  .addCommand(createSimilarCommand())
  .addCommand(createOppositeCommand())
  .addCommand(createAnalyzeCommand())
  // Configuration
  .addCommand(createConfigCommand())
  // Profiles (nested subcommand structure)
  .addCommand(createProfilesCommand())
  // Epistemic status (nested subcommand structure)
  .addCommand(createEpistemicStatusCommand())
  // Graph sync
  .addCommand(createSyncCommand());
