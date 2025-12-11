/**
 * Chord Diagram for Category Flow Visualization (ADR-077)
 *
 * Shows how edge categories connect through shared concepts.
 * When two edges meet at the same concept, their categories are connected.
 * Arcs represent categories, ribbons represent co-occurrence at shared nodes.
 */

import { useMemo, useState, useCallback, useRef, useLayoutEffect } from 'react';
import * as d3 from 'd3';
import { getCategoryColor } from '../../../config/categoryColors';
import type { CategoryStats, EdgeTypeData } from '../types';

interface GraphLink {
  source: string | { id: string };
  target: string | { id: string };
  relationship_type?: string;
  type?: string;
  category?: string;
}

// Pre-computed flow data from API
interface CategoryFlow {
  source: string;
  target: string;
  count: number;
}

interface ChordDiagramProps {
  categories: CategoryStats[];
  edgeTypes: EdgeTypeData[];
  links?: GraphLink[]; // Optional: if provided, computes inter-category flows
  flows?: CategoryFlow[]; // Optional: pre-computed flows from API (takes precedence over links)
  categoryTotals?: Record<string, number>; // Optional: pre-computed category totals for diagonal
  onCategoryClick?: (category: string) => void;
  onCategoryHover?: (category: string | null) => void;
  onChordHover?: (source: string, target: string, count: number) => void;
  selectedCategory?: string | null;
}

