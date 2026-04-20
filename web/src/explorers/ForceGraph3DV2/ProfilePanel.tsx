/**
 * Profile Panel (placeholder, mirroring V1)
 *
 * Satisfies the ExplorerPlugin interface. Real settings UI for V2 lives
 * in the on-canvas settings panel (see M5 task #19).
 */

import React from 'react';
import type { SettingsPanelProps } from '../../types/explorer';
import type { ForceGraph3DV2Settings } from './types';

export const ProfilePanel: React.FC<SettingsPanelProps<ForceGraph3DV2Settings>> = () => {
  return (
    <div className="space-y-6 p-4">
      <section>
        <h3 className="text-lg font-semibold mb-3">Profile</h3>
        <p className="text-sm text-muted-foreground">
          V2 is built on the unified rendering engine (ADR-702).
        </p>
        <p className="text-xs text-muted-foreground mt-2">
          Graph controls are available in the settings panel on the canvas.
        </p>
      </section>
    </div>
  );
};
