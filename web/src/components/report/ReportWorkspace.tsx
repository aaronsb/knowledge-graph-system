/**
 * Report Workspace
 *
 * Tabular views of graph/polarity data sent from explorers.
 * Uses IconRailPanel for saved reports list navigation.
 */

import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronUp, ChevronDown } from 'lucide-react';
import {
  FileText,
  FolderOpen,
  Trash2,
  Clock,
  Copy,
  Download,
  Table2,
  GitBranch,
  Compass,
  Settings2,
  CheckCircle2,
  RefreshCw,
  Loader2,
  Search,
  FileSearch,
  Save,
  Eye,
  X,
  Route,
  Pencil,
} from 'lucide-react';
import * as d3 from 'd3';
import { IconRailPanel } from '../shared/IconRailPanel';
import { DocumentViewer } from '../shared/DocumentViewer';
import { apiClient } from '../../api/client';
import { getCategoryColor } from '../../config/categoryColors';
import {
  useReportStore,
  type Report,
  type GraphReportData,
  type PolarityReportData,
  type DocumentReportData,
  type TraversalReportData,
  type PreviousValues,
} from '../../store/reportStore';

// Generate ontology color using same d3.interpolateTurbo scale as explorers
const getOntologyColor = (ontology: string, allOntologies: string[]): string => {
  const sortedOntologies = [...allOntologies].sort();
  const index = sortedOntologies.indexOf(ontology);
  if (index === -1) return '#6b7280';
  const t = sortedOntologies.length === 1 ? 0.5 : 0.1 + (index / (sortedOntologies.length - 1)) * 0.8;
  return d3.interpolateTurbo(t);
};

