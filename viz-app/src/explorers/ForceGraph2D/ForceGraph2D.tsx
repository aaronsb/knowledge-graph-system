/**
 * Force-Directed 2D Graph Explorer - Main Component
 *
 * Interactive 2D force-directed graph visualization using D3.js.
 * Follows ADR-034 Explorer Plugin Interface.
 */

import React, { useEffect, useRef, useState, useMemo } from 'react';
import * as d3 from 'd3';
import type { ExplorerProps } from '../../types/explorer';
import type { D3Node, D3Link } from '../../types/graph';
import type { ForceGraph2DSettings, ForceGraph2DData } from './types';
import { getNeighbors } from '../../utils/graphTransform';

export const ForceGraph2D: React.FC<
  ExplorerProps<ForceGraph2DData, ForceGraph2DSettings>
> = ({ data, settings, onNodeClick, className }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const [dimensions, setDimensions] = useState({ width: 1000, height: 800 });
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const simulationRef = useRef<d3.Simulation<D3Node, D3Link> | null>(null);

  // Calculate neighbors for highlighting
  const neighbors = useMemo(() => {
    if (!hoveredNode || !settings.interaction.highlightNeighbors) return new Set<string>();
    return getNeighbors(hoveredNode, data.links);
  }, [hoveredNode, data.links, settings.interaction.highlightNeighbors]);

  // Initialize and update force simulation
  useEffect(() => {
    if (!svgRef.current || !data.nodes.length) return;

    const svg = d3.select(svgRef.current);
    const width = dimensions.width;
    const height = dimensions.height;

    // Clear previous content
    svg.selectAll('*').remove();

    // Create container groups
    const g = svg.append('g').attr('class', 'graph-container');
    const linksGroup = g.append('g').attr('class', 'links');
    const nodesGroup = g.append('g').attr('class', 'nodes');

    // Setup zoom behavior
    if (settings.interaction.enableZoom || settings.interaction.enablePan) {
      const zoom = d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.1, 10])
        .on('zoom', (event) => {
          g.attr('transform', event.transform);
        });

      if (settings.interaction.enableZoom && settings.interaction.enablePan) {
        svg.call(zoom);
      } else if (settings.interaction.enableZoom) {
        svg.call(zoom).on('mousedown.zoom', null);
      } else if (settings.interaction.enablePan) {
        svg.call(zoom).on('wheel.zoom', null);
      }
    }

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

    simulationRef.current = simulation;

    // Stop simulation if physics disabled
    if (!settings.physics.enabled) {
      simulation.stop();
    }

    // Draw links
    const link = linksGroup
      .selectAll<SVGLineElement, D3Link>('line')
      .data(data.links)
      .join('line')
      .attr('stroke', (d) => d.color)
      .attr('stroke-width', (d) => (d.value || 1) * settings.visual.linkWidth)
      .attr('stroke-opacity', 0.6)
      .attr('marker-end', settings.visual.showArrows ? 'url(#arrowhead)' : '');

    // Add arrow marker definition
    if (settings.visual.showArrows) {
      svg
        .append('defs')
        .append('marker')
        .attr('id', 'arrowhead')
        .attr('viewBox', '-0 -5 10 10')
        .attr('refX', 20)
        .attr('refY', 0)
        .attr('orient', 'auto')
        .attr('markerWidth', 8)
        .attr('markerHeight', 8)
        .append('path')
        .attr('d', 'M 0,-5 L 10,0 L 0,5')
        .attr('fill', '#999');
    }

    // Draw nodes
    const node = nodesGroup
      .selectAll<SVGCircleElement, D3Node>('circle')
      .data(data.nodes)
      .join('circle')
      .attr('r', (d) => (d.size || 10) * settings.visual.nodeSize)
      .attr('fill', (d) => d.color)
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .attr('cursor', 'pointer')
      .on('click', (_event, d) => {
        if (onNodeClick) onNodeClick(d.id);
      })
      .on('mouseenter', (_event, d) => {
        setHoveredNode(d.id);
      })
      .on('mouseleave', () => {
        setHoveredNode(null);
      });

    // Add labels if enabled
    if (settings.visual.showLabels) {
      const labels = nodesGroup
        .selectAll<SVGTextElement, D3Node>('text')
        .data(data.nodes)
        .join('text')
        .text((d) => d.label)
        .attr('font-size', 10)
        .attr('dx', (d) => (d.size || 10) * settings.visual.nodeSize + 5)
        .attr('dy', 4)
        .attr('fill', '#333')
        .attr('pointer-events', 'none');

      simulation.on('tick', () => {
        labels.attr('x', (d) => d.x || 0).attr('y', (d) => d.y || 0);
      });
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
      link
        .attr('x1', (d) => (typeof d.source === 'object' ? d.source.x || 0 : 0))
        .attr('y1', (d) => (typeof d.source === 'object' ? d.source.y || 0 : 0))
        .attr('x2', (d) => (typeof d.target === 'object' ? d.target.x || 0 : 0))
        .attr('y2', (d) => (typeof d.target === 'object' ? d.target.y || 0 : 0));

      node.attr('cx', (d) => d.x || 0).attr('cy', (d) => d.y || 0);
    });

    return () => {
      simulation.stop();
    };
  }, [data, settings, dimensions, onNodeClick]);

  // Update highlighting based on hover
  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);

    svg.selectAll<SVGCircleElement, D3Node>('circle').attr('opacity', (d) => {
      if (!hoveredNode) return 1;
      if (d.id === hoveredNode) return 1;
      if (neighbors.has(d.id)) return 1;
      return 0.2;
    });

    svg.selectAll<SVGLineElement, D3Link>('line').attr('stroke-opacity', (link) => {
      if (!hoveredNode) return 0.6;
      const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
      const targetId = typeof link.target === 'string' ? link.target : link.target.id;
      if (sourceId === hoveredNode || targetId === hoveredNode) return 1;
      return 0.1;
    });
  }, [hoveredNode, neighbors]);

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

  return (
    <div className={`relative w-full h-full ${className || ''}`}>
      <svg
        ref={svgRef}
        width={dimensions.width}
        height={dimensions.height}
        className="bg-white dark:bg-gray-900"
      />

      {/* Node count indicator */}
      <div className="absolute top-4 right-4 bg-white dark:bg-gray-800 rounded-lg shadow-lg px-3 py-2 text-sm">
        <div className="text-gray-600 dark:text-gray-400">
          {data.nodes.length} nodes • {data.links.length} edges
        </div>
      </div>
    </div>
  );
};
