/**
 * Explorer View
 *
 * Encapsulates the explorer visualization functionality including:
 * - Search bar with query modes
 * - Graph data fetching
 * - Explorer rendering (2D/3D)
 * - Saved queries management (ADR-083)
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { History, Settings, Trash2 } from 'lucide-react';
import { SearchBar } from '../components/shared/SearchBar';
import { IconRailPanel } from '../components/shared/IconRailPanel';
import { useGraphStore } from '../store/graphStore';
import { useReportStore } from '../store/reportStore';
import { useQueryDefinitionStore } from '../store/queryDefinitionStore';
import type { GraphReportData } from '../store/reportStore';
import { useSubgraph, useFindConnection } from '../hooks/useGraphData';
import { getExplorer } from '../explorers';
import { getZIndexValue } from '../config/zIndex';
import type { VisualizationType } from '../types/explorer';

interface ExplorerViewProps {
  explorerType: VisualizationType;
}

export const ExplorerView: React.FC<ExplorerViewProps> = ({ explorerType }) => {
  const navigate = useNavigate();
  const [urlParams, setUrlParams] = useSearchParams();
  const {
    searchParams,
    similarityThreshold,
    graphData: storeGraphData,
    rawGraphData,
    setGraphData,
    setRawGraphData,
    mergeRawGraphData,
    setSelectedExplorer,
    setSearchParams,
    setSimilarityThreshold,
  } = useGraphStore();
  const { addReport } = useReportStore();
  const {
    definitions: savedQueriesMap,
    definitionIds: savedQueryIds,
    loadDefinitions: loadSavedQueries,
    deleteDefinition: deleteSavedQuery,
    isLoading: isLoadingQueries,
  } = useQueryDefinitionStore();

  // Convert to array for rendering
  const savedQueries = savedQueryIds.map(id => savedQueriesMap[id]).filter(Boolean);

  // UI state for IconRailPanel
  const [activeTab, setActiveTab] = useState('history');

  // Track if we're initializing from URL to prevent loops
  const initializingFromUrl = React.useRef(false);

  // Load saved queries on mount
  useEffect(() => {
    loadSavedQueries();
  }, [loadSavedQueries]);

  // Set the explorer type when this view mounts
  useEffect(() => {
    setSelectedExplorer(explorerType);
  }, [explorerType, setSelectedExplorer]);

  // Initialize from URL parameters on mount
  useEffect(() => {
    const conceptId = urlParams.get('conceptId');
    const mode = urlParams.get('mode') as 'concept' | 'neighborhood' | 'path' | null;
    const similarity = urlParams.get('similarity');
    const depth = urlParams.get('depth');
    const fromConceptId = urlParams.get('fromConceptId');
    const toConceptId = urlParams.get('toConceptId');
    const maxHops = urlParams.get('maxHops');

    if (conceptId && mode) {
      initializingFromUrl.current = true;

      if (mode === 'concept') {
        // Concept mode: load single concept with similar concepts
        setSearchParams({
          mode: 'concept',
          conceptId: conceptId,
          loadMode: 'clean',
        });
        if (similarity) {
          setSimilarityThreshold(parseFloat(similarity));
        }
      } else if (mode === 'neighborhood') {
        // Neighborhood mode: load subgraph around concept
        setSearchParams({
          mode: 'neighborhood',
          centerConceptId: conceptId,
          depth: depth ? parseInt(depth) : 2,
          loadMode: 'clean',
        });
      }

      // Reset flag after a tick to allow URL sync to run
      setTimeout(() => {
        initializingFromUrl.current = false;
      }, 100);
    } else if (mode === 'path' && fromConceptId && toConceptId) {
      initializingFromUrl.current = true;

      // Path mode: find connection between concepts
      setSearchParams({
        mode: 'path',
        fromConceptId: fromConceptId,
        toConceptId: toConceptId,
        maxHops: maxHops ? parseInt(maxHops) : 5,
        depth: depth ? parseInt(depth) : undefined,
        loadMode: 'clean',
      });

      setTimeout(() => {
        initializingFromUrl.current = false;
      }, 100);
    }
  }, [urlParams, setSearchParams, setSimilarityThreshold]);

  // Sync store state → URL parameters (bidirectional)
  useEffect(() => {
    // Don't update URL if we're initializing from URL
    if (initializingFromUrl.current) return;

    // Don't update URL if no search params set
    if (!searchParams.mode) return;

    const newParams = new URLSearchParams();

    if (searchParams.mode === 'concept' && searchParams.conceptId) {
      newParams.set('conceptId', searchParams.conceptId);
      newParams.set('mode', 'concept');
      newParams.set('similarity', similarityThreshold.toString());
    } else if (searchParams.mode === 'neighborhood' && searchParams.centerConceptId) {
      newParams.set('conceptId', searchParams.centerConceptId);
      newParams.set('mode', 'neighborhood');
      newParams.set('depth', (searchParams.depth || 2).toString());
    } else if (searchParams.mode === 'path' && searchParams.fromConceptId && searchParams.toConceptId) {
      newParams.set('mode', 'path');
      newParams.set('fromConceptId', searchParams.fromConceptId);
      newParams.set('toConceptId', searchParams.toConceptId);
      newParams.set('maxHops', (searchParams.maxHops || 5).toString());
      if (searchParams.depth) {
        newParams.set('depth', searchParams.depth.toString());
      }
    }

    // Only update URL if params have changed
    const currentParams = urlParams.toString();
    const updatedParams = newParams.toString();
    if (currentParams !== updatedParams) {
      setUrlParams(newParams, { replace: true }); // Use replace to avoid cluttering history
    }
  }, [searchParams, similarityThreshold, urlParams, setUrlParams]);

  // React to searchParams - fetch data based on mode
  // Concept mode: load single concept with neighbors
  const { data: conceptData, isLoading: isLoadingConcept } = useSubgraph(
    searchParams.mode === 'concept' ? searchParams.conceptId || null : null,
    {
      depth: 1,
      enabled: searchParams.mode === 'concept' && !!searchParams.conceptId,
    }
  );

  // Neighborhood mode: load subgraph with specified depth
  const { data: neighborhoodData, isLoading: isLoadingNeighborhood } = useSubgraph(
    searchParams.mode === 'neighborhood' ? searchParams.centerConceptId || null : null,
    {
      depth: searchParams.depth || 2,
      enabled: searchParams.mode === 'neighborhood' && !!searchParams.centerConceptId,
    }
  );

  // Path mode: find paths between two concepts
  const { data: pathData, isLoading: isLoadingPath, error: pathError } = useFindConnection(
    searchParams.mode === 'path' ? searchParams.fromConceptId || null : null,
    searchParams.mode === 'path' ? searchParams.toConceptId || null : null,
    {
      maxHops: searchParams.maxHops || 5,
      enabled: searchParams.mode === 'path' && !!searchParams.fromConceptId && !!searchParams.toConceptId,
    }
  );

  // Update rawGraphData when query results come back (cache API data)
  useEffect(() => {
    // Mode-aware data selection: use data from the active query mode only
    // (prevents stale cached data from a previous mode shadowing new results)
    let newData;
    switch (searchParams.mode) {
      case 'concept': newData = conceptData; break;
      case 'neighborhood': newData = neighborhoodData; break;
      case 'path': newData = pathData; break;
      default: newData = conceptData || neighborhoodData || pathData;
    }
    if (!newData) return;

    const graphPayload = { nodes: newData.nodes || [], links: newData.links || [] };

    if (searchParams.loadMode === 'clean') {
      setGraphData(null);
      setRawGraphData(graphPayload);
    } else if (searchParams.loadMode === 'add') {
      mergeRawGraphData(graphPayload);
    }
  }, [conceptData, neighborhoodData, pathData, searchParams.loadMode, searchParams.mode]);

  const isLoading = isLoadingConcept || isLoadingNeighborhood || isLoadingPath;
  const error = pathError;
  const graphData = storeGraphData;

  // Get the current explorer plugin
  const explorerPlugin = getExplorer(explorerType);

  // Transform rawGraphData using current explorer's dataTransformer
  useEffect(() => {
    if (!rawGraphData || !explorerPlugin) {
      return;
    }

    const transformedData = explorerPlugin.dataTransformer(rawGraphData);
    setGraphData(transformedData);
  }, [rawGraphData, explorerPlugin, explorerType]);

  // Local settings state for the current explorer
  const [explorerSettings, setExplorerSettings] = useState(
    explorerPlugin?.defaultSettings || {}
  );

  // Update settings when explorer changes
  useEffect(() => {
    if (explorerPlugin) {
      setExplorerSettings(explorerPlugin.defaultSettings);
    }
  }, [explorerPlugin, explorerType]);

  if (!explorerPlugin) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <h2 className="text-xl font-semibold mb-2">No Explorer Selected</h2>
          <p className="text-muted-foreground">Select an explorer from the sidebar</p>
        </div>
      </div>
    );
  }

  const ExplorerComponent = explorerPlugin.component;

  // Stable callback for node clicks to prevent simulation restarts
  const handleNodeClick = useCallback((nodeId: string) => {
    // Follow Concept: Load clicked node's neighborhood
    const store = useGraphStore.getState();
    store.setFocusedNodeId(nodeId);
    store.setSearchParams({
      mode: 'neighborhood',
      centerConceptId: nodeId,
      depth: 2, // Default depth for Follow Concept
      loadMode: 'add', // Add to existing graph
    });
  }, []);

  // Send current graph to Reports
  const handleSendToReports = useCallback(async () => {
    if (!rawGraphData || rawGraphData.nodes.length === 0) return;

    const reportData: GraphReportData = {
      type: 'graph',
      nodes: rawGraphData.nodes.map((n: any) => ({
        id: n.concept_id || n.id,
        label: n.label,
        description: n.description,
        ontology: n.ontology,
        grounding_strength: n.grounding_strength,
        diversity_score: n.diversity_score,
        evidence_count: n.evidence_count,
      })),
      links: rawGraphData.links.map((l: any) => ({
        source: l.from_id || l.source,
        target: l.to_id || l.target,
        type: l.relationship_type || l.type || 'RELATED',
        grounding_strength: l.grounding_strength,
      })),
      searchParams: {
        mode: searchParams.mode || 'unknown',
        conceptId: searchParams.conceptId || searchParams.centerConceptId,
        depth: searchParams.depth,
      },
    };

    await addReport({
      name: '', // Will auto-generate name based on content
      type: 'graph',
      data: reportData,
      sourceExplorer: explorerType === 'force-3d' ? '3d' : '2d',
    });

    navigate('/report');
  }, [rawGraphData, searchParams, explorerType, addReport, navigate]);

  // Load a saved query
  const handleLoadQuery = useCallback((query: any) => {
    const definition = query.definition;
    if (definition?.searchParams) {
      setSearchParams(definition.searchParams);
      if (definition.similarityThreshold) {
        setSimilarityThreshold(definition.similarityThreshold);
      }
    }
  }, [setSearchParams, setSimilarityThreshold]);

  // Delete a saved query
  const handleDeleteQuery = useCallback(async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    await deleteSavedQuery(id);
  }, [deleteSavedQuery]);

  // Saved queries panel content
  const savedQueriesPanelContent = (
    <div className="p-3">
      {isLoadingQueries ? (
        <div className="text-center text-muted-foreground text-sm py-4">
          Loading...
        </div>
      ) : savedQueries.length === 0 ? (
        <div className="text-center text-muted-foreground text-sm py-4">
          <History className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p>No saved queries</p>
          <p className="text-xs mt-1">Save queries from the search panel</p>
        </div>
      ) : (
        <div className="space-y-2">
          {savedQueries.map((query) => (
            <div
              key={query.id}
              className="border rounded-lg p-3 bg-card hover:bg-accent/50 transition-colors cursor-pointer group"
              onClick={() => handleLoadQuery(query)}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm truncate">{query.name}</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {new Date(query.created_at).toLocaleDateString()}
                  </div>
                </div>
                <button
                  onClick={(e) => handleDeleteQuery(query.id, e)}
                  className="opacity-0 group-hover:opacity-100 text-destructive hover:text-destructive/80 transition-opacity p-1"
                  title="Delete query"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  // Settings panel content
  const settingsPanelContent = (
    <div className="p-3 space-y-4">
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-sm font-medium">Similarity Threshold</label>
          <span className="text-sm font-mono text-primary">{Math.round(similarityThreshold * 100)}%</span>
        </div>
        <input
          type="range"
          min="0.3"
          max="0.95"
          step="0.05"
          value={similarityThreshold}
          onChange={(e) => setSimilarityThreshold(parseFloat(e.target.value))}
          className="w-full"
        />
        <p className="text-xs text-muted-foreground mt-1">
          Minimum similarity for concept search
        </p>
      </div>
    </div>
  );

  // Tab definitions for IconRailPanel
  const tabs = [
    {
      id: 'history',
      label: 'Saved Queries',
      icon: History,
      content: savedQueriesPanelContent,
    },
    {
      id: 'settings',
      label: 'Settings',
      icon: Settings,
      content: settingsPanelContent,
    },
  ];

  return (
    <div className="h-full flex">
      {/* Left sidebar with IconRailPanel */}
      <IconRailPanel
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        defaultExpanded={false}
      />

      {/* Main visualization area */}
      <div className="flex-1 flex flex-col">
        {/* Search Bar at top */}
        <div
          className="border-b border-border bg-card"
          style={{ zIndex: getZIndexValue('searchBar') }}
        >
          <div className="p-4">
            <SearchBar />
          </div>
        </div>

        {/* Visualization Area */}
        <div
          className={`flex-1 relative ${!graphData && !isLoading ? 'pointer-events-none' : ''}`}
          style={{ zIndex: getZIndexValue('content') }}
        >
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-background/50 z-10">
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
                <p className="text-muted-foreground">Loading graph data...</p>
              </div>
            </div>
          )}

          {error && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <h3 className="text-lg font-semibold mb-2">Error Loading Data</h3>
                <p className="text-muted-foreground">{(error as Error).message}</p>
              </div>
            </div>
          )}

          {!graphData && !isLoading && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-0">
              <div className="text-center max-w-md">
                <h3 className="text-xl font-semibold mb-2">Welcome to Knowledge Graph Visualization</h3>
                <p className="text-muted-foreground mb-4">
                  Search for a concept above to start exploring the graph
                </p>
                <div className="text-sm text-muted-foreground">
                  <p>Tips:</p>
                  <ul className="mt-2 space-y-1 text-left">
                    <li>• Use the search bar above to find concepts</li>
                    <li>• Click nodes to explore connections</li>
                    <li>• Use the sidebar for saved queries and settings</li>
                    <li>• Drag nodes to reposition them</li>
                  </ul>
                </div>
              </div>
            </div>
          )}

          {graphData && !isLoading && (
            <ExplorerComponent
              data={graphData}
              settings={explorerSettings}
              onSettingsChange={setExplorerSettings}
              onNodeClick={handleNodeClick}
              onSendToReports={rawGraphData && rawGraphData.nodes.length > 0 ? handleSendToReports : undefined}
            />
          )}
        </div>
      </div>
    </div>
  );
};
