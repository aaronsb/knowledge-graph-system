/**
 * Document Explorer - Radial Tidy Tree Visualization
 *
 * Visualizes document→concept relationships as a radial tidy tree with
 * spreading activation decay (ADR-085).
 *
 * Tree structure represents activation paths:
 * - Root: Document
 * - Hop 0: Concepts extracted from this document
 * - Hop 1+: Related concepts (spreading activation)
 */

import React, { useEffect, useRef, useState, useMemo } from 'react';
import * as d3 from 'd3';
import type { ExplorerProps } from '../../types/explorer';
import type {
  DocumentExplorerSettings,
  DocumentExplorerData,
  ConceptNode,
  ConceptTreeNode,
} from './types';
import { useThemeStore } from '../../store/themeStore';
import {
  NodeInfoBox,
  StatsPanel,
  PanelStack,
  LABEL_FONTS,
} from '../common';

// Grounding status colors (match existing explorer)
const GROUNDING_COLORS = {
  strong: '#22c55e',     // Green
  moderate: '#eab308',   // Yellow
  weak: '#6b7280',       // Gray
  contradicted: '#ef4444', // Red
};

function getGroundingColor(strength: number): string {
  if (strength >= 0.6) return GROUNDING_COLORS.strong;
  if (strength >= 0.3) return GROUNDING_COLORS.moderate;
  if (strength >= 0) return GROUNDING_COLORS.weak;
  return GROUNDING_COLORS.contradicted;
}

/**
 * Calculate intensity using spreading activation decay
 */
function calculateIntensity(
  hop: number,
  groundingStrength: number,
  decayFactor: number
): number {
  const hopDecay = Math.pow(decayFactor, hop);
  return hopDecay * Math.max(0, groundingStrength);
}

// Extended tree node type with D3 hierarchy computed properties
interface PositionedTreeNode extends ConceptTreeNode {
  x: number;  // angle in radians (from d3.tree)
  y: number;  // radius (from d3.tree)
  fx: number; // cartesian x
  fy: number; // cartesian y
  depth: number;
  parent: PositionedTreeNode | null;
}

/**
 * Convert polar coordinates to cartesian
 * Matches the reference radial-tidy-tree.html implementation
 */
function radialPoint(x: number, y: number): [number, number] {
  return [y * Math.cos(x - Math.PI / 2), y * Math.sin(x - Math.PI / 2)];
}

/**
 * Calculate radial tidy tree positions for all nodes
 * Uses D3's tree layout for proper subtree spacing
 */
function calculateTreePositions(
  treeRoot: ConceptTreeNode,
  ringRadius: number
): { nodes: PositionedTreeNode[]; hierarchy: d3.HierarchyPointNode<ConceptTreeNode> } {
  // Build d3 hierarchy from our tree structure
  const root = d3.hierarchy<ConceptTreeNode>(treeRoot);

  // Calculate max depth for radius scaling
  const maxDepth = Math.max(1, root.height);
  const totalRadius = (maxDepth + 1) * ringRadius;

  // Create radial tree layout - matches reference implementation
  const treeLayout = d3.tree<ConceptTreeNode>()
    .size([2 * Math.PI, totalRadius])
    .separation((a, b) => {
      // Reference: (a.parent == b.parent ? 1 : 2) / a.depth
      return (a.parent === b.parent ? 1 : 2) / Math.max(1, a.depth);
    });

  // Apply layout
  const treeNodes = treeLayout(root);

  // Convert polar to cartesian and collect positioned nodes
  const positionedNodes: PositionedTreeNode[] = [];

  treeNodes.each((node) => {
    const [fx, fy] = radialPoint(node.x, node.y);

    const positioned: PositionedTreeNode = {
      ...node.data,
      x: node.x,  // angle in radians
      y: node.y,  // radius
      fx,
      fy,
      depth: node.depth,
      parent: node.parent as unknown as PositionedTreeNode | null,
    };

    positionedNodes.push(positioned);
  });

  return { nodes: positionedNodes, hierarchy: treeNodes };
}

/**
 * Fallback: Calculate uniform radial positions when no tree structure
 */
