/**
 * ForceGraph — Plugin Definitions
 *
 * Two plugin entries share the same component, transformer, and
 * settings panel; they differ only in `config` (id / name / icon) and
 * `defaultSettings.projection`. This is the transitional shape during
 * d3-2D coexistence: once `force-2d` (d3) retires, the `(V2)` suffix
 * drops and these two entries can consolidate into a single "Force
 * Graph" plugin with the projection toggle as the user-facing affordance.
 *
 * Follows ADR-034 Explorer Plugin Interface.
 * Built on the unified rendering engine per ADR-702 (r3f + instanced
 * GPU rendering + GPU-accelerated force simulation).
 */

import { Boxes, Map } from 'lucide-react';
import type { ExplorerPlugin, VisualizationType } from '../../types/explorer';
import type { ComponentType } from 'react';
import { ForceGraph3D } from './ForceGraph3D';
import { SettingsPanel } from './SettingsPanel';
import type { ForceGraph3DData, ForceGraph3DSettings, Projection } from './types';
import { DEFAULT_SETTINGS } from './types';
import { transformForEngine } from './dataTransformer';

function createForceGraphPlugin(
  type: VisualizationType,
  name: string,
  description: string,
  icon: ComponentType<{ className?: string }>,
  projection: Projection
): ExplorerPlugin<ForceGraph3DData, ForceGraph3DSettings> {
  return {
    config: { id: type, type, name, description, icon, requiredDataShape: 'graph' },
    component: ForceGraph3D,
    settingsPanel: SettingsPanel,
    dataTransformer: transformForEngine,
    defaultSettings: { ...DEFAULT_SETTINGS, projection },
  };
}

export const ForceGraph3DExplorer = createForceGraphPlugin(
  'force-3d',
  'Force-Directed 3D',
  'Unified r3f + GPU engine — 3D with instanced nodes and shader-driven edges',
  Boxes,
  '3D'
);

export const ForceGraph2DV2Explorer = createForceGraphPlugin(
  'force-2d-v2',
  'Force-Directed 2D (V2)',
  'Unified r3f + GPU engine — 2D projection on the same scene primitives',
  Map,
  '2D'
);

import { registerExplorer } from '../registry';
registerExplorer(ForceGraph3DExplorer);
registerExplorer(ForceGraph2DV2Explorer);
