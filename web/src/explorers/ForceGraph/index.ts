/**
 * Force Graph — Plugin Definition
 *
 * The unified force-graph explorer. Backed by the r3f + GPU rendering
 * engine described in ADR-702. Projection (2D / 3D) is a user-facing
 * setting on the same plugin — the engine dispatches camera, drag plane,
 * and simulation axis count from `settings.projection`.
 *
 * Follows ADR-710 Explorer Plugin Interface.
 */

import { Network } from 'lucide-react';
import type { ExplorerPlugin } from '../../types/explorer';
import { ForceGraph } from './ForceGraph';
import { SettingsPanel } from './SettingsPanel';
import type { ForceGraphData, ForceGraphSettings } from './types';
import { DEFAULT_SETTINGS } from './types';
import { transformForEngine } from './dataTransformer';

export const ForceGraphExplorer: ExplorerPlugin<ForceGraphData, ForceGraphSettings> = {
  config: {
    id: 'force-graph',
    type: 'force-graph',
    name: 'Force Graph',
    description: 'Unified r3f + GPU engine — 2D or 3D projection toggleable in settings',
    icon: Network,
    requiredDataShape: 'graph',
  },
  component: ForceGraph,
  settingsPanel: SettingsPanel,
  dataTransformer: transformForEngine,
  defaultSettings: DEFAULT_SETTINGS,
};

import { registerExplorer } from '../registry';
registerExplorer(ForceGraphExplorer);
