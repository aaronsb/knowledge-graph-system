/**
 * Document Explorer - Plugin Definition
 *
 * Multi-document concept graph driven by saved exploration queries.
 */

import { FileText } from 'lucide-react';
import type { ExplorerPlugin } from '../../types/explorer';
import { DocumentExplorer } from './DocumentExplorer';
import { ProfilePanel } from './ProfilePanel';
import type { DocumentExplorerSettings, DocumentExplorerData } from './types';
import { DEFAULT_SETTINGS } from './types';

/** Document Explorer Plugin — multi-document concept graph. */
export const DocumentExplorerPlugin: ExplorerPlugin<DocumentExplorerData, DocumentExplorerSettings> = {
  config: {
    id: 'document',
    type: 'document',
    name: 'Document Explorer',
    description: 'Multi-document concept graph from saved queries',
    icon: FileText,
    requiredDataShape: 'graph',
  },

  component: DocumentExplorer,
  settingsPanel: ProfilePanel,

  dataTransformer: (apiData) => {
    // Not called — DocumentExplorerWorkspace builds its own data.
    const data = apiData as unknown as Record<string, any>;
    return {
      documents: [],
      nodes: (data.nodes || []).map((n: any) => ({
        id: n.concept_id || n.id,
        label: n.label || 'Unknown',
        type: 'query-concept' as const,
        documentIds: [],
        size: 6,
      })),
      links: (data.links || []).map((l: any) => ({
        source: l.source || l.from_id,
        target: l.target || l.to_id,
        type: l.type || l.relationship_type || 'RELATED',
        visible: true,
      })),
      queryConceptIds: [],
    };
  },

  defaultSettings: DEFAULT_SETTINGS,
};

// Auto-register this explorer
import { registerExplorer } from '../registry';
registerExplorer(DocumentExplorerPlugin);
