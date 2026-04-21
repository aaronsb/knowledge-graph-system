/**
 * Legend Component
 *
 * Displays dynamic legend for node colors and edge colors
 * with collapsible sections and vertical resize capability.
 */

import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import * as d3 from 'd3';
import { categoryColors } from '../../config/categoryColors';
import { useGraphStore } from '../../store/graphStore';
import type { GraphData } from '../../types/graph';

/** Optional Show/Hide visibility section. Each toggle is independent so
 *  callers can wire only the controls they support (e.g. 2D might not
 *  have showNodeLabels). Section is omitted when no controls are passed. */
export interface LegendVisibilityControls {
  showArrows?: boolean;
  showEdgeLabels?: boolean;
  showNodeLabels?: boolean;
  onToggleArrows?: (v: boolean) => void;
  onToggleEdgeLabels?: (v: boolean) => void;
  onToggleNodeLabels?: (v: boolean) => void;
}

interface LegendProps {
  data: GraphData;
  nodeColorMode: 'ontology' | 'degree' | 'centrality';
  visibilityControls?: LegendVisibilityControls;
}

export const Legend: React.FC<LegendProps> = ({ data, nodeColorMode, visibilityControls }) => {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(['nodeColors', 'edgeColors', 'visibility'])
  );

  const {
    filters,
    toggleEdgeCategoryVisibility,
    setAllEdgeCategoriesVisible,
  } = useGraphStore();

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  };

  // Extract ontologies and their colors
  const ontologies = Array.from(new Set(data.nodes.map((n) => n.group))).sort();
  const ontologyColors = new Map<string, string>();
  data.nodes.forEach((n) => {
    if (!ontologyColors.has(n.group)) {
      ontologyColors.set(n.group, n.color);
    }
  });

  // Extract edge categories
  const categories = Array.from(new Set(data.links.map((l) => l.category).filter(Boolean))).sort();

  // Initialize all categories as visible when categories change
  useEffect(() => {
    if (categories.length > 0 && filters.visibleEdgeCategories.size === 0) {
      setAllEdgeCategoriesVisible(categories, true);
    }
  }, [categories.length]); // Only run when number of categories changes

  // Check if a category is visible (empty set = all visible)
  const isCategoryVisible = (category: string) => {
    if (filters.visibleEdgeCategories.size === 0) return true;
    return filters.visibleEdgeCategories.has(category);
  };

  // Generate gradient string from D3 color scale
  const generateGradient = (interpolator: (t: number) => string, steps: number = 10) => {
    const colors = Array.from({ length: steps }, (_, i) => interpolator(i / (steps - 1)));
    return `linear-gradient(to right, ${colors.join(', ')})`;
  };

  // Render node color legend based on mode
  const renderNodeColorLegend = () => {
    if (nodeColorMode === 'ontology') {
      return (
        <div className="space-y-1.5">
          {ontologies.map((ontology) => (
            <div key={ontology} className="flex items-center gap-2 text-xs">
              <div
                className="w-3 h-3 rounded-full flex-shrink-0"
                style={{ backgroundColor: ontologyColors.get(ontology) || '#6b7280' }}
              />
              <span className="text-card-foreground truncate" title={ontology}>
                {ontology}
              </span>
            </div>
          ))}
        </div>
      );
    } else if (nodeColorMode === 'degree') {
      return (
        <div className="space-y-2">
          <div className="text-xs text-foreground font-medium">Degree (Connections)</div>
          <div
            className="h-4 rounded"
            style={{
              background: generateGradient(d3.interpolateViridis),
            }}
          />
          <div className="flex justify-between text-[0.625rem] text-muted-foreground">
            <span>Low</span>
            <span>High</span>
          </div>
        </div>
      );
    } else if (nodeColorMode === 'centrality') {
      return (
        <div className="space-y-2">
          <div className="text-xs text-foreground font-medium">Centrality</div>
          <div
            className="h-4 rounded"
            style={{
              background: generateGradient(d3.interpolatePlasma),
            }}
          />
          <div className="flex justify-between text-[0.625rem] text-muted-foreground">
            <span>Low</span>
            <span>High</span>
          </div>
        </div>
      );
    }
  };

  return (
    <div
      className="bg-card/95 border border-border rounded-lg shadow-xl flex flex-col"
      style={{ width: '240px', maxHeight: '95vh' }}
    >
      {/* Content */}
      <div className="overflow-y-auto overflow-x-hidden p-3 space-y-3">
        {/* Node Colors Section */}
        <div className="border-b border-border pb-3">
          <button
            onClick={() => toggleSection('nodeColors')}
            className="w-full flex items-center justify-between text-sm font-medium text-card-foreground hover:text-foreground transition-colors"
          >
            <span>Node Colors</span>
            {expandedSections.has('nodeColors') ? (
              <ChevronDown size={14} className="text-muted-foreground" />
            ) : (
              <ChevronRight size={14} className="text-muted-foreground" />
            )}
          </button>
          {expandedSections.has('nodeColors') && (
            <div className="mt-3">{renderNodeColorLegend()}</div>
          )}
        </div>

        {/* Edge Colors Section */}
        <div className={visibilityControls ? 'border-b border-border pb-3' : ''}>
          <button
            onClick={() => toggleSection('edgeColors')}
            className="w-full flex items-center justify-between text-sm font-medium text-card-foreground hover:text-foreground transition-colors"
          >
            <span>Edge Categories</span>
            {expandedSections.has('edgeColors') ? (
              <ChevronDown size={14} className="text-muted-foreground" />
            ) : (
              <ChevronRight size={14} className="text-muted-foreground" />
            )}
          </button>
          {expandedSections.has('edgeColors') && (
            <div className="mt-3 space-y-1.5">
              {categories.map((category) => {
                const color = categoryColors[category || 'default'] || categoryColors.default;
                const isVisible = isCategoryVisible(category);
                return (
                  <div key={category} className="flex items-center gap-2 text-xs">
                    <input
                      type="checkbox"
                      checked={isVisible}
                      onChange={() => toggleEdgeCategoryVisibility(category)}
                      className="w-3 h-3 rounded cursor-pointer"
                      style={{
                        accentColor: color,
                      }}
                    />
                    <span
                      style={{ color: isVisible ? color : '#6b7280' }}
                      className={`font-medium capitalize cursor-pointer ${!isVisible ? 'opacity-50' : ''}`}
                      onClick={() => toggleEdgeCategoryVisibility(category)}
                    >
                      {category}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Show / Hide Section — opt-in via visibilityControls prop */}
        {visibilityControls && (
          <div>
            <button
              onClick={() => toggleSection('visibility')}
              className="w-full flex items-center justify-between text-sm font-medium text-card-foreground hover:text-foreground transition-colors"
            >
              <span>Show / Hide</span>
              {expandedSections.has('visibility') ? (
                <ChevronDown size={14} className="text-muted-foreground" />
              ) : (
                <ChevronRight size={14} className="text-muted-foreground" />
              )}
            </button>
            {expandedSections.has('visibility') && (
              <div className="mt-3 space-y-1.5">
                {visibilityControls.onToggleArrows !== undefined && (
                  <label className="flex items-center gap-2 text-xs cursor-pointer">
                    <input
                      type="checkbox"
                      checked={visibilityControls.showArrows ?? false}
                      onChange={(e) => visibilityControls.onToggleArrows?.(e.target.checked)}
                      className="w-3 h-3 rounded cursor-pointer"
                    />
                    <span className="text-card-foreground">Arrows</span>
                  </label>
                )}
                {visibilityControls.onToggleEdgeLabels !== undefined && (
                  <label className="flex items-center gap-2 text-xs cursor-pointer">
                    <input
                      type="checkbox"
                      checked={visibilityControls.showEdgeLabels ?? false}
                      onChange={(e) => visibilityControls.onToggleEdgeLabels?.(e.target.checked)}
                      className="w-3 h-3 rounded cursor-pointer"
                    />
                    <span className="text-card-foreground">Edge labels</span>
                  </label>
                )}
                {visibilityControls.onToggleNodeLabels !== undefined && (
                  <label className="flex items-center gap-2 text-xs cursor-pointer">
                    <input
                      type="checkbox"
                      checked={visibilityControls.showNodeLabels ?? false}
                      onChange={(e) => visibilityControls.onToggleNodeLabels?.(e.target.checked)}
                      className="w-3 h-3 rounded cursor-pointer"
                    />
                    <span className="text-card-foreground">Node labels</span>
                  </label>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
