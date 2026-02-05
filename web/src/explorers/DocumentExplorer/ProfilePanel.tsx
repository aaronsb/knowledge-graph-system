/**
 * Document Explorer Profile Panel (Placeholder)
 *
 * Satisfies the explorer plugin interface requirement for a settings panel.
 * Visual settings are available on the canvas UI.
 */

import React from 'react';
import type { SettingsPanelProps } from '../../types/explorer';
import type { DocumentExplorerSettings } from './types';

export const ProfilePanel: React.FC<SettingsPanelProps<DocumentExplorerSettings>> = () => {
  return (
    <div className="space-y-6 p-4">
      <section>
        <h3 className="text-lg font-semibold mb-3">Document Explorer</h3>
        <p className="text-sm text-muted-foreground">
          Multi-document concept graph driven by saved queries.
        </p>
        <p className="text-xs text-muted-foreground mt-2">
          Load a saved exploration query to see all related documents
          and their concepts as a force-directed graph.
          Click a document to focus on its concept neighborhood.
        </p>
      </section>
    </div>
  );
};
