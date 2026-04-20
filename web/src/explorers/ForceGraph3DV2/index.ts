/**
 * ForceGraph3D V2 — Plugin Definition
 *
 * Follows ADR-034 Explorer Plugin Interface.
 * V2 is built on the unified rendering engine per ADR-702.
 */

import { Boxes } from 'lucide-react';
import type { ExplorerPlugin } from '../../types/explorer';
import { ForceGraph3DV2 } from './ForceGraph3DV2';
import { ProfilePanel } from './ProfilePanel';
import type { ForceGraph3DV2Data, ForceGraph3DV2Settings } from './types';
import { DEFAULT_SETTINGS } from './types';
import { transformForEngine } from './dataTransformer';

export const ForceGraph3DV2Explorer: ExplorerPlugin<
  ForceGraph3DV2Data,
  ForceGraph3DV2Settings
> = {
  config: {
    id: 'force-3d-v2',
    type: 'force-3d-v2',
    name: 'Force-Directed 3D (V2)',
    description: 'Unified r3f + GPU engine — 3D with instanced nodes and shader-driven edges',
    icon: Boxes,
    requiredDataShape: 'graph',
  },

  component: ForceGraph3DV2,
  settingsPanel: ProfilePanel,
  dataTransformer: transformForEngine,
  defaultSettings: DEFAULT_SETTINGS,
};

import { registerExplorer } from '../registry';
registerExplorer(ForceGraph3DV2Explorer);
