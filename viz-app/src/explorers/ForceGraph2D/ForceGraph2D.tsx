/**
 * Force-Directed 2D Graph Explorer - Main Component
 *
 * Interactive 2D force-directed graph visualization using D3.js.
 * Follows ADR-034 Explorer Plugin Interface.
 */

import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import * as d3 from 'd3';
import { ArrowRight, Plus } from 'lucide-react';
import type { ExplorerProps } from '../../types/explorer';
import type { D3Node, D3Link } from '../../types/graph';
import type { ForceGraph2DSettings, ForceGraph2DData } from './types';
import { getNeighbors, transformForD3 } from '../../utils/graphTransform';
import { useGraphStore } from '../../store/graphStore';
import { ContextMenu, type ContextMenuItem } from '../../components/shared/ContextMenu';
import { apiClient } from '../../api/client';

export const ForceGraph2D: React.FC<
  ExplorerProps<ForceGraph2DData, ForceGraph2DSettings>
> = ({ data, settings, onNodeClick, className }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const [dimensions, setDimensions] = useState({ width: 1000, height: 800 });
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const simulationRef = useRef<d3.Simulation<D3Node, D3Link> | null>(null);

  // Imperative function to apply gold ring - can be called anytime
  const applyGoldRing = useCallback((nodeId: string) => {
    if (!svgRef.current || !settings.interaction.showOriginNode) return;

    const svg = d3.select(svgRef.current);

    // Remove from previous node
    svg.selectAll('circle.origin-node')
      .interrupt()
      .attr('stroke', '#fff')
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

  // Context menu state
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    nodeId: string;
    nodeLabel: string;
  } | null>(null);

  // Get navigation state and settings from store
  const { originNodeId, setOriginNodeId, similarityThreshold, setGraphData, graphData } = useGraphStore();

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

    // Add edge labels showing relationship types
    const edgeLabels = linksGroup
      .selectAll<SVGTextElement, D3Link>('text')
      .data(data.links)
      .join('text')
      .text((d) => d.type)
      .attr('font-size', 9)
      .attr('font-weight', 400)
      .attr('fill', '#aaa')
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
      .attr('fill', (d) => d.color)
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .attr('cursor', 'pointer')
      .attr('data-node-id', (d) => d.id) // Add ID for selection
      .on('click', (_event, d) => {
        // Left-click: Select node (show gold ring)
        setOriginNodeId(d.id);
        setContextMenu(null); // Close any open context menu
        applyGoldRing(d.id); // Immediate visual feedback
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

      // Update edge label positions and rotation to align with edges
      edgeLabels.attr('transform', (d) => {
        const sourceX = typeof d.source === 'object' ? d.source.x || 0 : 0;
        const sourceY = typeof d.source === 'object' ? d.source.y || 0 : 0;
        const targetX = typeof d.target === 'object' ? d.target.x || 0 : 0;
        const targetY = typeof d.target === 'object' ? d.target.y || 0 : 0;

        // Calculate midpoint
        const midX = (sourceX + targetX) / 2;
        const midY = (sourceY + targetY) / 2;

        // Calculate angle to rotate text along edge
        let angle = Math.atan2(targetY - sourceY, targetX - sourceX) * (180 / Math.PI);

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
      if (!d || !hoveredNode) return 1;
      if (d.id === hoveredNode) return 1;
      if (neighbors.has(d.id)) return 1;
      return 0.2;
    });

    svg.selectAll<SVGLineElement, D3Link>('line').attr('stroke-opacity', (link) => {
      if (!hoveredNode) return 0.6;
      const sourceId = typeof link.source === 'string' ? link.source : link.source?.id;
      const targetId = typeof link.target === 'string' ? link.target : link.target?.id;
      if (!sourceId || !targetId) return 0.6; // Handle undefined during transition
      if (sourceId === hoveredNode || targetId === hoveredNode) return 1;
      return 0.1;
    });
  }, [hoveredNode, neighbors]);

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
      // Cleanup: remove gold ring
      if (svgRef.current) {
        d3.select(svgRef.current)
          .selectAll('circle.origin-node')
          .interrupt()
          .attr('stroke', '#fff')
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
  const handleFollowConcept = useCallback(async (nodeId: string) => {
    try {
      // 1. Get concept details including embedding
      const conceptDetails = await apiClient.getConceptDetails(nodeId);

      if (!conceptDetails || !conceptDetails.embedding) {
        console.error('No embedding found for concept');
        return;
      }

      // 2. Search using concept's existing embedding
      const searchResults = await apiClient.searchByEmbedding({
        embedding: conceptDetails.embedding,
        limit: 50,
        min_similarity: similarityThreshold,
      });

      if (!searchResults || !searchResults.results || searchResults.results.length === 0) {
        console.warn('No similar concepts found');
        return;
      }

      // 3. Build subgraph from search results
      const relatedConceptIds = searchResults.results.map((r: any) => r.concept_id);
      const subgraphData = await apiClient.getSubgraph({
        center_concept_id: nodeId,
        depth: 1,
        limit: 100,
      });

      // 4. Transform to D3 format and replace graph
      const transformedData = transformForD3(subgraphData.nodes, subgraphData.links);
      setGraphData(transformedData);
      setOriginNodeId(nodeId);
    } catch (error) {
      console.error('Failed to follow concept:', error);
    }
  }, [similarityThreshold, setGraphData, setOriginNodeId]);

  // Handler: Add concept to graph (merge)
  const handleAddToGraph = useCallback(async (nodeId: string) => {
    try {
      // 1. Get concept details including embedding
      const conceptDetails = await apiClient.getConceptDetails(nodeId);

      if (!conceptDetails || !conceptDetails.embedding) {
        console.error('No embedding found for concept');
        return;
      }

      // 2. Search using concept's existing embedding
      const searchResults = await apiClient.searchByEmbedding({
        embedding: conceptDetails.embedding,
        limit: 50,
        min_similarity: similarityThreshold,
      });

      if (!searchResults || !searchResults.results || searchResults.results.length === 0) {
        console.warn('No similar concepts found');
        return;
      }

      // 3. Build subgraph from search results
      const subgraphData = await apiClient.getSubgraph({
        center_concept_id: nodeId,
        depth: 1,
        limit: 100,
      });

      // 4. Transform to D3 format and merge with existing graph
      const transformedData = transformForD3(subgraphData.nodes, subgraphData.links);
      const mergedData = mergeGraphData(transformedData);
      setGraphData(mergedData);
      setOriginNodeId(nodeId);
    } catch (error) {
      console.error('Failed to add concept to graph:', error);
    }
  }, [similarityThreshold, mergeGraphData, setGraphData, setOriginNodeId]);

  // Context menu items
  const contextMenuItems: ContextMenuItem[] = contextMenu
    ? [
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

      {/* Context Menu */}
      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          items={contextMenuItems}
          onClose={() => setContextMenu(null)}
        />
      )}
    </div>
  );
};
