/**
 * Radial Edge Types Visualization (ADR-077)
 *
 * Shows edge types arranged as spokes radiating from center,
 * grouped by category. Bar length encodes edge count.
 */

import { useMemo, useState, useCallback, useRef, useLayoutEffect } from 'react';
import { getCategoryColor } from '../../../config/categoryColors';
import { useSvgPanZoom } from '../../../hooks/useSvgPanZoom';
import type { CategoryStats, EdgeTypeData } from '../types';

interface RadialEdgeTypesProps {
  categories: CategoryStats[];
  edgeTypes: EdgeTypeData[];
  onTypeClick?: (type: string) => void;
  onTypeHover?: (type: string | null) => void;
  onCategoryHover?: (category: string | null) => void;
  selectedType?: string | null;
  selectedCategory?: string | null;
}

export function RadialEdgeTypes({
  categories,
  edgeTypes,
  onTypeClick,
  onTypeHover,
  onCategoryHover,
  selectedType,
  selectedCategory,
}: RadialEdgeTypesProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const zoomRef = useRef<SVGGElement>(null);
  const [dimensions, setDimensions] = useState({ width: 600, height: 600 });
  const [hoveredType, setHoveredType] = useState<string | null>(null);
  const [hoveredCategory, setHoveredCategory] = useState<string | null>(null);

  // Self-sizing: fill the container
  useLayoutEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
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

  useSvgPanZoom(svgRef, zoomRef);

  const { width, height } = dimensions;

  // Sort edge types by category and edge count
  const sortedTypes = useMemo(() => {
    return [...edgeTypes]
      .filter(et => et.edge_count > 0)
      .sort((a, b) => {
        // First by category
        const catCompare = a.category.localeCompare(b.category);
        if (catCompare !== 0) return catCompare;
        // Then by edge count descending
        return b.edge_count - a.edge_count;
      });
  }, [edgeTypes]);

  // Calculate max edge count for scaling
  const maxEdgeCount = useMemo(() => {
    return Math.max(...sortedTypes.map(et => et.edge_count), 1);
  }, [sortedTypes]);

  // Group types by category for arc segments
  const categoryGroups = useMemo(() => {
    const groups = new Map<string, EdgeTypeData[]>();
    for (const et of sortedTypes) {
      const existing = groups.get(et.category) || [];
      existing.push(et);
      groups.set(et.category, existing);
    }
    return groups;
  }, [sortedTypes]);

  const handleTypeHover = useCallback((type: string | null) => {
    setHoveredType(type);
    onTypeHover?.(type);
  }, [onTypeHover]);

  const handleCategoryHover = useCallback((category: string | null) => {
    setHoveredCategory(category);
    onCategoryHover?.(category);
  }, [onCategoryHover]);

  if (sortedTypes.length === 0) {
    return (
      <div ref={containerRef} className="w-full h-full flex items-center justify-center text-muted-foreground">
        No edge type data available
      </div>
    );
  }

  const centerX = width / 2;
  const centerY = height / 2;
  const innerRadius = 80;
  const maxBarLength = Math.min(width, height) / 2 - innerRadius - 60;

  // Calculate angle per type
  const totalTypes = sortedTypes.length;
  const anglePerType = (2 * Math.PI) / totalTypes;
  const gapAngle = anglePerType * 0.1; // 10% gap between bars

  // Active states
  const activeCategory = hoveredCategory || selectedCategory;
  const activeType = hoveredType || selectedType;

  return (
    <div ref={containerRef} className="w-full h-full flex items-center justify-center">
      <svg ref={svgRef} width={width} height={height} className="overflow-visible">
      <g ref={zoomRef}>
      <g transform={`translate(${centerX}, ${centerY})`}>
        {/* Center circle */}
        <circle
          r={innerRadius - 5}
          fill="var(--card)"
          stroke="var(--border)"
          strokeWidth={1}
        />

        {/* Category labels in center */}
        <text
          textAnchor="middle"
          dominantBaseline="middle"
          className="text-sm font-medium fill-foreground"
        >
          {activeCategory || activeType || 'Edge Types'}
        </text>
        <text
          y={18}
          textAnchor="middle"
          dominantBaseline="middle"
          className="text-xs fill-muted-foreground"
        >
          {activeCategory
            ? `${categoryGroups.get(activeCategory)?.length || 0} types`
            : activeType
            ? edgeTypes.find(et => et.relationship_type === activeType)?.category || ''
            : `${totalTypes} total`}
        </text>

        {/* Edge type bars */}
        {sortedTypes.map((et, i) => {
          const angle = i * anglePerType - Math.PI / 2; // Start from top
          const barLength = (et.edge_count / maxEdgeCount) * maxBarLength;
          const color = getCategoryColor(et.category);

          const isTypeActive = !activeType || activeType === et.relationship_type;
          const isCategoryActive = !activeCategory || activeCategory === et.category;
          const isActive = isTypeActive && isCategoryActive;
          const opacity = isActive ? 1 : 0.15;

          // Calculate bar coordinates
          const x1 = Math.cos(angle) * innerRadius;
          const y1 = Math.sin(angle) * innerRadius;
          const x2 = Math.cos(angle) * (innerRadius + barLength);
          const y2 = Math.sin(angle) * (innerRadius + barLength);

          // Calculate bar width based on gap
          const barWidth = Math.max(2, (anglePerType - gapAngle) * innerRadius * 0.5);

          return (
            <g key={et.relationship_type}>
              {/* Bar */}
              <line
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke={color}
                strokeWidth={barWidth}
                strokeLinecap="round"
                opacity={opacity}
                className="cursor-pointer transition-opacity duration-200"
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

              {/* Label for hovered type */}
              {(hoveredType === et.relationship_type || selectedType === et.relationship_type) && (
                <g>
                  <text
                    x={Math.cos(angle) * (innerRadius + barLength + 10)}
                    y={Math.sin(angle) * (innerRadius + barLength + 10)}
                    textAnchor={Math.cos(angle) > 0 ? 'start' : 'end'}
                    dominantBaseline="middle"
                    className="text-xs fill-foreground pointer-events-none"
                    transform={
                      Math.abs(angle) > Math.PI / 2
                        ? `rotate(180, ${Math.cos(angle) * (innerRadius + barLength + 10)}, ${Math.sin(angle) * (innerRadius + barLength + 10)})`
                        : undefined
                    }
                  >
                    {et.relationship_type} ({et.edge_count})
                  </text>
                </g>
              )}
            </g>
          );
        })}

        {/* Category arc labels on outer ring */}
        {Array.from(categoryGroups.entries()).map(([category, types]) => {
          const startIndex = sortedTypes.findIndex(et => et.category === category);
          const endIndex = startIndex + types.length - 1;
          const startAngle = startIndex * anglePerType - Math.PI / 2;
          const endAngle = (endIndex + 1) * anglePerType - Math.PI / 2;
          const midAngle = (startAngle + endAngle) / 2;
          const labelRadius = Math.min(width, height) / 2 - 25;

          const color = getCategoryColor(category);
          const isActive = !activeCategory || activeCategory === category;

          return (
            <g key={`category-${category}`}>
              {/* Category arc */}
              <path
                d={describeArc(0, 0, labelRadius - 15, startAngle, endAngle)}
                fill="none"
                stroke={color}
                strokeWidth={4}
                strokeLinecap="round"
                opacity={isActive ? 0.8 : 0.2}
                className="cursor-pointer transition-opacity duration-200"
                onMouseEnter={() => handleCategoryHover(category)}
                onMouseLeave={() => handleCategoryHover(null)}
              />

              {/* Category label */}
              <text
                x={Math.cos(midAngle) * labelRadius}
                y={Math.sin(midAngle) * labelRadius}
                textAnchor="middle"
                dominantBaseline="middle"
                fontSize={10}
                fill="currentColor"
                className={`pointer-events-none transition-opacity duration-200 ${isActive ? 'opacity-100' : 'opacity-30'}`}
                transform={`rotate(${midAngle * 180 / Math.PI + 90}, ${Math.cos(midAngle) * labelRadius}, ${Math.sin(midAngle) * labelRadius})`}
              >
                {category}
              </text>
            </g>
          );
        })}
      </g>
      </g>
    </svg>
    </div>
  );
}

// Helper to create arc path
function describeArc(x: number, y: number, radius: number, startAngle: number, endAngle: number): string {
  const start = {
    x: x + radius * Math.cos(startAngle),
    y: y + radius * Math.sin(startAngle),
  };
  const end = {
    x: x + radius * Math.cos(endAngle),
    y: y + radius * Math.sin(endAngle),
  };
  const largeArcFlag = endAngle - startAngle <= Math.PI ? 0 : 1;

  return `M ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArcFlag} 1 ${end.x} ${end.y}`;
}