// Format utilities
const formatDate = (dateString: string) => {
  const date = new Date(dateString);
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

// Sort types for tables
type SortField = string;
type SortDirection = 'asc' | 'desc' | null;

interface SortState {
  field: SortField | null;
  direction: SortDirection;
}

// Sortable column header component
const SortableHeader: React.FC<{
  field: string;
  label: string;
  sortState: SortState;
  onSort: (field: string) => void;
  align?: 'left' | 'right' | 'center';
}> = ({ field, label, sortState, onSort, align = 'left' }) => {
  const isActive = sortState.field === field;
  const alignClass = align === 'right' ? 'justify-end' : align === 'center' ? 'justify-center' : 'justify-start';

  return (
    <th
      className={`px-3 py-2 font-medium cursor-pointer hover:bg-muted/70 select-none text-${align}`}
      onClick={() => onSort(field)}
    >
      <div className={`flex items-center gap-1 ${alignClass}`}>
        <span>{label}</span>
        <span className="w-3">
          {isActive && sortState.direction === 'asc' && <ChevronUp className="w-3 h-3" />}
          {isActive && sortState.direction === 'desc' && <ChevronDown className="w-3 h-3" />}
        </span>
      </div>
    </th>
  );
};

// Generic sort function
const sortData = <T,>(data: T[], field: string, direction: SortDirection): T[] => {
  if (!direction || !field) return data;

  return [...data].sort((a, b) => {
    const aVal = (a as any)[field];
    const bVal = (b as any)[field];

    // Handle undefined/null values - put them at the end
    if (aVal == null && bVal == null) return 0;
    if (aVal == null) return 1;
    if (bVal == null) return -1;

    // String comparison
    if (typeof aVal === 'string' && typeof bVal === 'string') {
      const cmp = aVal.localeCompare(bVal);
      return direction === 'asc' ? cmp : -cmp;
    }

    // Number comparison
    const cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
    return direction === 'asc' ? cmp : -cmp;
  });
};

// Delta indicator component
const DeltaIndicator: React.FC<{
  current?: number;
  previous?: number;
  precision?: number;
}> = ({ current, previous, precision = 3 }) => {
  if (current === undefined || current === null) return <span className="text-muted-foreground">-</span>;
  if (previous === undefined || previous === null) return <span className="font-mono">{current.toFixed(precision)}</span>;

  const delta = current - previous;
  const threshold = Math.pow(10, -(precision + 1)); // Small threshold to avoid float comparison issues

  if (Math.abs(delta) < threshold) {
    return (
      <span className="font-mono">
        {current.toFixed(precision)}
        <span className="ml-1 text-muted-foreground">–</span>
      </span>
    );
  }

  if (delta > 0) {
    return (
      <span className="font-mono">
        {current.toFixed(precision)}
        <span className="ml-1 text-status-active">↑</span>
      </span>
    );
  }

  return (
    <span className="font-mono">
      {current.toFixed(precision)}
      <span className="ml-1 text-destructive">↓</span>
    </span>
  );
};

// Copy to clipboard with feedback
const copyToClipboard = async (text: string, format: string, setCopied: (f: string | null) => void) => {
  try {
    await navigator.clipboard.writeText(text);
    setCopied(format);
    setTimeout(() => setCopied(null), 2000);
  } catch (err) {
    console.error('Failed to copy:', err);
  }
};

// Convert report to JSON string
const toJSON = (report: Report): string => {
  return JSON.stringify(report.data, null, 2);
};

// Convert graph report to CSV
const graphToCSV = (data: GraphReportData): string => {
  const lines: string[] = [];

  // Concepts section
  lines.push('# Concepts');
  lines.push('ID,Label,Description,Ontology,Grounding,Diversity,Evidence');
  data.nodes.forEach(n => {
    lines.push([
      n.id,
      `"${(n.label || '').replace(/"/g, '""')}"`,
      `"${(n.description || '').replace(/"/g, '""')}"`,
      n.ontology || '',
      n.grounding_strength?.toFixed(3) || '',
      n.diversity_score?.toFixed(3) || '',
      n.evidence_count || '',
    ].join(','));
  });

  lines.push('');
  lines.push('# Relationships');
  lines.push('Source,Type,Target,Category,Confidence');
  data.links.forEach(l => {
    lines.push([
      l.source,
      l.type,
      l.target,
      (l as any).category || '',
      l.grounding_strength?.toFixed(3) || '',
    ].join(','));
  });

  return lines.join('\n');
};

// Convert polarity report to CSV
const polarityToCSV = (data: PolarityReportData): string => {
  const lines: string[] = [];

  lines.push('# Polarity Axis');
  lines.push(`Positive Pole,${data.positivePole.label}`);
  lines.push(`Negative Pole,${data.negativePole.label}`);
  lines.push(`Axis Magnitude,${data.axisMagnitude.toFixed(3)}`);

  lines.push('');
  lines.push('# Projected Concepts');
  lines.push('ID,Label,Position,Positive Similarity,Negative Similarity,Grounding');
  data.concepts.forEach(c => {
    lines.push([
      c.concept_id,
      `"${(c.label || '').replace(/"/g, '""')}"`,
      c.position.toFixed(3),
      c.positive_similarity.toFixed(3),
      c.negative_similarity.toFixed(3),
      c.grounding_strength?.toFixed(3) || '',
    ].join(','));
  });

  return lines.join('\n');
};

// Convert document report to CSV
const documentToCSV = (data: DocumentReportData): string => {
  const lines: string[] = [];

  if (data.searchParams?.query) {
    lines.push(`# Query: ${data.searchParams.query}`);
    if (data.searchParams.min_similarity) {
      lines.push(`# Min Similarity: ${data.searchParams.min_similarity}`);
    }
    if (data.searchParams.ontologies?.length) {
      lines.push(`# Ontologies: ${data.searchParams.ontologies.join(', ')}`);
    }
    lines.push('');
  }

  lines.push('Filename,Ontology,Content Type,Similarity,Sources,Concepts,Document ID');
  data.documents.forEach(d => {
    lines.push([
      `"${d.filename.replace(/"/g, '""')}"`,
      d.ontology,
      d.content_type,
      d.best_similarity?.toFixed(3) || '',
      d.source_count,
      d.concept_count,
      d.document_id,
    ].join(','));
  });

  return lines.join('\n');
};

// Convert traversal report to CSV
const traversalToCSV = (data: TraversalReportData): string => {
  const lines: string[] = [];

  lines.push(`# Traversal`);
  lines.push(`Origin,${data.origin.label}`);
  lines.push(`Destination,${data.destination.label}`);
  lines.push(`Max Hops,${data.maxHops}`);
  lines.push(`Paths Found,${data.pathCount}`);

  data.paths.forEach((path, i) => {
    lines.push('');
    lines.push(`# Path ${i + 1} (${path.hops} hops)`);
    lines.push('Step,Label,Description,Grounding,Diversity,Relationship');
    path.nodes.forEach((n, j) => {
      const relAfter = j < path.relationships.length ? path.relationships[j] : '';
      lines.push([
        j + 1,
        `"${(n.label || '').replace(/"/g, '""')}"`,
        `"${(n.description || '').replace(/"/g, '""')}"`,
        n.grounding_strength?.toFixed(3) || '',
        n.diversity_score?.toFixed(3) || '',
        relAfter,
      ].join(','));
    });
  });

  return lines.join('\n');
};

// Convert to Markdown
const toMarkdown = (report: Report): string => {
  const lines: string[] = [];
  lines.push(`# ${report.name}`);
  lines.push(`*Generated: ${formatDate(report.createdAt)}*`);
  lines.push('');

  if (report.type === 'graph') {
    const data = report.data as GraphReportData;

    lines.push('## Concepts');
    lines.push('| Label | Description | Ontology | Grounding | Diversity |');
    lines.push('|-------|-------------|----------|-----------|-----------|');
    data.nodes.forEach(n => {
      lines.push(`| ${n.label || ''} | ${(n.description || '').slice(0, 50)}... | ${n.ontology || ''} | ${n.grounding_strength?.toFixed(2) || '-'} | ${n.diversity_score?.toFixed(2) || '-'} |`);
    });

    lines.push('');
    lines.push('## Relationships');
    lines.push('| Source | Type | Target |');
    lines.push('|--------|------|--------|');
    data.links.slice(0, 50).forEach(l => {
      const sourceNode = data.nodes.find(n => n.id === l.source);
      const targetNode = data.nodes.find(n => n.id === l.target);
      lines.push(`| ${sourceNode?.label || l.source} | ${l.type} | ${targetNode?.label || l.target} |`);
    });
    if (data.links.length > 50) {
      lines.push(`*... and ${data.links.length - 50} more relationships*`);
    }
  } else if (report.type === 'polarity') {
    const data = report.data as PolarityReportData;

    lines.push('## Polarity Axis');
    lines.push(`- **Positive Pole:** ${data.positivePole.label}`);
    lines.push(`- **Negative Pole:** ${data.negativePole.label}`);
    lines.push(`- **Axis Magnitude:** ${data.axisMagnitude.toFixed(3)}`);

    lines.push('');
    lines.push('## Direction Distribution');
    lines.push(`- Positive: ${data.directionDistribution.positive}`);
    lines.push(`- Neutral: ${data.directionDistribution.neutral}`);
    lines.push(`- Negative: ${data.directionDistribution.negative}`);

    lines.push('');
    lines.push('## Projected Concepts');
    lines.push('| Label | Position | Grounding |');
    lines.push('|-------|----------|-----------|');
    data.concepts.forEach(c => {
      lines.push(`| ${c.label} | ${c.position.toFixed(3)} | ${c.grounding_strength?.toFixed(2) || '-'} |`);
    });
  } else if (report.type === 'traversal') {
    const data = report.data as TraversalReportData;

    lines.push('## Traversal');
    lines.push(`- **Origin:** ${data.origin.label}`);
    lines.push(`- **Destination:** ${data.destination.label}`);
    lines.push(`- **Paths Found:** ${data.pathCount}`);

    data.paths.forEach((path, i) => {
      lines.push('');
      lines.push(`### Path ${i + 1} (${path.hops} hops)`);
      lines.push('');
      path.nodes.forEach((n, j) => {
        lines.push(`${j + 1}. **${n.label}**${n.grounding_strength != null ? ` (grounding: ${n.grounding_strength.toFixed(2)})` : ''}`);
        if (j < path.relationships.length) {
          lines.push(`   *${path.relationships[j]}* ↓`);
        }
      });
    });
  } else {
    const data = report.data as DocumentReportData;

    if (data.searchParams?.query) {
      lines.push('## Query Parameters');
      lines.push(`- **Search:** ${data.searchParams.query}`);
      if (data.searchParams.min_similarity) {
        lines.push(`- **Min Similarity:** ${data.searchParams.min_similarity}`);
      }
      if (data.searchParams.ontologies?.length) {
        lines.push(`- **Ontologies:** ${data.searchParams.ontologies.join(', ')}`);
      }
      lines.push('');
    }

    lines.push('## Documents');
    lines.push('| Filename | Ontology | Similarity | Sources | Concepts |');
    lines.push('|----------|----------|------------|---------|----------|');
    data.documents.forEach(d => {
      lines.push(`| ${d.filename} | ${d.ontology} | ${d.best_similarity?.toFixed(2) || '-'} | ${d.source_count} | ${d.concept_count} |`);
    });
  }

  return lines.join('\n');
};

export const ReportWorkspace: React.FC = () => {
  const navigate = useNavigate();
  const {
    reports,
    selectedReportId,
    selectReport,
    deleteReport,
    renameReport,
    updateReportData,
  } = useReportStore();

  const [activeTab, setActiveTab] = useState<string>('reports');
  const [copiedFormat, setCopiedFormat] = useState<string | null>(null);
  const [editingName, setEditingName] = useState<string | null>(null);
  const [editNameValue, setEditNameValue] = useState('');
  const [isRecalculating, setIsRecalculating] = useState(false);
  const [recalculateProgress, setRecalculateProgress] = useState<{ current: number; total: number } | null>(null);

  // Sort states for different tables
  const [conceptSort, setConceptSort] = useState<SortState>({ field: null, direction: null });
  const [relationshipSort, setRelationshipSort] = useState<SortState>({ field: null, direction: null });
  const [polaritySort, setPolaritySort] = useState<SortState>({ field: null, direction: null });
  const [documentSort, setDocumentSort] = useState<SortState>({ field: null, direction: null });

  // Document query state
  const [docQuery, setDocQuery] = useState('');
  const [docMinSimilarity, setDocMinSimilarity] = useState(0.5);
  const [docOntologies, setDocOntologies] = useState<string[]>([]);
  const [availableOntologies, setAvailableOntologies] = useState<string[]>([]);
  const [docResults, setDocResults] = useState<DocumentReportData['documents']>([]);
  const [isSearchingDocs, setIsSearchingDocs] = useState(false);
  const [docSearchError, setDocSearchError] = useState<string | null>(null);

  // Document viewer state (uses shared DocumentViewer component)
  const [viewingDocument, setViewingDocument] = useState<{
    document_id: string;
    filename: string;
    content_type: string;
  } | null>(null);

  // Load available ontologies on mount
  useEffect(() => {
    const loadOntologies = async () => {
      try {
        const response = await apiClient.listOntologies();
        setAvailableOntologies(response.ontologies.map((o) => o.ontology));
      } catch (err) {
        console.error('Failed to load ontologies:', err);
      }
    };
    loadOntologies();
  }, []);

  // Derive selected report from reactive state (not getSelectedReport which isn't reactive)
  const selectedReport = useMemo(
    () => reports.find((r) => r.id === selectedReportId) || null,
    [reports, selectedReportId]
  );

  // Reset sort states when switching reports
  useEffect(() => {
    setConceptSort({ field: null, direction: null });
    setRelationshipSort({ field: null, direction: null });
    setPolaritySort({ field: null, direction: null });
  }, [selectedReportId]);

  // Memoized sorted data - must be at top level to follow Rules of Hooks
  const sortedNodes = useMemo(() => {
    if (!selectedReport || selectedReport.type !== 'graph') return [];
    const data = selectedReport.data as GraphReportData;
    return sortData(data.nodes, conceptSort.field || '', conceptSort.direction);
  }, [selectedReport, conceptSort.field, conceptSort.direction]);

  const linksWithLabels = useMemo(() => {
    if (!selectedReport || selectedReport.type !== 'graph') return [];
    const data = selectedReport.data as GraphReportData;
    return data.links.map((link) => {
      const sourceNode = data.nodes.find((n) => n.id === link.source);
      const targetNode = data.nodes.find((n) => n.id === link.target);
      return {
        ...link,
        sourceLabel: sourceNode?.label || link.source,
        targetLabel: targetNode?.label || link.target,
        category: (link as any).category,
      };
    });
  }, [selectedReport]);

  const sortedLinks = useMemo(
    () => sortData(linksWithLabels, relationshipSort.field || '', relationshipSort.direction),
    [linksWithLabels, relationshipSort.field, relationshipSort.direction]
  );

  const sortedPolarityConcepts = useMemo(() => {
    if (!selectedReport || selectedReport.type !== 'polarity') return [];
    const data = selectedReport.data as PolarityReportData;
    return sortData(data.concepts, polaritySort.field || '', polaritySort.direction);
  }, [selectedReport, polaritySort.field, polaritySort.direction]);

  const sortedDocuments = useMemo(() => {
    if (!selectedReport || selectedReport.type !== 'document') return [];
    const data = selectedReport.data as DocumentReportData;
    return sortData(data.documents, documentSort.field || '', documentSort.direction);
  }, [selectedReport, documentSort.field, documentSort.direction]);

  // Document search handler
  const handleDocumentSearch = useCallback(async () => {
    if (!docQuery.trim()) {
      setDocSearchError('Enter a search query');
      return;
    }

    setIsSearchingDocs(true);
    setDocSearchError(null);

    try {
      // If specific ontologies selected, search each one; otherwise search all
      const ontologiesToSearch = docOntologies.length > 0 ? docOntologies : [undefined];
      const allDocs: DocumentReportData['documents'] = [];

      for (const ontology of ontologiesToSearch) {
        const response = await apiClient.searchDocuments({
          query: docQuery,
          min_similarity: docMinSimilarity,
          limit: 100,
          ontology,
        });

        // Add documents with concept_count derived from concept_ids
        response.documents.forEach((doc) => {
          // Avoid duplicates if same doc appears in multiple ontology searches
          if (!allDocs.find((d) => d.document_id === doc.document_id)) {
            allDocs.push({
              document_id: doc.document_id,
              filename: doc.filename,
              ontology: doc.ontology,
              content_type: doc.content_type,
              best_similarity: doc.best_similarity,
              source_count: doc.source_count,
              concept_count: doc.concept_ids?.length || 0,
            });
          }
        });
      }

      // Sort by similarity descending
      allDocs.sort((a, b) => (b.best_similarity || 0) - (a.best_similarity || 0));
      setDocResults(allDocs);
    } catch (err) {
      console.error('Document search failed:', err);
      setDocSearchError('Search failed. Please try again.');
    } finally {
      setIsSearchingDocs(false);
    }
  }, [docQuery, docMinSimilarity, docOntologies]);

  // Save document results as a report
  const handleSaveDocumentReport = useCallback(async () => {
    if (docResults.length === 0) return;

    const { addReport } = useReportStore.getState();
    const data: DocumentReportData = {
      type: 'document',
      documents: docResults,
      searchParams: {
        query: docQuery,
        min_similarity: docMinSimilarity,
        ontologies: docOntologies.length > 0 ? docOntologies : undefined,
      },
    };

    const name = `docs: "${docQuery}" (${docResults.length})`;
    await addReport({
      name,
      type: 'document',
      data,
      sourceExplorer: 'document',
    });

    // Switch to reports tab to see the saved report
    setActiveTab('reports');
  }, [docResults, docQuery, docMinSimilarity, docOntologies]);

  // View document content (uses shared DocumentViewer component)
  const handleViewDocument = useCallback((doc: {
    document_id: string;
    filename: string;
    content_type: string;
  }) => {
    setViewingDocument(doc);
  }, []);

  // Sort handler - toggles through: null -> asc -> desc -> null
  const handleSort = (setter: React.Dispatch<React.SetStateAction<SortState>>) => (field: string) => {
    setter((prev) => {
      if (prev.field !== field) {
        return { field, direction: 'asc' };
      }
      if (prev.direction === 'asc') {
        return { field, direction: 'desc' };
      }
      return { field: null, direction: null };
    });
  };

  // Recalculate data for a graph report (fetch full concept details and relationship grounding)
  // Batch-enrich concept nodes with fresh grounding/diversity from API
  const enrichConceptNodes = useCallback(async (
    nodeIds: string[],
    onProgress?: (current: number, total: number) => void,
  ): Promise<Map<string, any>> => {
    const detailsMap = new Map<string, any>();
    const batchSize = 5;

    for (let i = 0; i < nodeIds.length; i += batchSize) {
      const batch = nodeIds.slice(i, i + batchSize);
      const results = await Promise.allSettled(
        batch.map((id) => apiClient.getConceptDetails(id))
      );
      let failCount = 0;
      results.forEach((result, idx) => {
        if (result.status === 'fulfilled') {
          detailsMap.set(batch[idx], result.value);
        } else {
          failCount++;
        }
      });
      if (failCount > 0) {
        console.warn(`enrichConceptNodes: ${failCount} concept(s) failed to fetch in batch`);
      }
      onProgress?.(Math.min(i + batchSize, nodeIds.length), nodeIds.length);
    }
    return detailsMap;
  }, []);

  const handleRecalculate = useCallback(async () => {
    if (!selectedReport) return;

    setIsRecalculating(true);
    setRecalculateProgress(null);

    try {
      if (selectedReport.type === 'graph') {
        const graphData = selectedReport.data as GraphReportData;
        setRecalculateProgress({ current: 0, total: graphData.nodes.length });

        const detailsMap = await enrichConceptNodes(
          graphData.nodes.map((n) => n.id),
          (current, total) => setRecalculateProgress({ current, total }),
        );

        const enrichedNodes = graphData.nodes.map((node) => {
          const details = detailsMap.get(node.id);
          if (!details) return node;
          return {
            id: node.id,
            label: details.label || node.label,
            description: details.description,
            ontology: details.ontology || node.ontology,
            grounding_strength: details.grounding_strength,
            diversity_score: details.diversity_score,
            evidence_count: details.evidence?.length || 0,
          };
        });

        const enrichedLinks = graphData.links.map((link) => {
          const sourceDetails = detailsMap.get(link.source);
          if (sourceDetails?.relationships) {
            const rel = sourceDetails.relationships.find(
              (r: any) => r.to_id === link.target && r.rel_type === link.type
            );
            if (rel) {
              return {
                ...link,
                grounding_strength: rel.avg_grounding ?? rel.confidence,
                category: rel.category,
                epistemic_status: rel.epistemic_status,
              };
            }
          }
          return link;
        });

        updateReportData(selectedReport.id, { ...graphData, nodes: enrichedNodes, links: enrichedLinks });

      } else if (selectedReport.type === 'traversal') {
        const travData = selectedReport.data as TraversalReportData;
        // Collect unique node IDs across all paths
        const allNodeIds = new Set<string>();
        travData.paths.forEach((p) => p.nodes.forEach((n) => allNodeIds.add(n.id)));
        setRecalculateProgress({ current: 0, total: allNodeIds.size });

        const detailsMap = await enrichConceptNodes(
          Array.from(allNodeIds),
          (current, total) => setRecalculateProgress({ current, total }),
        );

        const enrichedPaths = travData.paths.map((path) => ({
          ...path,
          nodes: path.nodes.map((node) => {
            const details = detailsMap.get(node.id);
            if (!details) return node;
            return {
              ...node,
              grounding_strength: details.grounding_strength,
              diversity_score: details.diversity_score,
              description: details.description || node.description,
            };
          }),
        }));

        updateReportData(selectedReport.id, { ...travData, paths: enrichedPaths });

      } else if (selectedReport.type === 'polarity') {
        const polarityData = selectedReport.data as PolarityReportData;
        setRecalculateProgress({ current: 0, total: polarityData.concepts.length });

        const detailsMap = await enrichConceptNodes(
          polarityData.concepts.map((c) => c.concept_id),
          (current, total) => setRecalculateProgress({ current, total }),
        );

        const enrichedConcepts = polarityData.concepts.map((concept) => {
          const details = detailsMap.get(concept.concept_id);
          if (!details) return concept;
          return {
            ...concept,
            grounding_strength: details.grounding_strength,
          };
        });

        updateReportData(selectedReport.id, { ...polarityData, concepts: enrichedConcepts });
      }
    } catch (err) {
      console.error('Failed to recalculate:', err);
    } finally {
      setIsRecalculating(false);
      setRecalculateProgress(null);
    }
  }, [selectedReport, updateReportData, enrichConceptNodes]);

  const handleDeleteReport = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm('Delete this report?')) {
      await deleteReport(id);
    }
  };

  const handleFinishRename = async (id: string) => {
    if (editNameValue.trim()) {
      await renameReport(id, editNameValue.trim());
    }
    setEditingName(null);
  };

  const getReportIcon = (report: Report) => {
    if (report.type === 'polarity') return Compass;
    if (report.type === 'document') return FileText;
    if (report.type === 'traversal') return Route;
    return GitBranch;
  };

  // Reports list tab content
  const reportsContent = (
    <div className="p-2">
      <div className="flex items-center justify-between mb-2 px-2">
        <span className="text-xs font-medium text-muted-foreground">
          {reports.length} saved
        </span>
      </div>

      {reports.length === 0 ? (
        <div className="text-center py-8 text-sm text-muted-foreground">
          <FileText className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p>No saved reports</p>
          <p className="text-xs mt-1">Use "Send to Reports" from an explorer</p>
        </div>
      ) : (
        <div className="space-y-1">
          {reports.map((report) => {
            const Icon = getReportIcon(report);
            const isSelected = selectedReportId === report.id;
            const nodeCount = report.type === 'graph'
              ? (report.data as GraphReportData).nodes.length
              : report.type === 'polarity'
              ? (report.data as PolarityReportData).concepts.length
              : report.type === 'traversal'
              ? (report.data as TraversalReportData).pathCount
              : (report.data as DocumentReportData).documents.length;

            return (
              <div
                key={report.id}
                onClick={() => selectReport(report.id)}
                className={`
                  w-full text-left p-2 rounded-lg transition-colors group cursor-pointer
                  ${isSelected
                    ? 'bg-primary text-primary-foreground'
                    : 'hover:bg-accent'
                  }
                `}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate">
                      <Icon className="w-3 h-3 inline mr-1.5" />
                      {report.name}
                    </div>
                    <div className="flex items-center gap-1.5 text-xs opacity-70 mt-0.5">
                      <span>{nodeCount} items</span>
                      <span>·</span>
                      <Clock className="w-3 h-3" />
                      <span>{formatDate(report.createdAt)}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => handleDeleteReport(report.id, e)}
                      className={`
                        p-1 rounded
                        ${isSelected
                          ? 'hover:bg-primary-foreground/20'
                          : 'hover:bg-destructive/20 text-destructive'
                        }
                      `}
                      title="Delete report"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );

  // Settings tab content (placeholder for future options)
  const settingsContent = (
    <div className="p-4 text-sm text-muted-foreground">
      <Settings2 className="w-8 h-8 mx-auto mb-2 opacity-50" />
      <p className="text-center">Report settings coming soon</p>
    </div>
  );

  // Documents query tab content
  const documentsContent = (
    <div className="p-3 space-y-4">
      <div className="text-xs font-medium text-muted-foreground mb-2">
        Document Query
      </div>

      {/* Search input */}
      <div>
        <label className="text-xs text-muted-foreground mb-1 block">Search phrase</label>
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-muted-foreground" />
          <input
            type="text"
            value={docQuery}
            onChange={(e) => setDocQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleDocumentSearch()}
            placeholder="e.g., machine learning"
            className="w-full pl-7 pr-2 py-1.5 text-sm bg-background border rounded focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
      </div>

      {/* Similarity threshold */}
      <div>
        <label className="text-xs text-muted-foreground mb-1 block">
          Min similarity: {(docMinSimilarity * 100).toFixed(0)}%
        </label>
        <input
          type="range"
          min="0.3"
          max="0.95"
          step="0.05"
          value={docMinSimilarity}
          onChange={(e) => setDocMinSimilarity(parseFloat(e.target.value))}
          className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer"
        />
      </div>

      {/* Ontology filter */}
      <div>
        <label className="text-xs text-muted-foreground mb-1 block">
          Ontologies {docOntologies.length > 0 && `(${docOntologies.length})`}
        </label>
        <div className="max-h-24 overflow-y-auto border rounded p-1 space-y-0.5">
          {availableOntologies.length === 0 ? (
            <div className="text-xs text-muted-foreground py-1 px-2">Loading...</div>
          ) : (
            availableOntologies.map((ont) => (
              <label key={ont} className="flex items-center gap-2 text-xs py-0.5 px-1 hover:bg-accent rounded cursor-pointer">
                <input
                  type="checkbox"
                  checked={docOntologies.includes(ont)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setDocOntologies([...docOntologies, ont]);
                    } else {
                      setDocOntologies(docOntologies.filter((o) => o !== ont));
                    }
                  }}
                  className="w-3 h-3"
                />
                <span className="truncate">{ont}</span>
              </label>
            ))
          )}
        </div>
        {docOntologies.length > 0 && (
          <button
            onClick={() => setDocOntologies([])}
            className="text-xs text-muted-foreground hover:text-foreground mt-1"
          >
            Clear all
          </button>
        )}
      </div>

      {/* Search button */}
      <button
        onClick={handleDocumentSearch}
        disabled={isSearchingDocs || !docQuery.trim()}
        className="w-full py-1.5 text-sm bg-primary text-primary-foreground rounded hover:bg-primary/90 disabled:opacity-50 flex items-center justify-center gap-2"
      >
        {isSearchingDocs ? (
          <>
            <Loader2 className="w-3 h-3 animate-spin" />
            Searching...
          </>
        ) : (
          <>
            <FileSearch className="w-3 h-3" />
            Search Documents
          </>
        )}
      </button>

      {docSearchError && (
        <p className="text-xs text-destructive">{docSearchError}</p>
      )}

      {/* Results summary */}
      {docResults.length > 0 && (
        <div className="pt-2 border-t">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-muted-foreground">
              {docResults.length} documents found
            </span>
            <button
              onClick={handleSaveDocumentReport}
              className="text-xs flex items-center gap-1 text-primary hover:underline"
              title="Save as report"
            >
              <Save className="w-3 h-3" />
              Save
            </button>
          </div>
          <div className="max-h-32 overflow-y-auto space-y-1">
            {docResults.slice(0, 10).map((doc) => (
              <div
                key={doc.document_id}
                className="text-xs p-1.5 bg-muted/50 rounded truncate"
                title={doc.filename}
              >
                <span className="font-medium">{doc.filename}</span>
                <span className="text-muted-foreground ml-1">
                  ({(doc.best_similarity || 0) * 100 | 0}%)
                </span>
              </div>
            ))}
            {docResults.length > 10 && (
              <div className="text-xs text-muted-foreground text-center">
                +{docResults.length - 10} more
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );

  const panelTabs = [
    { id: 'reports', icon: FolderOpen, label: 'Reports', content: reportsContent },
    { id: 'documents', icon: FileSearch, label: 'Documents', content: documentsContent },
    { id: 'settings', icon: Settings2, label: 'Settings', content: settingsContent },
  ];

  // Render table for graph report
  const renderGraphTable = (data: GraphReportData, report: Report) => {
    const prevValues = report.previousValues || {};
    // Get all unique ontologies for color calculation
    const allOntologies = [...new Set(data.nodes.map(n => n.ontology).filter(Boolean))];

    return (
      <div className="space-y-6">
        {/* Query Info */}
        {data.searchParams && (
          <div className="p-3 bg-muted/30 rounded-lg border text-sm">
            <div className="flex items-center gap-4 flex-wrap">
              <span className="text-muted-foreground">Mode:</span>
              <span className="font-medium capitalize">{data.searchParams.mode}</span>
              {data.searchParams.conceptId && (
                <>
                  <span className="text-muted-foreground">Center:</span>
                  <span className="font-mono text-xs bg-background px-2 py-0.5 rounded">
                    {data.searchParams.conceptId}
                  </span>
                </>
              )}
              {data.searchParams.depth && (
                <>
                  <span className="text-muted-foreground">Depth:</span>
                  <span className="font-medium">{data.searchParams.depth}</span>
                </>
              )}
            </div>
          </div>
        )}

        {/* Concepts Table */}
        <div>
          <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
            <Table2 className="w-4 h-4" />
            Concepts ({data.nodes.length})
          </h3>
          <div className="border rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/50">
                  <tr>
                    <SortableHeader field="label" label="Label" sortState={conceptSort} onSort={handleSort(setConceptSort)} />
                    <SortableHeader field="description" label="Description" sortState={conceptSort} onSort={handleSort(setConceptSort)} />
                    <SortableHeader field="ontology" label="Ontology" sortState={conceptSort} onSort={handleSort(setConceptSort)} />
                    <SortableHeader field="grounding_strength" label="Grounding" sortState={conceptSort} onSort={handleSort(setConceptSort)} align="right" />
                    <SortableHeader field="diversity_score" label="Diversity" sortState={conceptSort} onSort={handleSort(setConceptSort)} align="right" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {sortedNodes.map((node) => {
                    const prev = prevValues[node.id];
                    return (
                      <tr key={node.id} className="hover:bg-muted/30">
                        <td className="px-3 py-2 font-medium">{node.label}</td>
                        <td className="px-3 py-2 text-muted-foreground max-w-xs truncate">
                          {node.description || '-'}
                        </td>
                        <td className="px-3 py-2">
                          {node.ontology ? (
                            <span
                              className="px-1.5 py-0.5 text-xs rounded"
                              style={{
                                backgroundColor: `${getOntologyColor(node.ontology, allOntologies)}40`,
                                color: getOntologyColor(node.ontology, allOntologies),
                              }}
                            >
                              {node.ontology}
                            </span>
                          ) : '-'}
                        </td>
                        <td className="px-3 py-2 text-right text-xs">
                          <DeltaIndicator
                            current={node.grounding_strength}
                            previous={prev?.grounding_strength}
                          />
                        </td>
                        <td className="px-3 py-2 text-right text-xs">
                          <DeltaIndicator
                            current={node.diversity_score}
                            previous={prev?.diversity_score}
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>

      {/* Relationships Table */}
      <div>
        <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
          <GitBranch className="w-4 h-4" />
          Relationships ({data.links.length})
        </h3>
        <div className="border rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 sticky top-0">
                <tr>
                  <SortableHeader field="sourceLabel" label="Source" sortState={relationshipSort} onSort={handleSort(setRelationshipSort)} />
                  <SortableHeader field="type" label="Type" sortState={relationshipSort} onSort={handleSort(setRelationshipSort)} align="center" />
                  <SortableHeader field="targetLabel" label="Target" sortState={relationshipSort} onSort={handleSort(setRelationshipSort)} />
                  <SortableHeader field="category" label="Category" sortState={relationshipSort} onSort={handleSort(setRelationshipSort)} />
                  <SortableHeader field="grounding_strength" label="Confidence" sortState={relationshipSort} onSort={handleSort(setRelationshipSort)} align="right" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {sortedLinks.map((link, i) => (
                  <tr key={i} className="hover:bg-muted/30">
                    <td className="px-3 py-2">{link.sourceLabel}</td>
                    <td className="px-3 py-2 text-center">
                      <span
                        className="px-2 py-0.5 text-xs rounded"
                        style={{
                          backgroundColor: `${getCategoryColor(link.category)}30`,
                          color: getCategoryColor(link.category),
                        }}
                      >
                        {link.type}
                      </span>
                    </td>
                    <td className="px-3 py-2">{link.targetLabel}</td>
                    <td className="px-3 py-2">
                      {link.category ? (
                        <span
                          className="px-1.5 py-0.5 text-xs rounded capitalize"
                          style={{
                            backgroundColor: `${getCategoryColor(link.category)}20`,
                            color: getCategoryColor(link.category),
                          }}
                        >
                          {link.category}
                        </span>
                      ) : '-'}
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-xs">
                      {link.grounding_strength?.toFixed(3) || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
    );
  };

  // Render table for polarity report
  const renderPolarityTable = (data: PolarityReportData) => {
    return (
      <div className="space-y-6">
        {/* Axis Info */}
        <div className="grid grid-cols-3 gap-4">
          <div className="p-4 border rounded-lg">
            <div className="text-xs text-muted-foreground mb-1">Positive Pole</div>
            <div className="font-semibold text-blue-500">
              {data.positivePole.label}
            </div>
          </div>
          <div className="p-4 border rounded-lg text-center">
            <div className="text-xs text-muted-foreground mb-1">Axis Magnitude</div>
            <div className="font-semibold font-mono">{data.axisMagnitude.toFixed(3)}</div>
          </div>
          <div className="p-4 border rounded-lg text-right">
            <div className="text-xs text-muted-foreground mb-1">Negative Pole</div>
            <div className="font-semibold text-orange-500">
              {data.negativePole.label}
            </div>
          </div>
        </div>

        {/* Direction Distribution */}
        <div className="flex gap-4 justify-center text-sm">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-blue-500"></div>
            <span>Positive: {data.directionDistribution.positive}</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-muted-foreground"></div>
            <span>Neutral: {data.directionDistribution.neutral}</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-orange-500"></div>
            <span>Negative: {data.directionDistribution.negative}</span>
          </div>
        </div>

        {/* Concepts Table */}
        <div>
          <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
            <Table2 className="w-4 h-4" />
            Projected Concepts ({data.concepts.length})
          </h3>
          <div className="border rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/50">
                  <tr>
                    <SortableHeader field="label" label="Label" sortState={polaritySort} onSort={handleSort(setPolaritySort)} />
                    <SortableHeader field="position" label="Position" sortState={polaritySort} onSort={handleSort(setPolaritySort)} align="right" />
                    <SortableHeader field="positive_similarity" label="+ Similarity" sortState={polaritySort} onSort={handleSort(setPolaritySort)} align="right" />
                    <SortableHeader field="negative_similarity" label="- Similarity" sortState={polaritySort} onSort={handleSort(setPolaritySort)} align="right" />
                    <SortableHeader field="grounding_strength" label="Grounding" sortState={polaritySort} onSort={handleSort(setPolaritySort)} align="right" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {sortedPolarityConcepts.map((concept) => (
                    <tr key={concept.concept_id} className="hover:bg-muted/30">
                      <td className="px-3 py-2 font-medium">{concept.label}</td>
                      <td className="px-3 py-2 text-right">
                        <span className={`font-mono text-xs px-1.5 py-0.5 rounded ${
                          concept.position > 0.1
                            ? 'bg-blue-500/20 text-blue-500'
                            : concept.position < -0.1
                            ? 'bg-orange-500/20 text-orange-500'
                            : 'bg-muted text-muted-foreground'
                        }`}>
                          {concept.position > 0 ? '+' : ''}{concept.position.toFixed(3)}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-xs">
                        {concept.positive_similarity.toFixed(3)}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-xs">
                        {concept.negative_similarity.toFixed(3)}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-xs">
                        {concept.grounding_strength?.toFixed(3) || '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Render table for traversal report
  const renderTraversalTable = (data: TraversalReportData) => {
    return (
      <div className="space-y-6">
        {/* Origin → Destination header */}
        <div className="grid grid-cols-3 gap-3">
          <div className="p-3 bg-muted/30 rounded-lg border text-center">
            <div className="text-xs text-muted-foreground mb-1">Origin</div>
            <div className="font-semibold text-sm">{data.origin.label}</div>
          </div>
          <div className="p-3 bg-muted/30 rounded-lg border text-center flex items-center justify-center">
            <div>
              <div className="text-xs text-muted-foreground mb-1">Paths</div>
              <div className="font-semibold text-lg">{data.pathCount}</div>
            </div>
          </div>
          <div className="p-3 bg-muted/30 rounded-lg border text-center">
            <div className="text-xs text-muted-foreground mb-1">Destination</div>
            <div className="font-semibold text-sm">{data.destination.label}</div>
          </div>
        </div>

        {/* Paths */}
        {data.paths.map((path, pathIdx) => (
          <div key={pathIdx}>
            <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
              <Route className="w-4 h-4" />
              Path {pathIdx + 1} ({path.hops} hops)
            </h3>
            <div className="border rounded-lg overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground w-12">#</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Concept</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Description</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Grounding</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">Diversity</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground w-32">Relationship</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {path.nodes.map((node, nodeIdx) => (
                      <tr key={node.id} className="hover:bg-muted/30">
                        <td className="px-3 py-2 text-muted-foreground font-mono text-xs">
                          {nodeIdx + 1}
                        </td>
                        <td className="px-3 py-2 font-medium">
                          {node.label}
                        </td>
                        <td className="px-3 py-2 text-muted-foreground text-xs max-w-xs truncate" title={node.description}>
                          {node.description || '-'}
                        </td>
                        <td className="px-3 py-2 text-right">
                          {node.grounding_strength != null ? (
                            <span className={`font-mono text-xs px-1.5 py-0.5 rounded ${
                              node.grounding_strength >= 0.7
                                ? 'bg-green-500/20 text-green-600'
                                : node.grounding_strength >= 0.3
                                ? 'bg-yellow-500/20 text-yellow-600'
                                : 'bg-red-500/20 text-red-600'
                            }`}>
                              {(node.grounding_strength * 100).toFixed(0)}%
                            </span>
                          ) : '-'}
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-xs">
                          {node.diversity_score?.toFixed(2) || '-'}
                        </td>
                        <td className="px-3 py-2">
                          {nodeIdx < path.relationships.length ? (
                            <span className="text-xs px-1.5 py-0.5 rounded"
                              style={{
                                backgroundColor: `${getCategoryColor(path.relationships[nodeIdx])}30`,
                                color: getCategoryColor(path.relationships[nodeIdx]),
                              }}
                            >
                              {path.relationships[nodeIdx]} ↓
                            </span>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        ))}

        {data.pathCount === 0 && (
          <div className="text-center text-muted-foreground py-8">
            No paths found between origin and destination.
          </div>
        )}
      </div>
    );
  };

  // Render table for document report
  const renderDocumentTable = (data: DocumentReportData) => {
    // Get all unique ontologies for color calculation
    const allOntologies = [...new Set(data.documents.map(d => d.ontology).filter(Boolean))];

    return (
      <div className="space-y-6">
        {/* Query Info */}
        {data.searchParams && (
          <div className="p-3 bg-muted/30 rounded-lg border text-sm">
            <div className="flex items-center gap-4 flex-wrap">
              {data.searchParams.query && (
                <>
                  <span className="text-muted-foreground">Query:</span>
                  <span className="font-medium">"{data.searchParams.query}"</span>
                </>
              )}
              {data.searchParams.min_similarity && (
                <>
                  <span className="text-muted-foreground">Min Similarity:</span>
                  <span className="font-medium">{(data.searchParams.min_similarity * 100).toFixed(0)}%</span>
                </>
              )}
              {data.searchParams.ontologies && data.searchParams.ontologies.length > 0 && (
                <>
                  <span className="text-muted-foreground">Ontologies:</span>
                  <span className="font-medium">{data.searchParams.ontologies.join(', ')}</span>
                </>
              )}
            </div>
          </div>
        )}

        {/* Documents Table */}
        <div>
          <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
            <Table2 className="w-4 h-4" />
            Documents ({data.documents.length})
          </h3>
          <div className="border rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="px-3 py-2 w-10"></th>
                    <SortableHeader field="filename" label="Filename" sortState={documentSort} onSort={handleSort(setDocumentSort)} />
                    <SortableHeader field="ontology" label="Ontology" sortState={documentSort} onSort={handleSort(setDocumentSort)} />
                    <SortableHeader field="content_type" label="Type" sortState={documentSort} onSort={handleSort(setDocumentSort)} />
                    <SortableHeader field="best_similarity" label="Similarity" sortState={documentSort} onSort={handleSort(setDocumentSort)} align="right" />
                    <SortableHeader field="source_count" label="Sources" sortState={documentSort} onSort={handleSort(setDocumentSort)} align="right" />
                    <SortableHeader field="concept_count" label="Concepts" sortState={documentSort} onSort={handleSort(setDocumentSort)} align="right" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {sortedDocuments.map((doc) => (
                    <tr key={doc.document_id} className="hover:bg-muted/30">
                      <td className="px-3 py-2">
                        <button
                          onClick={() => handleViewDocument(doc)}
                          className="p-1 rounded hover:bg-accent"
                          title="View document"
                        >
                          <Eye className="w-4 h-4 text-muted-foreground" />
                        </button>
                      </td>
                      <td className="px-3 py-2 font-medium max-w-xs truncate" title={doc.filename}>
                        {doc.filename}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className="px-1.5 py-0.5 text-xs rounded"
                          style={{
                            backgroundColor: `${getOntologyColor(doc.ontology, allOntologies)}40`,
                            color: getOntologyColor(doc.ontology, allOntologies),
                          }}
                        >
                          {doc.ontology}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-muted-foreground text-xs">
                        {doc.content_type}
                      </td>
                      <td className="px-3 py-2 text-right">
                        {doc.best_similarity != null ? (
                          <span className={`font-mono text-xs px-1.5 py-0.5 rounded ${
                            doc.best_similarity >= 0.8
                              ? 'bg-green-500/20 text-green-600'
                              : doc.best_similarity >= 0.6
                              ? 'bg-yellow-500/20 text-yellow-600'
                              : 'bg-muted text-muted-foreground'
                          }`}>
                            {(doc.best_similarity * 100).toFixed(0)}%
                          </span>
                        ) : '-'}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-xs">
                        {doc.source_count}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-xs">
                        {doc.concept_count}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="h-full flex">
      {/* Left Panel - Icon Rail with Reports list */}
      <IconRailPanel
        tabs={panelTabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        defaultExpanded={true}
      />

      {/* Center - Report View */}
      <div className="flex-1 flex flex-col bg-background">
        {/* Toolbar */}
        <div className="h-14 border-b border-border bg-card px-4 flex items-center justify-between">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <FileText className="w-5 h-5 text-muted-foreground flex-shrink-0" />
            <div className="flex-1 min-w-0">
              {selectedReport && editingName === selectedReport.id ? (
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    autoFocus
                    value={editNameValue}
                    onChange={(e) => setEditNameValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleFinishRename(selectedReport.id);
                      if (e.key === 'Escape') setEditingName(null);
                    }}
                    className="font-semibold text-sm px-2 py-1 bg-background border border-border rounded flex-1 min-w-0 focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  <button
                    onClick={() => handleFinishRename(selectedReport.id)}
                    className="p-1 rounded hover:bg-accent text-primary"
                    title="Save"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setEditingName(null)}
                    className="p-1 rounded hover:bg-accent text-muted-foreground"
                    title="Cancel"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <span className="font-semibold truncate">
                    {selectedReport?.name || 'No Report Selected'}
                  </span>
                  {selectedReport && (
                    <button
                      onClick={() => {
                        setEditingName(selectedReport.id);
                        setEditNameValue(selectedReport.name);
                      }}
                      className="p-1 rounded hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
                      title="Rename report"
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              )}
              {selectedReport?.lastCalculatedAt && !editingName && (
                <div className="text-xs text-muted-foreground flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  Computed: {formatDate(selectedReport.lastCalculatedAt)}
                </div>
              )}
            </div>
          </div>

          {/* Actions */}
          {selectedReport && (
            <div className="flex items-center gap-2">
              {/* Recalculate button */}
              {selectedReport.type !== 'document' && (
                <button
                  onClick={handleRecalculate}
                  disabled={isRecalculating}
                  className="px-3 py-1.5 text-sm rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 flex items-center gap-2"
                  title="Recalculate grounding and diversity scores"
                >
                  {isRecalculating ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      {recalculateProgress
                        ? `${recalculateProgress.current}/${recalculateProgress.total}`
                        : 'Calculating...'}
                    </>
                  ) : (
                    <>
                      <RefreshCw className="w-4 h-4" />
                      Recalculate
                    </>
                  )}
                </button>
              )}

              <div className="w-px h-6 bg-border" />

              {/* Copy/Export buttons */}
            <div className="flex items-center gap-1">
              <button
                onClick={() => copyToClipboard(toJSON(selectedReport), 'json', setCopiedFormat)}
                className="px-2 py-1 text-xs rounded hover:bg-accent flex items-center gap-1"
                title="Copy as JSON"
              >
                {copiedFormat === 'json' ? <CheckCircle2 className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
                JSON
              </button>
              <button
                onClick={() => {
                  const csv = selectedReport.type === 'graph'
                    ? graphToCSV(selectedReport.data as GraphReportData)
                    : selectedReport.type === 'polarity'
                    ? polarityToCSV(selectedReport.data as PolarityReportData)
                    : selectedReport.type === 'traversal'
                    ? traversalToCSV(selectedReport.data as TraversalReportData)
                    : documentToCSV(selectedReport.data as DocumentReportData);
                  copyToClipboard(csv, 'csv', setCopiedFormat);
                }}
                className="px-2 py-1 text-xs rounded hover:bg-accent flex items-center gap-1"
                title="Copy as CSV"
              >
                {copiedFormat === 'csv' ? <CheckCircle2 className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
                CSV
              </button>
              <button
                onClick={() => copyToClipboard(toMarkdown(selectedReport), 'md', setCopiedFormat)}
                className="px-2 py-1 text-xs rounded hover:bg-accent flex items-center gap-1"
                title="Copy as Markdown"
              >
                {copiedFormat === 'md' ? <CheckCircle2 className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
                MD
              </button>
              <div className="w-px h-4 bg-border mx-1" />
              <button
                onClick={() => {
                  const content = toJSON(selectedReport);
                  const blob = new Blob([content], { type: 'application/json' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `${selectedReport.name.replace(/[^a-z0-9]/gi, '-').toLowerCase()}.json`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
                className="px-2 py-1 text-xs rounded hover:bg-accent flex items-center gap-1"
                title="Download JSON file"
              >
                <Download className="w-3 h-3" />
              </button>
            </div>
            </div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4">
          {selectedReport ? (
            selectedReport.type === 'graph'
              ? renderGraphTable(selectedReport.data as GraphReportData, selectedReport)
              : selectedReport.type === 'polarity'
              ? renderPolarityTable(selectedReport.data as PolarityReportData)
              : selectedReport.type === 'traversal'
              ? renderTraversalTable(selectedReport.data as TraversalReportData)
              : renderDocumentTable(selectedReport.data as DocumentReportData)
          ) : (
            <div className="h-full flex items-center justify-center">
              <div className="text-center text-muted-foreground">
                <FileText className="w-16 h-16 mx-auto mb-4 opacity-30" />
                <h3 className="text-lg font-medium mb-2">No Report Selected</h3>
                <p className="text-sm max-w-sm mx-auto">
                  Use the Documents tab to query documents, or use "Send to Reports"
                  from an explorer to create a tabular view of your data.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Document Viewer Modal (shared component) */}
      <DocumentViewer
        document={viewingDocument}
        onClose={() => setViewingDocument(null)}
      />
    </div>
  );
};
