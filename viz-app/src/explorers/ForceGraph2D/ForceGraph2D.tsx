/**
 * Force-Directed 2D Graph Explorer - Main Component
 *
 * Interactive 2D force-directed graph visualization using D3.js.
 * Follows ADR-034 Explorer Plugin Interface.
 */

import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import * as d3 from 'd3';
import { ArrowRight, Plus, ChevronDown, ChevronRight, MapPin, MapPinOff, Pin, PinOff, Circle, Grid3x3, EyeOff } from 'lucide-react';
import type { ExplorerProps } from '../../types/explorer';
import type { D3Node, D3Link } from '../../types/graph';
import type { ForceGraph2DSettings, ForceGraph2DData } from './types';
import { getNeighbors, transformForD3 } from '../../utils/graphTransform';
import { useGraphStore } from '../../store/graphStore';
import { useVocabularyStore } from '../../store/vocabularyStore';
import { getCategoryColor, categoryColors } from '../../config/categoryColors';
import { ContextMenu, type ContextMenuItem } from '../../components/shared/ContextMenu';
import { apiClient } from '../../api/client';
import { Legend } from './Legend';
import { CanvasSettingsPanel } from './CanvasSettingsPanel';

/**
 * Format grounding strength with emoji indicator (matches CLI format)
 */
function formatGrounding(grounding: number | undefined | null): { emoji: string; label: string; percentage: string; color: string } | null {
  if (grounding === undefined || grounding === null) return null;

  const percentage = (grounding * 100).toFixed(0);

  // Color mapping: green (100%) → yellow (50%) → red (0% or negative)
  let color: string;
  if (grounding >= 0.8) {
    color = '#22c55e'; // green
  } else if (grounding >= 0.6) {
    color = '#84cc16'; // lime
  } else if (grounding >= 0.4) {
    color = '#eab308'; // yellow
  } else if (grounding >= 0.2) {
    color = '#f59e0b'; // amber
  } else if (grounding >= 0.0) {
    color = '#f97316'; // orange
  } else if (grounding >= -0.4) {
    color = '#ef4444'; // red
  } else {
    color = '#dc2626'; // deep red
  }

  if (grounding >= 0.8) {
    return { emoji: '✓', label: 'Strong', percentage: `${percentage}%`, color };
  } else if (grounding >= 0.4) {
    return { emoji: '⚡', label: 'Moderate', percentage: `${percentage}%`, color };
  } else if (grounding >= 0.0) {
    return { emoji: '◯', label: 'Weak', percentage: `${percentage}%`, color };
  } else if (grounding >= -0.4) {
    return { emoji: '◯', label: 'Contested', percentage: `${percentage}%`, color };
  } else {
    return { emoji: '✗', label: 'Contradicted', percentage: `${percentage}%`, color };
  }
}

/**
 * Get brighter color for relationship type text
 * Uses same category colors as edges but +40% brightness
 */
function getRelationshipTextColor(relationshipType: string): string {
  // Get category from vocabulary store
  const vocabStore = useVocabularyStore.getState();
  const category = vocabStore.getCategory(relationshipType) || 'default';

  // Get base color from shared config
  const baseColor = getCategoryColor(category);
  return d3.color(baseColor)?.brighter(0.4).toString() || baseColor;
}

/**
 * Node Info Box - Speech bubble style info display for nodes with collapsible sections
 */
interface NodeInfoBoxProps {
  info: {
    nodeId: string;
    label: string;
    group: string;
    degree: number;
    x: number;
    y: number;
  };
  zoomTransform: { x: number; y: number; k: number };
  onDismiss: () => void;
}

