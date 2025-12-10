/**
 * Explorer Plugin Interface
 *
 * Defines the standard interface for all visualization explorers.
 * Each explorer implements this interface for consistent integration.
 */

import type { ComponentType } from 'react';

export type VisualizationType =
  | 'force-2d'
  | 'force-3d'
  | 'hierarchy'
  | 'sankey'
  | 'matrix'
  | 'timeline'
  | 'density';

export type DataShape = 'graph' | 'tree' | 'flow' | 'matrix' | 'temporal';

export interface ExplorerConfig {
  id: string;
  type: VisualizationType;
  name: string;
  description: string;
  icon: ComponentType<{ className?: string }>;
  requiredDataShape: DataShape;
}

export interface ExplorerProps<TData = any, TSettings = any> {
  data: TData;
  settings: TSettings;
  onSettingsChange?: (settings: TSettings) => void;
  onNodeClick?: (nodeId: string) => void;
  onSelectionChange?: (selection: string[]) => void;
  onSendToReports?: () => void;
  className?: string;
}

export interface SettingsPanelProps<TSettings = any> {
  settings: TSettings;
  onChange: (settings: TSettings) => void;
}

export interface ExplorerPlugin<TData = any, TSettings = any> {
  config: ExplorerConfig;
  component: ComponentType<ExplorerProps<TData, TSettings>>;
  settingsPanel: ComponentType<SettingsPanelProps<TSettings>>;
  dataTransformer: (apiData: any) => TData;
  defaultSettings: TSettings;
}
