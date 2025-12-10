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
} from 'lucide-react';
import * as d3 from 'd3';
import { IconRailPanel } from '../shared/IconRailPanel';
import { apiClient } from '../../api/client';
import { getCategoryColor } from '../../config/categoryColors';
import {
  useReportStore,
  type Report,
  type GraphReportData,
  type PolarityReportData,
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
  if (current === undefined) return <span className="text-muted-foreground">-</span>;
  if (previous === undefined) return <span className="font-mono">{current.toFixed(precision)}</span>;

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
  } else {
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
  const handleRecalculate = useCallback(async () => {
    if (!selectedReport || selectedReport.type !== 'graph') return;

    setIsRecalculating(true);
    const graphData = selectedReport.data as GraphReportData;
    const totalNodes = graphData.nodes.length;
    setRecalculateProgress({ current: 0, total: totalNodes });

    try {
      // Fetch details for all concepts in parallel (batched)
      const enrichedNodes: GraphReportData['nodes'] = [];
      const conceptDetailsMap = new Map<string, any>(); // Store full details for relationship lookup
      const batchSize = 5; // Limit concurrent requests

      for (let i = 0; i < graphData.nodes.length; i += batchSize) {
        const batch = graphData.nodes.slice(i, i + batchSize);
        const batchResults = await Promise.all(
          batch.map(async (node) => {
            try {
              const details = await apiClient.getConceptDetails(node.id);
              conceptDetailsMap.set(node.id, details); // Store for relationship lookup
              return {
                id: node.id,
                label: details.label || node.label,
                description: details.description,
                ontology: details.ontology || node.ontology,
                grounding_strength: details.grounding_strength,
                diversity_score: details.diversity_score,
                evidence_count: details.evidence?.length || 0,
              };
            } catch (err) {
              // If fetch fails, keep original data
              return node;
            }
          })
        );
        enrichedNodes.push(...batchResults);
        setRecalculateProgress({ current: enrichedNodes.length, total: totalNodes });
      }

      // Build enriched links with grounding and category from concept relationships
      const enrichedLinks = graphData.links.map((link) => {
        // Look up relationship details from source concept's relationships
        const sourceDetails = conceptDetailsMap.get(link.source);
        if (sourceDetails?.relationships) {
          const rel = sourceDetails.relationships.find(
            (r: any) => r.to_id === link.target && r.rel_type === link.type
          );
          if (rel) {
            // Use avg_grounding if available, otherwise fall back to confidence
            const grounding = rel.avg_grounding ?? rel.confidence;
            return {
              ...link,
              grounding_strength: grounding,
              category: rel.category,
              epistemic_status: rel.epistemic_status,
            };
          }
        }
        return link;
      });

      // Update report with enriched data
      const newData: GraphReportData = {
        ...graphData,
        nodes: enrichedNodes,
        links: enrichedLinks,
      };
      updateReportData(selectedReport.id, newData);
    } catch (err) {
      console.error('Failed to recalculate:', err);
    } finally {
      setIsRecalculating(false);
      setRecalculateProgress(null);
    }
  }, [selectedReport, updateReportData]);

  const handleDeleteReport = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm('Delete this report?')) {
      deleteReport(id);
    }
  };

  const handleStartRename = (report: Report, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingName(report.id);
    setEditNameValue(report.name);
  };

  const handleFinishRename = (id: string) => {
    if (editNameValue.trim()) {
      renameReport(id, editNameValue.trim());
    }
    setEditingName(null);
  };

  const getReportIcon = (report: Report) => {
    if (report.type === 'polarity') return Compass;
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
              : (report.data as PolarityReportData).concepts.length;

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
                    {editingName === report.id ? (
                      <input
                        type="text"
                        value={editNameValue}
                        onChange={(e) => setEditNameValue(e.target.value)}
                        onBlur={() => handleFinishRename(report.id)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleFinishRename(report.id);
                          if (e.key === 'Escape') setEditingName(null);
                        }}
                        className="w-full px-1 py-0.5 text-sm bg-background text-foreground rounded border"
                        autoFocus
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : (
                      <div
                        className="font-medium text-sm truncate"
                        onDoubleClick={(e) => handleStartRename(report, e)}
                      >
                        <Icon className="w-3 h-3 inline mr-1.5" />
                        {report.name}
                      </div>
                    )}
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

  const panelTabs = [
    { id: 'reports', icon: FolderOpen, label: 'Reports', content: reportsContent },
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
          <div className="flex items-center gap-3">
            <FileText className="w-5 h-5 text-muted-foreground" />
            <div>
              <div className="font-semibold">
                {selectedReport?.name || 'No Report Selected'}
              </div>
              {selectedReport?.lastCalculatedAt && (
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
              {selectedReport.type === 'graph' && (
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
                    : polarityToCSV(selectedReport.data as PolarityReportData);
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
              : renderPolarityTable(selectedReport.data as PolarityReportData)
          ) : (
            <div className="h-full flex items-center justify-center">
              <div className="text-center text-muted-foreground">
                <FileText className="w-16 h-16 mx-auto mb-4 opacity-30" />
                <h3 className="text-lg font-medium mb-2">No Report Selected</h3>
                <p className="text-sm max-w-sm mx-auto">
                  Use "Send to Reports" from the 2D, 3D, or Polarity Explorer
                  to create a tabular view of your graph data.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