function calculateFlatRadialPositions(
  concepts: ConceptNode[],
  ringRadius: number
): ConceptNode[] {
  // Group concepts by hop
  const byHop = new Map<number, ConceptNode[]>();
  concepts.forEach(c => {
    const list = byHop.get(c.hop) || [];
    list.push(c);
    byHop.set(c.hop, list);
  });

  // Position each hop ring
  const positionedConcepts: ConceptNode[] = [];
  const MIN_NODE_SPACING = 40;

  byHop.forEach((nodesInHop, hop) => {
    const count = nodesInHop.length;
    const minRadiusForSpacing = (count * MIN_NODE_SPACING) / (2 * Math.PI);
    const baseRadius = (hop + 1) * ringRadius;
    const radius = Math.max(baseRadius, minRadiusForSpacing);

    nodesInHop.forEach((node, i) => {
      const angle = (i / count) * 2 * Math.PI - Math.PI / 2;
      positionedConcepts.push({
        ...node,
        fx: Math.cos(angle) * radius,
        fy: Math.sin(angle) * radius,
      });
    });
  });

  return positionedConcepts;
}

export const DocumentExplorer: React.FC<
  ExplorerProps<DocumentExplorerData, DocumentExplorerSettings>
> = ({ data, settings, onSettingsChange, onNodeClick, className }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const zoomBehaviorRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const [zoomTransform, setZoomTransform] = useState({ x: 0, y: 0, k: 1 });

  const { appliedTheme: theme } = useThemeStore();

  // Calculate tree positions (or fallback to flat radial)
  const { positionedNodes, treeHierarchy } = useMemo(() => {
    if (!data?.document) return { positionedNodes: [], treeHierarchy: null };

    // Use tree layout if tree structure is available
    if (data.treeRoot) {
      const result = calculateTreePositions(data.treeRoot, settings.layout.ringRadius);
      return { positionedNodes: result.nodes, treeHierarchy: result.hierarchy };
    }

    // Fallback: flat radial layout (converts ConceptNode to PositionedTreeNode-like)
    const flatPositioned = calculateFlatRadialPositions(data.concepts || [], settings.layout.ringRadius);
    const nodes = flatPositioned.map(c => ({
      ...c,
      x: 0,
      y: 0,
      depth: c.hop + 1, // depth 0 is document, hop 0 -> depth 1
      parent: null,
      children: [],
    })) as PositionedTreeNode[];
    return { positionedNodes: nodes, treeHierarchy: null };
  }, [data, settings.layout.ringRadius]);

  // Separate document node (root) and concept nodes
  const { documentNode, conceptNodes } = useMemo(() => {
    const docNode = positionedNodes.find(n => n.type === 'document') || null;
    const concepts = positionedNodes.filter(n => n.type === 'concept');
    return { documentNode: docNode, conceptNodes: concepts };
  }, [positionedNodes]);

  // Calculate node intensities based on hop (spreading activation decay)
  const nodeIntensities = useMemo(() => {
    const intensities = new Map<string, number>();
    conceptNodes.forEach(c => {
      intensities.set(
        c.id,
        calculateIntensity(c.hop, c.grounding_strength, settings.visual.decayFactor)
      );
    });
    return intensities;
  }, [conceptNodes, settings.visual.decayFactor]);

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

  // Get tree links directly from hierarchy (matches reference implementation)
  const treeLinks = useMemo(() => {
    if (!treeHierarchy) return [];
    // Use d3's built-in links() which returns proper source/target hierarchy nodes
    return treeHierarchy.links();
  }, [treeHierarchy]);

  // Main D3 rendering
  useEffect(() => {
    if (!svgRef.current || !documentNode) return;

    const svg = d3.select(svgRef.current);
    const { width, height } = dimensions;
    const centerX = width / 2;
    const centerY = height / 2;

    // Clear previous content
    svg.selectAll('*').remove();

    // Create main group for zoom/pan
    const g = svg.append('g').attr('class', 'main-group');

    // Setup zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform.toString());
        setZoomTransform({ x: event.transform.x, y: event.transform.y, k: event.transform.k });
      });

    if (settings.interaction.enableZoom || settings.interaction.enablePan) {
      svg.call(zoom);
      // Initial transform to center
      svg.call(zoom.transform, d3.zoomIdentity.translate(centerX, centerY));
    }

    zoomBehaviorRef.current = zoom;

    // Draw hop rings (background guides)
    const maxDepth = Math.max(...conceptNodes.map(c => c.depth), 1);
    const ringGroup = g.append('g').attr('class', 'rings');
    for (let depth = 1; depth <= maxDepth; depth++) {
      ringGroup.append('circle')
        .attr('cx', 0)
        .attr('cy', 0)
        .attr('r', depth * settings.layout.ringRadius)
        .attr('fill', 'none')
        .attr('stroke', theme === 'dark' ? '#374151' : '#e5e7eb')
        .attr('stroke-width', 1)
        .attr('stroke-dasharray', '4,4')
        .attr('opacity', 0.5);
    }

    // Draw tree links as curved paths (matches reference radial-tidy-tree.html)
    const linkGroup = g.append('g').attr('class', 'links');

    if (treeLinks.length > 0) {
      // Create radial link generator - matches reference exactly
      const linkGenerator = d3.linkRadial<d3.HierarchyPointLink<ConceptTreeNode>, d3.HierarchyPointNode<ConceptTreeNode>>()
        .angle(d => d.x)
        .radius(d => d.y);

      linkGroup.selectAll('path')
        .data(treeLinks)
        .join('path')
        .attr('class', 'link')
        .attr('d', linkGenerator)
        .attr('fill', 'none')
        .attr('stroke', d => {
          // Fade links based on target depth (spreading activation)
          const targetIntensity = nodeIntensities.get(d.target.data.id) || 0.5;
          const alpha = 0.3 + 0.4 * targetIntensity;
          return theme === 'dark'
            ? `rgba(107, 114, 128, ${alpha})`
            : `rgba(85, 85, 85, ${alpha})`;
        })
        .attr('stroke-width', 1.5);
    } else if (data.links) {
      // Fallback: straight lines for non-tree data
      const nodeMap = new Map<string, PositionedTreeNode>();
      positionedNodes.forEach(n => nodeMap.set(n.id, n));

      linkGroup.selectAll('line')
        .data(data.links)
        .join('line')
        .attr('x1', d => nodeMap.get(d.source)?.fx || 0)
        .attr('y1', d => nodeMap.get(d.source)?.fy || 0)
        .attr('x2', d => nodeMap.get(d.target)?.fx || 0)
        .attr('y2', d => nodeMap.get(d.target)?.fy || 0)
        .attr('stroke', theme === 'dark' ? '#6b7280' : '#9ca3af')
        .attr('stroke-width', 1)
        .attr('opacity', 0.4);
    }

    // Draw concept nodes
    const nodeGroup = g.append('g').attr('class', 'nodes');
    const conceptNodeElements = nodeGroup.selectAll<SVGGElement, PositionedTreeNode>('g.concept')
      .data(conceptNodes)
      .join('g')
      .attr('class', 'concept')
      .attr('transform', d => `translate(${d.fx},${d.fy})`)
      .style('cursor', 'pointer')
      .on('mouseenter', (event, d) => {
        if (settings.interaction.highlightOnHover) {
          setHoveredNode(d.id);
        }
      })
      .on('mouseleave', () => setHoveredNode(null))
      .on('click', (event, d) => {
        event.stopPropagation();
        setSelectedNode(d.id);
        onNodeClick?.(d.id);
      });

    // Concept circles - smaller like reference (r=2.5 base)
    conceptNodeElements.append('circle')
      .attr('r', d => {
        const intensity = nodeIntensities.get(d.id) || 0.5;
        const baseSize = 2.5 + 3 * intensity;
        return baseSize * settings.visual.nodeSize;
      })
      .attr('fill', d => {
        if (settings.visual.colorBy === 'grounding') {
          return getGroundingColor(d.grounding_strength);
        }
        // TODO: ontology-based coloring
        return '#6366f1';
      })
      .attr('opacity', d => {
        const intensity = nodeIntensities.get(d.id) || 0.5;
        return settings.visual.minOpacity + (1 - settings.visual.minOpacity) * intensity;
      })
      .attr('stroke', d => d.id === hoveredNode || d.id === selectedNode ? '#fff' : 'none')
      .attr('stroke-width', 2);

    // Concept labels - radial rotation like reference radial-tidy-tree.html
    if (settings.visual.showLabels) {
      conceptNodeElements.append('text')
        .text(d => d.label || 'Unknown')  // Full label, no truncation
        .attr('dy', '0.31em')
        // Position label outside the node, along radial direction
        .attr('x', d => {
          const isLeaf = !d.children || d.children.length === 0;
          // Smaller offset to match smaller nodes
          const offset = isLeaf ? 6 : -6;
          // Flip offset for left side of tree
          return d.x < Math.PI === isLeaf ? offset : -offset;
        })
        .attr('text-anchor', d => {
          const isLeaf = !d.children || d.children.length === 0;
          // Right side: start anchor; Left side: end anchor (flipped for readability)
          return d.x < Math.PI === isLeaf ? 'start' : 'end';
        })
        // Rotate text to follow radial direction, flip on left side
        .attr('transform', d => {
          const angleDeg = (d.x < Math.PI ? d.x - Math.PI / 2 : d.x + Math.PI / 2) * 180 / Math.PI;
          return `rotate(${angleDeg})`;
        })
        .attr('font-family', LABEL_FONTS.family)
        .attr('font-size', '10px')
        .attr('fill', theme === 'dark' ? '#e5e7eb' : '#374151')
        .attr('opacity', d => {
          const intensity = nodeIntensities.get(d.id) || 0.5;
          return settings.visual.minOpacity + (1 - settings.visual.minOpacity) * intensity;
        })
        // Text shadow for readability (like reference)
        .style('text-shadow', theme === 'dark'
          ? '0 1px 0 #000, 0 -1px 0 #000, 1px 0 0 #000, -1px 0 0 #000'
          : '0 1px 0 #fff, 0 -1px 0 #fff, 1px 0 0 #fff, -1px 0 0 #fff'
        );
    }

    // Draw document node (center) - position from tree layout
    const docGroup = g.append('g')
      .attr('class', 'document-node')
      .attr('transform', `translate(${documentNode.fx},${documentNode.fy})`);

    // Pulsing ring effect
    docGroup.append('circle')
      .attr('cx', 0)
      .attr('cy', 0)
      .attr('r', settings.layout.centerSize)
      .attr('fill', 'none')
      .attr('stroke', '#f59e0b')
      .attr('stroke-width', 2)
      .attr('opacity', 0.6)
      .style('animation', 'pulse 2s ease-in-out infinite');

    // Main document circle
    docGroup.append('circle')
      .attr('cx', 0)
      .attr('cy', 0)
      .attr('r', settings.layout.centerSize - 4)
      .attr('fill', '#f59e0b')
      .attr('opacity', 0.9);

    // Document icon (simple file shape)
    const iconSize = settings.layout.centerSize * 0.5;
    docGroup.append('path')
      .attr('d', `M${-iconSize/2},${-iconSize/2} L${iconSize/3},${-iconSize/2} L${iconSize/2},${-iconSize/3} L${iconSize/2},${iconSize/2} L${-iconSize/2},${iconSize/2} Z`)
      .attr('fill', '#fff')
      .attr('opacity', 0.9);

    // Document label - full name, no truncation
    docGroup.append('text')
      .text(() => documentNode.label || 'Document')
      .attr('y', settings.layout.centerSize + 16)
      .attr('text-anchor', 'middle')
      .attr('font-family', LABEL_FONTS.family)
      .attr('font-size', '12px')
      .attr('font-weight', '600')
      .attr('fill', theme === 'dark' ? '#fbbf24' : '#d97706');

    // Add CSS animation for pulse
    if (!document.getElementById('doc-explorer-pulse-style')) {
      const style = document.createElement('style');
      style.id = 'doc-explorer-pulse-style';
      style.textContent = `
        @keyframes pulse {
          0%, 100% { transform: scale(1); opacity: 0.6; }
          50% { transform: scale(1.1); opacity: 0.3; }
        }
      `;
      document.head.appendChild(style);
    }

  }, [documentNode, conceptNodes, treeLinks, positionedNodes, dimensions, settings, theme, hoveredNode, selectedNode, nodeIntensities, data.links, onNodeClick]);

  // Get selected node data for info box
  const selectedNodeData = useMemo(() => {
    if (!selectedNode) return null;
    return conceptNodes.find(c => c.id === selectedNode);
  }, [selectedNode, conceptNodes]);

  return (
    <div className={`relative w-full h-full overflow-hidden ${className || ''}`}>
      <svg
        ref={svgRef}
        width={dimensions.width}
        height={dimensions.height}
        className={`${theme === 'dark' ? 'bg-gray-900' : 'bg-gray-50'}`}
      />

      {/* Left panel stack - Legend omitted for MVP */}

      {/* Right panel stack */}
      <PanelStack side="right">
        <StatsPanel
          nodeCount={conceptNodes.length + 1}
          edgeCount={treeLinks.length || data.links?.length || 0}
        />
      </PanelStack>

      {/* Node info box */}
      {selectedNodeData && (
        <NodeInfoBox
          info={{
            nodeId: selectedNode!,
            label: selectedNodeData.label || 'Unknown',
            group: selectedNodeData.ontology || 'unknown',
            degree: selectedNodeData.instanceCount || 1,
            x: (selectedNodeData.fx || 0) * zoomTransform.k + zoomTransform.x,
            y: (selectedNodeData.fy || 0) * zoomTransform.k + zoomTransform.y,
          }}
          onDismiss={() => setSelectedNode(null)}
        />
      )}
    </div>
  );
};

export default DocumentExplorer;
