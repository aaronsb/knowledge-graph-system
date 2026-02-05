/**
 * Document Explorer - Plugin Definition
 *
 * Radial visualization of document→concept relationships (ADR-085).
 * Uses spreading activation decay for opacity visualization.
 */

import { FileText } from 'lucide-react';
import type { ExplorerPlugin } from '../../types/explorer';
import { DocumentExplorer } from './DocumentExplorer';
import { ProfilePanel } from './ProfilePanel';
import type { DocumentExplorerSettings, DocumentExplorerData } from './types';
import { DEFAULT_SETTINGS } from './types';

/**
 * Document Explorer Plugin
 *
 * Radial visualization with document at center, concepts in orbital rings.
 * Intensity (opacity) decreases with hop distance following spreading activation decay.
 */
export const DocumentExplorerPlugin: ExplorerPlugin<DocumentExplorerData, DocumentExplorerSettings> = {
  config: {
    id: 'document',
    type: 'document',
    name: 'Document Explorer',
    description: 'Radial view of document→concept relationships with decay',
    icon: FileText,
    requiredDataShape: 'graph',
  },

  component: DocumentExplorer,
  settingsPanel: ProfilePanel,

  dataTransformer: (apiData) => {
    // Transform API response to DocumentExplorerData
    // Note: This transformer is not called from ExplorerView (DocumentExplorerWorkspace
    // builds its own data). It exists for plugin interface completeness.
    const data = apiData as unknown as Record<string, any>;
    return {
      document: data.document || {
        id: 'unknown',
        type: 'document',
        label: 'Unknown Document',
        ontology: 'unknown',
        conceptCount: 0,
      },
      concepts: (data.concepts || []).map((c: any, i: number) => ({
        id: c.concept_id || c.id,
        type: 'concept' as const,
        label: c.label || c.name || 'Unknown',
        ontology: c.ontology || 'unknown',
        hop: c.hop ?? 0,
        grounding_strength: c.grounding_strength ?? 0.5,
        grounding_display: c.grounding_display,
        instanceCount: c.instance_count || c.instanceCount || 1,
      })),
      links: (data.links || []).map((l: any) => ({
        source: l.source || l.from_id,
        target: l.target || l.to_id,
        type: l.type || l.relationship_type || 'RELATED',
        confidence: l.confidence,
      })),
    };
  },

  defaultSettings: DEFAULT_SETTINGS,
};

// Auto-register this explorer
import { registerExplorer } from '../registry';
registerExplorer(DocumentExplorerPlugin);
