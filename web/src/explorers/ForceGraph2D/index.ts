/**
 * Force-Directed 2D Graph Explorer - Plugin Definition
 *
 * Follows ADR-034 Explorer Plugin Interface.
 * This is the Phase 1 MVP explorer.
 */

import { Network } from 'lucide-react';
import type { ExplorerPlugin } from '../../types/explorer';
import { ForceGraph2D } from './ForceGraph2D';
import { ProfilePanel } from './ProfilePanel';
import type { ForceGraph2DSettings, ForceGraph2DData } from './types';
import { DEFAULT_SETTINGS } from './types';
import { transformForD3 } from '../../utils/graphTransform';

/**
 * Force-Directed 2D Graph Explorer Plugin
 *
 * Interactive 2D force-directed graph visualization with physics simulation.
 * Best for exploring conceptual neighborhoods and relationship patterns.
 */
export const ForceGraph2DExplorer: ExplorerPlugin<ForceGraph2DData, ForceGraph2DSettings> = {
  config: {
    id: 'force-2d',
    type: 'force-2d',
    name: 'Force-Directed 2D',
    description: 'Explore conceptual neighborhoods with physics-based layout',
    icon: Network,
    requiredDataShape: 'graph',
  },

  component: ForceGraph2D,
  settingsPanel: ProfilePanel,

  dataTransformer: (apiData) => {
    // Always transform raw API data to ensure proper field names (concept_id → id, from_id → source, etc.)
    return transformForD3(apiData.nodes || [], apiData.links || []);
  },

  defaultSettings: DEFAULT_SETTINGS,
};

// Auto-register this explorer
import { registerExplorer } from '../registry';
registerExplorer(ForceGraph2DExplorer);
