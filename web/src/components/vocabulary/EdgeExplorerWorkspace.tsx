/**
 * Edge Explorer Workspace (ADR-077)
 *
 * System-wide vocabulary exploration with three view modes:
 * - Chord: Category flow diagram
 * - Radial: Edge types as spokes
 * - Matrix: Category adjacency matrix
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import { ChordDiagram } from './visualizations/ChordDiagram';
import { RadialEdgeTypes } from './visualizations/RadialEdgeTypes';
import { CategoryMatrix } from './visualizations/CategoryMatrix';
import { getCategoryColor } from '../../config/categoryColors';
import { apiClient } from '../../api/client';
import type { CategoryStats, EdgeTypeData, ViewMode, VocabularyStats } from './types';

// Category flows data from API
interface CategoryFlowData {
  flows: Array<{ source: string; target: string; count: number }>;
  categoryTotals: Record<string, number>;
}

export function EdgeExplorerWorkspace() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('chord');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [hoveredCategory, setHoveredCategory] = useState<string | null>(null);
  const [stats, setStats] = useState<VocabularyStats | null>(null);
  const [categoryFlows, setCategoryFlows] = useState<CategoryFlowData | null>(null);

  // Fetch vocabulary data
  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        setError(null);

        // Fetch vocabulary types and category flows in parallel
        const [response, flowsResponse] = await Promise.all([
          apiClient.getVocabularyTypes({
            include_inactive: false,
            include_builtin: true,
          }),
          apiClient.getCategoryFlows(),
        ]);

        // Store category flows for chord diagram
        setCategoryFlows({
          flows: flowsResponse.flows,
          categoryTotals: flowsResponse.category_totals,
        });

        // Transform API response to our format
        const edgeTypes: EdgeTypeData[] = response.types.map((t: any) => ({
          relationship_type: t.relationship_type,
          category: t.category,
          edge_count: t.edge_count || 0,
          is_builtin: t.is_builtin,
          is_active: t.is_active,
          category_confidence: t.category_confidence,
          category_ambiguous: t.category_ambiguous,
          epistemic_status: t.epistemic_status,
          avg_grounding: t.avg_grounding,
        }));

        // Aggregate by category
        const categoryMap = new Map<string, CategoryStats>();
        for (const et of edgeTypes) {
          const existing = categoryMap.get(et.category) || {
            category: et.category,
            totalTypes: 0,
            activeTypes: 0,
            totalEdges: 0,
            builtinTypes: 0,
            customTypes: 0,
          };

          existing.totalTypes++;
          if (et.is_active) existing.activeTypes++;
          existing.totalEdges += et.edge_count;
          if (et.is_builtin) existing.builtinTypes++;
          else existing.customTypes++;

          categoryMap.set(et.category, existing);
        }

        const categories = Array.from(categoryMap.values()).sort(
          (a, b) => b.totalEdges - a.totalEdges
        );

        setStats({
          totalTypes: response.total,
          activeTypes: response.active,
          builtinTypes: response.builtin,
          customTypes: response.custom,
          totalEdges: edgeTypes.reduce((sum, et) => sum + et.edge_count, 0),
          categories,
          edgeTypes,
        });
      } catch (err: any) {
        setError(err.message || 'Failed to load vocabulary data');
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, []);

  // Filter edge types by selected category
  const filteredEdgeTypes = useMemo(() => {
    if (!stats) return [];
    if (!selectedCategory) return stats.edgeTypes;
    return stats.edgeTypes.filter(et => et.category === selectedCategory);
  }, [stats, selectedCategory]);

  // Get active category for highlighting
  const activeCategory = hoveredCategory || selectedCategory;

  const handleCategoryClick = useCallback((category: string) => {
    setSelectedCategory(prev => prev === category ? null : category);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-muted-foreground">Loading vocabulary data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-destructive">{error}</div>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-muted-foreground">No vocabulary data available</div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 border-b border-border bg-card px-4 py-3">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold">Edge Explorer</h1>
            <p className="text-sm text-muted-foreground">
              System-wide vocabulary analysis
            </p>
          </div>
          {/* View mode tabs */}
          <div className="flex gap-1 bg-muted rounded-lg p-1">
            {(['chord', 'radial', 'matrix'] as ViewMode[]).map(mode => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                  viewMode === mode
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {mode.charAt(0).toUpperCase() + mode.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Visualization area - fills available space */}
        <div className="flex-1 relative">
          <div className="absolute inset-0">
            {viewMode === 'chord' && (
              <ChordDiagram
                categories={stats.categories}
                edgeTypes={stats.edgeTypes}
                flows={categoryFlows?.flows}
                categoryTotals={categoryFlows?.categoryTotals}
                selectedCategory={selectedCategory}
                onCategoryClick={handleCategoryClick}
                onCategoryHover={setHoveredCategory}
              />
            )}
            {viewMode === 'radial' && (
              <RadialEdgeTypes
                categories={stats.categories}
                edgeTypes={stats.edgeTypes}
                selectedCategory={selectedCategory}
                onCategoryHover={setHoveredCategory}
              />
            )}
            {viewMode === 'matrix' && (
              <CategoryMatrix
                categories={stats.categories}
                edgeTypes={stats.edgeTypes}
                selectedCategory={selectedCategory}
                onCategoryHover={setHoveredCategory}
              />
            )}
          </div>
        </div>

        {/* Side panel */}
        <div className="w-80 border-l border-border bg-card overflow-y-auto flex-shrink-0">
          {/* Stats summary */}
          <div className="p-4 border-b border-border">
            <h2 className="text-sm font-semibold mb-3">Overview</h2>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <span className="text-muted-foreground">Types:</span>
                <span className="ml-2 font-medium">{stats.totalTypes}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Edges:</span>
                <span className="ml-2 font-medium">{stats.totalEdges.toLocaleString()}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Builtin:</span>
                <span className="ml-2 font-medium">{stats.builtinTypes}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Custom:</span>
                <span className="ml-2 font-medium">{stats.customTypes}</span>
              </div>
            </div>
          </div>

          {/* Categories */}
          <div className="p-4 border-b border-border">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold">Categories</h2>
              {selectedCategory && (
                <button
                  onClick={() => setSelectedCategory(null)}
                  className="text-xs text-muted-foreground hover:text-foreground"
                >
                  Clear filter
                </button>
              )}
            </div>
            <div className="space-y-1">
              {stats.categories.map(cat => {
                const isSelected = selectedCategory === cat.category;
                const isHighlighted = activeCategory === cat.category;
                const color = getCategoryColor(cat.category);

                return (
                  <button
                    key={cat.category}
                    onClick={() => handleCategoryClick(cat.category)}
                    onMouseEnter={() => setHoveredCategory(cat.category)}
                    onMouseLeave={() => setHoveredCategory(null)}
                    className={`w-full flex items-center justify-between px-2 py-1.5 rounded text-sm transition-colors ${
                      isSelected
                        ? 'bg-accent'
                        : isHighlighted
                        ? 'bg-accent/50'
                        : 'hover:bg-accent/30'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <div
                        className="w-3 h-3 rounded-sm"
                        style={{ backgroundColor: color }}
                      />
                      <span>{cat.category}</span>
                    </div>
                    <span className="text-muted-foreground">
                      {cat.totalEdges.toLocaleString()}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Edge types list */}
          <div className="p-4">
            <h2 className="text-sm font-semibold mb-3">
              Edge Types
              {selectedCategory && (
                <span className="font-normal text-muted-foreground ml-1">
                  ({selectedCategory})
                </span>
              )}
            </h2>
            <div className="space-y-1">
              {filteredEdgeTypes
                .sort((a, b) => b.edge_count - a.edge_count)
                .slice(0, 50)
                .map(et => {
                  const color = getCategoryColor(et.category);
                  return (
                    <div
                      key={et.relationship_type}
                      className="flex items-center justify-between px-2 py-1 text-sm rounded hover:bg-accent/30"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <div
                          className="w-2 h-2 rounded-full flex-shrink-0"
                          style={{ backgroundColor: color }}
                        />
                        <span className="truncate" title={et.relationship_type}>
                          {et.relationship_type}
                        </span>
                        {et.is_builtin && (
                          <span className="text-xs text-muted-foreground">[B]</span>
                        )}
                      </div>
                      <span className="text-muted-foreground flex-shrink-0 ml-2">
                        {et.edge_count}
                      </span>
                    </div>
                  );
                })}
              {filteredEdgeTypes.length > 50 && (
                <div className="text-xs text-muted-foreground text-center py-2">
                  Showing 50 of {filteredEdgeTypes.length} types
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
