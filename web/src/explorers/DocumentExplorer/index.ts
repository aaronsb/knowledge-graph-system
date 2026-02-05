/**
 * Document Explorer - Plugin Definition
 *
 * Force-directed concept cloud for single-document exploration (ADR-085).
 */

import { FileText } from 'lucide-react';
import type { ExplorerPlugin } from '../../types/explorer';
import { DocumentExplorer } from './DocumentExplorer';
import { ProfilePanel } from './ProfilePanel';
import type { DocumentExplorerSettings, DocumentExplorerData } from './types';
import { DEFAULT_SETTINGS } from './types';

/** Document Explorer Plugin — concept cloud for a single document. */
export const DocumentExplorerPlugin: ExplorerPlugin<DocumentExplorerData, DocumentExplorerSettings> = {
  config: {
    id: 'document',
    type: 'document',
    name: 'Document Explorer',
    description: 'Concept cloud for a single document',
    icon: FileText,
    requiredDataShape: 'graph',
  },

  component: DocumentExplorer,
  settingsPanel: ProfilePanel,

  dataTransformer: (apiData) => {
    // Note: This transformer is not called from ExplorerView (DocumentExplorerWorkspace
    // builds its own data). It exists for plugin interface completeness.
    const data = apiData as unknown as Record<string, any>;
    return {
      document: data.document || {
        id: 'unknown',
        label: 'Unknown Document',
        ontology: 'unknown',
      },
      concepts: (data.concepts || []).map((c: any) => ({
        id: c.concept_id || c.id,
        label: c.label || c.name || 'Unknown',
      })),
      links: (data.links || []).map((l: any) => ({
        source: l.source || l.from_id,
        target: l.target || l.to_id,
        type: l.type || l.relationship_type || 'RELATED',
      })),
      queryConceptIds: [],
    };
  },

  defaultSettings: DEFAULT_SETTINGS,
};

// Auto-register this explorer
import { registerExplorer } from '../registry';
registerExplorer(DocumentExplorerPlugin);
