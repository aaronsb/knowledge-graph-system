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
 * Calculate radial tidy tree positions for all nodes
 * Uses D3's tree layout for proper subtree spacing
 */
function calculateTreePositions(
  treeRoot: ConceptTreeNode,
  ringRadius: number
): PositionedTreeNode[] {
  // Build d3 hierarchy from our tree structure
  const root = d3.hierarchy<ConceptTreeNode>(treeRoot);

  // Calculate max depth for radius scaling
  const maxDepth = Math.max(1, root.height);
  const totalRadius = (maxDepth + 1) * ringRadius;

  // Create radial tree layout
  const treeLayout = d3.tree<ConceptTreeNode>()
    .size([2 * Math.PI, totalRadius])
    .separation((a, b) => {
      // More space between different parents, less within same parent
      return (a.parent === b.parent ? 1 : 1.5) / Math.max(1, a.depth);
    });

  // Apply layout
  const treeNodes = treeLayout(root);

  // Convert polar to cartesian and collect positioned nodes
  const positionedNodes: PositionedTreeNode[] = [];

  treeNodes.each((node) => {
    const angle = node.x - Math.PI / 2; // Rotate so 0 is at top
    const radius = node.y;

    const positioned: PositionedTreeNode = {
      ...node.data,
      x: node.x,
      y: node.y,
      fx: radius * Math.cos(angle),
      fy: radius * Math.sin(angle),
      depth: node.depth,
      parent: node.parent as unknown as PositionedTreeNode | null,
    };

    positionedNodes.push(positioned);
  });

  return positionedNodes;
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
  const positionedNodes = useMemo((): PositionedTreeNode[] => {
    if (!data?.document) return [];

    // Use tree layout if tree structure is available
    if (data.treeRoot) {
      return calculateTreePositions(data.treeRoot, settings.layout.ringRadius);
    }

    // Fallback: flat radial layout (converts ConceptNode to PositionedTreeNode-like)
    const flatPositioned = calculateFlatRadialPositions(data.concepts || [], settings.layout.ringRadius);
    return flatPositioned.map(c => ({
      ...c,
      x: 0,
      y: 0,
      depth: c.hop + 1, // depth 0 is document, hop 0 -> depth 1
      parent: null,
      children: [],
    })) as PositionedTreeNode[];
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

  // Build tree links from positioned nodes (for curved path rendering)
  const treeLinks = useMemo(() => {
    if (!data.treeRoot) return [];

    // Create lookup map for quick access
    const nodeMap = new Map<string, PositionedTreeNode>();
    positionedNodes.forEach(n => nodeMap.set(n.id, n));

    // Build links by traversing tree structure
    const links: Array<{ source: PositionedTreeNode; target: PositionedTreeNode }> = [];

    const traverse = (node: ConceptTreeNode) => {
      const sourcePos = nodeMap.get(node.id);
      if (!sourcePos) return;

      node.children?.forEach(child => {
        const targetPos = nodeMap.get(child.id);
        if (targetPos) {
          links.push({ source: sourcePos, target: targetPos });
        }
        traverse(child);
      });
    };

    traverse(data.treeRoot);
    return links;
  }, [data.treeRoot, positionedNodes]);

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

    // Draw tree links as curved paths
    const linkGroup = g.append('g').attr('class', 'links');

    if (treeLinks.length > 0) {
      // Use radial link generator for tree edges
      linkGroup.selectAll('path')
        .data(treeLinks)
        .join('path')
        .attr('d', d => {
          // Calculate radial curve from source to target
          const sourceAngle = d.source.x - Math.PI / 2;
          const targetAngle = d.target.x - Math.PI / 2;
          const sourceRadius = d.source.y;
          const targetRadius = d.target.y;

          // Use d3.linkRadial for curved tree links
          const link = d3.linkRadial<unknown, { x: number; y: number }>()
            .angle(node => node.x - Math.PI / 2)
            .radius(node => node.y);

          return link({ source: d.source, target: d.target });
        })
        .attr('fill', 'none')
        .attr('stroke', d => {
          // Fade links based on target hop (spreading activation)
          const targetIntensity = nodeIntensities.get(d.target.id) || 0.5;
          const alpha = 0.2 + 0.4 * targetIntensity;
          return theme === 'dark'
            ? `rgba(107, 114, 128, ${alpha})`
            : `rgba(156, 163, 175, ${alpha})`;
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

    // Concept circles
    conceptNodeElements.append('circle')
      .attr('r', d => {
        const intensity = nodeIntensities.get(d.id) || 0.5;
        const baseSize = 8 + 12 * intensity;
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

    // Concept labels
    if (settings.visual.showLabels) {
      conceptNodeElements.append('text')
        .text(d => {
          const label = d.label || 'Unknown';
          return label.length > 20 ? label.slice(0, 20) + '...' : label;
        })
        .attr('dy', d => {
          const intensity = nodeIntensities.get(d.id) || 0.5;
          return (8 + 12 * intensity) * settings.visual.nodeSize + 12;
        })
        .attr('text-anchor', 'middle')
        .attr('font-family', LABEL_FONTS.family)
        .attr('font-size', '11px')
        .attr('fill', theme === 'dark' ? '#e5e7eb' : '#374151')
        .attr('opacity', d => {
          const intensity = nodeIntensities.get(d.id) || 0.5;
          return settings.visual.minOpacity + (1 - settings.visual.minOpacity) * intensity;
        });
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

    // Document label
    docGroup.append('text')
      .text(() => {
        const label = documentNode.label || 'Document';
        return label.length > 25 ? label.slice(0, 25) + '...' : label;
      })
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
