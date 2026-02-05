/**
 * Document Explorer — Multi-Document Concept Graph
 *
 * Force-directed graph showing concepts from multiple documents.
 * Documents are "celebrity" hub nodes; concepts cluster around them.
 *
 * Three node types:
 * - Document (golden, large) — hub nodes with high charge
 * - Query concept (amber) — from the saved exploration query
 * - Extended concept (indigo) — connected to documents but not in query
 *
 * Focus mode: clicking a document dims everything else.
 */

import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import * as d3 from 'd3';
import type { ExplorerProps } from '../../types/explorer';
import type {
  DocumentExplorerSettings,
  DocumentExplorerData,
  DocNodeType,
} from './types';
import { useThemeStore } from '../../store/themeStore';
import {
  NodeInfoBox,
  StatsPanel,
  PanelStack,
  LABEL_FONTS,
} from '../common';

// ---------------------------------------------------------------------------
// Colors
// ---------------------------------------------------------------------------

const COLORS: Record<DocNodeType, { fill: string; stroke: string }> = {
  'document':         { fill: '#f59e0b', stroke: '#fbbf24' },
  'query-concept':    { fill: '#d97706', stroke: '#fcd34d' },
  'extended-concept': { fill: '#6366f1', stroke: '#818cf8' },
};

const DIMMED_OPACITY = 0.08;

// ---------------------------------------------------------------------------
// Force simulation types
// ---------------------------------------------------------------------------

interface SimNode extends d3.SimulationNodeDatum {
  id: string;
  label: string;
  type: DocNodeType;
  documentIds: string[];
  size: number;
}

interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  type: string;
  visible: boolean;
}

// ---------------------------------------------------------------------------
// Extended props (workspace passes focus state)
// ---------------------------------------------------------------------------

interface DocumentExplorerExtraProps {
  focusedDocumentId?: string | null;
  onFocusChange?: (docId: string | null) => void;
  onViewDocument?: (docId: string) => void;
}

export const DocumentExplorer: React.FC<
  ExplorerProps<DocumentExplorerData, DocumentExplorerSettings> & DocumentExplorerExtraProps
