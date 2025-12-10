/**
 * Report Store - Zustand State Management
 *
 * Manages report state for tabular views of graph/polarity data.
 * Reports are sent from explorers (2D, 3D, Polarity) via "Send to Reports".
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// Report types
export type ReportType = 'graph' | 'polarity';

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

export type ReportData = GraphReportData | PolarityReportData;

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
  sourceExplorer: '2d' | '3d' | 'polarity';
  // Recalculation tracking
  lastCalculatedAt?: string;
  previousValues?: PreviousValues;
}

interface ReportStore {
  // Reports list
  reports: Report[];

  // Currently selected report
  selectedReportId: string | null;

  // Add a new report
  addReport: (report: Omit<Report, 'id' | 'createdAt'>) => string;

  // Delete a report
  deleteReport: (id: string) => void;

  // Select a report
  selectReport: (id: string | null) => void;

  // Rename a report
  renameReport: (id: string, name: string) => void;

  // Clear all reports
  clearReports: () => void;

  // Get selected report
  getSelectedReport: () => Report | null;

  // Update report data after recalculation (preserves previous values for delta)
  updateReportData: (id: string, newData: ReportData) => void;
}

// Generate unique ID
const generateId = () => `report_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

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
  } else {
    const polarityData = data as PolarityReportData;
    return `${polarityData.positivePole.label} ↔ ${polarityData.negativePole.label} - ${timestamp}`;
  }
};

export const useReportStore = create<ReportStore>()(
  persist(
    (set, get) => ({
      reports: [],
      selectedReportId: null,

      addReport: (reportInput) => {
        const id = generateId();
        const name = reportInput.name || generateDefaultName(reportInput.type, reportInput.data);
        const report: Report = {
          ...reportInput,
          id,
          name,
          createdAt: new Date().toISOString(),
        };

        set((state) => ({
          reports: [report, ...state.reports],
          selectedReportId: id,
        }));

        return id;
      },

      deleteReport: (id) => {
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

      renameReport: (id, name) => {
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

      updateReportData: (id, newData) => {
        set((state) => ({
          reports: state.reports.map((report) => {
            if (report.id !== id) return report;

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

            return {
              ...report,
              data: newData,
              previousValues,
              lastCalculatedAt: new Date().toISOString(),
            };
          }),
        }));
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
