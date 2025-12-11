/**
 * Category Matrix Visualization (ADR-077)
 *
 * Shows a grid of edge types organized by category.
 * Cell color intensity encodes edge count.
 */

import { useMemo, useState, useCallback } from 'react';
import { getCategoryColor } from '../../../config/categoryColors';
import type { CategoryStats, EdgeTypeData } from '../types';

interface CategoryMatrixProps {
  categories: CategoryStats[];
  edgeTypes: EdgeTypeData[];
  width?: number;
  height?: number;
  onTypeClick?: (type: string) => void;
  onTypeHover?: (type: string | null) => void;
  onCategoryHover?: (category: string | null) => void;
  selectedType?: string | null;
  selectedCategory?: string | null;
}

export function CategoryMatrix({
  categories,
  edgeTypes,
  width = 800,
  height = 600,
  onTypeClick,
  onTypeHover,
  onCategoryHover,
  selectedType,
  selectedCategory,
}: CategoryMatrixProps) {
  const [hoveredType, setHoveredType] = useState<string | null>(null);
  const [hoveredCategory, setHoveredCategory] = useState<string | null>(null);

  // Group edge types by category
  const categoryGroups = useMemo(() => {
    const groups = new Map<string, EdgeTypeData[]>();
    for (const et of edgeTypes) {
      const existing = groups.get(et.category) || [];
      existing.push(et);
      groups.set(et.category, existing);
    }
    // Sort types within each category by edge count
    for (const [, types] of groups) {
      types.sort((a, b) => b.edge_count - a.edge_count);
    }
    return groups;
  }, [edgeTypes]);

  // Sort categories by total edge count
  const sortedCategories = useMemo(() => {
    return [...categories].sort((a, b) => b.totalEdges - a.totalEdges);
  }, [categories]);

  // Calculate max edge count for color scaling
  const maxEdgeCount = useMemo(() => {
    return Math.max(...edgeTypes.map(et => et.edge_count), 1);
  }, [edgeTypes]);

  // Find the maximum number of types in any category
  const maxTypesInCategory = useMemo(() => {
    return Math.max(...Array.from(categoryGroups.values()).map(types => types.length), 1);
  }, [categoryGroups]);

  const handleTypeHover = useCallback((type: string | null) => {
    setHoveredType(type);
    onTypeHover?.(type);
  }, [onTypeHover]);

  const handleCategoryHover = useCallback((category: string | null) => {
    setHoveredCategory(category);
    onCategoryHover?.(category);
  }, [onCategoryHover]);

  if (sortedCategories.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        No category data available
      </div>
    );
  }

  // Layout calculations
  const margin = { top: 40, right: 20, bottom: 20, left: 120 };
  const categoryLabelWidth = 100;
  const cellSize = Math.min(
    (width - margin.left - margin.right) / maxTypesInCategory,
    (height - margin.top - margin.bottom) / sortedCategories.length,
    30 // Max cell size
  );
  const cellPadding = 2;

  const activeCategory = hoveredCategory || selectedCategory;
  const activeType = hoveredType || selectedType;

  return (
    <div className="overflow-auto" style={{ maxWidth: width, maxHeight: height }}>
      <svg
        width={margin.left + maxTypesInCategory * cellSize + margin.right}
        height={margin.top + sortedCategories.length * cellSize + margin.bottom}
        className="overflow-visible"
      >
        {/* Title */}
        <text
          x={margin.left}
          y={20}
          className="text-sm font-medium fill-foreground"
        >
          Edge Types by Category
        </text>
        <text
          x={margin.left}
          y={34}
          className="text-xs fill-muted-foreground"
        >
          {edgeTypes.length} types, {edgeTypes.reduce((sum, et) => sum + et.edge_count, 0).toLocaleString()} edges
        </text>

        {/* Category rows */}
        {sortedCategories.map((cat, rowIndex) => {
          const types = categoryGroups.get(cat.category) || [];
          const color = getCategoryColor(cat.category);
          const y = margin.top + rowIndex * cellSize;
          const isCategoryActive = !activeCategory || activeCategory === cat.category;

          return (
            <g key={cat.category}>
              {/* Category label */}
              <text
                x={margin.left - 10}
                y={y + cellSize / 2}
                textAnchor="end"
                dominantBaseline="middle"
                className={`text-xs cursor-pointer transition-opacity duration-200 ${
                  isCategoryActive ? 'fill-foreground' : 'fill-muted-foreground opacity-40'
                }`}
                onMouseEnter={() => handleCategoryHover(cat.category)}
                onMouseLeave={() => handleCategoryHover(null)}
              >
                {cat.category}
              </text>

              {/* Category indicator bar */}
              <rect
                x={margin.left - 6}
                y={y + 2}
                width={3}
                height={cellSize - 4}
                fill={color}
                opacity={isCategoryActive ? 0.8 : 0.2}
                rx={1}
              />

              {/* Type cells */}
              {types.map((et, colIndex) => {
                const x = margin.left + colIndex * cellSize;
                const intensity = Math.pow(et.edge_count / maxEdgeCount, 0.5); // Square root for better distribution
                const isTypeActive = !activeType || activeType === et.relationship_type;
                const isActive = isCategoryActive && isTypeActive;

                return (
                  <g key={et.relationship_type}>
                    <rect
                      x={x + cellPadding}
                      y={y + cellPadding}
                      width={cellSize - cellPadding * 2}
                      height={cellSize - cellPadding * 2}
                      fill={color}
                      fillOpacity={isActive ? intensity * 0.8 + 0.1 : 0.05}
                      stroke={
                        activeType === et.relationship_type
                          ? 'var(--foreground)'
                          : isActive
                          ? color
                          : 'transparent'
                      }
                      strokeWidth={activeType === et.relationship_type ? 2 : 1}
                      strokeOpacity={isActive ? 0.5 : 0.1}
                      rx={2}
                      className="cursor-pointer transition-all duration-200"
                      onMouseEnter={() => {
                        handleTypeHover(et.relationship_type);
                        handleCategoryHover(et.category);
                      }}
                      onMouseLeave={() => {
                        handleTypeHover(null);
                        handleCategoryHover(null);
                      }}
                      onClick={() => onTypeClick?.(et.relationship_type)}
                    />

                    {/* Tooltip on hover */}
                    {hoveredType === et.relationship_type && (
                      <g>
                        <rect
                          x={x + cellSize + 5}
                          y={y - 10}
                          width={Math.max(et.relationship_type.length * 6 + 40, 100)}
                          height={40}
                          fill="var(--popover)"
                          stroke="var(--border)"
                          strokeWidth={1}
                          rx={4}
                          className="pointer-events-none"
                        />
                        <text
                          x={x + cellSize + 12}
                          y={y + 6}
                          className="text-xs font-medium fill-foreground pointer-events-none"
                        >
                          {et.relationship_type}
                        </text>
                        <text
                          x={x + cellSize + 12}
                          y={y + 20}
                          className="text-xs fill-muted-foreground pointer-events-none"
                        >
                          {et.edge_count.toLocaleString()} edges
                          {et.is_builtin ? ' [builtin]' : ''}
                        </text>
                      </g>
                    )}
                  </g>
                );
              })}

              {/* Category edge count */}
              <text
                x={margin.left + types.length * cellSize + 10}
                y={y + cellSize / 2}
                dominantBaseline="middle"
                className={`text-xs transition-opacity duration-200 ${
                  isCategoryActive ? 'fill-muted-foreground' : 'fill-muted-foreground opacity-30'
                }`}
              >
                {cat.totalEdges.toLocaleString()}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
