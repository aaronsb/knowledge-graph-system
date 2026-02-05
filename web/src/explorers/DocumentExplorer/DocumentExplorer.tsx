/**
 * Document Explorer — Multi-Document Concept Graph
 *
 * Force-directed graph showing concepts from multiple documents.
 * Documents are "celebrity" hub nodes; concepts cluster around them.
 *
 * Physics model:
 * - Initial load → simulation runs → settles → stops. Done.
 * - Drag moves a node manually (no physics). Connected links follow.
 * - "Reheat" button → one-shot simulation restart → settles → stops.
 * - Pan, zoom, click, focus, settings changes — never restart physics.
 *
 * Callback refs prevent the simulation from restarting when parent re-renders.
 */

import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import * as d3 from 'd3';
import { RotateCcw } from 'lucide-react';
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
  /** Passage search rings — Map<nodeId, Array<{ color, hitCount, maxHitCount, bestSimilarity }>> */
  passageRings?: Map<string, Array<{ color: string; hitCount: number; maxHitCount: number; bestSimilarity: number }>>;
  /** Color → query text lookup for labeling rings in info dialogs. */
  queryColorLabels?: Map<string, string>;
}

export const DocumentExplorer: React.FC<
  ExplorerProps<DocumentExplorerData, DocumentExplorerSettings> & DocumentExplorerExtraProps
