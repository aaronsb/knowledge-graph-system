/**
 * Vocabulary Chord Workspace (ADR-077)
 *
 * Query-specific vocabulary analysis that works with graph data
 * from 2D/3D explorers. Shows chord diagram for the current subgraph's
 * vocabulary usage and compares to system-wide patterns.
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import { FolderOpen } from 'lucide-react';
import { ChordDiagram } from './visualizations/ChordDiagram';
import { getCategoryColor } from '../../config/categoryColors';
import { IconRailPanel } from '../shared/IconRailPanel';
import { SavedQueriesPanel } from '../shared/SavedQueriesPanel';
import { useQueryReplay } from '../../hooks/useQueryReplay';
import { useGraphStore } from '../../store/graphStore';
import { apiClient } from '../../api/client';
import type { CategoryStats, EdgeTypeData, ViewMode, VocabularyStats } from './types';

interface SubgraphComparison {
  category: string;
  subgraphEdges: number;
  subgraphPercent: number;
  systemPercent: number;
  delta: number; // positive = overrepresented in subgraph
}

/** Query-specific vocabulary analysis showing chord diagram for the current subgraph.
 *  Reads rawGraphData from graphStore; supports loading saved queries via IconRailPanel.
 *  @verified 2fd1194f */
export function VocabularyChordWorkspace() {
  const [viewMode, setViewMode] = useState<ViewMode>('chord');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [hoveredCategory, setHoveredCategory] = useState<string | null>(null);
  const [systemStats, setSystemStats] = useState<VocabularyStats | null>(null);
  const [activeTab, setActiveTab] = useState('queries');

  // Get graph data from store
  const rawGraphData = useGraphStore((state) => state.rawGraphData);
  const { replayQuery, isReplaying } = useQueryReplay();

  // Fetch system-wide vocabulary stats for comparison
  useEffect(() => {
    async function fetchSystemStats() {
      try {
        const response = await apiClient.getVocabularyTypes({
          include_inactive: false,
          include_builtin: true,
        });

        const edgeTypes: EdgeTypeData[] = response.types.map((t: any) => ({
          relationship_type: t.relationship_type,
          category: t.category,
          edge_count: t.edge_count || 0,
          is_builtin: t.is_builtin,
          is_active: t.is_active,
          category_confidence: t.category_confidence,
          category_ambiguous: t.category_ambiguous,
        }));

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

        setSystemStats({
          totalTypes: response.total,
          activeTypes: response.active,
          builtinTypes: response.builtin,
          customTypes: response.custom,
          totalEdges: edgeTypes.reduce((sum, et) => sum + et.edge_count, 0),
          categories: Array.from(categoryMap.values()).sort((a, b) => b.totalEdges - a.totalEdges),
          edgeTypes,
        });
      } catch (err) {
        console.error('Failed to load system vocabulary stats:', err);
      }
    }

    fetchSystemStats();
  }, []);

  // Build a lookup map from systemStats for category information
  const systemTypeMap = useMemo(() => {
    if (!systemStats?.edgeTypes) return new Map<string, EdgeTypeData>();
    const map = new Map<string, EdgeTypeData>();
    for (const et of systemStats.edgeTypes) {
      // Store with both original and uppercase for flexible matching
      map.set(et.relationship_type, et);
      map.set(et.relationship_type.toUpperCase(), et);
    }
    return map;
  }, [systemStats]);

  // Compute subgraph vocabulary stats from rawGraphData using systemStats for categories
  const subgraphStats = useMemo((): VocabularyStats | null => {
    if (!rawGraphData?.links || rawGraphData.links.length === 0) {
      return null;
    }

    // Count edges by relationship type
    const typeCountMap = new Map<string, number>();
    for (const link of rawGraphData.links) {
      const type = link.relationship_type || 'UNKNOWN';
      typeCountMap.set(type, (typeCountMap.get(type) || 0) + 1);
    }

    // Build edge type data with categories from system vocabulary
    const edgeTypes: EdgeTypeData[] = [];
    for (const [type, count] of typeCountMap) {
      // Look up category from system vocabulary (which has complete API data)
      const systemType = systemTypeMap.get(type) || systemTypeMap.get(type.toUpperCase());
      const category = systemType?.category || 'unknown';

      edgeTypes.push({
        relationship_type: type,
        category,
        edge_count: count,
        is_builtin: systemType?.is_builtin ?? true,
        is_active: systemType?.is_active ?? true,
        category_confidence: systemType?.category_confidence,
        category_ambiguous: systemType?.category_ambiguous,
      });
    }

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
      existing.activeTypes++;
      existing.totalEdges += et.edge_count;
      if (et.is_builtin) existing.builtinTypes++;
      else existing.customTypes++;
      categoryMap.set(et.category, existing);
    }

    const categories = Array.from(categoryMap.values()).sort(
      (a, b) => b.totalEdges - a.totalEdges
    );

    return {
      totalTypes: edgeTypes.length,
      activeTypes: edgeTypes.length,
      builtinTypes: edgeTypes.filter((et) => et.is_builtin).length,
      customTypes: edgeTypes.filter((et) => !et.is_builtin).length,
      totalEdges: rawGraphData.links.length,
      categories,
      edgeTypes,
    };
  }, [rawGraphData, systemTypeMap]);

  // Compute comparison between subgraph and system
  const comparison = useMemo((): SubgraphComparison[] => {
    if (!subgraphStats || !systemStats) return [];

    const systemTotal = systemStats.totalEdges || 1;
    const subgraphTotal = subgraphStats.totalEdges || 1;

    // Get all categories from both
    const allCategories = new Set([
      ...subgraphStats.categories.map((c) => c.category),
      ...systemStats.categories.map((c) => c.category),
    ]);

    const comparisons: SubgraphComparison[] = [];
    for (const category of allCategories) {
      const subgraphCat = subgraphStats.categories.find((c) => c.category === category);
      const systemCat = systemStats.categories.find((c) => c.category === category);

      const subgraphEdges = subgraphCat?.totalEdges || 0;
      const systemEdges = systemCat?.totalEdges || 0;

      const subgraphPercent = (subgraphEdges / subgraphTotal) * 100;
      const systemPercent = (systemEdges / systemTotal) * 100;

      comparisons.push({
        category,
        subgraphEdges,
        subgraphPercent,
        systemPercent,
        delta: subgraphPercent - systemPercent,
      });
    }

    // Sort by absolute delta (most different first)
    return comparisons.sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));
  }, [subgraphStats, systemStats]);

  // Filter edge types by selected category
  const filteredEdgeTypes = useMemo(() => {
    if (!subgraphStats) return [];
    if (!selectedCategory) return subgraphStats.edgeTypes;
    return subgraphStats.edgeTypes.filter((et) => et.category === selectedCategory);
  }, [subgraphStats, selectedCategory]);

  const handleCategoryClick = useCallback((category: string) => {
    setSelectedCategory((prev) => (prev === category ? null : category));
  }, []);

  const activeCategory = hoveredCategory || selectedCategory;

  const hasGraphData = rawGraphData && rawGraphData.links.length > 0;

  const sidebar = (
    <IconRailPanel
      tabs={[{
        id: 'queries',
        icon: FolderOpen,
        label: 'Saved Queries',
        content: (
          <SavedQueriesPanel
            onLoadQuery={replayQuery}
            definitionTypeFilter="exploration"
          />
        ),
      }]}
      activeTab={activeTab}
      onTabChange={setActiveTab}
    />
  );

  if (!hasGraphData) {
    return (
      <div className="h-full flex overflow-hidden">
        {sidebar}
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-muted-foreground">
            {isReplaying ? (
              <>
                <p className="text-lg mb-2">Loading Query...</p>
                <p className="text-sm">Replaying exploration steps</p>
              </>
            ) : (
              <>
                <p className="text-lg mb-2">No Graph Data</p>
                <p className="text-sm">
                  Load a saved query from the sidebar, or build a graph
                  <br />
                  in the 2D/3D explorer and switch to this view.
                </p>
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex overflow-hidden">
      {sidebar}

      {/* Main content area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex-shrink-0 border-b border-border bg-card px-4 py-3">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-lg font-semibold">Vocabulary Analysis</h1>
              <p className="text-sm text-muted-foreground">
                {rawGraphData.nodes?.length || 0} nodes, {rawGraphData.links?.length || 0} edges
              </p>
            </div>
            {/* View mode tabs */}
            <div className="flex gap-1 bg-muted rounded-lg p-1">
              {(['chord', 'radial', 'matrix'] as ViewMode[]).map((mode) => (
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

        {/* Visualization + side panel */}
        <div className="flex-1 flex overflow-hidden">
        {/* Visualization area - fills available space */}
        <div className="flex-1 relative">
          {subgraphStats && viewMode === 'chord' && (
            <div className="absolute inset-0">
              <ChordDiagram
                categories={subgraphStats.categories}
                edgeTypes={subgraphStats.edgeTypes}
                links={rawGraphData?.links}
                selectedCategory={selectedCategory}
                onCategoryClick={handleCategoryClick}
                onCategoryHover={setHoveredCategory}
              />
            </div>
          )}
          {viewMode === 'radial' && (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              Radial view - use Edge Explorer for full system analysis
            </div>
          )}
          {viewMode === 'matrix' && (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              Matrix view - use Edge Explorer for full system analysis
            </div>
          )}
        </div>

        {/* Side panel */}
        <div className="w-80 border-l border-border bg-card overflow-y-auto flex-shrink-0">
          {/* Subgraph stats */}
          {subgraphStats && (
            <div className="p-4 border-b border-border">
              <h2 className="text-sm font-semibold mb-3">Subgraph Overview</h2>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <span className="text-muted-foreground">Edge Types:</span>
                  <span className="ml-2 font-medium">{subgraphStats.totalTypes}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Total Edges:</span>
                  <span className="ml-2 font-medium">{subgraphStats.totalEdges}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Categories:</span>
                  <span className="ml-2 font-medium">{subgraphStats.categories.length}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Nodes:</span>
                  <span className="ml-2 font-medium">{rawGraphData.nodes?.length || 0}</span>
                </div>
              </div>
            </div>
          )}

          {/* Category comparison */}
          {comparison.length > 0 && (
            <div className="p-4 border-b border-border">
              <h2 className="text-sm font-semibold mb-3">vs System Average</h2>
              <div className="space-y-2">
                {comparison.slice(0, 8).map((comp) => {
                  const color = getCategoryColor(comp.category);
                  const isHighlighted = activeCategory === comp.category;

                  return (
                    <button
                      key={comp.category}
                      onClick={() => handleCategoryClick(comp.category)}
                      onMouseEnter={() => setHoveredCategory(comp.category)}
                      onMouseLeave={() => setHoveredCategory(null)}
                      className={`w-full text-left transition-colors rounded px-2 py-1.5 ${
                        isHighlighted ? 'bg-accent' : 'hover:bg-accent/30'
                      }`}
                    >
                      <div className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2">
                          <div
                            className="w-3 h-3 rounded-sm"
                            style={{ backgroundColor: color }}
                          />
                          <span>{comp.category}</span>
                        </div>
                        <span
                          className={`text-xs font-medium ${
                            comp.delta > 5
                              ? 'text-green-500'
                              : comp.delta < -5
                              ? 'text-red-500'
                              : 'text-muted-foreground'
                          }`}
                        >
                          {comp.delta > 0 ? '+' : ''}
                          {comp.delta.toFixed(1)}%
                        </span>
                      </div>
                      <div className="flex gap-1 mt-1">
                        {/* Subgraph bar */}
                        <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{
                              backgroundColor: color,
                              width: `${Math.min(comp.subgraphPercent * 2, 100)}%`,
                            }}
                          />
                        </div>
                        {/* System bar (faded) */}
                        <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full opacity-30"
                            style={{
                              backgroundColor: color,
                              width: `${Math.min(comp.systemPercent * 2, 100)}%`,
                            }}
                          />
                        </div>
                      </div>
                      <div className="flex justify-between text-xs text-muted-foreground mt-0.5">
                        <span>Subgraph {comp.subgraphPercent.toFixed(1)}%</span>
                        <span>System {comp.systemPercent.toFixed(1)}%</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Edge types in subgraph */}
          {subgraphStats && (
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
                  .map((et) => {
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
                        </div>
                        <span className="text-muted-foreground flex-shrink-0 ml-2">
                          {et.edge_count}
                        </span>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
    </div>
  );
}
