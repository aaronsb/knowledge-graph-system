/**
 * Profile Panel (Placeholder)
 *
 * Satisfies the explorer plugin interface requirement for a settings panel.
 * Canvas settings are handled by CanvasSettingsPanel (on-graph UI).
 * This panel is reserved for future user profile settings.
 */

import React from 'react';
import type { SettingsPanelProps } from '../../types/explorer';
import type { ForceGraph2DSettings } from './types';

export const ProfilePanel: React.FC<SettingsPanelProps<ForceGraph2DSettings>> = () => {
  return (
    <div className="space-y-6 p-4">
      <section>
        <h3 className="text-lg font-semibold mb-3">Profile</h3>
        <p className="text-sm text-muted-foreground">
          User profile and preferences coming soon.
        </p>
        <p className="text-xs text-muted-foreground mt-2">
          Graph visualization settings are available in the settings panel on the canvas
          (upper right corner).
        </p>
      </section>
    </div>
  );
};
