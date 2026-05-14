/**
 * ForceGraph3D — Plugin Definition
 *
 * Follows ADR-034 Explorer Plugin Interface.
 * Built on the unified rendering engine per ADR-702 (r3f + instanced GPU
 * rendering + GPU-accelerated force simulation).
 */

import { Boxes } from 'lucide-react';
import type { ExplorerPlugin } from '../../types/explorer';
import { ForceGraph3D } from './ForceGraph3D';
import { SettingsPanel } from './SettingsPanel';
import type { ForceGraph3DData, ForceGraph3DSettings } from './types';
import { DEFAULT_SETTINGS } from './types';
import { transformForEngine } from './dataTransformer';

export const ForceGraph3DExplorer: ExplorerPlugin<
  ForceGraph3DData,
  ForceGraph3DSettings
> = {
  config: {
    id: 'force-3d',
    type: 'force-3d',
    name: 'Force-Directed 3D',
    description: 'Unified r3f + GPU engine — 3D with instanced nodes and shader-driven edges',
    icon: Boxes,
    requiredDataShape: 'graph',
  },

  component: ForceGraph3D,
  settingsPanel: SettingsPanel,
  dataTransformer: transformForEngine,
  defaultSettings: DEFAULT_SETTINGS,
};

import { registerExplorer } from '../registry';
registerExplorer(ForceGraph3DExplorer);
