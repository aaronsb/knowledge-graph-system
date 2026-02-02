/**
 * Force-Directed 2D Graph Explorer - Main Component
 *
 * Interactive 2D force-directed graph visualization using D3.js.
 * Follows ADR-034 Explorer Plugin Interface.
 */

import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import * as d3 from 'd3';
import type { ExplorerProps } from '../../types/explorer';
import type { D3Node, D3Link } from '../../types/graph';
import type { ForceGraph2DSettings, ForceGraph2DData } from './types';
import { getNeighbors, transformForD3, filterByEdgeCategory } from '../../utils/graphTransform';
import { useGraphStore } from '../../store/graphStore';
import { useThemeStore } from '../../store/themeStore';
import { getCategoryColor, categoryColors } from '../../config/categoryColors';
import { ContextMenu, type ContextMenuItem } from '../../components/shared/ContextMenu';
import { FileSpreadsheet } from 'lucide-react';
import {
  NodeInfoBox,
  EdgeInfoBox,
  StatsPanel,
  Legend,
  PanelStack,
  useGraphNavigation,
  buildContextMenuItems,
  type GraphContextMenuHandlers,
  LABEL_FONTS,
  LABEL_STYLE_2D,
  ColorTransform,
} from '../common';
import { SLIDER_RANGES } from './types';

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
> = ({ data, settings, onSettingsChange, onNodeClick, onSendToReports, className }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const [dimensions, setDimensions] = useState({ width: 1000, height: 800 });
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<string | null>(null);
  const [focusedNode, setFocusedNode] = useState<string | null>(null);
  const simulationRef = useRef<d3.Simulation<D3Node, D3Link> | null>(null);
  const zoomBehaviorRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);

  // Get current theme for label colors (use appliedTheme which resolves 'system' to actual theme)
  const { appliedTheme: theme } = useThemeStore();

  // Get edge category filters from store
  const { filters } = useGraphStore();

  // Apply edge category filter to data
  const filteredData = useMemo(() => {
    return filterByEdgeCategory(data, filters.visibleEdgeCategories);
  }, [data, filters.visibleEdgeCategories]);

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

  // Imperative function to apply blue ring for destination
  const applyBlueRing = useCallback((nodeId: string) => {
    if (!svgRef.current || !settings.interaction.showOriginNode) return;

    const svg = d3.select(svgRef.current);

    // Remove from previous node (restore brighter stroke)
    svg.selectAll('circle.destination-node')
      .interrupt()
      .attr('stroke', function() {
        const d = d3.select(this).datum() as D3Node;
        const color = nodeColors.get(d.id) || d.color;
        return d3.color(color)?.brighter(0.4).toString() || color;
      })
      .attr('stroke-width', 2)
      .attr('stroke-opacity', 1)
      .classed('destination-node', false);

    // Add to target node
    const targetCircle = svg.select<SVGCircleElement>(`circle[data-node-id="${nodeId}"]`);

    if (!targetCircle.empty()) {
      targetCircle
        .attr('stroke', '#4169E1')  // Royal Blue for destination
        .attr('stroke-width', 4)
        .classed('destination-node', true);

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

  // Unified context menu state (handles both node and background clicks)
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    nodeId: string | null;  // null for background clicks
    nodeLabel: string | null;  // null for background clicks
  } | null>(null);

  // Right-click drag tracking for pan behavior
  const rightClickStartRef = useRef<{ x: number; y: number; time: number } | null>(null);
  const [isRightClickDragging, setIsRightClickDragging] = useState(false);

  // Get navigation state and settings from store
  const { originNodeId, setOriginNodeId, destinationNodeId, setDestinationNodeId, setFocusedNodeId, setGraphData, graphData } = useGraphStore();

  // Calculate neighbors for highlighting (hover)
  const neighbors = useMemo(() => {
    if (!hoveredNode || !settings.interaction.highlightNeighbors) return new Set<string>();
    return getNeighbors(hoveredNode, filteredData.links);
  }, [hoveredNode, filteredData.links, settings.interaction.highlightNeighbors]);

  // Calculate neighbors for focus mode (stronger highlight)
  const focusNeighbors = useMemo(() => {
    if (!focusedNode || !settings.interaction.highlightNeighbors) return new Set<string>();
    return getNeighbors(focusedNode, filteredData.links);
  }, [focusedNode, filteredData.links, settings.interaction.highlightNeighbors]);

  // Calculate node colors based on nodeColorBy setting
  const nodeColors = useMemo(() => {
    const colors = new Map<string, string>();

    if (settings.visual.nodeColorBy === 'ontology') {
      // Color by ontology (default behavior from transformForD3)
      filteredData.nodes.forEach(node => {
        colors.set(node.id, node.color);
      });
    } else if (settings.visual.nodeColorBy === 'degree') {
      // Color by degree (number of connections)
      const degrees = new Map<string, number>();
      filteredData.links.forEach(link => {
        const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
        const targetId = typeof link.target === 'string' ? link.target : link.target.id;
        degrees.set(sourceId, (degrees.get(sourceId) || 0) + 1);
        degrees.set(targetId, (degrees.get(targetId) || 0) + 1);
      });

      const maxDegree = Math.max(...Array.from(degrees.values()), 1);
      const colorScale = d3.scaleSequential(d3.interpolateViridis).domain([0, maxDegree]);

      filteredData.nodes.forEach(node => {
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
  }, [filteredData.nodes, data.links, settings.visual.nodeColorBy]);

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
  }, [filteredData.links, settings.visual.edgeColorBy]);

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

    // Auto-disable shadows for large graphs (performance protection)
    const totalElements = data.nodes.length + data.links.length;
    if (totalElements > 5000 && settings.visual.showShadows) {
      console.warn(`⚠️ Graph has ${totalElements} elements. Auto-disabling shadows for performance. You can re-enable manually.`);
      onSettingsChange?.({
        ...settings,
        visual: { ...settings.visual, showShadows: false },
      });
    }

    // Clear previous content
    svg.selectAll('*').remove();

    // Define SVG filters for shadow effects
    const defs = svg.append('defs');
    const shadowFilter = defs.append('filter')
      .attr('id', 'drop-shadow')
      .attr('x', '-50%')
      .attr('y', '-50%')
      .attr('width', '200%')
      .attr('height', '200%');

    shadowFilter.append('feGaussianBlur')
      .attr('in', 'SourceAlpha')
      .attr('stdDeviation', 2);

    shadowFilter.append('feOffset')
      .attr('dx', 3.6)
      .attr('dy', 3.6)
      .attr('result', 'offsetblur');

    shadowFilter.append('feComponentTransfer')
      .append('feFuncA')
      .attr('type', 'linear')
      .attr('slope', 0.8);

    const feMerge = shadowFilter.append('feMerge');
    feMerge.append('feMergeNode');
    feMerge.append('feMergeNode')
      .attr('in', 'SourceGraphic');

    // Create container groups (order determines layering)
    const g = svg.append('g').attr('class', 'graph-container');

    // Create grid group INSIDE graph container so it transforms with the graph
    const gridGroup = g.append('g').attr('class', 'grid-layer');

    // Shadow layers (rendered below main elements)
    const edgeShadowsGroup = g.append('g').attr('class', 'edge-shadows');
    const linksGroup = g.append('g').attr('class', 'links');
    const nodeShadowsGroup = g.append('g').attr('class', 'node-shadows');
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

          // Update zoom transform state for info box positioning
          setZoomTransform({
            x: event.transform.x,
            y: event.transform.y,
            k: event.transform.k,
          });
        });

      // Store zoom behavior in ref for travel functions to use
      zoomBehaviorRef.current = zoom;

      if (settings.interaction.enableZoom && settings.interaction.enablePan) {
        svg.call(zoom);
      } else if (settings.interaction.enableZoom) {
        svg.call(zoom).on('mousedown.zoom', null);
      } else if (settings.interaction.enablePan) {
        svg.call(zoom).on('wheel.zoom', null);
      }
    }

    // Check if nodes already have positions (from merge/previous simulation)
    const hasExistingPositions = filteredData.nodes.some(n => n.x !== undefined && n.y !== undefined);

    // Create force simulation
    const simulation = d3
      .forceSimulation<D3Node>(filteredData.nodes)
      .force(
        'link',
        d3
          .forceLink<D3Node, D3Link>(filteredData.links)
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

    // Draw edge shadows if enabled
    // Edge shadows now handled by SVG filter on the edges themselves

    // Draw links as paths (supports curves for multiple edges)
    const link = linksGroup
      .selectAll<SVGPathElement, D3Link>('path')
      .data(filteredData.links)
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
      .style('filter', settings.visual.showShadows ? 'url(#drop-shadow)' : null)
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

          // Check if this is a self-loop
          const isSelfLoop = sourceId === targetId;

          if (isSelfLoop) {
            // Self-loop: position at apex of hairpin curve
            const nodeRadius = ((d.source as any).size || 10) * settings.visual.nodeSize;
            const baseLoopSize = nodeRadius * 3;
            const loopSize = baseLoopSize + Math.abs(curveOffset);

            const startAngle = curveOffset * 0.3;
            const endAngle = startAngle + Math.PI / 6;
            const midAngle = (startAngle + endAngle) / 2;

            // Recreate cubic Bezier curve
            const loopStartX = sourceX + nodeRadius * Math.cos(startAngle);
            const loopStartY = sourceY + nodeRadius * Math.sin(startAngle);
            const control1X = sourceX + loopSize * Math.cos(midAngle - 0.3);
            const control1Y = sourceY + loopSize * Math.sin(midAngle - 0.3);
            const control2X = sourceX + loopSize * Math.cos(midAngle + 0.3);
            const control2Y = sourceY + loopSize * Math.sin(midAngle + 0.3);
            const loopEndX = sourceX + nodeRadius * Math.cos(endAngle);
            const loopEndY = sourceY + nodeRadius * Math.sin(endAngle);

            // Calculate position at t=0.5 (apex)
            const t = 0.5;
            const mt = 1 - t;
            midX = mt * mt * mt * loopStartX +
                   3 * mt * mt * t * control1X +
                   3 * mt * t * t * control2X +
                   t * t * t * loopEndX;
            midY = mt * mt * mt * loopStartY +
                   3 * mt * mt * t * control1Y +
                   3 * mt * t * t * control2Y +
                   t * t * t * loopEndY;
          } else if (curveOffset === 0) {
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
      .data(filteredData.links)
      .join('text')
      .text((d) => d.type)
      .attr('font-family', LABEL_FONTS.family)
      .attr('font-size', settings.visual?.edgeLabelSize ?? 9)
      .attr('font-weight', LABEL_STYLE_2D.edge.fontWeight)
      .attr('fill', (d) => {
        // Use unified color transformation
        const baseColor = d.color || '#6b7280';
        const colors = ColorTransform.getLabelColors(baseColor, 'edge', theme);
        return colors.fill;
      })
      .attr('stroke', (d) => {
        // Use unified color transformation
        const baseColor = d.color || '#6b7280';
        const colors = ColorTransform.getLabelColors(baseColor, 'edge', theme);
        return colors.stroke;
      })
      .attr('stroke-width', LABEL_STYLE_2D.edge.strokeWidth)
      .attr('paint-order', LABEL_STYLE_2D.edge.paintOrder)
      .attr('text-anchor', 'middle')
      .attr('pointer-events', 'none')
      .style('user-select', 'none');

    // Render node highlights FIRST (before circles) if shadows enabled, so circles are on top
    if (settings.visual.showShadows) {
      // Node shadows now handled by SVG filter on the nodes themselves

      // Node highlights (reflection and shade arcs) - MUST be created before circles
      nodesGroup
        .selectAll<SVGPathElement, any>('.highlight-arc')
        .data(data.nodes.flatMap(d => [
          { node: d, arcType: 'reflection' },
          { node: d, arcType: 'shade' }
        ]))
        .join('path')
        .attr('class', 'highlight-arc')
        .attr('d', (d: any) => {
          const nodeRadius = ((d.node.size || 10) * settings.visual.nodeSize);
          const arcRadius = nodeRadius * 0.8; // 80% of node diameter

          // Arc angles in degrees (0° = right/3 o'clock)
          const isReflection = d.arcType === 'reflection';
          const startAngle = isReflection ? 290 : 110; // degrees
          const endAngle = isReflection ? 340 : 160;   // degrees

          // Convert to radians
          const startRad = (startAngle - 90) * (Math.PI / 180);
          const endRad = (endAngle - 90) * (Math.PI / 180);

          // Calculate arc path (80% of node radius)
          const x1 = arcRadius * Math.cos(startRad);
          const y1 = arcRadius * Math.sin(startRad);
          const x2 = arcRadius * Math.cos(endRad);
          const y2 = arcRadius * Math.sin(endRad);

          // Large arc flag: 0 for arcs <= 180°, 1 for arcs > 180°
          const largeArcFlag = 0;

          return `M ${x1} ${y1} A ${arcRadius} ${arcRadius} 0 ${largeArcFlag} 1 ${x2} ${y2}`;
        })
        .attr('fill', 'none')
        .attr('stroke', (d: any) => {
          const baseColor = nodeColors.get(d.node.id) || d.node.color;
          const color = d3.color(baseColor);
          if (!color) return baseColor;

          if (d.arcType === 'reflection') {
            // Increase luminance for reflection (nearly white)
            return color.brighter(2.5).toString();
          } else {
            // Decrease luminance for shade (darker)
            return color.darker(1.5).toString();
          }
        })
        .attr('stroke-width', 3)
        .attr('stroke-linecap', 'round')
        .attr('pointer-events', 'none');
    }

    // Draw nodes (AFTER highlights so they're on top and receive events)
    const node = nodesGroup
      .selectAll<SVGCircleElement, D3Node>('circle')
      .data(filteredData.nodes)
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
      .style('filter', settings.visual.showShadows ? 'url(#drop-shadow)' : null)
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
        event.stopPropagation(); // Prevent canvas context menu from showing
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
        .data(filteredData.nodes)
        .join('text')
        .text((d) => d.label)
        .attr('font-family', LABEL_FONTS.family)
        .attr('font-size', settings.visual?.nodeLabelSize ?? 12)
        .attr('font-weight', LABEL_STYLE_2D.node.fontWeight)
        .attr('fill', (d) => {
          // Use unified color transformation
          const baseColor = d.color || '#6b7280';
          const colors = ColorTransform.getLabelColors(baseColor, 'node', theme);
          return colors.fill;
        })
        .attr('stroke', (d) => {
          // Use unified color transformation
          const baseColor = d.color || '#6b7280';
          const colors = ColorTransform.getLabelColors(baseColor, 'node', theme);
          return colors.stroke;
        })
        .attr('stroke-width', LABEL_STYLE_2D.node.strokeWidth)
        .attr('paint-order', LABEL_STYLE_2D.node.paintOrder)
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

        // Check if this is a self-loop (edge connects to itself)
        const isSelfLoop = sourceId === targetId;

        if (isSelfLoop) {
          // Self-loop: create hairpin curve using cubic Bezier
          const nodeRadius = sourceNode ? ((sourceNode.size || 10) * settings.visual.nodeSize) : 10;

          // Loop size increases with curve offset (for multiple self-loops)
          const baseLoopSize = nodeRadius * 3; // Minimum loop size
          const loopSize = baseLoopSize + Math.abs(curveOffset);

          // Create start and end points on node boundary (30 degrees apart)
          const startAngle = curveOffset * 0.3; // Rotate based on offset (spreads multiple loops)
          const endAngle = startAngle + Math.PI / 6; // 30 degrees apart
          const midAngle = (startAngle + endAngle) / 2;

          const loopStartX = sourceX + nodeRadius * Math.cos(startAngle);
          const loopStartY = sourceY + nodeRadius * Math.sin(startAngle);
          const loopEndX = sourceX + nodeRadius * Math.cos(endAngle);
          const loopEndY = sourceY + nodeRadius * Math.sin(endAngle);

          // Control points push curve outward (hairpin shape)
          const control1X = sourceX + loopSize * Math.cos(midAngle - 0.3);
          const control1Y = sourceY + loopSize * Math.sin(midAngle - 0.3);
          const control2X = sourceX + loopSize * Math.cos(midAngle + 0.3);
          const control2Y = sourceY + loopSize * Math.sin(midAngle + 0.3);

          // SVG cubic Bezier path: M start C control1 control2 end
          return `M ${loopStartX},${loopStartY} C ${control1X},${control1Y} ${control2X},${control2Y} ${loopEndX},${loopEndY}`;
        }

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
        const sourceNode = typeof d.source === 'object' ? d.source : null;
        const targetNode = typeof d.target === 'object' ? d.target : null;

        const sourceX = sourceNode?.x || 0;
        const sourceY = sourceNode?.y || 0;
        const targetX = targetNode?.x || 0;
        const targetY = targetNode?.y || 0;

        // Get curve offset for label positioning
        const sourceId = typeof d.source === 'string' ? d.source : d.source.id;
        const targetId = typeof d.target === 'string' ? d.target : d.target.id;
        const linkKey = `${sourceId}->${targetId}-${d.type}`;
        const curveOffset = linkCurveOffsets.get(linkKey) || 0;

        // Check if this is a self-loop
        const isSelfLoop = sourceId === targetId;

        let midX, midY, angle;

        if (isSelfLoop) {
          // Self-loop: position label at apex of hairpin curve
          const nodeRadius = sourceNode ? ((sourceNode.size || 10) * settings.visual.nodeSize) : 10;
          const baseLoopSize = nodeRadius * 3;
          const loopSize = baseLoopSize + Math.abs(curveOffset);

          const startAngle = curveOffset * 0.3;
          const endAngle = startAngle + Math.PI / 6;
          const midAngle = (startAngle + endAngle) / 2;

          // Recreate cubic Bezier curve
          const loopStartX = sourceX + nodeRadius * Math.cos(startAngle);
          const loopStartY = sourceY + nodeRadius * Math.sin(startAngle);
          const loopEndX = sourceX + nodeRadius * Math.cos(endAngle);
          const loopEndY = sourceY + nodeRadius * Math.sin(endAngle);
          const control1X = sourceX + loopSize * Math.cos(midAngle - 0.3);
          const control1Y = sourceY + loopSize * Math.sin(midAngle - 0.3);
          const control2X = sourceX + loopSize * Math.cos(midAngle + 0.3);
          const control2Y = sourceY + loopSize * Math.sin(midAngle + 0.3);

          // Calculate position at t=0.5 (apex) on cubic Bezier
          const t = 0.5;
          const mt = 1 - t;
          midX = mt * mt * mt * loopStartX +
                 3 * mt * mt * t * control1X +
                 3 * mt * t * t * control2X +
                 t * t * t * loopEndX;
          midY = mt * mt * mt * loopStartY +
                 3 * mt * mt * t * control1Y +
                 3 * mt * t * t * control2Y +
                 t * t * t * loopEndY;

          // Calculate tangent at t=0.5 for cubic Bezier
          const tangentX = 3 * mt * mt * (control1X - loopStartX) +
                          6 * mt * t * (control2X - control1X) +
                          3 * t * t * (loopEndX - control2X);
          const tangentY = 3 * mt * mt * (control1Y - loopStartY) +
                          6 * mt * t * (control2Y - control1Y) +
                          3 * t * t * (loopEndY - control2Y);
          angle = Math.atan2(tangentY, tangentX) * (180 / Math.PI);
        } else if (curveOffset === 0) {
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

      // Update highlight positions if enabled (shadows handled by SVG filter)
      if (settings.visual.showShadows) {
        // Update node highlight arc positions
        nodesGroup.selectAll('.highlight-arc')
          .attr('transform', (d: any) => `translate(${d.node.x || 0}, ${d.node.y || 0})`);
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
  }, [filteredData, settings, dimensions, onNodeClick, nodeColors, linkColors, linkCurveOffsets, theme]);

  // Helper function to render grid in graph coordinates
  const renderGrid = useCallback(() => {
    if (!svgRef.current || !settings.visual.showGrid) return;

    const svg = d3.select(svgRef.current);
    const g = svg.select('.graph-container');
    const gridGroup = g.select('.grid-layer');

    if (gridGroup.empty()) return;

    // Clear existing grid
    gridGroup.selectAll('*').remove();

    // Get canvas background color and derive grid colors
    const canvasColor = d3.color(
      window.getComputedStyle(svgRef.current).backgroundColor || '#ffffff'
    );
    const mainGridColor = canvasColor ? canvasColor.brighter(2.0).toString() : '#d0d0d0';
    const subGridColor = canvasColor ? canvasColor.brighter(1.0).toString() : '#e8e8e8';

    // Grid spacing in graph coordinates
    const mainGridSize = 100;
    const subGridSize = mainGridSize / 2;

    // Render a large grid centered at origin (will transform with zoom/pan)
    const gridExtent = 5000; // Large enough to cover any reasonable zoom/pan

    // Draw subdivision grid
    for (let x = -gridExtent; x <= gridExtent; x += subGridSize) {
      if (x % mainGridSize !== 0) {
        gridGroup
          .append('line')
          .attr('class', 'sub-grid-line')
          .attr('x1', x)
          .attr('y1', -gridExtent)
          .attr('x2', x)
          .attr('y2', gridExtent)
          .attr('stroke', subGridColor)
          .attr('stroke-width', 1)
          .attr('opacity', 0.6);
      }
    }

    for (let y = -gridExtent; y <= gridExtent; y += subGridSize) {
      if (y % mainGridSize !== 0) {
        gridGroup
          .append('line')
          .attr('class', 'sub-grid-line')
          .attr('x1', -gridExtent)
          .attr('y1', y)
          .attr('x2', gridExtent)
          .attr('y2', y)
          .attr('stroke', subGridColor)
          .attr('stroke-width', 1)
          .attr('opacity', 0.6);
      }
    }

    // Draw main grid
    for (let x = -gridExtent; x <= gridExtent; x += mainGridSize) {
      gridGroup
        .append('line')
        .attr('class', 'main-grid-line')
        .attr('x1', x)
        .attr('y1', -gridExtent)
        .attr('x2', x)
        .attr('y2', gridExtent)
        .attr('stroke', mainGridColor)
        .attr('stroke-width', 1)
        .attr('opacity', 0.8);
    }

    for (let y = -gridExtent; y <= gridExtent; y += mainGridSize) {
      gridGroup
        .append('line')
        .attr('class', 'main-grid-line')
        .attr('x1', -gridExtent)
        .attr('y1', y)
        .attr('x2', gridExtent)
        .attr('y2', y)
        .attr('stroke', mainGridColor)
        .attr('stroke-width', 1)
        .attr('opacity', 0.8);
    }
  }, [settings.visual.showGrid]);

  // Render grid when SVG structure is rebuilt or visibility changes
  useEffect(() => {
    // Small delay to ensure grid-layer is created
    const timer = setTimeout(() => renderGrid(), 0);
    return () => clearTimeout(timer);
  }, [renderGrid, data, settings, dimensions]);

  // Update highlighting based on focus and hover
  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);

    // Node highlighting (focus takes priority over hover)
    svg.selectAll<SVGCircleElement, D3Node>('circle').attr('opacity', (d) => {
      if (!d) return 1;

      // Focus mode (stronger fade)
      if (focusedNode) {
        if (d.id === focusedNode) return 1;
        if (focusNeighbors.has(d.id)) return 1;
        return 0.05;  // Much stronger fade for focus
      }

      // Hover mode (lighter fade)
      if (hoveredNode) {
        if (d.id === hoveredNode) return 1;
        if (neighbors.has(d.id)) return 1;
        return 0.2;  // Lighter fade for hover
      }

      return 1;  // No focus or hover
    });

    // Edge highlighting (paths not lines) - focus takes priority
    svg.selectAll<SVGPathElement, D3Link>('path').each(function(link) {
      const path = d3.select(this);
      const linkKey = path.attr('data-link-key');

      // Guard against undefined link data during graph updates
      if (!link) {
        return;
      }

      const sourceId = typeof link.source === 'string' ? link.source : link.source?.id;
      const targetId = typeof link.target === 'string' ? link.target : link.target?.id;

      if (hoveredEdge) {
        // Edge hover mode
        if (linkKey === hoveredEdge) {
          path.attr('stroke-opacity', 1).attr('stroke-width', ((link.value || 1) * settings.visual.linkWidth) * 2);
        } else {
          path.attr('stroke-opacity', 0.2).attr('stroke-width', (link.value || 1) * settings.visual.linkWidth);
        }
      } else if (focusedNode) {
        // Focus mode (stronger fade)
        if (!sourceId || !targetId) {
          path.attr('stroke-opacity', 0.6);
        } else if (sourceId === focusedNode || targetId === focusedNode) {
          path.attr('stroke-opacity', 1);
        } else {
          path.attr('stroke-opacity', 0.02);  // Much stronger fade for focus
        }
        path.attr('stroke-width', (link.value || 1) * settings.visual.linkWidth);
      } else if (hoveredNode) {
        // Node hover mode (lighter fade)
        if (!sourceId || !targetId) {
          path.attr('stroke-opacity', 0.6);
        } else if (sourceId === hoveredNode || targetId === hoveredNode) {
          path.attr('stroke-opacity', 1);
        } else {
          path.attr('stroke-opacity', 0.1);  // Lighter fade for hover
        }
        path.attr('stroke-width', (link.value || 1) * settings.visual.linkWidth);
      } else {
        // No focus or hover
        path.attr('stroke-opacity', 0.6).attr('stroke-width', (link.value || 1) * settings.visual.linkWidth);
      }
    });
  }, [focusedNode, hoveredNode, hoveredEdge, neighbors, focusNeighbors, settings.visual.linkWidth]);

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

  // "Destination" highlighting - async update after DOM ready
  useEffect(() => {
    if (!destinationNodeId || !settings.interaction.showOriginNode) return;

    // Wait for next frame to ensure DOM is fully rendered
    const rafId = requestAnimationFrame(() => {
      // Double-raf for extra safety (ensures layout is complete)
      requestAnimationFrame(() => {
        applyBlueRing(destinationNodeId);
      });
    });

    return () => {
      cancelAnimationFrame(rafId);
      // Cleanup: remove blue ring (restore brighter stroke)
      if (svgRef.current) {
        d3.select(svgRef.current)
          .selectAll('circle.destination-node')
          .interrupt()
          .attr('stroke', function() {
            const d = d3.select(this).datum() as D3Node;
            const color = nodeColors.get(d.id) || d.color;
            return d3.color(color)?.brighter(0.4).toString() || color;
          })
          .attr('stroke-width', 2)
          .attr('stroke-opacity', 1)
          .classed('destination-node', false);
      }
    };
  }, [destinationNodeId, settings.interaction.showOriginNode, data, applyBlueRing]);

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

  // Use common graph navigation hook
  const { handleFollowConcept, handleAddToGraph } = useGraphNavigation(mergeGraphData);

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
  }, [filteredData.nodes, settings.physics.enabled]);

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

  // Travel to origin node (center it in viewport with zoom)
  const travelToOrigin = useCallback(() => {
    if (!originNodeId || !svgRef.current || !zoomBehaviorRef.current) return;

    const originNode = data.nodes.find(n => n.id === originNodeId);
    if (!originNode || originNode.x === undefined || originNode.y === undefined) return;

    const svg = d3.select(svgRef.current);
    const width = dimensions.width;
    const height = dimensions.height;

    // Calculate transform to center the origin node in viewport
    const scale = 1.5; // Zoom in to 1.5x for better focus
    const x = width / 2 - originNode.x * scale;   // Center horizontally
    const y = height / 2 - originNode.y * scale;  // Center vertically

    // Animate transition with cubic ease in/out (smooth acceleration/deceleration like mouse pan)
    // Speed automatically adjusts based on distance - farther = faster, but same duration
    svg.transition()
      .duration(750)
      .ease(d3.easeCubicInOut)  // Smooth acceleration at start, deceleration at end
      .call(
        zoomBehaviorRef.current.transform,
        d3.zoomIdentity.translate(x, y).scale(scale)
      );
  }, [originNodeId, data.nodes, dimensions]);

  // Travel to destination node (center it in viewport with zoom)
  const travelToDestination = useCallback(() => {
    if (!destinationNodeId || !svgRef.current || !zoomBehaviorRef.current) return;

    const destinationNode = data.nodes.find(n => n.id === destinationNodeId);
    if (!destinationNode || destinationNode.x === undefined || destinationNode.y === undefined) return;

    const svg = d3.select(svgRef.current);
    const width = dimensions.width;
    const height = dimensions.height;

    // Calculate transform to center the destination node in viewport
    const scale = 1.5; // Zoom in to 1.5x for better focus
    const x = width / 2 - destinationNode.x * scale;   // Center horizontally
    const y = height / 2 - destinationNode.y * scale;  // Center vertically

    // Animate transition with cubic ease in/out (smooth acceleration/deceleration like mouse pan)
    // Speed automatically adjusts based on distance - farther = faster, but same duration
    svg.transition()
      .duration(750)
      .ease(d3.easeCubicInOut)  // Smooth acceleration at start, deceleration at end
      .call(
        zoomBehaviorRef.current.transform,
        d3.zoomIdentity.translate(x, y).scale(scale)
      );
  }, [destinationNodeId, data.nodes, dimensions]);

  // Build unified context menu items (context-aware for node vs background)
  const contextMenuItems: ContextMenuItem[] = contextMenu
    ? buildContextMenuItems(
        // Pass node context (null for background clicks)
        contextMenu.nodeId && contextMenu.nodeLabel
          ? { nodeId: contextMenu.nodeId, nodeLabel: contextMenu.nodeLabel }
          : null,
        {
          handleFollowConcept,
          handleAddToGraph,
          setOriginNode: setOriginNodeId,
          setDestinationNode: setDestinationNodeId,
          travelToOrigin,
          travelToDestination,
          setFocusedNode,
          focusedNodeId: focusedNode,
          isPinned,
          togglePinNode,
          unpinAllNodes,
          applyOriginMarker: applyGoldRing,
          applyDestinationMarker: applyBlueRing,
        },
        { onClose: () => setContextMenu(null) },
        originNodeId,
        destinationNodeId
      )
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
        className="bg-gradient-to-br from-gray-300 to-gray-400 dark:bg-gradient-to-br dark:from-gray-900 dark:to-black"
        onClick={() => {
          // Close context menu when clicking on canvas background
          setContextMenu(null);
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

          // Only show background context menu if NOT dragging
          // (nodes/edges have their own context menu handlers that stopPropagation)
          if (!isRightClickDragging) {
            // Show unified context menu with null node context (background click)
            setContextMenu({
              x: e.clientX,
              y: e.clientY,
              nodeId: null,
              nodeLabel: null,
            });
          } else {
            // Was dragging, so don't show context menu
            setIsRightClickDragging(false);
          }
        }}
      />

      {/* Left-side panel stack */}
      <PanelStack side="left" gap={16} initialTop={16}>
        <Legend data={filteredData} nodeColorMode={settings.visual.nodeColorBy} />
      </PanelStack>

      {/* Right-side panel stack */}
      <PanelStack side="right" gap={16} initialTop={16}>
        {/* Stats and Send to Reports row */}
        <div className="flex items-center gap-2">
          <StatsPanel nodeCount={filteredData.nodes.length} edgeCount={filteredData.links.length} />
          {onSendToReports && (
            <button
              onClick={onSendToReports}
              className="flex items-center gap-1.5 px-3 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 shadow-lg transition-colors text-sm font-medium"
              title="Send to Reports"
            >
              <FileSpreadsheet className="w-4 h-4" />
              <span>Reports</span>
            </button>
          )}
        </div>

      </PanelStack>

      {/* Unified Context Menu (context-aware for node vs background) */}
      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          items={contextMenuItems}
          onClose={() => setContextMenu(null)}
        />
      )}

      {/* Edge Info Boxes */}
      <div className="absolute inset-0 pointer-events-none" style={{ zIndex: 1000 }}>
        {activeEdgeInfos.map(info => {
          // Apply zoom transform to graph coordinates
          const screenX = info.x * zoomTransform.k + zoomTransform.x;
          const screenY = info.y * zoomTransform.k + zoomTransform.y;
          return (
            <EdgeInfoBox
              key={info.linkKey}
              info={{ ...info, x: screenX, y: screenY }}
              onDismiss={() => handleDismissEdgeInfo(info.linkKey)}
            />
          );
        })}
      </div>

      {/* Node Info Boxes */}
      <div className="absolute inset-0 pointer-events-none" style={{ zIndex: 1000 }}>
        {activeNodeInfos.map(info => {
          // Apply zoom transform to graph coordinates
          const screenX = info.x * zoomTransform.k + zoomTransform.x;
          const screenY = info.y * zoomTransform.k + zoomTransform.y;
          return (
            <NodeInfoBox
              key={info.nodeId}
              info={{ ...info, x: screenX, y: screenY }}
              onDismiss={() => handleDismissNodeInfo(info.nodeId)}
            />
          );
        })}
      </div>
    </div>
  );
};
