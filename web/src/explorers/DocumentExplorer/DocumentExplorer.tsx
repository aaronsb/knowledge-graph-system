/**
 * Document Explorer - Radial Visualization
 *
 * Visualizes document→concept relationships as a radial graph with
 * spreading activation decay (ADR-085).
 */

import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import * as d3 from 'd3';
import type { ExplorerProps } from '../../types/explorer';
import type {
  DocumentExplorerSettings,
  DocumentExplorerData,
  ConceptNode,
  DocumentNode,
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

/**
 * Calculate fixed radial positions for all nodes
 */
function calculateRadialPositions(
  document: DocumentNode,
  concepts: ConceptNode[],
  ringRadius: number
): { document: DocumentNode; concepts: ConceptNode[] } {
  // Document at center
  const positionedDoc = { ...document, fx: 0, fy: 0 };

  // Group concepts by hop
  const byHop = new Map<number, ConceptNode[]>();
  concepts.forEach(c => {
    const list = byHop.get(c.hop) || [];
    list.push(c);
    byHop.set(c.hop, list);
  });

  // Position each hop ring
  const positionedConcepts: ConceptNode[] = [];
  byHop.forEach((nodesInHop, hop) => {
    const count = nodesInHop.length;
    nodesInHop.forEach((node, i) => {
      const angle = (i / count) * 2 * Math.PI - Math.PI / 2; // Start at top
      const radius = hop * ringRadius;
      positionedConcepts.push({
        ...node,
        fx: Math.cos(angle) * radius,
        fy: Math.sin(angle) * radius,
      });
    });
  });

  return { document: positionedDoc, concepts: positionedConcepts };
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

  // Calculate radial positions
  const positionedData = useMemo(() => {
    if (!data?.document || !data?.concepts) {
      return { document: null, concepts: [] };
    }
    return calculateRadialPositions(
      data.document,
      data.concepts,
      settings.layout.ringRadius
    );
  }, [data, settings.layout.ringRadius]);

  // Calculate node intensities
  const nodeIntensities = useMemo(() => {
    const intensities = new Map<string, number>();
    positionedData.concepts.forEach(c => {
      intensities.set(
        c.id,
        calculateIntensity(c.hop, c.grounding_strength, settings.visual.decayFactor)
      );
    });
    return intensities;
  }, [positionedData.concepts, settings.visual.decayFactor]);

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

  // Main D3 rendering
  useEffect(() => {
    if (!svgRef.current || !positionedData.document) return;

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
    const maxHop = Math.max(...positionedData.concepts.map(c => c.hop), 1);
    const ringGroup = g.append('g').attr('class', 'rings');
    for (let hop = 1; hop <= maxHop; hop++) {
      ringGroup.append('circle')
        .attr('cx', 0)
        .attr('cy', 0)
        .attr('r', hop * settings.layout.ringRadius)
        .attr('fill', 'none')
        .attr('stroke', theme === 'dark' ? '#374151' : '#e5e7eb')
        .attr('stroke-width', 1)
        .attr('stroke-dasharray', '4,4')
        .attr('opacity', 0.5);
    }

    // Draw links
    const linkGroup = g.append('g').attr('class', 'links');
    if (data.links) {
      linkGroup.selectAll('line')
        .data(data.links)
        .join('line')
        .attr('x1', d => {
          if (d.source === positionedData.document?.id) return 0;
          const node = positionedData.concepts.find(c => c.id === d.source);
          return node?.fx || 0;
        })
        .attr('y1', d => {
          if (d.source === positionedData.document?.id) return 0;
          const node = positionedData.concepts.find(c => c.id === d.source);
          return node?.fy || 0;
        })
        .attr('x2', d => {
          if (d.target === positionedData.document?.id) return 0;
          const node = positionedData.concepts.find(c => c.id === d.target);
          return node?.fx || 0;
        })
        .attr('y2', d => {
          if (d.target === positionedData.document?.id) return 0;
          const node = positionedData.concepts.find(c => c.id === d.target);
          return node?.fy || 0;
        })
        .attr('stroke', theme === 'dark' ? '#6b7280' : '#9ca3af')
        .attr('stroke-width', 1)
        .attr('opacity', 0.4);
    }

    // Draw concept nodes
    const nodeGroup = g.append('g').attr('class', 'nodes');
    const conceptNodes = nodeGroup.selectAll<SVGGElement, ConceptNode>('g.concept')
      .data(positionedData.concepts)
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
    conceptNodes.append('circle')
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
      conceptNodes.append('text')
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

    // Draw document node (center)
    const docGroup = g.append('g').attr('class', 'document-node');

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
        const label = positionedData.document?.label || 'Document';
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

  }, [positionedData, dimensions, settings, theme, hoveredNode, selectedNode, nodeIntensities, data.links, onNodeClick]);

  // Get selected node data for info box
  const selectedNodeData = useMemo(() => {
    if (!selectedNode) return null;
    return positionedData.concepts.find(c => c.id === selectedNode);
  }, [selectedNode, positionedData.concepts]);

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
          nodeCount={positionedData.concepts.length + 1}
          edgeCount={data.links?.length || 0}
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
            x: (selectedNodeData.fx || 0) * zoomTransform.k + zoomTransform.x + dimensions.width / 2,
            y: (selectedNodeData.fy || 0) * zoomTransform.k + zoomTransform.y + dimensions.height / 2,
          }}
          onDismiss={() => setSelectedNode(null)}
        />
      )}
    </div>
  );
};

export default DocumentExplorer;