> = ({ data, settings, onNodeClick, className, focusedDocumentId, onFocusChange, onViewDocument, passageRings, queryColorLabels }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedConceptId, setSelectedConceptId] = useState<string | null>(null);
  const [zoomTransform, setZoomTransform] = useState({ x: 0, y: 0, k: 1 });
  const simulationRef = useRef<d3.Simulation<SimNode, SimLink> | null>(null);

  // Physics status indicator
  const [physicsActive, setPhysicsActive] = useState(true);

  // Refs for SVG selections (used by drag handler and settings effects)
  const linkElementsRef = useRef<d3.Selection<SVGLineElement, SimLink, SVGGElement, unknown> | null>(null);
  const nodeElementsRef = useRef<d3.Selection<SVGGElement, SimNode, SVGGElement, unknown> | null>(null);

  // -----------------------------------------------------------------------
  // Callback refs — keep current without causing simulation restarts.
  // The simulation effect reads these via .current, so it doesn't depend
  // on the callback identity and won't restart when parent re-renders.
  // -----------------------------------------------------------------------
  const onNodeClickRef = useRef(onNodeClick);
  const onFocusChangeRef = useRef(onFocusChange);
  const onViewDocumentRef = useRef(onViewDocument);
  const settingsRef = useRef(settings);

  useEffect(() => { onNodeClickRef.current = onNodeClick; }, [onNodeClick]);
  useEffect(() => { onFocusChangeRef.current = onFocusChange; }, [onFocusChange]);
  useEffect(() => { onViewDocumentRef.current = onViewDocument; }, [onViewDocument]);
  useEffect(() => { settingsRef.current = settings; }, [settings]);

  const { appliedTheme: theme } = useThemeStore();

  // Focused document's concept set (for dimming)
  const focusedConceptSet = useMemo(() => {
    if (!focusedDocumentId || !data) return null;
    const doc = data.documents.find(d => d.id === focusedDocumentId);
    if (!doc) return null;
    return new Set(doc.conceptIds);
  }, [focusedDocumentId, data]);

  // Build simulation data — depends only on data, NOT settings.
  // Settings-driven sizes are computed at render time via settingsRef so
  // changing a slider never restarts the simulation.
  const { simNodes, simLinks } = useMemo(() => {
    if (!data) return { simNodes: [] as SimNode[], simLinks: [] as SimLink[] };

    const simNodes: SimNode[] = data.nodes.map(n => ({
      id: n.id,
      label: n.label,
      type: n.type,
      documentIds: n.documentIds,
      size: n.size,  // base size — render-time scaling applied separately
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
  }, [data]);

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
    if (!focusedConceptSet) return true;
    if (node.id === focusedDocumentId) return true;
    if (node.type === 'document') return false;
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

  // Shared tick renderer — updates SVG positions from node data
  const renderPositions = useCallback(() => {
    linkElementsRef.current
      ?.attr('x1', d => (d.source as SimNode).x || 0)
      .attr('y1', d => (d.source as SimNode).y || 0)
      .attr('x2', d => (d.target as SimNode).x || 0)
      .attr('y2', d => (d.target as SimNode).y || 0);

    nodeElementsRef.current
      ?.attr('transform', d => `translate(${d.x || 0},${d.y || 0})`);
  }, []);

  // -----------------------------------------------------------------------
  // Main D3 rendering + force simulation
  //
  // Dependencies: simNodes, simLinks, dimensions, theme.
  // NOT: settings (ref), callbacks (refs). This prevents restarts from
  // settings changes, focus changes, or parent re-renders.
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (!svgRef.current || simNodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    const { width, height } = dimensions;

    svg.selectAll('*').remove();
    setPhysicsActive(true);

    const g = svg.append('g').attr('class', 'main-group');

    // Zoom/pan — never touches physics
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.05, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform.toString());
        setZoomTransform({ x: event.transform.x, y: event.transform.y, k: event.transform.k });
      });

    svg.call(zoom);

    // Click background to clear focus (no physics disturbance)
    svg.on('click', () => {
      onFocusChangeRef.current?.(null);
      setSelectedConceptId(null);
    });

    // Concept edges (only visible ones rendered)
    const linkGroup = g.append('g').attr('class', 'links');
    const linkElements = linkGroup.selectAll<SVGLineElement, SimLink>('line')
      .data(simLinks.filter(l => l.visible))
      .join('line')
      .attr('stroke', theme === 'dark' ? 'rgba(107, 114, 128, 0.35)' : 'rgba(85, 85, 85, 0.25)')
      .attr('stroke-width', 0.8)
      .attr('display', settingsRef.current.visual.showEdges ? null : 'none');

    linkElementsRef.current = linkElements;

    // Nodes
    const nodeGroup = g.append('g').attr('class', 'nodes');
    const nodeElements = nodeGroup.selectAll<SVGGElement, SimNode>('g')
      .data(simNodes)
      .join('g')
      .style('cursor', 'pointer')
      .on('mouseenter', (_event: MouseEvent, d: SimNode) => {
        if (settingsRef.current.interaction.highlightOnHover) setHoveredNode(d.id);
      })
      .on('mouseleave', () => setHoveredNode(null))
      .on('click', (event: MouseEvent, d: SimNode) => {
        event.stopPropagation();
        if (d.type === 'document') {
          onFocusChangeRef.current?.(d.id);
          onNodeClickRef.current?.(d.id);
        } else {
          setSelectedConceptId(d.id);
        }
      })
      .on('dblclick', (event: MouseEvent, d: SimNode) => {
        event.stopPropagation();
        if (d.type === 'document') {
          onViewDocumentRef.current?.(d.id);
        }
      });

    nodeElementsRef.current = nodeElements;

    // Render-time size helper — reads settings from ref, never triggers simulation restart
    const renderSize = (d: SimNode) => {
      const s = settingsRef.current;
      return d.type === 'document' ? s.layout.documentSize : d.size * s.visual.nodeSize;
    };

    // Node circles
    nodeElements.append('circle')
      .attr('r', (d: SimNode) => renderSize(d))
      .attr('fill', (d: SimNode) => COLORS[d.type].fill)
      .attr('stroke', (d: SimNode) => COLORS[d.type].stroke)
      .attr('stroke-width', (d: SimNode) => d.type === 'document' ? 3 : 1.5)
      .attr('opacity', (d: SimNode) => d.type === 'document' ? 0.95 : 0.8);

    // Document icon (file shape)
    nodeElements.filter((d: SimNode) => d.type === 'document')
      .append('path')
      .attr('d', (d: SimNode) => {
        const s = renderSize(d) * 0.45;
        return `M${-s / 2},${-s / 2} L${s / 3},${-s / 2} L${s / 2},${-s / 3} L${s / 2},${s / 2} L${-s / 2},${s / 2} Z`;
      })
      .attr('fill', '#fff')
      .attr('opacity', 0.9);

    // Labels
    nodeElements.append('text')
      .text((d: SimNode) => d.label)
      .attr('dy', (d: SimNode) => renderSize(d) + 12)
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
      .attr('display', settingsRef.current.visual.showLabels ? null : 'none')
      .style('text-shadow', theme === 'dark'
        ? '0 1px 0 #000, 0 -1px 0 #000, 1px 0 0 #000, -1px 0 0 #000'
        : '0 1px 0 #fff, 0 -1px 0 #fff, 1px 0 0 #fff, -1px 0 0 #fff'
      );

    // -----------------------------------------------------------------------
    // Force simulation — runs once on load, then stops.
    // -----------------------------------------------------------------------
    const simulation = d3.forceSimulation<SimNode, SimLink>(simNodes)
      .alpha(1)
      .alphaDecay(0.015)
      .alphaMin(0.008)
      .alphaTarget(0)
      .force('link',
        d3.forceLink<SimNode, SimLink>(simLinks)
          .id(d => d.id)
          .distance((l) => (l as SimLink).visible ? 100 : 25)
          .strength((l) => (l as SimLink).visible ? 0.2 : 0.15)
      )
      .force('charge', d3.forceManyBody<SimNode>().strength((d) => {
        if (d.type === 'document') return -500;
        if (d.type === 'query-concept') return -120;
        return -80;
      }))
      .force('center', d3.forceCenter(width / 2, height / 2).strength(0.05))
      .force('collision', d3.forceCollide<SimNode>().radius((d) => {
        const sz = renderSize(d);
        if (d.type === 'document') return sz + 20;
        return sz + 4;
      }));

    simulationRef.current = simulation;

    simulation.on('tick', renderPositions);
    simulation.on('end', () => setPhysicsActive(false));

    // -----------------------------------------------------------------------
    // Drag — purely manual. No physics restart. Ever.
    // -----------------------------------------------------------------------
    const drag = d3.drag<SVGGElement, SimNode>()
      .on('start', (_event, d) => {
        d.fx = d.x;
        d.fy = d.y;
      })
      .on('drag', (event, d) => {
        d.x = d.fx = event.x;
        d.y = d.fy = event.y;
        renderPositions();
      })
      .on('end', (_event, d) => {
        d.x = d.fx!;
        d.y = d.fy!;
        // Only release fixed position if simulation is stopped.
        // If sim is still running (e.g. after reheat), keep pinned to avoid drift.
        const sim = simulationRef.current;
        if (!sim || sim.alpha() < sim.alphaMin()) {
          d.fx = null;
          d.fy = null;
        }
      });

    nodeElements.call(drag);

    return () => {
      simulation.stop();
      linkElementsRef.current = null;
      nodeElementsRef.current = null;
    };
    // Only restart simulation when data or dimensions actually change.
    // Callbacks and settings are accessed via refs — never trigger restarts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [simNodes, simLinks, dimensions, theme, renderPositions]);

  // Reheat — one-shot energy injection from current positions
  const handleReheat = useCallback(() => {
    const sim = simulationRef.current;
    if (!sim) return;
    sim.alpha(0.5).restart();
    setPhysicsActive(true);
  }, []);

  // -----------------------------------------------------------------------
  // Settings-driven visual updates (no simulation restart)
  // -----------------------------------------------------------------------
  useEffect(() => {
    linkElementsRef.current
      ?.attr('display', settings.visual.showEdges ? null : 'none');
  }, [settings.visual.showEdges]);

  useEffect(() => {
    if (!svgRef.current) return;
    d3.select(svgRef.current).selectAll<SVGTextElement, SimNode>('g.nodes g text')
      .attr('display', settings.visual.showLabels ? null : 'none');
  }, [settings.visual.showLabels]);

  // Update node sizes when settings change (no simulation restart)
  useEffect(() => {
    if (!svgRef.current) return;
    const renderSize = (d: SimNode) =>
      d.type === 'document' ? settings.layout.documentSize : d.size * settings.visual.nodeSize;

    d3.select(svgRef.current).selectAll<SVGCircleElement, SimNode>('g.nodes g circle:not(.query-ring)')
      .attr('r', renderSize);
    d3.select(svgRef.current).selectAll<SVGTextElement, SimNode>('g.nodes g text')
      .attr('dy', (d: SimNode) => renderSize(d) + 12);
    d3.select(svgRef.current).selectAll<SVGPathElement, SimNode>('g.nodes g path')
      .attr('d', (d: SimNode) => {
        const s = renderSize(d) * 0.45;
        return `M${-s / 2},${-s / 2} L${s / 3},${-s / 2} L${s / 2},${-s / 3} L${s / 2},${s / 2} L${-s / 2},${s / 2} Z`;
      });
  }, [settings.layout.documentSize, settings.visual.nodeSize]);

  // -----------------------------------------------------------------------
  // Passage search rings — concentric colored rings around matching nodes.
  // Rings are children of node <g> groups so they inherit transform position.
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);

    // Clear existing rings
    svg.selectAll('.query-ring').remove();

    if (!passageRings || passageRings.size === 0) return;

    const renderSize = (d: SimNode) => {
      const s = settingsRef.current;
      return d.type === 'document' ? s.layout.documentSize : d.size * s.visual.nodeSize;
    };

    svg.selectAll<SVGGElement, SimNode>('g.nodes g').each(function(d) {
      const rings = passageRings.get(d.id);
      if (!rings) return;

      const g = d3.select(this);
      const baseR = renderSize(d);
      const ringWidth = 3;
      const gap = 2;

      rings.forEach((ring, i) => {
        // Thickness encodes hit frequency: min 1.5px (1 hit) → max 5px (max hits)
        const MIN_WIDTH = 1.5;
        const MAX_WIDTH = 5;
        const t = ring.maxHitCount > 1
          ? (ring.hitCount - 1) / (ring.maxHitCount - 1)  // 0..1 normalized
          : 0;
        const strokeWidth = MIN_WIDTH + t * (MAX_WIDTH - MIN_WIDTH);

        const r = baseR + gap + (i * (ringWidth + 1));
        g.insert('circle', ':first-child')
          .attr('class', 'query-ring')
          .attr('r', r)
          .attr('fill', 'none')
          .attr('stroke', ring.color)
          .attr('stroke-width', strokeWidth)
          .attr('stroke-opacity', 0.75);
      });
    });
  }, [passageRings]);

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
    svg.selectAll<SVGCircleElement, SimNode>('g.nodes g circle:not(.query-ring)')
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

  // Query hit bar for the selected concept's NodeInfoBox
  const selectedNodeQueryBar = useMemo(() => {
    if (!selectedConceptId || !passageRings || !queryColorLabels) return undefined;
    const rings = passageRings.get(selectedConceptId);
    if (!rings || rings.length === 0) return undefined;

    return (
      <div className="flex border-b border-border">
        {rings.map((ring) => (
          <div
            key={ring.color}
            className="flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2 text-[10px] font-medium"
            style={{ backgroundColor: `${ring.color}25`, color: ring.color }}
          >
            <span className="truncate">{queryColorLabels.get(ring.color) || '?'}</span>
            <span className="opacity-70">{ring.hitCount}</span>
          </div>
        ))}
      </div>
    );
  }, [selectedConceptId, passageRings, queryColorLabels]);

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

      {/* Reheat button */}
      <div className="absolute top-4 left-4">
        <button
          onClick={handleReheat}
          disabled={physicsActive}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium border transition-colors ${
            physicsActive
              ? 'bg-amber-500/15 border-amber-500/30 text-amber-500 cursor-default'
              : 'bg-card/90 border-border text-muted-foreground hover:text-foreground hover:bg-accent'
          }`}
          title={physicsActive ? 'Simulation running...' : 'Reheat layout'}
        >
          <RotateCcw className={`h-3.5 w-3.5 ${physicsActive ? 'animate-spin' : ''}`} />
          {physicsActive ? 'Settling...' : 'Reheat'}
        </button>
      </div>

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
          headerExtra={selectedNodeQueryBar}
        />
      )}
    </div>
  );
};

export default DocumentExplorer;
