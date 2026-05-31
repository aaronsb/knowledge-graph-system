/**
 * Vision Commands (ADR-802)
 * Manages the active vision (image->prose) provider selection — the reasoning
 * capability that backs multimodal image ingestion. Mirrors the extraction
 * command shape; vision is resolved independently (active vision config →
 * active extraction provider if vision-capable → fail loud).
 */

import { Command } from 'commander';
import { KnowledgeGraphClient } from '../../api/client';
import * as colors from '../colors';
import { separator } from '../colors';

/**
 * Show the effective vision configuration
 */
function createVisionConfigCommand(client: KnowledgeGraphClient): Command {
  return new Command('config')
    .description('Show the effective vision (image->prose) provider/model')
    .action(async () => {
      try {
        console.log('\n' + separator());
        console.log(colors.ui.title('👁  Vision Configuration'));
        console.log(separator());

        const detail = await client.getVisionConfigDetail();
        const eff = detail.effective || {};
        const row = detail.config;

        console.log(`\n  ${colors.ui.key('Effective Provider:')} ${eff.provider ? colors.ui.value(eff.provider) : colors.status.error('unresolved')}`);
        console.log(`  ${colors.ui.key('Effective Model:')} ${colors.ui.value(eff.model || '(catalog default)')}`);
        console.log(`  ${colors.ui.key('Source:')} ${colors.ui.value(eff.source)}`);

        if (eff.source === 'extraction_default') {
          console.log(`\n  ${colors.status.dim('No explicit vision provider set — inheriting the active extraction provider (it has a vision-capable model).')}`);
        } else if (eff.source === 'unresolved') {
          console.log(`\n  ${colors.status.warning('⚠️  No vision provider resolves. Set one with `kg admin vision set --provider <p>`, or ensure the active extraction provider has a supports_vision model.')}`);
        }

        if (row) {
          console.log(`\n  ${colors.ui.header('Active vision config row:')}`);
          console.log(`    ${colors.ui.key('Provider:')} ${colors.ui.value(row.provider)}`);
          console.log(`    ${colors.ui.key('Model:')} ${colors.ui.value(row.model_name || '(catalog)')}`);
          if (row.max_tokens != null) console.log(`    ${colors.ui.key('Max Tokens:')} ${colors.ui.value(row.max_tokens)}`);
          if (row.temperature != null) console.log(`    ${colors.ui.key('Temperature:')} ${colors.ui.value(row.temperature)}`);
        }

        console.log('\n' + separator() + '\n');
      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to get vision configuration'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

/**
 * List providers and their vision capability (catalog-driven)
 */
function createVisionProvidersCommand(client: KnowledgeGraphClient): Command {
  return new Command('providers')
    .description('List providers and whether they have a vision-capable catalog model')
    .action(async () => {
      try {
        console.log('\n' + separator());
        console.log(colors.ui.title('👁  Vision-Capable Providers'));
        console.log(separator() + '\n');

        const { providers } = await client.getVisionProviders();
        for (const p of providers) {
          const mark = p.supports_vision ? colors.status.success('✓') : colors.status.dim('✗');
          const models = p.vision_models.length ? colors.status.dim(`(${p.vision_models.join(', ')})`) : colors.status.dim('(no vision model in catalog)');
          console.log(`  ${mark} ${colors.ui.value(p.provider)} ${models}`);
        }
        console.log('\n' + colors.status.dim('  ✓ = can be activated for vision without an explicit model.'));
        console.log('\n' + separator() + '\n');
      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to list vision providers'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

/**
 * Set / activate the vision provider
 */
function createVisionSetCommand(client: KnowledgeGraphClient): Command {
  return new Command('set')
    .description('Set/activate the vision (image->prose) provider')
    .option('--provider <provider>', 'Provider: openai, anthropic, ollama, openrouter, llamacpp')
    .option('--model <model>', 'Vision model id (optional; resolved from the catalog when omitted)')
    .option('--max-tokens <n>', 'Max output tokens for image description', parseInt)
    .option('--temperature <n>', 'Sampling temperature 0.0-1.0', parseFloat)
    .option('--no-activate', 'Persist the provider config without making it the active vision provider')
    .action(async (options) => {
      try {
        console.log('\n' + separator());
        console.log(colors.ui.title('👁  Update Vision Configuration'));
        console.log(separator());

        if (!options.provider) {
          console.error(colors.status.error('\n✗ --provider is required'));
          console.log(colors.status.dim('  Example: kg admin vision set --provider anthropic\n'));
          process.exit(1);
        }

        const config: any = { provider: options.provider, active: options.activate !== false };
        if (options.model) config.model_name = options.model;
        if (options.maxTokens) config.max_tokens = options.maxTokens;
        if (options.temperature !== undefined) config.temperature = options.temperature;

        const result = await client.updateVisionConfig(config);
        const eff = result.effective || {};

        console.log('\n' + colors.status.success('✓ Vision configuration updated'));
        console.log(`\n  ${colors.ui.key('Effective Provider:')} ${colors.ui.value(eff.provider)}`);
        console.log(`  ${colors.ui.key('Effective Model:')} ${colors.ui.value(eff.model || '(catalog default)')}`);
        console.log('\n' + separator() + '\n');
      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to update vision configuration'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

/**
 * Vision command group
 */
export function createVisionCommand(client: KnowledgeGraphClient): Command {
  const visionCommand = new Command('vision')
    .description('Manage the vision (image->prose) provider (ADR-802)');

  visionCommand.addCommand(createVisionConfigCommand(client));
  visionCommand.addCommand(createVisionProvidersCommand(client));
  visionCommand.addCommand(createVisionSetCommand(client));

  return visionCommand;
}
