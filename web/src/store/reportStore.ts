/**
 * Report Store - Zustand State Management (ADR-083)
 *
 * Manages report state for tabular views of graph/polarity data.
 * Reports are sent from explorers (2D, 3D, Polarity) via "Send to Reports".
 * Uses artifacts API for persistence with localStorage as cache/fallback.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { apiClient } from '../api/client';
import type { Representation } from '../types/artifacts';

// Report types
export type ReportType = 'graph' | 'polarity' | 'document' | 'traversal';

// Graph report data (from 2D/3D explorers)
export interface GraphReportData {
  type: 'graph';
  nodes: Array<{
    id: string;
    label: string;
    description?: string;
    ontology?: string;
    grounding_strength?: number;
    diversity_score?: number;
    evidence_count?: number;
  }>;
  links: Array<{
    source: string;
    target: string;
    type: string;
    grounding_strength?: number;
    category?: string;
    epistemic_status?: string;
  }>;
  searchParams?: {
    mode: string;
    query?: string;
    conceptId?: string;
    depth?: number;
  };
}

// Polarity report data (from Polarity Explorer)
export interface PolarityReportData {
  type: 'polarity';
  positivePole: { concept_id: string; label: string };
  negativePole: { concept_id: string; label: string };
  axisMagnitude: number;
  concepts: Array<{
    concept_id: string;
    label: string;
    position: number; // -1 to +1
    positive_similarity: number;
    negative_similarity: number;
    grounding_strength?: number;
  }>;
  directionDistribution: {
    positive: number;
    neutral: number;
    negative: number;
  };
  groundingCorrelation?: number;
}

// Document report data (from Document Explorer or direct query)
export interface DocumentReportData {
  type: 'document';
  documents: Array<{
    document_id: string;
    filename: string;
    ontology: string;
    content_type: string;
    best_similarity?: number;
    source_count: number;
    concept_count: number;
  }>;
  searchParams?: {
    query?: string;
    min_similarity?: number;
    ontologies?: string[];
  };
}

// Traversal report data (path between origin and destination)
export interface TraversalReportData {
  type: 'traversal';
  origin: { concept_id: string; label: string };
  destination: { concept_id: string; label: string };
  maxHops: number;
  pathCount: number;
  paths: Array<{
    hops: number;
    nodes: Array<{
      id: string;
      label: string;
      description?: string;
      grounding_strength?: number;
      confidence_level?: string;
      diversity_score?: number;
    }>;
    relationships: string[];
  }>;
}

export type ReportData = GraphReportData | PolarityReportData | DocumentReportData | TraversalReportData;

// Previous values for delta comparison (keyed by concept_id)
export interface PreviousValues {
  [conceptId: string]: {
    grounding_strength?: number;
    diversity_score?: number;
    evidence_count?: number;
    position?: number; // For polarity reports
  };
}

export interface Report {
  id: string;
  name: string;
  type: ReportType;
  data: ReportData;
  createdAt: string;
  sourceExplorer: '2d' | '3d' | 'polarity' | 'document' | 'traversal';
  // Recalculation tracking
  lastCalculatedAt?: string;
  previousValues?: PreviousValues;
  // API-specific fields (ADR-083)
  artifactId?: number;
  isSynced?: boolean;
  isFresh?: boolean;
}

interface ReportStore {
  // Reports list
  reports: Report[];

  // Currently selected report
  selectedReportId: string | null;

  // Loading state
  isLoading: boolean;
  error: string | null;

  // Add a new report (async - persists to API)
  addReport: (report: Omit<Report, 'id' | 'createdAt'>) => Promise<string>;

  // Delete a report (async)
  deleteReport: (id: string) => Promise<void>;

  // Select a report
  selectReport: (id: string | null) => void;

  // Rename a report (async)
  renameReport: (id: string, name: string) => Promise<void>;

  // Clear all reports
  clearReports: () => void;

  // Get selected report
  getSelectedReport: () => Report | null;

  // Update report data after recalculation (preserves previous values for delta)
  updateReportData: (id: string, newData: ReportData) => Promise<void>;

  // Load reports from API
  loadReports: () => Promise<void>;

  // Migrate localStorage reports to API
  migrateFromLocalStorage: () => Promise<number>;
}

// Generate unique ID (for local-only reports)
const generateLocalId = () => `local-report_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

// Generate default name based on report type and data
const generateDefaultName = (type: ReportType, data: ReportData): string => {
  const timestamp = new Date().toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  if (type === 'graph') {
    const graphData = data as GraphReportData;
    const nodeCount = graphData.nodes.length;
    const mode = graphData.searchParams?.mode || 'graph';
    return `${mode} (${nodeCount} nodes) - ${timestamp}`;
  } else if (type === 'polarity') {
    const polarityData = data as PolarityReportData;
    return `${polarityData.positivePole.label} ↔ ${polarityData.negativePole.label} - ${timestamp}`;
  } else if (type === 'traversal') {
    const travData = data as TraversalReportData;
    return `${travData.origin.label} → ${travData.destination.label} - ${timestamp}`;
  } else {
    const docData = data as DocumentReportData;
    const docCount = docData.documents.length;
    const query = docData.searchParams?.query || 'all';
    return `docs: "${query}" (${docCount}) - ${timestamp}`;
  }
};

// Get concept IDs from report data
const getConceptIds = (data: ReportData): string[] => {
  if (data.type === 'graph') {
    return (data as GraphReportData).nodes.map(n => n.id);
  } else if (data.type === 'polarity') {
    return (data as PolarityReportData).concepts.map(c => c.concept_id);
  } else if (data.type === 'traversal') {
    const travData = data as TraversalReportData;
    const ids = new Set<string>();
    travData.paths.forEach(p => p.nodes.forEach(n => ids.add(n.id)));
    return Array.from(ids);
  } else {
    // Document reports don't have concept IDs at the report level
    return [];
  }
};

// Map source explorer to representation
const getRepresentation = (source: '2d' | '3d' | 'polarity' | 'document' | 'traversal'): Representation => {
  switch (source) {
    case '2d': return 'force_graph_2d';
    case '3d': return 'force_graph_3d';
    case 'polarity': return 'polarity_explorer';
    case 'document': return 'document_explorer';
    default: return 'report_workspace';
  }
};

export const useReportStore = create<ReportStore>()(
  persist(
    (set, get) => ({
      reports: [],
      selectedReportId: null,
      isLoading: false,
      error: null,

      addReport: async (reportInput) => {
        const localId = generateLocalId();
        const name = reportInput.name || generateDefaultName(reportInput.type, reportInput.data);
        const createdAt = new Date().toISOString();

        // Create local report first
        const report: Report = {
          ...reportInput,
          id: localId,
          name,
          createdAt,
          isSynced: false,
        };

        // Add to local state immediately
        set((state) => ({
          reports: [report, ...state.reports],
          selectedReportId: localId,
        }));

        // Try to persist to API
        try {
          const artifact = await apiClient.createArtifact({
            artifact_type: 'report',
            representation: getRepresentation(reportInput.sourceExplorer),
            name,
            parameters: {
              reportType: reportInput.type,
              sourceExplorer: reportInput.sourceExplorer,
            },
            payload: reportInput.data as unknown as Record<string, unknown>,
            concept_ids: getConceptIds(reportInput.data),
          });

          // Update local report with artifact ID
          const apiId = `api-${artifact.id}`;
          set((state) => ({
            reports: state.reports.map(r =>
              r.id === localId
                ? { ...r, id: apiId, artifactId: artifact.id, isSynced: true, isFresh: true }
                : r
            ),
            selectedReportId: apiId,
          }));

          return apiId;
        } catch (err) {
          console.warn('Failed to save report to API, using local storage:', err);
          return localId;
        }
      },

      deleteReport: async (id) => {
        const report = get().reports.find(r => r.id === id);

        // Delete from API if synced
        if (report?.artifactId) {
          try {
            await apiClient.deleteArtifact(report.artifactId);
          } catch (err) {
            console.error('Failed to delete from API:', err);
          }
        }

        set((state) => {
          const newReports = state.reports.filter((r) => r.id !== id);
          return {
            reports: newReports,
            selectedReportId: state.selectedReportId === id
              ? (newReports[0]?.id || null)
              : state.selectedReportId,
          };
        });
      },

      selectReport: (id) => {
        set({ selectedReportId: id });
      },

      renameReport: async (id, name) => {
        // Note: Artifacts don't have a rename endpoint, so we just update locally
        // The name is stored in artifact metadata, would need artifact update
        set((state) => ({
          reports: state.reports.map((r) =>
            r.id === id ? { ...r, name } : r
          ),
        }));
      },

      clearReports: () => {
        set({ reports: [], selectedReportId: null });
      },

      getSelectedReport: () => {
        const state = get();
        return state.reports.find((r) => r.id === state.selectedReportId) || null;
      },

      updateReportData: async (id, newData) => {
        const report = get().reports.find(r => r.id === id);
        if (!report) return;

        // Extract current values to store as previous
        const previousValues: PreviousValues = {};

        if (report.data.type === 'graph') {
          const graphData = report.data as GraphReportData;
          graphData.nodes.forEach((node) => {
            previousValues[node.id] = {
              grounding_strength: node.grounding_strength,
              diversity_score: node.diversity_score,
              evidence_count: node.evidence_count,
            };
          });
        } else if (report.data.type === 'polarity') {
          const polarityData = report.data as PolarityReportData;
          polarityData.concepts.forEach((concept) => {
            previousValues[concept.concept_id] = {
              grounding_strength: concept.grounding_strength,
              position: concept.position,
            };
          });
        }

        // Update local state
        set((state) => ({
          reports: state.reports.map((r) =>
            r.id === id
              ? {
                  ...r,
                  data: newData,
                  previousValues,
                  lastCalculatedAt: new Date().toISOString(),
                }
              : r
          ),
        }));

        // If synced to API, create new artifact version
        // Note: We could use artifact regeneration here in the future
      },

      loadReports: async () => {
        set({ isLoading: true, error: null });

        try {
          const response = await apiClient.listArtifacts({
            artifact_type: 'report',
            limit: 100,
          });

          const apiReports: Report[] = [];

          for (const artifact of response.artifacts) {
            // Load payload for each report
            try {
              const full = await apiClient.getArtifactPayload(artifact.id);
              const data = full.payload as unknown as ReportData;
              const params = artifact.parameters as { reportType?: string; sourceExplorer?: string };

              apiReports.push({
                id: `api-${artifact.id}`,
                name: artifact.name || 'Unnamed Report',
                type: (params.reportType as ReportType) || (data.type as ReportType) || 'graph',
                data,
                createdAt: artifact.created_at,
                sourceExplorer: (params.sourceExplorer as Report['sourceExplorer']) || '2d',
                artifactId: artifact.id,
                isSynced: true,
                isFresh: artifact.is_fresh,
              });
            } catch (err) {
              console.error(`Failed to load report ${artifact.id}:`, err);
            }
          }

          // Merge with local-only reports
          const localReports = get().reports.filter(r => !r.artifactId);

          // Sort by createdAt (most recent first)
          const allReports = [...apiReports, ...localReports].sort(
            (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
          );

          set({
            reports: allReports,
            isLoading: false,
          });
        } catch (err) {
          console.warn('Failed to load reports from API:', err);
          set({ isLoading: false });
        }
      },

      migrateFromLocalStorage: async () => {
        const localReports = get().reports.filter(r => !r.artifactId);
        let migrated = 0;

        for (const report of localReports) {
          try {
            const artifact = await apiClient.createArtifact({
              artifact_type: 'report',
              representation: getRepresentation(report.sourceExplorer),
              name: report.name,
              parameters: {
                reportType: report.type,
                sourceExplorer: report.sourceExplorer,
              },
              payload: report.data as unknown as Record<string, unknown>,
              concept_ids: getConceptIds(report.data),
            });

            // Update local report with artifact ID
            set((state) => ({
              reports: state.reports.map(r =>
                r.id === report.id
                  ? { ...r, id: `api-${artifact.id}`, artifactId: artifact.id, isSynced: true, isFresh: true }
                  : r
              ),
            }));

            migrated++;
          } catch (err) {
            console.error(`Failed to migrate report ${report.id}:`, err);
          }
        }

        return migrated;
      },
    }),
    {
      name: 'kg-reports-storage',
      partialize: (state) => ({
        reports: state.reports,
        selectedReportId: state.selectedReportId,
      }),
    }
  )
);
