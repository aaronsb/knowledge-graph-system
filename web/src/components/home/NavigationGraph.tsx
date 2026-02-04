/**
 * NavigationGraph
 *
 * A static, deterministic graph visualization of the workstation's features.
 * Uses the platform's own visual language (nodes + edges) to explain itself.
 * Nodes are clickable and navigate to the corresponding view.
 * No physics — fixed positions for consistent rendering.
 */

import React, { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';

interface GraphNode {
  id: string;
  label: string;
  x: number;
  y: number;
  route: string;
  category: 'core' | 'explore' | 'analyze' | 'build' | 'data';
  size: number;
}

interface GraphEdge {
  from: string;
  to: string;
  label: string;
}

const CATEGORY_COLORS: Record<string, { fill: string; stroke: string; text: string }> = {
  core: { fill: 'hsl(var(--primary-h), var(--primary-s), var(--primary-l))', stroke: 'hsl(var(--primary-h), var(--primary-s), calc(var(--primary-l) - 10%))', text: '#fff' },
  data: { fill: '#22c55e', stroke: '#16a34a', text: '#fff' },
  explore: { fill: '#f97316', stroke: '#ea580c', text: '#fff' },
  analyze: { fill: '#a855f7', stroke: '#9333ea', text: '#fff' },
  build: { fill: '#06b6d4', stroke: '#0891b2', text: '#fff' },
};

const NODES: GraphNode[] = [
  // Core data model
  { id: 'concepts', label: 'Concepts', x: 480, y: 220, route: '/explore/2d', category: 'core', size: 48 },
  { id: 'relationships', label: 'Relationships', x: 720, y: 130, route: '/vocabulary', category: 'core', size: 36 },
  { id: 'ontologies', label: 'Ontologies', x: 720, y: 310, route: '/embeddings', category: 'core', size: 36 },

  // Data input
  { id: 'documents', label: 'Documents', x: 160, y: 140, route: '/explore/documents', category: 'data', size: 34 },
  { id: 'ingest', label: 'Ingest', x: 160, y: 310, route: '/ingest', category: 'data', size: 28 },

  // Explorers
  { id: 'graph2d', label: '2D Graph', x: 350, y: 70, route: '/explore/2d', category: 'explore', size: 28 },
  { id: 'graph3d', label: '3D Graph', x: 530, y: 55, route: '/explore/3d', category: 'explore', size: 28 },
  { id: 'docexplorer', label: 'Document\nExplorer', x: 280, y: 195, route: '/explore/documents', category: 'explore', size: 26 },

  // Analyzers
  { id: 'polarity', label: 'Polarity', x: 900, y: 70, route: '/polarity', category: 'analyze', size: 28 },
  { id: 'embeddings', label: 'Embedding\nLandscape', x: 920, y: 230, route: '/embeddings', category: 'analyze', size: 26 },
  { id: 'edgeexplorer', label: 'Edge\nExplorer', x: 900, y: 380, route: '/vocabulary', category: 'analyze', size: 26 },

  // Build
  { id: 'blocks', label: 'Block\nEditor', x: 350, y: 380, route: '/blocks', category: 'build', size: 28 },
  { id: 'vocab', label: 'Vocabulary\nAnalysis', x: 560, y: 400, route: '/vocabulary/chord', category: 'build', size: 24 },
];

const EDGES: GraphEdge[] = [
  // Data flow
  { from: 'documents', to: 'concepts', label: 'EXTRACTS' },
  { from: 'ingest', to: 'documents', label: 'UPLOADS' },
  { from: 'concepts', to: 'relationships', label: 'CONNECTED_BY' },
  { from: 'concepts', to: 'ontologies', label: 'GROUPED_IN' },

  // Exploration paths
  { from: 'concepts', to: 'graph2d', label: 'VISUALIZED_IN' },
  { from: 'concepts', to: 'graph3d', label: 'VISUALIZED_IN' },
  { from: 'documents', to: 'docexplorer', label: 'VIEWED_IN' },
  { from: 'concepts', to: 'docexplorer', label: 'EXPLORES' },

  // Analysis paths
  { from: 'concepts', to: 'polarity', label: 'PROJECTED_ON' },
  { from: 'ontologies', to: 'embeddings', label: 'MAPPED_IN' },
  { from: 'relationships', to: 'edgeexplorer', label: 'ANALYZED_IN' },
  { from: 'relationships', to: 'polarity', label: 'MEASURES' },

  // Build paths
  { from: 'concepts', to: 'blocks', label: 'QUERIED_BY' },
  { from: 'relationships', to: 'vocab', label: 'BREAKDOWN' },
  { from: 'concepts', to: 'vocab', label: 'SCOPED_TO' },
];

const WIDTH = 1060;
const HEIGHT = 460;

/** Static SVG graph of workstation features as clickable nodes with category coloring.
 *  Fixed positions (no physics) for deterministic rendering on the home page.
 *  @verified b38d816f */
export const NavigationGraph: React.FC = () => {
  const navigate = useNavigate();
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  const nodeMap = new Map(NODES.map(n => [n.id, n]));

  const handleNodeClick = useCallback((route: string) => {
    navigate(route);
  }, [navigate]);

  return (
    <svg
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className="w-full"
      style={{ fontFamily: 'var(--font-sans, "IBM Plex Sans Condensed", sans-serif)' }}
    >
      {/* Edges */}
      {EDGES.map((edge, i) => {
        const from = nodeMap.get(edge.from);
        const to = nodeMap.get(edge.to);
        if (!from || !to) return null;

        const midX = (from.x + to.x) / 2;
        const midY = (from.y + to.y) / 2;

        // Slight curve offset for visual interest
        const dx = to.x - from.x;
        const dy = to.y - from.y;
        const len = Math.sqrt(dx * dx + dy * dy);
        const perpX = -dy / len * 12;
        const perpY = dx / len * 12;
        const ctrlX = midX + perpX;
        const ctrlY = midY + perpY;

        // Highlight edges connected to hovered node
        const isHighlighted = hoveredNode === edge.from || hoveredNode === edge.to;

        return (
          <g key={`edge-${i}`}>
            <path
              d={`M ${from.x} ${from.y} Q ${ctrlX} ${ctrlY} ${to.x} ${to.y}`}
              fill="none"
              stroke="hsl(var(--border-h), var(--border-s), var(--border-l))"
              strokeWidth={isHighlighted ? 2 : 1.5}
              strokeOpacity={isHighlighted ? 0.8 : 0.35}
            />
            <text
              x={ctrlX}
              y={ctrlY - 6}
              textAnchor="middle"
              fontSize={9}
              fontWeight={500}
              fill="hsl(var(--fg-h), calc(var(--fg-s) - 20%), calc(var(--fg-l) + 20%))"
              fillOpacity={isHighlighted ? 0.7 : 0.35}
              style={{ fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)', letterSpacing: '0.02em' }}
            >
              {edge.label}
            </text>
          </g>
        );
      })}

      {/* Nodes */}
      {NODES.map((node) => {
        const colors = CATEGORY_COLORS[node.category];
        const lines = node.label.split('\n');
        const isHovered = hoveredNode === node.id;

        return (
          <g
            key={node.id}
            onClick={() => handleNodeClick(node.route)}
            onMouseEnter={() => setHoveredNode(node.id)}
            onMouseLeave={() => setHoveredNode(null)}
            style={{ cursor: 'pointer' }}
            role="button"
            tabIndex={0}
            aria-label={`Navigate to ${node.label.replace('\n', ' ')}`}
          >
            {/* Glow */}
            <circle
              cx={node.x}
              cy={node.y}
              r={node.size + 6}
              fill={colors.fill}
              fillOpacity={isHovered ? 0.3 : 0.12}
            />
            {/* Node circle */}
            <circle
              cx={node.x}
              cy={node.y}
              r={node.size}
              fill={colors.fill}
              stroke={isHovered ? '#fff' : colors.stroke}
              strokeWidth={isHovered ? 3 : 2}
              opacity={isHovered ? 1 : 0.9}
            />
            {/* Label */}
            {lines.map((line, li) => (
              <text
                key={li}
                x={node.x}
                y={node.y + (li - (lines.length - 1) / 2) * 14}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={node.size >= 36 ? 14 : node.size >= 28 ? 12 : 10}
                fontWeight={600}
                fill={colors.text}
                pointerEvents="none"
              >
                {line}
              </text>
            ))}
          </g>
        );
      })}

      {/* Legend */}
      {[
        { label: 'Core', category: 'core' },
        { label: 'Data', category: 'data' },
        { label: 'Explore', category: 'explore' },
        { label: 'Analyze', category: 'analyze' },
        { label: 'Build', category: 'build' },
      ].map((item, i) => {
        const colors = CATEGORY_COLORS[item.category];
        return (
          <g key={item.category} transform={`translate(${16 + i * 100}, ${HEIGHT - 20})`}>
            <circle cx={7} cy={0} r={7} fill={colors.fill} opacity={0.8} />
            <text x={20} y={1} fontSize={11} fontWeight={500} fill="hsl(var(--fg-h), var(--fg-s), var(--fg-l))" fillOpacity={0.6} dominantBaseline="central">
              {item.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
};
