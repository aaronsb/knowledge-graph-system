/**
 * Admin Search Config Command (ADR-508)
 * Get or set the server-side default similarity threshold that clients inherit
 * when they don't pass --min-similarity.
 */

import { Command } from 'commander';
import { createClientFromEnv } from '../../api/client';
import * as colors from '../colors';

export function createSearchThresholdCommand(): Command {
  return new Command('search-threshold')
    .description('Get or set the default search similarity threshold clients inherit (ADR-508)')
    .argument('[value]', 'New threshold 0.0-1.0; omit to show the current value')
    .action(async (value?: string) => {
      try {
        const client = createClientFromEnv();

        if (value === undefined) {
          const cfg = await client.getSearchThreshold();
          const shown = cfg.threshold ?? cfg.fallback;
          console.log(
            `${colors.ui.key('Default search threshold:')} ${colors.ui.value(String(shown))}` +
            (cfg.threshold === null ? colors.status.dim(`  (unset — using fallback ${cfg.fallback})`) : '')
          );
          return;
        }

        const t = parseFloat(value);
        if (Number.isNaN(t) || t < 0 || t > 1) {
          console.error(colors.status.error(`✗ Threshold must be a number in [0.0, 1.0], got "${value}"`));
          process.exit(1);
        }
        const res = await client.setSearchThreshold(t);
        console.log(colors.status.success(`✓ Default search threshold set to ${res.threshold}`));
      } catch (error: any) {
        console.error(colors.status.error('✗ Failed'));
        console.error(colors.status.error(error.response?.data?.detail || error.message));
        process.exit(1);
      }
    });
}
