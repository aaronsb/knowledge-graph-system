/**
 * Force-Directed 3D Graph Explorer - Plugin Definition
 *
 * Follows ADR-034 Explorer Plugin Interface.
 * 3D WebGL visualization using react-force-graph-3d.
 */

import { Box } from 'lucide-react';
import type { ExplorerPlugin } from '../../types/explorer';
import { ForceGraph3D } from './ForceGraph3D';
import { ProfilePanel } from './ProfilePanel';
import type { ForceGraph3DSettings, ForceGraph3DData } from './types';
import { DEFAULT_SETTINGS } from './types';
import { transformForD3 } from '../../utils/graphTransform';

/**
 * Force-Directed 3D Graph Explorer Plugin
 *
 * Interactive 3D force-directed graph visualization with WebGL rendering.
 * Best for exploring spatial relationships and large conceptual networks.
 */
export const ForceGraph3DExplorer: ExplorerPlugin<ForceGraph3DData, ForceGraph3DSettings> = {
  config: {
    id: 'force-3d',
    type: 'force-3d',
    name: 'Force-Directed 3D',
    description: 'Explore conceptual neighborhoods in 3D space with WebGL',
    icon: Box,
    requiredDataShape: 'graph',
  },

  component: ForceGraph3D,
  settingsPanel: ProfilePanel,

  dataTransformer: (apiData) => {
    // Always transform to ensure node.size and node.color are calculated
    return transformForD3(apiData.nodes || [], apiData.links || []);
  },

  defaultSettings: DEFAULT_SETTINGS,
};

// Auto-register this explorer
import { registerExplorer } from '../registry';
registerExplorer(ForceGraph3DExplorer);
