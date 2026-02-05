/**
 * Document Explorer - Force-Directed Concept Cloud
 *
 * Visualizes a single document's concepts as a force-directed graph.
 * Two-tone coloring: amber for query-matched concepts, indigo for others.
 * Inter-concept edges show the document's internal conceptual structure.
 */

import React, { useEffect, useRef, useState, useMemo } from 'react';
import * as d3 from 'd3';
import type { ExplorerProps } from '../../types/explorer';
import type {
  DocumentExplorerSettings,
  DocumentExplorerData,
  ConceptNode,
} from './types';
import { useThemeStore } from '../../store/themeStore';
import {
  NodeInfoBox,
  StatsPanel,
  PanelStack,
  LABEL_FONTS,
} from '../common';

// Two-tone palette
const COLORS = {
  queryMatch: '#f59e0b',     // Amber — concept overlaps with exploration query
  documentOnly: '#6366f1',   // Indigo — concept only in this document
  document: '#f59e0b',       // Amber — the document node
};

/** Force simulation node (extends ConceptNode with mutable position). */
interface SimNode extends d3.SimulationNodeDatum {
  id: string;
  label: string;
  type: 'concept' | 'document';
  isQueryMatch: boolean;
  size: number;
}

/** Force simulation link. */
interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  type: string;
}

export const DocumentExplorer: React.FC<
  ExplorerProps<DocumentExplorerData, DocumentExplorerSettings>
