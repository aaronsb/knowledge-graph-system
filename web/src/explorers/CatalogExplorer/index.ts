/**
 * Catalog Explorer — Plugin Definition (ADR-501)
 *
 * Folder-style browse of the ontology -> document -> concept hierarchy.
 * Self-fetching like DocumentExplorer (its dataTransformer is a no-op), so it
 * mounts via its own workspace wrapper rather than ExplorerView's graph-data
 * pipeline. Registered for parity and future registry-driven listings.
 */

import { FolderTree } from 'lucide-react';
import type { ExplorerPlugin } from '../../types/explorer';
import { CatalogExplorer } from './CatalogExplorer';
import { SettingsPanel } from './SettingsPanel';
import type { CatalogExplorerData, CatalogExplorerSettings } from './types';
import { DEFAULT_SETTINGS } from './types';

export const CatalogExplorerPlugin: ExplorerPlugin<
  CatalogExplorerData,
  CatalogExplorerSettings
> = {
  config: {
    id: 'catalog',
    type: 'hierarchy',
    name: 'Catalog Explorer',
    description: 'Browse ontologies → documents → concepts',
    icon: FolderTree,
    requiredDataShape: 'tree',
  },
  component: CatalogExplorer,
  settingsPanel: SettingsPanel,
  // Self-fetching: data comes from /catalog on demand, not from rawGraphData.
  dataTransformer: () => ({}) as CatalogExplorerData,
  defaultSettings: DEFAULT_SETTINGS,
};

import { registerExplorer } from '../registry';
registerExplorer(CatalogExplorerPlugin);