> = ({ data, settings, onNodeClick, className, focusedDocumentId, onFocusChange, onViewDocument }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedConceptId, setSelectedConceptId] = useState<string | null>(null);
  const [zoomTransform, setZoomTransform] = useState({ x: 0, y: 0, k: 1 });
  const simulationRef = useRef<d3.Simulation<SimNode, SimLink> | null>(null);

  const { appliedTheme: theme } = useThemeStore();

  // Focused document's concept set (for dimming)
  const focusedConceptSet = useMemo(() => {
    if (!focusedDocumentId || !data) return null;
    const doc = data.documents.find(d => d.id === focusedDocumentId);
    if (!doc) return null;
    return new Set(doc.conceptIds);
  }, [focusedDocumentId, data]);

  // Build simulation data
  const { simNodes, simLinks } = useMemo(() => {
    if (!data) return { simNodes: [] as SimNode[], simLinks: [] as SimLink[] };

    const simNodes: SimNode[] = data.nodes.map(n => ({
      id: n.id,
      label: n.label,
      type: n.type,
      documentIds: n.documentIds,
      size: n.type === 'document' ? settings.layout.documentSize : n.size * settings.visual.nodeSize,
    }));

    const nodeIds = new Set(simNodes.map(n => n.id));

    const simLinks: SimLink[] = data.links
      .filter(l => nodeIds.has(l.source) && nodeIds.has(l.target))
      .map(l => ({
        source: l.source,
        target: l.target,
        type: l.type,
        visible: l.visible,
      }));

    return { simNodes, simLinks };
  }, [data, settings.layout.documentSize, settings.visual.nodeSize]);

  // Visible stats (exclude clustering links)
  const visibleLinkCount = useMemo(
    () => simLinks.filter(l => l.visible).length,
    [simLinks]
  );

  // Track container dimensions
  useEffect(() => {
    if (!svgRef.current) return;
    const container = svgRef.current.parentElement;
    if (!container) return;

    const updateDimensions = () => {
      const rect = container.getBoundingClientRect();
      setDimensions({ width: rect.width, height: rect.height });
    };

    updateDimensions();
    const observer = new ResizeObserver(updateDimensions);
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  // Is a node visible in focus mode?
  const isNodeInFocus = useCallback((node: SimNode): boolean => {
    if (!focusedConceptSet) return true; // no focus → all visible
    if (node.id === focusedDocumentId) return true;
    if (node.type === 'document') return false; // other documents dimmed
    return focusedConceptSet.has(node.id);
  }, [focusedConceptSet, focusedDocumentId]);

  // Is a link visible in focus mode?
  const isLinkInFocus = useCallback((link: SimLink): boolean => {
    if (!focusedConceptSet) return true;
    const sourceId = (link.source as SimNode).id ?? link.source;
    const targetId = (link.target as SimNode).id ?? link.target;
    const sInFocus = sourceId === focusedDocumentId || focusedConceptSet.has(sourceId as string);
    const tInFocus = targetId === focusedDocumentId || focusedConceptSet.has(targetId as string);
    return sInFocus && tInFocus;
  }, [focusedConceptSet, focusedDocumentId]);

  // Main D3 rendering + force simulation
  useEffect(() => {
    if (!svgRef.current || simNodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    const { width, height } = dimensions;

    svg.selectAll('*').remove();

    const g = svg.append('g').attr('class', 'main-group');

    // Zoom/pan
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.05, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform.toString());
        setZoomTransform({ x: event.transform.x, y: event.transform.y, k: event.transform.k });
      });

    if (settings.interaction.enableZoom || settings.interaction.enablePan) {
      svg.call(zoom);
    }

    // Click background to clear focus
    svg.on('click', () => {
      onFocusChange?.(null);
      setSelectedConceptId(null);
    });

    // Edges (only visible ones rendered)
    const linkGroup = g.append('g').attr('class', 'links');
    const linkElements = linkGroup.selectAll<SVGLineElement, SimLink>('line')
      .data(simLinks.filter(l => l.visible))
      .join('line')
      .attr('stroke', theme === 'dark' ? 'rgba(107, 114, 128, 0.35)' : 'rgba(85, 85, 85, 0.25)')
      .attr('stroke-width', 0.8);

    // Nodes
    const nodeGroup = g.append('g').attr('class', 'nodes');
    const nodeElements = nodeGroup.selectAll<SVGGElement, SimNode>('g')
      .data(simNodes)
      .join('g')
      .style('cursor', 'pointer')
      .on('mouseenter', (_event: MouseEvent, d: SimNode) => {
        if (settings.interaction.highlightOnHover) setHoveredNode(d.id);
      })
      .on('mouseleave', () => setHoveredNode(null))
      .on('click', (event: MouseEvent, d: SimNode) => {
        event.stopPropagation();
        if (d.type === 'document') {
          onFocusChange?.(d.id);
          onNodeClick?.(d.id);
        } else {
          setSelectedConceptId(d.id);
        }
      })
      .on('dblclick', (event: MouseEvent, d: SimNode) => {
        event.stopPropagation();
        if (d.type === 'document') {
          onViewDocument?.(d.id);
        }
      });

    // Node circles
    nodeElements.append('circle')
      .attr('r', (d: SimNode) => d.size)
      .attr('fill', (d: SimNode) => COLORS[d.type].fill)
      .attr('stroke', (d: SimNode) => COLORS[d.type].stroke)
      .attr('stroke-width', (d: SimNode) => d.type === 'document' ? 3 : 1.5)
      .attr('opacity', (d: SimNode) => d.type === 'document' ? 0.95 : 0.8);

    // Document icon (file shape)
    nodeElements.filter((d: SimNode) => d.type === 'document')
      .append('path')
      .attr('d', (d: SimNode) => {
        const s = d.size * 0.45;
        return `M${-s / 2},${-s / 2} L${s / 3},${-s / 2} L${s / 2},${-s / 3} L${s / 2},${s / 2} L${-s / 2},${s / 2} Z`;
      })
      .attr('fill', '#fff')
      .attr('opacity', 0.9);

    // Labels
    if (settings.visual.showLabels) {
      nodeElements.append('text')
        .text((d: SimNode) => d.label)
        .attr('dy', (d: SimNode) => d.size + 12)
        .attr('text-anchor', 'middle')
        .attr('font-family', LABEL_FONTS.family)
        .attr('font-size', (d: SimNode) => {
          if (d.type === 'document') return '11px';
          return d.type === 'query-concept' ? '9px' : '8px';
        })
        .attr('font-weight', (d: SimNode) => d.type === 'document' ? '600' : '400')
        .attr('fill', (d: SimNode) => {
          if (d.type === 'document') return theme === 'dark' ? '#fbbf24' : '#d97706';
          return theme === 'dark' ? '#d1d5db' : '#4b5563';
        })
        .attr('pointer-events', 'none')
        .style('text-shadow', theme === 'dark'
          ? '0 1px 0 #000, 0 -1px 0 #000, 1px 0 0 #000, -1px 0 0 #000'
          : '0 1px 0 #fff, 0 -1px 0 #fff, 1px 0 0 #fff, -1px 0 0 #fff'
        );
    }

    // Force simulation — "celebrity hub" pattern
    const simulation = d3.forceSimulation<SimNode, SimLink>(simNodes)
      .force('link',
        d3.forceLink<SimNode, SimLink>(simLinks)
          .id(d => d.id)
          .distance((l) => (l as SimLink).visible ? 80 : 40)
          .strength((l) => (l as SimLink).visible ? 0.3 : 0.05)
      )
      .force('charge', d3.forceManyBody<SimNode>().strength((d) => {
        if (d.type === 'document') return -500;
        if (d.type === 'query-concept') return -150;
        return -100;
      }))
      .force('center', d3.forceCenter(width / 2, height / 2).strength(0.05))
      .force('collision', d3.forceCollide<SimNode>().radius((d) => {
        if (d.type === 'document') return d.size + 20;
        return d.size + 6;
      }));

    simulationRef.current = simulation;

    simulation.on('tick', () => {
      linkElements
        .attr('x1', d => (d.source as SimNode).x || 0)
        .attr('y1', d => (d.source as SimNode).y || 0)
        .attr('x2', d => (d.target as SimNode).x || 0)
        .attr('y2', d => (d.target as SimNode).y || 0);

      nodeElements
        .attr('transform', d => `translate(${d.x || 0},${d.y || 0})`);
    });

    // Drag
    const drag = d3.drag<SVGGElement, SimNode>()
      .on('start', (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on('drag', (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on('end', (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });

    nodeElements.call(drag);

    return () => {
      simulation.stop();
    };
  }, [simNodes, simLinks, dimensions, settings, theme, onNodeClick, onFocusChange, onViewDocument]);

  // Focus mode: update opacity when focusedDocumentId changes
  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);

    svg.selectAll<SVGGElement, SimNode>('g.nodes g')
      .attr('opacity', (d: SimNode) => isNodeInFocus(d) ? 1 : DIMMED_OPACITY);

    svg.selectAll<SVGLineElement, SimLink>('g.links line')
      .attr('opacity', (d: SimLink) => isLinkInFocus(d) ? 0.6 : DIMMED_OPACITY);
  }, [focusedDocumentId, focusedConceptSet, isNodeInFocus, isLinkInFocus]);

  // Hover highlighting
  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll<SVGCircleElement, SimNode>('g.nodes g circle')
      .attr('stroke-width', (d: SimNode) => {
        if (d.id === hoveredNode || d.id === selectedConceptId) return 3;
        return d.type === 'document' ? 3 : 1.5;
      })
      .attr('stroke', (d: SimNode) => {
        if (d.id === hoveredNode || d.id === selectedConceptId) return '#fff';
        return COLORS[d.type].stroke;
      });
  }, [hoveredNode, selectedConceptId]);

  // Selected concept data for NodeInfoBox
  const selectedNodeData = useMemo(() => {
    if (!selectedConceptId) return null;
    return simNodes.find(n => n.id === selectedConceptId);
  }, [selectedConceptId, simNodes]);

  return (
    <div className={`relative w-full h-full overflow-hidden ${className || ''}`}>
      <svg
        ref={svgRef}
        width={dimensions.width}
        height={dimensions.height}
        className={theme === 'dark' ? 'bg-gray-900' : 'bg-gray-50'}
      />

      <PanelStack side="right">
        <StatsPanel
          nodeCount={simNodes.length}
          edgeCount={visibleLinkCount}
        />
      </PanelStack>

      {/* Legend */}
      <div className="absolute bottom-4 left-4 bg-card/90 backdrop-blur-sm border border-border rounded-lg p-3 text-xs space-y-1.5">
        <div className="flex items-center gap-2">
          <span className="inline-block w-3 h-3 rounded-full" style={{ background: COLORS.document.fill }} />
          <span>Document</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: COLORS['query-concept'].fill }} />
          <span>Query concept</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-block w-2 h-2 rounded-full" style={{ background: COLORS['extended-concept'].fill }} />
          <span>Extended concept</span>
        </div>
      </div>

      {/* NodeInfoBox for selected concept */}
      {selectedNodeData && selectedNodeData.type !== 'document' && (
        <NodeInfoBox
          info={{
            nodeId: selectedConceptId!,
            label: selectedNodeData.label || 'Unknown',
            group: selectedNodeData.type === 'query-concept' ? 'query match' : 'document extended',
            degree: simLinks.filter(l =>
              l.visible && (
                ((l.source as SimNode).id === selectedConceptId) ||
                ((l.target as SimNode).id === selectedConceptId)
              )
            ).length,
            x: (selectedNodeData.x || 0) * zoomTransform.k + zoomTransform.x,
            y: (selectedNodeData.y || 0) * zoomTransform.k + zoomTransform.y,
          }}
          onDismiss={() => setSelectedConceptId(null)}
        />
      )}
    </div>
  );
};

export default DocumentExplorer;
