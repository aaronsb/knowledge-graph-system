/**
 * Catalog Explorer Workspace (ADR-501)
 *
 * Route-mounted wrapper for the Catalog Explorer. Mirrors
 * DocumentExplorerWorkspace: holds the explorer's settings, provides a
 * settings rail, and renders the self-fetching explorer component. The tree
 * session state lives in catalogExplorerStore so it survives navigation.
 */

import React, { useState } from 'react';
import { Settings } from 'lucide-react';
import { IconRailPanel } from '../shared/IconRailPanel';
import { CatalogExplorer } from '../../explorers/CatalogExplorer/CatalogExplorer';
import { SettingsPanel } from '../../explorers/CatalogExplorer/SettingsPanel';
import { DEFAULT_SETTINGS } from '../../explorers/CatalogExplorer/types';
import type { CatalogExplorerSettings } from '../../explorers/CatalogExplorer/types';

export const CatalogExplorerWorkspace: React.FC = () => {
  const [settings, setSettings] = useState<CatalogExplorerSettings>(DEFAULT_SETTINGS);
  const [activeRailTab, setActiveRailTab] = useState('settings');

  return (
    <div className="flex h-full">
      <IconRailPanel
        tabs={[
          {
            id: 'settings',
            icon: Settings,
            label: 'Settings',
            content: <SettingsPanel settings={settings} onChange={setSettings} />,
          },
        ]}
        activeTab={activeRailTab}
        onTabChange={setActiveRailTab}
      />
      <div className="flex-1 min-w-0">
        <CatalogExplorer data={{}} settings={settings} onSettingsChange={setSettings} />
      </div>
    </div>
  );
};