const NodeInfoBox: React.FC<NodeInfoBoxProps> = ({ info, zoomTransform, onDismiss }) => {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['overview']));
  const [detailedData, setDetailedData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  // Fetch detailed node data on mount
  useEffect(() => {
    const fetchDetails = async () => {
      setLoading(true);
      try {
        const response = await apiClient.getConceptDetails(info.nodeId);
        setDetailedData(response);
      } catch (error) {
        console.error('Failed to fetch node details:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchDetails();
  }, [info.nodeId]);

  const toggleSection = (section: string) => {
    setExpandedSections(prev => {
      const newSet = new Set(prev);
      if (newSet.has(section)) {
        newSet.delete(section);
      } else {
        newSet.add(section);
      }
      return newSet;
    });
  };

  // Apply zoom transform to graph coordinates
  const screenX = info.x * zoomTransform.k + zoomTransform.x;
  const screenY = info.y * zoomTransform.k + zoomTransform.y;

  return (
    <div
      className="absolute pointer-events-auto"
      style={{
        left: `${screenX}px`,
        top: `${screenY}px`,
        transform: 'translate(-50%, calc(-100% - 20px))', // Position above node with offset
        zIndex: 9999, // Ensure info box draws on top of everything
      }}
    >
      <div className="relative">
        {/* Speech bubble pointer - always dark */}
        <div
          className="absolute left-1/2 bottom-0 w-0 h-0"
          style={{
            borderLeft: '8px solid transparent',
            borderRight: '8px solid transparent',
            borderTop: '8px solid rgb(31, 41, 55)', // gray-800
            transform: 'translateX(-50%) translateY(100%)',
          }}
        />

        {/* Info box content - always dark theme */}
        <div
          className="bg-gray-800 rounded-lg shadow-xl border border-gray-600 cursor-pointer hover:shadow-2xl transition-shadow"
          style={{ minWidth: '280px', maxWidth: '400px' }}
        >
          {/* Header - always visible */}
          <div
            className="px-4 py-3 border-b border-gray-700"
            onClick={(e) => {
              e.stopPropagation();
              onDismiss();
            }}
          >
            <div className="font-semibold text-gray-100 text-base">
              {info.label}
            </div>
            <div className="text-xs text-gray-400 mt-1">
              Click to dismiss
            </div>
          </div>

          {/* Collapsible sections */}
          <div className="overflow-y-auto" style={{ maxHeight: 'calc(100vh - 200px)' }}>
            {/* Overview Section */}
            <div className="border-b border-gray-700">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  toggleSection('overview');
                }}
                className="w-full px-4 py-2 flex items-center justify-between hover:bg-gray-700 transition-colors"
              >
                <span className="font-medium text-sm text-gray-300">Overview</span>
                {expandedSections.has('overview') ? (
                  <ChevronDown size={16} className="text-gray-500" />
                ) : (
                  <ChevronRight size={16} className="text-gray-500" />
                )}
              </button>
              {expandedSections.has('overview') && (
                <div className="px-4 py-3 space-y-2 text-sm bg-gray-750">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Ontology:</span>
                    <span className="font-medium text-gray-100">{info.group}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Connections:</span>
                    <span className="font-medium text-gray-100">{info.degree}</span>
                  </div>
                  {detailedData?.grounding_strength !== undefined && detailedData?.grounding_strength !== null && (() => {
                    const grounding = formatGrounding(detailedData.grounding_strength);
                    return grounding && (
                      <div className="flex justify-between">
                        <span className="text-gray-400">Grounding:</span>
                        <span className="font-medium" style={{ color: grounding.color }}>
                          {grounding.emoji} {grounding.label} ({grounding.percentage})
                        </span>
                      </div>
                    );
                  })()}
                </div>
              )}
            </div>

            {/* Relationships Section */}
            {detailedData?.relationships && (
              <div className="border-b border-gray-700">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleSection('relationships');
                  }}
                  className="w-full px-4 py-2 flex items-center justify-between hover:bg-gray-700 transition-colors"
                >
                  <span className="font-medium text-sm text-gray-300">
                    Relationships ({detailedData.relationships.length})
                  </span>
                  {expandedSections.has('relationships') ? (
                    <ChevronDown size={16} className="text-gray-500" />
                  ) : (
                    <ChevronRight size={16} className="text-gray-500" />
                  )}
                </button>
                {expandedSections.has('relationships') && (
                  <div className="px-4 py-3 space-y-2 text-xs bg-gray-750">
                    {detailedData.relationships.slice(0, 20).map((rel: any, idx: number) => {
                      const relType = rel.rel_type || rel.type;
                      const color = getRelationshipTextColor(relType);
                      return (
                        <div key={`${rel.to_id || rel.target_id}-${relType}-${idx}`} className="text-gray-300">
                          <span className="font-medium" style={{ color }}>{relType}</span> → {rel.to_label || rel.target_label || rel.to_id}
                        </div>
                      );
                    })}
                    {detailedData.relationships.length > 20 && (
                      <div className="text-gray-500 italic">
                        +{detailedData.relationships.length - 20} more
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Evidence Section */}
            {detailedData?.instances && (
              <div className="border-b border-gray-700">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleSection('evidence');
                  }}
                  className="w-full px-4 py-2 flex items-center justify-between hover:bg-gray-700 transition-colors"
                >
                  <span className="font-medium text-sm text-gray-300">
                    Evidence ({detailedData.instances.length})
                  </span>
                  {expandedSections.has('evidence') ? (
                    <ChevronDown size={16} className="text-gray-500" />
                  ) : (
                    <ChevronRight size={16} className="text-gray-500" />
                  )}
                </button>
                {expandedSections.has('evidence') && (
                  <div className="px-4 py-3 space-y-2 text-xs bg-gray-750">
                    {detailedData.instances.slice(0, 10).map((instance: any, idx: number) => (
                      <div key={`${instance.instance_id || instance.id || idx}-${instance.quote?.substring(0, 20) || ''}`} className="text-gray-300 italic border-l-2 border-gray-600 pl-2">
                        "{instance.quote?.substring(0, 150)}{instance.quote?.length > 150 ? '...' : ''}"
                      </div>
                    ))}
                    {detailedData.instances.length > 10 && (
                      <div className="text-gray-500 italic">
                        +{detailedData.instances.length - 10} more
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {loading && (
              <div className="px-4 py-3 text-center text-sm text-gray-400">
                Loading details...
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

/**
 * Edge Info Box - Speech bubble style info display for edges
 */
interface EdgeInfoBoxProps {
  info: {
    linkKey: string;
    sourceId: string;
    targetId: string;
    type: string;
    confidence: number;
    category?: string;
    x: number;
    y: number;
  };
  zoomTransform: { x: number; y: number; k: number };
  onDismiss: () => void;
}

const EdgeInfoBox: React.FC<EdgeInfoBoxProps> = ({ info, zoomTransform, onDismiss }) => {
  // Apply zoom transform to graph coordinates
  const screenX = info.x * zoomTransform.k + zoomTransform.x;
  const screenY = info.y * zoomTransform.k + zoomTransform.y;

  return (
    <div
      className="absolute pointer-events-auto"
      style={{
        left: `${screenX}px`,
        top: `${screenY}px`,
        transform: 'translate(-50%, -100%)', // Position above the edge midpoint
        zIndex: 9999, // Ensure info box draws on top of everything
      }}
    >
      {/* Speech bubble pointer - always dark */}
      <div className="relative">
        <div
          className="absolute left-1/2 bottom-0 w-0 h-0"
          style={{
            borderLeft: '8px solid transparent',
            borderRight: '8px solid transparent',
            borderTop: '8px solid rgb(31, 41, 55)', // gray-800
            transform: 'translateX(-50%) translateY(100%)',
          }}
        />
        {/* Info box content - always dark theme */}
        <div
          className="bg-gray-800 rounded-lg shadow-xl border border-gray-600 px-4 py-3 cursor-pointer hover:shadow-2xl transition-shadow"
          onClick={(e) => {
            e.stopPropagation();
            onDismiss();
          }}
          style={{ minWidth: '200px' }}
        >
          <div className="space-y-2 text-sm">
            <div className="font-semibold text-gray-100 border-b border-gray-700 pb-2">
              Edge Information
            </div>
            <div className="space-y-1">
              <div className="flex justify-between">
                <span className="text-gray-400">Type:</span>
                <span className="font-medium text-gray-100">{info.type}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Confidence:</span>
                <span className="font-medium text-gray-100">
                  {(info.confidence * 100).toFixed(1)}%
                </span>
              </div>
              {info.category && (
                <div className="flex justify-between">
                  <span className="text-gray-400">Category:</span>
                  <span className="font-medium text-gray-100">{info.category}</span>
                </div>
              )}
              <div className="text-xs text-gray-400 pt-2 border-t border-gray-700">
                Click to dismiss
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

/**
 * Calculate node position for info boxes
 * Uses override position during drag, otherwise uses node's current position
 */
function calculateNodePosition(
  nodeId: string,
  nodes: D3Node[],
  draggedNodeId?: string,
  draggedNodeX?: number,
  draggedNodeY?: number
): { x: number; y: number } {
  // If this is the dragged node and we have override coordinates, use them
  if (nodeId === draggedNodeId && draggedNodeX !== undefined && draggedNodeY !== undefined) {
    return { x: draggedNodeX, y: draggedNodeY };
  }

  // Otherwise find the node and use its current position
  const node = nodes.find(n => n.id === nodeId);
  return {
    x: node?.x || 0,
    y: node?.y || 0,
  };
}

/**
 * Calculate edge midpoint position for info boxes
 * Handles both straight and curved edges (quadratic Bezier)
 */
function calculateEdgeMidpoint(
  link: D3Link,
  curveOffset: number,
  draggedNodeId?: string,
  draggedNodeX?: number,
  draggedNodeY?: number
): { x: number; y: number } {
  const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
  const targetId = typeof link.target === 'string' ? link.target : link.target.id;

  // Get source position (use drag position if this is the dragged node)
  const sourceX = sourceId === draggedNodeId && draggedNodeX !== undefined
    ? draggedNodeX
    : (typeof link.source === 'object' ? link.source.x || 0 : 0);
  const sourceY = sourceId === draggedNodeId && draggedNodeY !== undefined
    ? draggedNodeY
    : (typeof link.source === 'object' ? link.source.y || 0 : 0);

  // Get target position (use drag position if this is the dragged node)
  const targetX = targetId === draggedNodeId && draggedNodeX !== undefined
    ? draggedNodeX
    : (typeof link.target === 'object' ? link.target.x || 0 : 0);
  const targetY = targetId === draggedNodeId && draggedNodeY !== undefined
    ? draggedNodeY
    : (typeof link.target === 'object' ? link.target.y || 0 : 0);

  let midX, midY;

  if (curveOffset === 0) {
    // Straight line - simple midpoint
    midX = (sourceX + targetX) / 2;
    midY = (sourceY + targetY) / 2;
  } else {
    // Curved line - calculate point on quadratic Bezier curve at t=0.5
    const dx = targetX - sourceX;
    const dy = targetY - sourceY;
    const distance = Math.sqrt(dx * dx + dy * dy);

    if (distance < 0.01) {
      // Guard against zero or very small distance
      midX = (sourceX + targetX) / 2;
      midY = (sourceY + targetY) / 2;
    } else {
      // Calculate control point
      const perpX = -dy / distance;
      const perpY = dx / distance;
      const controlX = (sourceX + targetX) / 2 + perpX * curveOffset;
      const controlY = (sourceY + targetY) / 2 + perpY * curveOffset;

      // Evaluate quadratic Bezier at t=0.5
      const t = 0.5;
      midX = (1 - t) * (1 - t) * sourceX + 2 * (1 - t) * t * controlX + t * t * targetX;
      midY = (1 - t) * (1 - t) * sourceY + 2 * (1 - t) * t * controlY + t * t * targetY;
    }
  }

  return { x: midX, y: midY };
}

export const ForceGraph2D: React.FC<
  ExplorerProps<ForceGraph2DData, ForceGraph2DSettings>
> = ({ data, settings, onSettingsChange, onNodeClick, className }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const [dimensions, setDimensions] = useState({ width: 1000, height: 800 });
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<string | null>(null);
  const simulationRef = useRef<d3.Simulation<D3Node, D3Link> | null>(null);

  // Track zoom transform for info box positioning
  const [zoomTransform, setZoomTransform] = useState({ x: 0, y: 0, k: 1 });

  // Track active edge info boxes
  interface EdgeInfo {
    linkKey: string;
    sourceId: string;
    targetId: string;
    type: string;
    confidence: number;
    category?: string;
    x: number;
    y: number;
  }
  const [activeEdgeInfos, setActiveEdgeInfos] = useState<EdgeInfo[]>([]);

  // Track active node info boxes
  interface NodeInfo {
    nodeId: string;
    label: string;
    group: string;
    degree: number;
    x: number;
    y: number;
  }
  const [activeNodeInfos, setActiveNodeInfos] = useState<NodeInfo[]>([]);

  // Imperative function to apply gold ring - can be called anytime
  const applyGoldRing = useCallback((nodeId: string) => {
    if (!svgRef.current || !settings.interaction.showOriginNode) return;

    const svg = d3.select(svgRef.current);

    // Remove from previous node (restore brighter stroke)
    svg.selectAll('circle.origin-node')
      .interrupt()
      .attr('stroke', function() {
        const d = d3.select(this).datum() as D3Node;
        const color = nodeColors.get(d.id) || d.color;
        return d3.color(color)?.brighter(0.4).toString() || color;
      })
      .attr('stroke-width', 2)
      .attr('stroke-opacity', 1)
      .classed('origin-node', false);

    // Add to target node
    const targetCircle = svg.select<SVGCircleElement>(`circle[data-node-id="${nodeId}"]`);

    if (!targetCircle.empty()) {
      targetCircle
        .attr('stroke', '#FFD700')
        .attr('stroke-width', 4)
        .classed('origin-node', true);

      // Start pulsing animation
      const pulse = () => {
        targetCircle
          .transition()
          .duration(1000)
          .attr('stroke-width', 6)
          .attr('stroke-opacity', 0.6)
          .transition()
          .duration(1000)
          .attr('stroke-width', 4)
          .attr('stroke-opacity', 1)
          .on('end', pulse);
      };
      pulse();
    }
  }, [settings.interaction.showOriginNode]);

  // Node context menu state
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    nodeId: string;
    nodeLabel: string;
  } | null>(null);

  // Canvas context menu state
  const [canvasContextMenu, setCanvasContextMenu] = useState<{
    x: number;
    y: number;
  } | null>(null);

  // Grid visibility state
  const [showGrid, setShowGrid] = useState(false);

  // Right-click drag tracking for pan behavior
  const rightClickStartRef = useRef<{ x: number; y: number; time: number } | null>(null);
  const [isRightClickDragging, setIsRightClickDragging] = useState(false);

  // Get navigation state and settings from store
  const { originNodeId, setOriginNodeId, setFocusedNodeId, setGraphData, graphData } = useGraphStore();

  // Calculate neighbors for highlighting
  const neighbors = useMemo(() => {
    if (!hoveredNode || !settings.interaction.highlightNeighbors) return new Set<string>();
    return getNeighbors(hoveredNode, data.links);
  }, [hoveredNode, data.links, settings.interaction.highlightNeighbors]);

  // Calculate node colors based on nodeColorBy setting
  const nodeColors = useMemo(() => {
    const colors = new Map<string, string>();

    if (settings.visual.nodeColorBy === 'ontology') {
      // Color by ontology (default behavior from transformForD3)
      data.nodes.forEach(node => {
        colors.set(node.id, node.color);
      });
    } else if (settings.visual.nodeColorBy === 'degree') {
      // Color by degree (number of connections)
      const degrees = new Map<string, number>();
      data.links.forEach(link => {
        const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
        const targetId = typeof link.target === 'string' ? link.target : link.target.id;
        degrees.set(sourceId, (degrees.get(sourceId) || 0) + 1);
        degrees.set(targetId, (degrees.get(targetId) || 0) + 1);
      });

      const maxDegree = Math.max(...Array.from(degrees.values()), 1);
      const colorScale = d3.scaleSequential(d3.interpolateViridis).domain([0, maxDegree]);

      data.nodes.forEach(node => {
        const degree = degrees.get(node.id) || 0;
        colors.set(node.id, colorScale(degree));
      });
    } else if (settings.visual.nodeColorBy === 'centrality') {
      // Color by centrality (using degree as proxy for now)
      const degrees = new Map<string, number>();
      data.links.forEach(link => {
        const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
        const targetId = typeof link.target === 'string' ? link.target : link.target.id;
        degrees.set(sourceId, (degrees.get(sourceId) || 0) + 1);
        degrees.set(targetId, (degrees.get(targetId) || 0) + 1);
      });

      const maxDegree = Math.max(...Array.from(degrees.values()), 1);
      const colorScale = d3.scaleSequential(d3.interpolatePlasma).domain([0, maxDegree]);

      data.nodes.forEach(node => {
        const degree = degrees.get(node.id) || 0;
        colors.set(node.id, colorScale(degree));
      });
    }

    return colors;
  }, [data.nodes, data.links, settings.visual.nodeColorBy]);

  // Calculate edge colors based on edgeColorBy setting
  const linkColors = useMemo(() => {
    const colors = new Map<string, string>();

    if (settings.visual.edgeColorBy === 'confidence') {
      // Find min/max confidence values in the data for dynamic scaling
      const confidenceValues = data.links.map(link => link.value || 0.5);
      const minConfidence = Math.min(...confidenceValues);
      const maxConfidence = Math.max(...confidenceValues);

      // Use actual data range, or fallback to [0, 1] if all values are the same
      const domain = minConfidence === maxConfidence
        ? [0, 1]
        : [minConfidence, maxConfidence];

      const colorScale = d3.scaleSequential(d3.interpolateTurbo).domain(domain);

      data.links.forEach(link => {
        const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
        const targetId = typeof link.target === 'string' ? link.target : link.target.id;
        const linkKey = `${sourceId}->${targetId}-${link.type}`;
        const confidence = link.value || 0.5;
        colors.set(linkKey, colorScale(confidence));
      });
    } else {
      // Category or uniform coloring
      data.links.forEach(link => {
        const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
        const targetId = typeof link.target === 'string' ? link.target : link.target.id;
        const linkKey = `${sourceId}->${targetId}-${link.type}`;

        if (settings.visual.edgeColorBy === 'category') {
          // Color by category (default from transformForD3)
          colors.set(linkKey, link.color);
        } else if (settings.visual.edgeColorBy === 'uniform') {
          // Uniform gray color
          colors.set(linkKey, '#6b7280');
        }
      });
    }

    return colors;
  }, [data.links, settings.visual.edgeColorBy]);

  // Calculate curve offsets for multiple edges between same nodes
  // This ensures edges don't overlap and their labels are visible
  const linkCurveOffsets = useMemo(() => {
    const offsets = new Map<string, number>();

    // Group links by node pair (undirected)
    const linkGroups = new Map<string, D3Link[]>();

    data.links.forEach(link => {
      const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
      const targetId = typeof link.target === 'string' ? link.target : link.target.id;

      // Create a consistent key for the node pair (sorted to treat as undirected)
      const pairKey = [sourceId, targetId].sort().join('->');

      if (!linkGroups.has(pairKey)) {
        linkGroups.set(pairKey, []);
      }
      linkGroups.get(pairKey)!.push(link);
    });

    // Assign curve offsets to links in groups with multiple edges
    linkGroups.forEach(links => {
      if (links.length > 1) {
        // Multiple edges between same nodes - distribute them with curves
        links.forEach((link, index) => {
          const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
          const targetId = typeof link.target === 'string' ? link.target : link.target.id;
          const linkKey = `${sourceId}->${targetId}-${link.type}`;

          // Calculate offset: center around 0 and spread evenly
          const totalLinks = links.length;
          const offsetMultiplier = index - (totalLinks - 1) / 2;
          const curveStrength = 30; // Base curve distance

          offsets.set(linkKey, offsetMultiplier * curveStrength);
        });
      } else {
        // Single edge - no curve needed (offset = 0)
        const link = links[0];
        const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
        const targetId = typeof link.target === 'string' ? link.target : link.target.id;
        const linkKey = `${sourceId}->${targetId}-${link.type}`;
        offsets.set(linkKey, 0);
      }
    });

    return offsets;
  }, [data.links]);

  // Initialize and update force simulation
  useEffect(() => {
    if (!svgRef.current || !data.nodes.length) return;

    const svg = d3.select(svgRef.current);
    const width = dimensions.width;
    const height = dimensions.height;

    // Clear previous content
    svg.selectAll('*').remove();

    // Get canvas background color and derive grid colors
    const canvasColor = d3.color(
      window.getComputedStyle(svgRef.current).backgroundColor || '#ffffff'
    );
    // Make grid more visible: use brighter values and higher opacity
    const mainGridColor = canvasColor ? canvasColor.brighter(1.0).toString() : '#d0d0d0';
    const subGridColor = canvasColor ? canvasColor.brighter(0.5).toString() : '#e8e8e8';

    // Create grid group (separate from graph container, not affected by zoom)
    const gridGroup = svg.append('g').attr('class', 'grid-layer');

    // Grid spacing (in absolute coordinates)
    const mainGridSize = 100; // Main grid every 100 pixels
    const subGridSize = mainGridSize / 2; // Subdivision at 50 pixels

    // Create grid lines (will be updated during pan)
    if (showGrid) {
      // Calculate grid bounds (larger than viewport to account for pan)
      const gridMargin = 2000; // Extra space beyond viewport
      const gridMinX = -gridMargin;
      const gridMaxX = width + gridMargin;
      const gridMinY = -gridMargin;
      const gridMaxY = height + gridMargin;

      // Draw subdivision grid (50% brighter - more subtle)
      for (let x = Math.floor(gridMinX / subGridSize) * subGridSize; x <= gridMaxX; x += subGridSize) {
        if (x % mainGridSize !== 0) { // Skip main grid positions
          gridGroup
            .append('line')
            .attr('class', 'sub-grid-line')
            .attr('x1', x)
            .attr('y1', gridMinY)
            .attr('x2', x)
            .attr('y2', gridMaxY)
            .attr('stroke', subGridColor)
            .attr('stroke-width', 1)
            .attr('opacity', 0.6);
        }
      }

      for (let y = Math.floor(gridMinY / subGridSize) * subGridSize; y <= gridMaxY; y += subGridSize) {
        if (y % mainGridSize !== 0) { // Skip main grid positions
          gridGroup
            .append('line')
            .attr('class', 'sub-grid-line')
            .attr('x1', gridMinX)
            .attr('y1', y)
            .attr('x2', gridMaxX)
            .attr('y2', y)
            .attr('stroke', subGridColor)
            .attr('stroke-width', 1)
            .attr('opacity', 0.6);
        }
      }

      // Draw main grid (100% brighter - more visible)
      for (let x = Math.floor(gridMinX / mainGridSize) * mainGridSize; x <= gridMaxX; x += mainGridSize) {
        gridGroup
          .append('line')
          .attr('class', 'main-grid-line')
          .attr('x1', x)
          .attr('y1', gridMinY)
          .attr('x2', x)
          .attr('y2', gridMaxY)
          .attr('stroke', mainGridColor)
          .attr('stroke-width', 1)
          .attr('opacity', 0.8);
      }

      for (let y = Math.floor(gridMinY / mainGridSize) * mainGridSize; y <= gridMaxY; y += mainGridSize) {
        gridGroup
          .append('line')
          .attr('class', 'main-grid-line')
          .attr('x1', gridMinX)
          .attr('y1', y)
          .attr('x2', gridMaxX)
          .attr('y2', y)
          .attr('stroke', mainGridColor)
          .attr('stroke-width', 1)
          .attr('opacity', 0.8);
      }
    }

    // Create container groups
    const g = svg.append('g').attr('class', 'graph-container');
    const linksGroup = g.append('g').attr('class', 'links');
    const nodesGroup = g.append('g').attr('class', 'nodes');

    // Setup zoom behavior
    if (settings.interaction.enableZoom || settings.interaction.enablePan) {
      const zoom = d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.1, 10])
        .filter((event) => {
          // Allow zoom/pan with:
          // - Left mouse button (button 0)
          // - Right mouse button (button 2) - for right-click+drag pan
          // - Mouse wheel (type 'wheel')
          // - Touch events
          return !event.ctrlKey && (
            event.type === 'wheel' ||
            event.type === 'touchstart' ||
            event.type === 'touchmove' ||
            event.button === 0 ||
            event.button === 2
          );
        })
        .on('zoom', (event) => {
          g.attr('transform', event.transform);

          // Update grid position (only translate, no scale - gives "moving map" effect)
          if (showGrid) {
            gridGroup.attr('transform', `translate(${event.transform.x}, ${event.transform.y})`);
          }

          // Update zoom transform state for info box positioning
          setZoomTransform({
            x: event.transform.x,
            y: event.transform.y,
            k: event.transform.k,
          });
        });

      if (settings.interaction.enableZoom && settings.interaction.enablePan) {
        svg.call(zoom);
      } else if (settings.interaction.enableZoom) {
        svg.call(zoom).on('mousedown.zoom', null);
      } else if (settings.interaction.enablePan) {
        svg.call(zoom).on('wheel.zoom', null);
      }
    }

    // Check if nodes already have positions (from merge/previous simulation)
    const hasExistingPositions = data.nodes.some(n => n.x !== undefined && n.y !== undefined);

    // Create force simulation
    const simulation = d3
      .forceSimulation<D3Node>(data.nodes)
      .force(
        'link',
        d3
          .forceLink<D3Node, D3Link>(data.links)
          .id((d) => d.id)
          .distance(settings.physics.linkDistance)
      )
      .force('charge', d3.forceManyBody().strength(settings.physics.charge))
      .force('center', d3.forceCenter(width / 2, height / 2).strength(settings.physics.gravity))
      .force('collision', d3.forceCollide().radius((d) => ((d as D3Node).size || 10) * settings.visual.nodeSize + 5))
      .velocityDecay(1 - settings.physics.friction);

    // If nodes already have positions (merged graph), start with lower alpha
    // to avoid explosive force effects
    if (hasExistingPositions) {
      simulation.alpha(0.3).alphaDecay(0.05);
    }

    simulationRef.current = simulation;

    // Stop simulation if physics disabled
    if (!settings.physics.enabled) {
      simulation.stop();
    }

    // Draw links as paths (supports curves for multiple edges)
    const link = linksGroup
      .selectAll<SVGPathElement, D3Link>('path')
      .data(data.links)
      .join('path')
      .attr('stroke', (d) => {
        const sourceId = typeof d.source === 'string' ? d.source : d.source.id;
        const targetId = typeof d.target === 'string' ? d.target : d.target.id;
        const linkKey = `${sourceId}->${targetId}-${d.type}`;
        return linkColors.get(linkKey) || d.color;
      })
      .attr('stroke-width', (d) => (d.value || 1) * settings.visual.linkWidth)
      .attr('stroke-opacity', 0.6)
      .attr('fill', 'none')
      .attr('marker-end', (d) => {
        if (!settings.visual.showArrows) return '';
        // Use category-specific marker
        const category = d.category || 'default';
        return `url(#arrowhead-${category})`;
      })
      .attr('cursor', 'pointer')
      .attr('data-link-key', (d) => {
        const sourceId = typeof d.source === 'string' ? d.source : d.source.id;
        const targetId = typeof d.target === 'string' ? d.target : d.target.id;
        return `${sourceId}->${targetId}-${d.type}`;
      })
      .on('mouseenter', (_event, d) => {
        const sourceId = typeof d.source === 'string' ? d.source : d.source.id;
        const targetId = typeof d.target === 'string' ? d.target : d.target.id;
        setHoveredEdge(`${sourceId}->${targetId}-${d.type}`);
      })
      .on('mouseleave', () => {
        setHoveredEdge(null);
      })
      .on('click', (event, d) => {
        event.stopPropagation(); // Prevent triggering background click
        const sourceId = typeof d.source === 'string' ? d.source : d.source.id;
        const targetId = typeof d.target === 'string' ? d.target : d.target.id;
        const linkKey = `${sourceId}->${targetId}-${d.type}`;

        // Use functional setState to ensure we have the latest state
        setActiveEdgeInfos(prev => {
          const exists = prev.some(info => info.linkKey === linkKey);
          if (exists) return prev; // Don't create duplicate

          // Calculate edge midpoint (will be updated during simulation)
          const sourceX = typeof d.source === 'object' ? d.source.x || 0 : 0;
          const sourceY = typeof d.source === 'object' ? d.source.y || 0 : 0;
          const targetX = typeof d.target === 'object' ? d.target.x || 0 : 0;
          const targetY = typeof d.target === 'object' ? d.target.y || 0 : 0;

          const curveOffset = linkCurveOffsets.get(linkKey) || 0;
          let midX, midY;

          if (curveOffset === 0) {
            midX = (sourceX + targetX) / 2;
            midY = (sourceY + targetY) / 2;
          } else {
            const dx = targetX - sourceX;
            const dy = targetY - sourceY;
            const distance = Math.sqrt(dx * dx + dy * dy);

            // Guard against zero distance
            if (distance < 0.01) {
              midX = (sourceX + targetX) / 2;
              midY = (sourceY + targetY) / 2;
            } else {
              const perpX = -dy / distance;
              const perpY = dx / distance;
              const controlX = (sourceX + targetX) / 2 + perpX * curveOffset;
              const controlY = (sourceY + targetY) / 2 + perpY * curveOffset;
              const t = 0.5;
              midX = (1 - t) * (1 - t) * sourceX + 2 * (1 - t) * t * controlX + t * t * targetX;
              midY = (1 - t) * (1 - t) * sourceY + 2 * (1 - t) * t * controlY + t * t * targetY;
            }
          }

          // Create new edge info
          const newInfo: EdgeInfo = {
            linkKey,
            sourceId,
            targetId,
            type: d.type,
            confidence: d.value || 1.0,
            category: d.category, // Vocabulary category (derivation, modification, etc.)
            x: midX,
            y: midY,
          };

          return [...prev, newInfo];
        });
      });

    // Add arrow marker definitions - one per category color
    if (settings.visual.showArrows) {
      const defs = svg.append('defs');

      // Create markers for each category (uses shared config)
      Object.entries(categoryColors).forEach(([category, color]) => {
        defs
          .append('marker')
          .attr('id', `arrowhead-${category}`)
          .attr('viewBox', '-0 -5 10 10')
          .attr('refX', 8) // Position arrow tip at node boundary
          .attr('refY', 0)
          .attr('orient', 'auto')
          .attr('markerWidth', 4)
          .attr('markerHeight', 4)
          .append('path')
          .attr('d', 'M 0,-5 L 10,0 L 0,5')
          .attr('fill', color);
      });
    }

    // Add edge labels showing relationship types
    const edgeLabels = linksGroup
      .selectAll<SVGTextElement, D3Link>('text')
      .data(data.links)
      .join('text')
      .text((d) => d.type)
      .attr('font-size', 9)
      .attr('font-weight', 400)
      .attr('fill', (d) => {
        // Use edge color +40% brightness
        const baseColor = d.color || '#6b7280';
        return d3.color(baseColor)?.brighter(0.4).toString() || baseColor;
      })
      .attr('stroke', '#1a1a2e')
      .attr('stroke-width', 0.5)
      .attr('paint-order', 'stroke')
      .attr('text-anchor', 'middle')
      .attr('pointer-events', 'none')
      .style('user-select', 'none');

    // Draw nodes
    const node = nodesGroup
      .selectAll<SVGCircleElement, D3Node>('circle')
      .data(data.nodes)
      .join('circle')
      .attr('r', (d) => (d.size || 10) * settings.visual.nodeSize)
      .attr('fill', (d) => nodeColors.get(d.id) || d.color)
      .attr('stroke', (d) => {
        const color = nodeColors.get(d.id) || d.color;
        return d3.color(color)?.brighter(0.4).toString() || color;
      })
      .attr('stroke-width', 2)
      .attr('cursor', 'pointer')
      .attr('data-node-id', (d) => d.id) // Add ID for selection
      .on('click', (event, d) => {
        event.stopPropagation();
        setContextMenu(null); // Close any open context menu

        // Left click: Immediately show info box
        // Use functional setState to ensure we have the latest state
        setActiveNodeInfos(prev => {
          const exists = prev.some(info => info.nodeId === d.id);
          if (exists) return prev; // Don't create duplicate

          // Calculate degree (number of connections)
          const degree = data.links.filter(link => {
            const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
            const targetId = typeof link.target === 'string' ? link.target : link.target.id;
            return sourceId === d.id || targetId === d.id;
          }).length;

          // Create new node info
          const newInfo: NodeInfo = {
            nodeId: d.id,
            label: d.label,
            group: d.group || 'Unknown',
            degree,
            x: d.x || 0,
            y: d.y || 0,
          };

          return [...prev, newInfo];
        });
      })
      .on('contextmenu', (event, d) => {
        // Right-click: Show context menu
        event.preventDefault();
        setContextMenu({
          x: event.clientX,
          y: event.clientY,
          nodeId: d.id,
          nodeLabel: d.label,
        });
      })
      .on('mouseenter', (_event, d) => {
        setHoveredNode(d.id);
      })
      .on('mouseleave', () => {
        setHoveredNode(null);
      });

    // Add labels if enabled
    let labels: d3.Selection<SVGTextElement, D3Node, SVGGElement, unknown> | null = null;
    if (settings.visual.showLabels) {
      labels = nodesGroup
        .selectAll<SVGTextElement, D3Node>('text')
        .data(data.nodes)
        .join('text')
        .text((d) => d.label)
        .attr('font-size', 11)
        .attr('font-weight', 500)
        .attr('fill', '#fff')
        .attr('stroke', '#000')
        .attr('stroke-width', 0.3)
        .attr('paint-order', 'stroke')
        .attr('text-anchor', 'middle')
        .attr('pointer-events', 'none')
        .style('user-select', 'none');
    }

    // Enable dragging if configured
    if (settings.interaction.enableDrag) {
      const drag = d3
        .drag<SVGCircleElement, D3Node>()
        .on('start', (event, d) => {
          if (!event.active && settings.physics.enabled) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event, d) => {
          d.fx = event.x;
          d.fy = event.y;

          // Update node info box position immediately during drag
          setActiveNodeInfos(prevInfos =>
            prevInfos.map(info => {
              const { x, y } = calculateNodePosition(info.nodeId, data.nodes, d.id, event.x, event.y);
              return { ...info, x, y };
            })
          );

          // Update edge info boxes for edges connected to this node
          if (activeEdgeInfos.length > 0) {
            setActiveEdgeInfos(prevInfos =>
              prevInfos.map(info => {
                // Find the corresponding link
                const link = data.links.find(l => {
                  const sourceId = typeof l.source === 'string' ? l.source : l.source.id;
                  const targetId = typeof l.target === 'string' ? l.target : l.target.id;
                  return `${sourceId}->${targetId}-${l.type}` === info.linkKey;
                });

                if (!link) return info;

                // Check if this edge is connected to the dragged node
                const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
                const targetId = typeof link.target === 'string' ? link.target : link.target.id;

                if (sourceId !== d.id && targetId !== d.id) return info; // Not connected

                // Recalculate edge midpoint with updated node position
                const curveOffset = linkCurveOffsets.get(info.linkKey) || 0;
                const { x: midX, y: midY } = calculateEdgeMidpoint(link, curveOffset, d.id, event.x, event.y);

                return { ...info, x: midX, y: midY };
              })
            );
          }
        })
        .on('end', (event, _d) => {
          if (!event.active && settings.physics.enabled) simulation.alphaTarget(0);
          // Keep node fixed after dragging
          // To unfix: _d.fx = null; _d.fy = null;
        });

      node.call(drag);
    }

    // Update positions on simulation tick
    simulation.on('tick', () => {
      // Update curved paths for links
      link.attr('d', (d) => {
        const sourceNode = typeof d.source === 'object' ? d.source : null;
        const targetNode = typeof d.target === 'object' ? d.target : null;

        const sourceX = sourceNode?.x || 0;
        const sourceY = sourceNode?.y || 0;
        const targetX = targetNode?.x || 0;
        const targetY = targetNode?.y || 0;

        // Get target node radius (account for node size + stroke width)
        const targetRadius = targetNode ? ((targetNode.size || 10) * settings.visual.nodeSize) + 2 : 10;

        // Get curve offset for this link
        const sourceId = typeof d.source === 'string' ? d.source : d.source.id;
        const targetId = typeof d.target === 'string' ? d.target : d.target.id;
        const linkKey = `${sourceId}->${targetId}-${d.type}`;
        const curveOffset = linkCurveOffsets.get(linkKey) || 0;

        // Calculate direction and distance
        const dx = targetX - sourceX;
        const dy = targetY - sourceY;
        const distance = Math.sqrt(dx * dx + dy * dy);

        // Guard against zero or very small distance
        if (distance < 0.01) {
          return `M ${sourceX},${sourceY} L ${targetX},${targetY}`;
        }

        if (curveOffset === 0) {
          // Straight line - shorten to stop at target node boundary + 1 unit gap
          const unitX = dx / distance;
          const unitY = dy / distance;
          const adjustedTargetX = targetX - unitX * (targetRadius + 1);
          const adjustedTargetY = targetY - unitY * (targetRadius + 1);
          return `M ${sourceX},${sourceY} L ${adjustedTargetX},${adjustedTargetY}`;
        } else {
          // Quadratic curve for multiple edges
          // Perpendicular unit vector
          const perpX = -dy / distance;
          const perpY = dx / distance;

          // Control point at midpoint + perpendicular offset
          const midX = (sourceX + targetX) / 2;
          const midY = (sourceY + targetY) / 2;
          const controlX = midX + perpX * curveOffset;
          const controlY = midY + perpY * curveOffset;

          // Calculate tangent at curve endpoint (t=1)
          // For quadratic Bezier, tangent at t=1 is in direction from control point to target
          const tangentX = targetX - controlX;
          const tangentY = targetY - controlY;
          const tangentLength = Math.sqrt(tangentX * tangentX + tangentY * tangentY);

          // Guard against zero-length tangent
          if (tangentLength < 0.01) {
            return `M ${sourceX},${sourceY} Q ${controlX},${controlY} ${targetX},${targetY}`;
          }

          // Normalize tangent and shorten curve to stop at target node boundary + 1 unit gap
          const tangentUnitX = tangentX / tangentLength;
          const tangentUnitY = tangentY / tangentLength;
          const adjustedTargetX = targetX - tangentUnitX * (targetRadius + 1);
          const adjustedTargetY = targetY - tangentUnitY * (targetRadius + 1);

          return `M ${sourceX},${sourceY} Q ${controlX},${controlY} ${adjustedTargetX},${adjustedTargetY}`;
        }
      });

      node.attr('cx', (d) => d.x || 0).attr('cy', (d) => d.y || 0);

      // Update edge label positions and rotation to align with edges
      edgeLabels.attr('transform', (d) => {
        const sourceX = typeof d.source === 'object' ? d.source.x || 0 : 0;
        const sourceY = typeof d.source === 'object' ? d.source.y || 0 : 0;
        const targetX = typeof d.target === 'object' ? d.target.x || 0 : 0;
        const targetY = typeof d.target === 'object' ? d.target.y || 0 : 0;

        // Get curve offset for label positioning
        const sourceId = typeof d.source === 'string' ? d.source : d.source.id;
        const targetId = typeof d.target === 'string' ? d.target : d.target.id;
        const linkKey = `${sourceId}->${targetId}-${d.type}`;
        const curveOffset = linkCurveOffsets.get(linkKey) || 0;

        let midX, midY, angle;

        if (curveOffset === 0) {
          // Straight line - position at midpoint
          midX = (sourceX + targetX) / 2;
          midY = (sourceY + targetY) / 2;
          angle = Math.atan2(targetY - sourceY, targetX - sourceX) * (180 / Math.PI);
        } else {
          // Curved line - position at curve midpoint (on the quadratic curve)
          const dx = targetX - sourceX;
          const dy = targetY - sourceY;
          const distance = Math.sqrt(dx * dx + dy * dy);

          // Guard against zero or very small distance
          if (distance < 0.01) {
            // Fallback to straight line positioning
            midX = (sourceX + targetX) / 2;
            midY = (sourceY + targetY) / 2;
            angle = 0;
          } else {
            // Perpendicular unit vector
            const perpX = -dy / distance;
            const perpY = dx / distance;

            // Control point
            const controlX = (sourceX + targetX) / 2 + perpX * curveOffset;
            const controlY = (sourceY + targetY) / 2 + perpY * curveOffset;

            // Point on quadratic curve at t=0.5 (midpoint)
            const t = 0.5;
            midX = (1 - t) * (1 - t) * sourceX + 2 * (1 - t) * t * controlX + t * t * targetX;
            midY = (1 - t) * (1 - t) * sourceY + 2 * (1 - t) * t * controlY + t * t * targetY;

            // Calculate tangent angle at midpoint
            const tangentX = 2 * (1 - t) * (controlX - sourceX) + 2 * t * (targetX - controlX);
            const tangentY = 2 * (1 - t) * (controlY - sourceY) + 2 * t * (targetY - controlY);
            angle = Math.atan2(tangentY, tangentX) * (180 / Math.PI);
          }
        }

        // Keep text readable (don't flip upside down)
        if (angle > 90 || angle < -90) {
          angle += 180;
        }

        return `translate(${midX},${midY}) rotate(${angle})`;
      });

      // Update node label positions to follow nodes (centered below node)
      if (labels) {
        labels
          .attr('x', (d) => d.x || 0)
          .attr('y', (d) => (d.y || 0) + (d.size || 10) * settings.visual.nodeSize + 14);
      }

      // Update info box positions to follow edges
      if (activeEdgeInfos.length > 0) {
        setActiveEdgeInfos(prevInfos =>
          prevInfos.map(info => {
            // Find the corresponding link
            const link = data.links.find(l => {
              const sourceId = typeof l.source === 'string' ? l.source : l.source.id;
              const targetId = typeof l.target === 'string' ? l.target : l.target.id;
              return `${sourceId}->${targetId}-${l.type}` === info.linkKey;
            });

            if (!link) return info; // Link not found, keep old position

            const curveOffset = linkCurveOffsets.get(info.linkKey) || 0;
            const { x: midX, y: midY } = calculateEdgeMidpoint(link, curveOffset);

            return { ...info, x: midX, y: midY };
          })
        );
      }

      // Update info box positions to follow nodes
      if (activeNodeInfos.length > 0) {
        setActiveNodeInfos(prevInfos =>
          prevInfos.map(info => {
            const { x, y } = calculateNodePosition(info.nodeId, data.nodes);
            return { ...info, x, y };
          })
        );
      }
    });

    return () => {
      simulation.stop();
    };
  }, [data, settings, dimensions, onNodeClick, nodeColors, linkColors, linkCurveOffsets, showGrid]);

  // Update highlighting based on hover
  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);

    // Node highlighting
    svg.selectAll<SVGCircleElement, D3Node>('circle').attr('opacity', (d) => {
      if (!d || !hoveredNode) return 1;
      if (d.id === hoveredNode) return 1;
      if (neighbors.has(d.id)) return 1;
      return 0.2;
    });

    // Edge highlighting (paths not lines)
    svg.selectAll<SVGPathElement, D3Link>('path').each(function(link) {
      const path = d3.select(this);
      const linkKey = path.attr('data-link-key');

      // Guard against undefined link data during graph updates
      if (!link) {
        return;
      }

      if (hoveredEdge) {
        // Edge hover mode
        if (linkKey === hoveredEdge) {
          path.attr('stroke-opacity', 1).attr('stroke-width', ((link.value || 1) * settings.visual.linkWidth) * 2);
        } else {
          path.attr('stroke-opacity', 0.2).attr('stroke-width', (link.value || 1) * settings.visual.linkWidth);
        }
      } else if (hoveredNode) {
        // Node hover mode
        const sourceId = typeof link.source === 'string' ? link.source : link.source?.id;
        const targetId = typeof link.target === 'string' ? link.target : link.target?.id;
        if (!sourceId || !targetId) {
          path.attr('stroke-opacity', 0.6);
        } else if (sourceId === hoveredNode || targetId === hoveredNode) {
          path.attr('stroke-opacity', 1);
        } else {
          path.attr('stroke-opacity', 0.1);
        }
        path.attr('stroke-width', (link.value || 1) * settings.visual.linkWidth);
      } else {
        // No hover
        path.attr('stroke-opacity', 0.6).attr('stroke-width', (link.value || 1) * settings.visual.linkWidth);
      }
    });
  }, [hoveredNode, hoveredEdge, neighbors, settings.visual.linkWidth]);

  // "You Are Here" highlighting for origin node - async update after DOM ready
  useEffect(() => {
    if (!originNodeId || !settings.interaction.showOriginNode) return;

    // Wait for next frame to ensure DOM is fully rendered
    const rafId = requestAnimationFrame(() => {
      // Double-raf for extra safety (ensures layout is complete)
      requestAnimationFrame(() => {
        applyGoldRing(originNodeId);
      });
    });

    return () => {
      cancelAnimationFrame(rafId);
      // Cleanup: remove gold ring (restore brighter stroke)
      if (svgRef.current) {
        d3.select(svgRef.current)
          .selectAll('circle.origin-node')
          .interrupt()
          .attr('stroke', function() {
            const d = d3.select(this).datum() as D3Node;
            const color = nodeColors.get(d.id) || d.color;
            return d3.color(color)?.brighter(0.4).toString() || color;
          })
          .attr('stroke-width', 2)
          .attr('stroke-opacity', 1)
          .classed('origin-node', false);
      }
    };
  }, [originNodeId, settings.interaction.showOriginNode, data, applyGoldRing]);

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      if (svgRef.current) {
        const rect = svgRef.current.parentElement?.getBoundingClientRect();
        if (rect) {
          setDimensions({ width: rect.width, height: rect.height });
        }
      }
    };

    window.addEventListener('resize', handleResize);
    handleResize();

    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Helper: Merge new graph data with existing (deduplicate nodes/links)
  // Preserves existing node positions to prevent force explosion
  const mergeGraphData = useCallback((newData: any) => {
    if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {
      return newData;
    }

    // Create map of existing nodes with their positions
    const existingNodesMap = new Map(
      graphData.nodes.map((n: any) => [n.id, n])
    );

    const mergedNodes: any[] = [];

    // First, add all existing nodes (preserving positions)
    graphData.nodes.forEach((node: any) => {
      mergedNodes.push(node);
    });

    // Then add new nodes (they'll get positioned by force simulation)
    newData.nodes.forEach((node: any) => {
      if (!existingNodesMap.has(node.id)) {
        // New node - position it near the center of existing graph
        const existingPositions = graphData.nodes
          .filter((n: any) => n.x !== undefined && n.y !== undefined)
          .map((n: any) => ({ x: n.x, y: n.y }));

        if (existingPositions.length > 0) {
          // Calculate centroid of existing nodes
          const centerX = existingPositions.reduce((sum, p) => sum + p.x, 0) / existingPositions.length;
          const centerY = existingPositions.reduce((sum, p) => sum + p.y, 0) / existingPositions.length;

          // Add small random offset to avoid exact overlap
          node.x = centerX + (Math.random() - 0.5) * 50;
          node.y = centerY + (Math.random() - 0.5) * 50;
        }

        mergedNodes.push(node);
      }
    });

    // Merge links (deduplicate by source -> target -> type)
    const existingLinks = graphData.links || [];
    const existingLinkKeys = new Set(
      existingLinks.map((l: any) => {
        const sourceId = typeof l.source === 'string' ? l.source : l.source.id;
        const targetId = typeof l.target === 'string' ? l.target : l.target.id;
        return `${sourceId}->${targetId}:${l.type}`;
      })
    );
    const mergedLinks = [...existingLinks];

    const newLinks = newData.links || [];
    newLinks.forEach((link: any) => {
      const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
      const targetId = typeof link.target === 'string' ? link.target : link.target.id;
      const key = `${sourceId}->${targetId}:${link.type}`;
      if (!existingLinkKeys.has(key)) {
        mergedLinks.push(link);
        existingLinkKeys.add(key);
      }
    });

    return {
      nodes: mergedNodes,
      links: mergedLinks,
    };
  }, [graphData]);

  // Handler: Follow concept (replace graph)
  // Matches SearchBar loadConcept('clean') pattern
  const handleFollowConcept = useCallback(async (nodeId: string) => {
    try {
      const response = await apiClient.getSubgraph({
        center_concept_id: nodeId,
        depth: 1, // Load immediate neighbors (same as SearchBar concept mode)
      });

      // Transform API data to D3 format
      const transformedData = transformForD3(response.nodes, response.links);

      // Replace graph (clean mode)
      setGraphData(transformedData);
      setFocusedNodeId(nodeId);
    } catch (error: any) {
      console.error('Failed to follow concept:', error);
      alert(`Failed to follow concept: ${error.message || 'Unknown error'}`);
    }
  }, [setGraphData, setFocusedNodeId]);

  // Handler: Add concept to graph (merge)
  // Matches SearchBar loadConcept('add') pattern
  const handleAddToGraph = useCallback(async (nodeId: string) => {
    try {
      const response = await apiClient.getSubgraph({
        center_concept_id: nodeId,
        depth: 1, // Load immediate neighbors (same as SearchBar concept mode)
      });

      // Transform API data to D3 format
      const transformedData = transformForD3(response.nodes, response.links);

      // Merge with existing graph (add mode)
      setGraphData(mergeGraphData(transformedData));
      setFocusedNodeId(nodeId);
    } catch (error: any) {
      console.error('Failed to add concept to graph:', error);
      alert(`Failed to add concept to graph: ${error.message || 'Unknown error'}`);
    }
  }, [mergeGraphData, setGraphData, setFocusedNodeId]);

  // Pin/Unpin node functionality
  const isPinned = useCallback((nodeId: string): boolean => {
    const node = data.nodes.find(n => n.id === nodeId);
    return node?.fx !== undefined && node?.fx !== null;
  }, [data.nodes]);

  const togglePinNode = useCallback((nodeId: string) => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    const nodeSelection = svg.select<SVGCircleElement>(`circle[data-node-id="${nodeId}"]`);

    if (!nodeSelection.empty()) {
      const nodeData = nodeSelection.datum() as D3Node;

      if (nodeData.fx !== undefined && nodeData.fx !== null) {
        // Unpin: remove fixed position
        nodeData.fx = null;
        nodeData.fy = null;
      } else {
        // Pin: set fixed position to current position
        nodeData.fx = nodeData.x;
        nodeData.fy = nodeData.y;
      }

      // Restart simulation briefly to apply changes
      if (settings.physics.enabled && simulationRef.current) {
        simulationRef.current.alpha(0.1).restart();
      }
    }
  }, [data.nodes, settings.physics.enabled]);

  const unpinAllNodes = useCallback(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);

    // Unpin all nodes
    svg.selectAll<SVGCircleElement, D3Node>('circle[data-node-id]').each(function() {
      const nodeData = d3.select(this).datum() as D3Node;
      nodeData.fx = null;
      nodeData.fy = null;
    });

    // Restart simulation to let forces take over
    if (settings.physics.enabled && simulationRef.current) {
      simulationRef.current.alpha(0.3).restart();
    }
  }, [settings.physics.enabled]);

  // Context menu items
  const contextMenuItems: ContextMenuItem[] = contextMenu
    ? [
        // Contextual mark/unmark location
        originNodeId === contextMenu.nodeId
          ? {
              label: 'Unmark Location',
              icon: MapPinOff,
              onClick: () => {
                setOriginNodeId(null);
                setContextMenu(null);
              },
            }
          : {
              label: 'Mark Location',
              icon: MapPin,
              onClick: () => {
                setOriginNodeId(contextMenu.nodeId);
                applyGoldRing(contextMenu.nodeId);
                setContextMenu(null);
              },
            },
        // Node submenu with pin operations
        {
          label: 'Node',
          icon: Circle,
          submenu: [
            // Contextual pin/unpin node
            isPinned(contextMenu.nodeId)
              ? {
                  label: 'Unpin Node',
                  icon: PinOff,
                  onClick: () => {
                    togglePinNode(contextMenu.nodeId);
                    setContextMenu(null);
                  },
                }
              : {
                  label: 'Pin Node',
                  icon: Pin,
                  onClick: () => {
                    togglePinNode(contextMenu.nodeId);
                    setContextMenu(null);
                  },
                },
            {
              label: 'Unpin All',
              icon: PinOff,
              onClick: () => {
                unpinAllNodes();
                setContextMenu(null);
              },
            },
          ],
        },
        {
          label: `Follow "${contextMenu.nodeLabel}"`,
          icon: ArrowRight,
          onClick: () => {
            handleFollowConcept(contextMenu.nodeId);
            setContextMenu(null);
          },
        },
        {
          label: `Add "${contextMenu.nodeLabel}" to Graph`,
          icon: Plus,
          onClick: () => {
            handleAddToGraph(contextMenu.nodeId);
            setContextMenu(null);
          },
        },
      ]
    : [];

  // Dismiss edge info box
  const handleDismissEdgeInfo = useCallback((linkKey: string) => {
    setActiveEdgeInfos(prev => prev.filter(info => info.linkKey !== linkKey));
  }, []);

  // Dismiss node info box
  const handleDismissNodeInfo = useCallback((nodeId: string) => {
    setActiveNodeInfos(prev => prev.filter(info => info.nodeId !== nodeId));
  }, []);

  return (
    <div className={`relative w-full h-full ${className || ''}`}>
      <svg
        ref={svgRef}
        width={dimensions.width}
        height={dimensions.height}
        className="bg-white dark:bg-gray-900"
        onClick={() => {
          // Close context menus when clicking on canvas background
          setContextMenu(null);
          setCanvasContextMenu(null);
        }}
        onMouseDown={(e) => {
          // Track right-click start position for drag detection
          if (e.button === 2) { // Right mouse button
            rightClickStartRef.current = {
              x: e.clientX,
              y: e.clientY,
              time: Date.now(),
            };
          }
        }}
        onMouseMove={(e) => {
          // Check if right-click is being dragged
          if (rightClickStartRef.current && e.buttons === 2) { // Right button still pressed
            const dx = e.clientX - rightClickStartRef.current.x;
            const dy = e.clientY - rightClickStartRef.current.y;
            const distance = Math.sqrt(dx * dx + dy * dy);

            // If moved more than 10 pixels, treat as pan (not context menu)
            if (distance > 10) {
              setIsRightClickDragging(true);
            }
          }
        }}
        onMouseUp={(e) => {
          // Reset right-click drag tracking
          if (e.button === 2) { // Right mouse button released
            rightClickStartRef.current = null;
            setIsRightClickDragging(false);
          }
        }}
        onContextMenu={(e) => {
          e.preventDefault(); // Always prevent default browser context menu

          // Only show canvas context menu if NOT dragging
          // (nodes/edges have their own context menu handlers that stopPropagation)
          if (!isRightClickDragging) {
            setContextMenu(null); // Close node context menu if open
            setCanvasContextMenu({
              x: e.clientX,
              y: e.clientY,
            });
          } else {
            // Was dragging, so don't show context menu
            setIsRightClickDragging(false);
          }
        }}
      />

      {/* Legend Panel */}
      <Legend data={data} nodeColorMode={settings.visual.nodeColorBy} />

      {/* Node count indicator */}
      <div className="absolute top-4 right-4 bg-white dark:bg-gray-800 rounded-lg shadow-lg px-3 py-2 text-sm">
        <div className="text-gray-600 dark:text-gray-400">
          {data.nodes.length} nodes • {data.links.length} edges
        </div>
      </div>

      {/* Settings Panel */}
      {onSettingsChange && (
        <CanvasSettingsPanel settings={settings} onChange={onSettingsChange} />
      )}

      {/* Node Context Menu */}
      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          items={contextMenuItems}
          onClose={() => setContextMenu(null)}
        />
      )}

      {/* Canvas Context Menu */}
      {canvasContextMenu && (
        <ContextMenu
          x={canvasContextMenu.x}
          y={canvasContextMenu.y}
          items={[
            showGrid
              ? {
                  label: 'Hide Grid',
                  icon: EyeOff,
                  onClick: () => {
                    setShowGrid(false);
                    setCanvasContextMenu(null);
                  },
                }
              : {
                  label: 'Show Grid',
                  icon: Grid3x3,
                  onClick: () => {
                    setShowGrid(true);
                    setCanvasContextMenu(null);
                  },
                },
          ]}
          onClose={() => setCanvasContextMenu(null)}
        />
      )}

      {/* Edge Info Boxes */}
      <div className="absolute inset-0 pointer-events-none" style={{ zIndex: 1000 }}>
        {activeEdgeInfos.map(info => (
          <EdgeInfoBox
            key={info.linkKey}
            info={info}
            zoomTransform={zoomTransform}
            onDismiss={() => handleDismissEdgeInfo(info.linkKey)}
          />
        ))}
      </div>

      {/* Node Info Boxes */}
      <div className="absolute inset-0 pointer-events-none" style={{ zIndex: 1000 }}>
        {activeNodeInfos.map(info => (
          <NodeInfoBox
            key={info.nodeId}
            info={info}
            zoomTransform={zoomTransform}
            onDismiss={() => handleDismissNodeInfo(info.nodeId)}
          />
        ))}
      </div>
    </div>
  );
};