> = ({ data, settings, onNodeClick, className }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [zoomTransform, setZoomTransform] = useState({ x: 0, y: 0, k: 1 });
  const simulationRef = useRef<d3.Simulation<SimNode, SimLink> | null>(null);

  const { appliedTheme: theme } = useThemeStore();

  // Build simulation data from explorer data
  const { simNodes, simLinks } = useMemo(() => {
    if (!data) return { simNodes: [] as SimNode[], simLinks: [] as SimLink[] };

    const querySet = new Set(data.queryConceptIds || []);

    // Document node
    const docNode: SimNode = {
      id: data.document.id,
      label: data.document.label,
      type: 'document',
      isQueryMatch: true,
      size: settings.layout.centerSize,
    };

    // Concept nodes
    const conceptNodes: SimNode[] = data.concepts.map(c => ({
      id: c.id,
      label: c.label,
      type: 'concept' as const,
      isQueryMatch: querySet.has(c.id),
      size: 6 * settings.visual.nodeSize,
    }));

    const nodes = [docNode, ...conceptNodes];
    const nodeIds = new Set(nodes.map(n => n.id));

    // Only keep edges where both endpoints exist
    const links: SimLink[] = data.links
      .filter(l => nodeIds.has(l.source) && nodeIds.has(l.target))
      .map(l => ({ source: l.source, target: l.target, type: l.type }));

    return { simNodes: nodes, simLinks: links };
  }, [data, settings.layout.centerSize, settings.visual.nodeSize]);

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

  // Main D3 rendering + force simulation
  useEffect(() => {
    if (!svgRef.current || simNodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    const { width, height } = dimensions;

    // Clear previous content
    svg.selectAll('*').remove();

    const g = svg.append('g').attr('class', 'main-group');

    // Zoom/pan
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform.toString());
        setZoomTransform({ x: event.transform.x, y: event.transform.y, k: event.transform.k });
      });

    if (settings.interaction.enableZoom || settings.interaction.enablePan) {
      svg.call(zoom);
    }

    // Edges
    const linkGroup = g.append('g').attr('class', 'links');
    const linkElements = linkGroup.selectAll<SVGLineElement, SimLink>('line')
      .data(simLinks)
      .join('line')
      .attr('stroke', theme === 'dark' ? 'rgba(107, 114, 128, 0.4)' : 'rgba(85, 85, 85, 0.3)')
      .attr('stroke-width', 1);

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
        setSelectedNode(d.id);
        onNodeClick?.(d.id);
      });

    // Node circles
    nodeElements.append('circle')
      .attr('r', (d: SimNode) => d.size)
      .attr('fill', (d: SimNode) => {
        if (d.type === 'document') return COLORS.document;
        return d.isQueryMatch ? COLORS.queryMatch : COLORS.documentOnly;
      })
      .attr('stroke', (d: SimNode) => {
        if (d.type === 'document') return '#fbbf24';
        return d.isQueryMatch ? '#fcd34d' : '#818cf8';
      })
      .attr('stroke-width', (d: SimNode) => d.type === 'document' ? 3 : 1.5)
      .attr('opacity', (d: SimNode) => d.type === 'document' ? 0.95 : 0.85);

    // Document icon (file shape inside document node)
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
        .attr('font-size', (d: SimNode) => d.type === 'document' ? '12px' : '10px')
        .attr('font-weight', (d: SimNode) => d.type === 'document' ? '600' : '400')
        .attr('fill', (d: SimNode) => {
          if (d.type === 'document') return theme === 'dark' ? '#fbbf24' : '#d97706';
          return theme === 'dark' ? '#e5e7eb' : '#374151';
        })
        .attr('pointer-events', 'none')
        .style('text-shadow', theme === 'dark'
          ? '0 1px 0 #000, 0 -1px 0 #000, 1px 0 0 #000, -1px 0 0 #000'
          : '0 1px 0 #fff, 0 -1px 0 #fff, 1px 0 0 #fff, -1px 0 0 #fff'
        );
    }

    // Force simulation
    const simulation = d3.forceSimulation<SimNode, SimLink>(simNodes)
      .force('link',
        d3.forceLink<SimNode, SimLink>(simLinks)
          .id(d => d.id)
          .distance(80)
      )
      .force('charge', d3.forceManyBody().strength(-150))
      .force('center', d3.forceCenter(width / 2, height / 2).strength(0.1))
      .force('collision', d3.forceCollide<SimNode>().radius(d => d.size + 8));

    simulationRef.current = simulation;

    // Tick handler — update positions
    simulation.on('tick', () => {
      linkElements
        .attr('x1', d => (d.source as SimNode).x || 0)
        .attr('y1', d => (d.source as SimNode).y || 0)
        .attr('x2', d => (d.target as SimNode).x || 0)
        .attr('y2', d => (d.target as SimNode).y || 0);

      nodeElements
        .attr('transform', d => `translate(${d.x || 0},${d.y || 0})`);
    });

    // Drag behavior
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
  }, [simNodes, simLinks, dimensions, settings, theme, onNodeClick]);

  // Hover/selection highlighting
  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll<SVGCircleElement, SimNode>('g.nodes g circle')
      .attr('stroke-width', (d: SimNode) => {
        if (d.id === hoveredNode || d.id === selectedNode) return 3;
        return d.type === 'document' ? 3 : 1.5;
      })
      .attr('stroke', (d: SimNode) => {
        if (d.id === hoveredNode || d.id === selectedNode) return '#fff';
        if (d.type === 'document') return '#fbbf24';
        return d.isQueryMatch ? '#fcd34d' : '#818cf8';
      });
  }, [hoveredNode, selectedNode]);

  // Selected node data for info box
  const selectedNodeData = useMemo(() => {
    if (!selectedNode) return null;
    return simNodes.find(n => n.id === selectedNode);
  }, [selectedNode, simNodes]);

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
          edgeCount={simLinks.length}
        />
      </PanelStack>

      {selectedNodeData && (
        <NodeInfoBox
          info={{
            nodeId: selectedNode!,
            label: selectedNodeData.label || 'Unknown',
            group: selectedNodeData.type === 'document' ? 'document' : (selectedNodeData.isQueryMatch ? 'query match' : 'document only'),
            degree: simLinks.filter(l =>
              (l.source as SimNode).id === selectedNode || (l.target as SimNode).id === selectedNode
            ).length,
            x: (selectedNodeData.x || 0) * zoomTransform.k + zoomTransform.x,
            y: (selectedNodeData.y || 0) * zoomTransform.k + zoomTransform.y,
          }}
          onDismiss={() => setSelectedNode(null)}
        />
      )}
    </div>
  );
};

export default DocumentExplorer;