export function ChordDiagram({
  categories,
  edgeTypes,
  links,
  flows,
  categoryTotals,
  onCategoryClick,
  onCategoryHover,
  onChordHover,
  selectedCategory,
}: ChordDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 500, height: 500 });
  const [hoveredCategory, setHoveredCategory] = useState<string | null>(null);
  const [hoveredChord, setHoveredChord] = useState<{ source: string; target: string; count: number } | null>(null);

  // Self-sizing: fill the container
  useLayoutEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
          // Use the smaller dimension for a square visualization
          const size = Math.min(rect.width, rect.height);
          setDimensions({ width: size, height: size });
        }
      }
    };

    updateSize();

    const resizeObserver = new ResizeObserver(updateSize);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => resizeObserver.disconnect();
  }, []);

  const { width, height } = dimensions;

  // Build a map from edge type to category
  const typeToCategory = useMemo(() => {
    const map = new Map<string, string>();
    for (const et of edgeTypes) {
      map.set(et.relationship_type, et.category);
    }
    return map;
  }, [edgeTypes]);

  // Build chord data - compute inter-category flows
  const { chordData, categoryNames, matrix } = useMemo(() => {
    // Get unique categories with edges
    const categoryNames = categories
      .filter(c => c.totalEdges > 0)
      .map(c => c.category)
      .sort();

    if (categoryNames.length === 0) {
      return { chordData: null, categoryNames: [], matrix: [] };
    }

    const categoryIndex = new Map(categoryNames.map((name, i) => [name, i]));
    const n = categoryNames.length;

    // Build adjacency matrix
    const matrix: number[][] = Array.from({ length: n }, () => Array(n).fill(0));

    // Priority 1: Use pre-computed flows from API (most efficient)
    if (flows && flows.length > 0) {
      // First, add diagonal entries from categoryTotals if provided
      if (categoryTotals) {
        for (const [cat, count] of Object.entries(categoryTotals)) {
          const idx = categoryIndex.get(cat);
          if (idx !== undefined) {
            matrix[idx][idx] = count;
          }
        }
      }

      // Then populate off-diagonal with flow data
      for (const flow of flows) {
        const idxA = categoryIndex.get(flow.source);
        const idxB = categoryIndex.get(flow.target);
        if (idxA !== undefined && idxB !== undefined) {
          // Flows are symmetric, populate both directions
          matrix[idxA][idxB] = flow.count;
          matrix[idxB][idxA] = flow.count;
        }
      }
    }
    // Priority 2: Compute flows from raw links (used by VocabularyChordWorkspace)
    else if (links && links.length > 0) {
      // First, count total edges per category for the diagonal
      const categoryCounts = new Map<string, number>();

      // Build a map of concept -> list of edge categories touching it (for inter-category flows)
      const conceptCategories = new Map<string, string[]>();

      for (const link of links) {
        const sourceId = typeof link.source === 'string' ? link.source : link.source?.id;
        const targetId = typeof link.target === 'string' ? link.target : link.target?.id;
        const edgeType = link.relationship_type || link.type || '';
        const category = link.category || typeToCategory.get(edgeType) || 'unknown';

        // Count edges per category
        categoryCounts.set(category, (categoryCounts.get(category) || 0) + 1);

        // Track which categories touch each concept (for inter-category flows)
        if (sourceId) {
          const existing = conceptCategories.get(sourceId) || [];
          existing.push(category);
          conceptCategories.set(sourceId, existing);
        }
        if (targetId) {
          const existing = conceptCategories.get(targetId) || [];
          existing.push(category);
          conceptCategories.set(targetId, existing);
        }
      }

      // Populate diagonal with total edge counts per category
      for (const [cat, count] of categoryCounts) {
        const idx = categoryIndex.get(cat);
        if (idx !== undefined) {
          matrix[idx][idx] = count;
        }
      }

      // For each concept, create inter-category connections (off-diagonal)
      for (const [, cats] of conceptCategories) {
        // Get unique categories at this concept
        const uniqueCats = [...new Set(cats)];

        // Only process if multiple different categories meet at this concept
        if (uniqueCats.length > 1) {
          for (let i = 0; i < uniqueCats.length; i++) {
            for (let j = i + 1; j < uniqueCats.length; j++) {
              const catA = uniqueCats[i];
              const catB = uniqueCats[j];
              const idxA = categoryIndex.get(catA);
              const idxB = categoryIndex.get(catB);

              if (idxA !== undefined && idxB !== undefined) {
                // Cross-category connection - count how many times each appears
                const countA = cats.filter(c => c === catA).length;
                const countB = cats.filter(c => c === catB).length;
                const connections = Math.min(countA, countB);
                matrix[idxA][idxB] += connections;
                matrix[idxB][idxA] += connections;
              }
            }
          }
        }
      }
    }
    // Priority 3: Fallback to diagonal only (no inter-category data)
    else {
      const categoryEdgeCounts = new Map<string, number>();
      for (const et of edgeTypes) {
        const current = categoryEdgeCounts.get(et.category) || 0;
        categoryEdgeCounts.set(et.category, current + (et.edge_count || 0));
      }

      for (const [cat, count] of categoryEdgeCounts) {
        const idx = categoryIndex.get(cat);
        if (idx !== undefined) {
          matrix[idx][idx] = count;
        }
      }
    }

    // Create chord layout
    const chord = d3.chord()
      .padAngle(0.05)
      .sortSubgroups(d3.descending)
      .sortChords(d3.descending);

    const chordData = chord(matrix);

    return { chordData, categoryNames, matrix };
  }, [categories, edgeTypes, links, flows, categoryTotals, typeToCategory]);

  const handleCategoryHover = useCallback((category: string | null) => {
    setHoveredCategory(category);
    onCategoryHover?.(category);
  }, [onCategoryHover]);

  const handleChordHover = useCallback((source: string, target: string, count: number) => {
    setHoveredChord({ source, target, count });
    onChordHover?.(source, target, count);
  }, [onChordHover]);

  const handleChordLeave = useCallback(() => {
    setHoveredChord(null);
  }, []);

  if (!chordData || categoryNames.length === 0) {
    return (
      <div ref={containerRef} className="w-full h-full flex items-center justify-center text-muted-foreground">
        No category data available
      </div>
    );
  }

  const outerRadius = Math.min(width, height) * 0.4;
  const innerRadius = outerRadius - 20;

  const arc = d3.arc<d3.ChordGroup>()
    .innerRadius(innerRadius)
    .outerRadius(outerRadius);

  const ribbon = d3.ribbon()
    .radius(innerRadius);

  // Determine which elements to highlight
  const activeCategory = hoveredCategory || selectedCategory;

  // Calculate total flows for the subtitle
  const totalFlows = matrix.reduce((sum, row) => sum + row.reduce((s, v) => s + v, 0), 0);

  return (
    <div ref={containerRef} className="w-full h-full flex items-center justify-center relative">
      <svg width={width} height={height} className="overflow-visible">
        <g transform={`translate(${width / 2}, ${height / 2})`}>
          {/* Category arcs */}
          {chordData.groups.map((group, i) => {
            const categoryName = categoryNames[i];
            const color = getCategoryColor(categoryName);
            const isActive = !activeCategory || activeCategory === categoryName;
            const opacity = isActive ? 1 : 0.2;

            // Calculate edge count for this category
            const edgeCount = categories.find(c => c.category === categoryName)?.totalEdges || 0;

            return (
              <g key={`arc-${i}`}>
                <path
                  d={arc(group) || ''}
                  fill={color}
                  fillOpacity={opacity}
                  stroke={color}
                  strokeWidth={1}
                  className="cursor-pointer transition-opacity duration-200"
                  onMouseEnter={() => handleCategoryHover(categoryName)}
                  onMouseLeave={() => handleCategoryHover(null)}
                  onClick={() => onCategoryClick?.(categoryName)}
                />
                {/* Category label */}
                <text
                  transform={`rotate(${(group.startAngle + group.endAngle) / 2 * 180 / Math.PI - 90}) translate(${outerRadius + 10}, 0) ${
                    (group.startAngle + group.endAngle) / 2 > Math.PI ? 'rotate(180)' : ''
                  }`}
                  textAnchor={(group.startAngle + group.endAngle) / 2 > Math.PI ? 'end' : 'start'}
                  fontSize={13}
                  fontWeight={600}
                  fill="currentColor"
                  className={`pointer-events-none transition-opacity duration-200 ${isActive ? 'opacity-100' : 'opacity-30'}`}
                >
                  {categoryName.toUpperCase()}
                </text>
                {/* Edge count label */}
                <text
                  transform={`rotate(${(group.startAngle + group.endAngle) / 2 * 180 / Math.PI - 90}) translate(${outerRadius + 10}, 14) ${
                    (group.startAngle + group.endAngle) / 2 > Math.PI ? 'rotate(180)' : ''
                  }`}
                  textAnchor={(group.startAngle + group.endAngle) / 2 > Math.PI ? 'end' : 'start'}
                  fontSize={11}
                  fill="currentColor"
                  className={`pointer-events-none transition-opacity duration-200 ${isActive ? 'opacity-60' : 'opacity-20'}`}
                >
                  {edgeCount} edges
                </text>
              </g>
            );
          })}

          {/* Ribbons (connections) */}
          {chordData.map((chord, i) => {
            const sourceCategory = categoryNames[chord.source.index];
            const targetCategory = categoryNames[chord.target.index];
            const sourceColor = getCategoryColor(sourceCategory);
            const flowCount = matrix[chord.source.index][chord.target.index];

            const isChordHovered = hoveredChord?.source === sourceCategory && hoveredChord?.target === targetCategory;
            const isActive = !activeCategory ||
              activeCategory === sourceCategory ||
              activeCategory === targetCategory;
            const opacity = isChordHovered ? 0.9 : isActive ? 0.65 : 0.05;

            const pathData = ribbon(chord as any) as unknown as string | null;

            return (
              <path
                key={`ribbon-${i}`}
                d={pathData || ''}
                fill={sourceColor}
                fillOpacity={opacity}
                stroke={isChordHovered ? 'var(--foreground)' : sourceColor}
                strokeOpacity={isChordHovered ? 0.8 : opacity * 0.5}
                strokeWidth={isChordHovered ? 1.5 : 0.5}
                className="cursor-pointer transition-all duration-200"
                onMouseEnter={() => handleChordHover(sourceCategory, targetCategory, flowCount)}
                onMouseLeave={handleChordLeave}
              />
            );
          })}
        </g>
      </svg>

      {/* Hover tooltip */}
      {hoveredChord && (
        <div
          className="absolute bg-popover border border-border rounded-md px-3 py-2 text-sm shadow-lg pointer-events-none"
          style={{
            left: '50%',
            top: '50%',
            transform: 'translate(-50%, -50%)',
          }}
        >
          <span className="font-medium">{hoveredChord.source}</span>
          <span className="text-muted-foreground mx-2">→</span>
          <span className="font-medium">{hoveredChord.target}</span>
          <span className="text-muted-foreground">: </span>
          <span className="font-medium">{hoveredChord.count} edges</span>
        </div>
      )}
    </div>
  );
}
