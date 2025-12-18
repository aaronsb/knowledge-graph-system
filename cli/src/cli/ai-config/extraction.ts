/**
 * Extraction Commands (ADR-041)
 * Manages AI extraction model configuration
 */

import { Command } from 'commander';
import { KnowledgeGraphClient } from '../../api/client';
import * as colors from '../colors';
import { separator } from '../colors';

/**
 * Show current extraction configuration
 */
function createExtractionConfigCommand(client: KnowledgeGraphClient): Command {
  return new Command('config')
    .description('Show current AI extraction configuration')
    .action(async () => {
      try {
        console.log('\n' + separator());
        console.log(colors.ui.title('🤖 AI Extraction Configuration'));
        console.log(separator());

        const config = await client.getExtractionConfig();

        console.log(`\n  ${colors.ui.key('Provider:')} ${colors.ui.value(config.provider)}`);
        console.log(`  ${colors.ui.key('Model:')} ${colors.ui.value(config.model)}`);
        console.log(`  ${colors.ui.key('Vision Support:')} ${config.supports_vision ? colors.status.success('Yes') : colors.status.dim('No')}`);
        console.log(`  ${colors.ui.key('JSON Mode:')} ${config.supports_json_mode ? colors.status.success('Yes') : colors.status.dim('No')}`);
        console.log(`  ${colors.ui.key('Max Tokens:')} ${colors.ui.value(config.max_tokens)}`);

        // Show rate limiting configuration (ADR-049)
        if (config.max_concurrent_requests !== undefined || config.max_retries !== undefined) {
          console.log(`\n  ${colors.ui.header('Rate Limiting Configuration:')}`);
          if (config.max_concurrent_requests !== undefined) {
            console.log(`    ${colors.ui.key('Max Concurrent Requests:')} ${colors.ui.value(config.max_concurrent_requests)}`);
          }
          if (config.max_retries !== undefined) {
            console.log(`    ${colors.ui.key('Max Retries:')} ${colors.ui.value(config.max_retries)}`);
          }
        }

        // Show local provider configuration (ADR-042)
        if (config.provider === 'ollama' || config.provider === 'vllm') {
          console.log(`\n  ${colors.ui.header('Local Inference Configuration:')}`);
          if (config.base_url) {
            console.log(`    ${colors.ui.key('Base URL:')} ${colors.ui.value(config.base_url)}`);
          }
          if (config.temperature !== undefined) {
            console.log(`    ${colors.ui.key('Temperature:')} ${colors.ui.value(config.temperature)}`);
          }
          if (config.top_p !== undefined) {
            console.log(`    ${colors.ui.key('Top P:')} ${colors.ui.value(config.top_p)}`);
          }
          if (config.gpu_layers !== undefined) {
            console.log(`    ${colors.ui.key('GPU Layers:')} ${colors.ui.value(config.gpu_layers === -1 ? 'auto' : config.gpu_layers)}`);
          }
          if (config.num_threads !== undefined) {
            console.log(`    ${colors.ui.key('CPU Threads:')} ${colors.ui.value(config.num_threads)}`);
          }
          if (config.thinking_mode !== undefined) {
            console.log(`    ${colors.ui.key('Thinking Mode:')} ${colors.ui.value(config.thinking_mode)}`);
          }
        }

        console.log(`\n  ${colors.status.dim('Config ID: ' + config.config_id)}`);
        console.log('\n' + separator() + '\n');

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to get extraction configuration'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

/**
 * Update extraction configuration
 */
function createExtractionSetCommand(client: KnowledgeGraphClient): Command {
  return new Command('set')
    .description('Update AI extraction configuration')
    .option('--provider <provider>', 'Provider: openai, anthropic, ollama, or vllm')
    .option('--model <model>', 'Model name (e.g., gpt-4o, mistral:7b-instruct)')
    .option('--vision', 'Enable vision support')
    .option('--no-vision', 'Disable vision support')
    .option('--json-mode', 'Enable JSON mode')
    .option('--no-json-mode', 'Disable JSON mode')
    .option('--max-tokens <n>', 'Max tokens', parseInt)
    .option('--base-url <url>', 'Base URL for local providers (e.g., http://localhost:11434)')
    .option('--temperature <n>', 'Sampling temperature 0.0-1.0 (default: 0.1)', parseFloat)
    .option('--top-p <n>', 'Nucleus sampling threshold 0.0-1.0 (default: 0.9)', parseFloat)
    .option('--gpu-layers <n>', 'GPU layers: -1=auto, 0=CPU only, >0=specific count', parseInt)
    .option('--num-threads <n>', 'CPU threads for inference (default: 4)', parseInt)
    .option('--thinking-mode <mode>', 'Thinking mode: off, low, medium, high (Ollama 0.12.x+)')
    .action(async (options) => {
      try {
        console.log('\n' + separator());
        console.log(colors.ui.title('🤖 Update AI Extraction Configuration'));
        console.log(separator());

        const config: any = {};

        // Common options
        if (options.provider) config.provider = options.provider;
        if (options.model) config.model_name = options.model;
        if (options.vision !== undefined) config.supports_vision = options.vision;
        if (options.jsonMode !== undefined) config.supports_json_mode = options.jsonMode;
        if (options.maxTokens) config.max_tokens = options.maxTokens;

        // Local provider options (ADR-042)
        if (options.baseUrl) config.base_url = options.baseUrl;
        if (options.temperature !== undefined) config.temperature = options.temperature;
        if (options.topP !== undefined) config.top_p = options.topP;
        if (options.gpuLayers !== undefined) config.gpu_layers = options.gpuLayers;
        if (options.numThreads !== undefined) config.num_threads = options.numThreads;
        if (options.thinkingMode) {
          // Validate thinking mode
          const validModes = ['off', 'low', 'medium', 'high'];
          if (!validModes.includes(options.thinkingMode)) {
            console.error(colors.status.error(`\n✗ Invalid thinking mode: ${options.thinkingMode}`));
            console.log(colors.status.dim('  Valid options: off, low, medium, high\n'));
            process.exit(1);
          }
          config.thinking_mode = options.thinkingMode;
        }

        if (Object.keys(config).length === 0) {
          console.error(colors.status.error('\n✗ No configuration options provided'));
          console.log(colors.status.dim('  Use --help to see available options\n'));
          process.exit(1);
        }

        // Validate provider-specific requirements
        if (config.provider === 'ollama' || config.provider === 'vllm') {
          if (!config.model_name && !options.model) {
            console.error(colors.status.error('\n✗ Model name required for local providers'));
            console.log(colors.status.dim('  Example: --model mistral:7b-instruct\n'));
            process.exit(1);
          }
        }

        const result = await client.updateExtractionConfig(config);

        console.log('\n' + colors.status.success('✓ Configuration updated successfully'));
        console.log(`\n  ${colors.ui.key('Config ID:')} ${colors.ui.value(result.config_id)}`);

        // Show helpful next steps for Ollama
        if (config.provider === 'ollama') {
          console.log(`\n  ${colors.ui.header('Next Steps:')}`);
          console.log(`    1. Ensure Ollama is running: ${colors.status.dim('./scripts/start-ollama.sh -y')}`);
          console.log(`    2. Pull model: ${colors.status.dim(`docker exec kg-ollama ollama pull ${config.model_name || '<model>'}`)}`);
          console.log(`    3. Test extraction: ${colors.status.dim('kg admin extraction test')}`);
        }

        if (result.reload_required) {
          console.log(`\n  ${colors.status.warning('⚠️  API restart required to apply changes')}`);
          console.log(`  ${colors.status.dim('Run: ./scripts/stop-api.sh && ./scripts/start-api.sh')}`);
        }

        console.log('\n' + separator() + '\n');

      } catch (error: any) {
        console.error(colors.status.error('✗ Failed to update extraction configuration'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}

/**
 * Extraction command group
 */
export function createExtractionCommand(client: KnowledgeGraphClient): Command {
  const extractionCommand = new Command('extraction')
    .description('Manage AI extraction model configuration (ADR-041)');

  extractionCommand.addCommand(createExtractionConfigCommand(client));
  extractionCommand.addCommand(createExtractionSetCommand(client));

  return extractionCommand;
}
