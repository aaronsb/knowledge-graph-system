/**
 * Catalog Explorer Settings Panel (ADR-501)
 *
 * Minimal controls: child-count badges toggle and sort order. Follows the
 * SettingsPanelProps contract used by the other explorer plugins.
 */

import React from 'react';
import type { SettingsPanelProps } from '../../types/explorer';
import type { CatalogExplorerSettings } from './types';

export const SettingsPanel: React.FC<SettingsPanelProps<CatalogExplorerSettings>> = ({
  settings,
  onChange,
}) => {
  return (
    <div className="p-3 space-y-3 text-sm">
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={settings.showCounts}
          onChange={(e) => onChange({ ...settings, showCounts: e.target.checked })}
        />
        Show child counts
      </label>

      <div className="space-y-1">
        <label className="block text-muted-foreground">Sort children by</label>
        <select
          value={settings.sort}
          onChange={(e) =>
            onChange({ ...settings, sort: e.target.value as CatalogExplorerSettings['sort'] })
          }
          className="w-full bg-background border border-border rounded px-2 py-1"
        >
          <option value="name">Name</option>
          <option value="child_count">Child count</option>
          <option value="created">Created</option>
        </select>
      </div>
    </div>
  );
};
