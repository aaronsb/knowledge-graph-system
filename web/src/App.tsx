/**
 * Main Application Component
 *
 * Integrates React Query, Zustand store, and explorer system.
 * Follows ADR-034 architecture.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { SearchBar } from './components/shared/SearchBar';
import { OAuthCallback } from './components/auth/OAuthCallback';
import { useGraphStore } from './store/graphStore';
import { useVocabularyStore } from './store/vocabularyStore';
import { useAuthStore } from './store/authStore';
import { useThemeStore } from './store/themeStore';
import { useSubgraph, useFindConnection } from './hooks/useGraphData';
import { getExplorer } from './explorers';
import { apiClient } from './api/client';
import { getZIndexClass, getZIndexValue } from './config/zIndex';
import './explorers'; // Import to register explorers

// Create React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

const AppContent: React.FC = () => {
  const { selectedExplorer, searchParams, graphData: storeGraphData, rawGraphData, setGraphData, setRawGraphData, queryMode, blockBuilderExpanded } = useGraphStore();
  const { setTypes, setLoading, setError } = useVocabularyStore();
  const { checkAuth } = useAuthStore();
  const { theme, setTheme } = useThemeStore();

  // Initialize theme on mount
  useEffect(() => {
    setTheme(theme);
  }, []);

  // Check authentication status on mount
  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  // Load vocabulary on mount
  useEffect(() => {
    const loadVocabulary = async () => {
      setLoading(true);
      try {
        // First load existing vocabulary (include inactive types that may still be in use)
        const response = await apiClient.getVocabularyTypes({
          include_inactive: true, // Include all types, even inactive ones
          include_builtin: true,
        });
        const types = response.types || [];

        // Check if any types (active or inactive but with edge_count > 0) are missing categories
        const typesWithoutCategory = types.filter((t: any) =>
          t.edge_count > 0 && !t.category
        );

        if (typesWithoutCategory.length > 0) {
          console.log(`⚠️ Found ${typesWithoutCategory.length} types without categories, refreshing...`);

          // Trigger category refresh
          await apiClient.refreshVocabularyCategories({ only_computed: true });

          // Reload vocabulary after refresh (include inactive again)
          const refreshedResponse = await apiClient.getVocabularyTypes({
            include_inactive: true,
            include_builtin: true,
          });
          setTypes(refreshedResponse.types || []);
          console.log(`✅ Refreshed and loaded ${refreshedResponse.types?.length || 0} vocabulary types`);
        } else {
          setTypes(types);
          console.log(`✅ Loaded ${types.length} vocabulary types (all have categories)`);
        }

        // Log category distribution
        const categoryCount: Record<string, number> = {};
        const currentTypes = useVocabularyStore.getState().types;
        currentTypes.forEach((t: any) => {
          categoryCount[t.category] = (categoryCount[t.category] || 0) + 1;
        });
        console.log('📊 Category distribution:', categoryCount);
      } catch (error) {
        console.error('❌ Failed to load vocabulary:', error);
        setError(error instanceof Error ? error.message : 'Failed to load vocabulary');
      }
    };
    loadVocabulary();
  }, []); // Run once on mount

  // No resize state needed - BlockBuilder sizes itself naturally

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
      enabled: searchParams.mode === 'path' && !!searchParams.fromConceptId && !!searchParams.toConceptId && !searchParams.depth, // Only if no depth enrichment
    }
  );

  // Path enrichment: When depth is specified, fetch neighborhoods around each hop
  const [enrichedPathData, setEnrichedPathData] = React.useState<any>(null);
  const [isEnrichingPath, setIsEnrichingPath] = React.useState(false);

  useEffect(() => {
    const enrichPath = async () => {
      if (searchParams.mode !== 'path' || !searchParams.depth || searchParams.depth === 0) {
        setEnrichedPathData(null);
        return;
      }

      if (!searchParams.fromConceptId || !searchParams.toConceptId) return;

      setIsEnrichingPath(true);
      try {
        // Step 1: Get the path
        const pathResult = await apiClient.findConnection({
          from_id: searchParams.fromConceptId,
          to_id: searchParams.toConceptId,
          max_hops: searchParams.maxHops || 5,
        });

        if (!pathResult.paths || pathResult.paths.length === 0) {
          setEnrichedPathData({ nodes: [], links: [] });
          setIsEnrichingPath(false);
          return;
        }

        // Step 2: Get the first/best path
        const bestPath = pathResult.paths[0];
        const nodeIds = bestPath.nodes.map((n: any) => n.id);

        // Step 3: Fetch neighborhood for each node in the path
        const neighborhoodPromises = nodeIds.map((nodeId: string) =>
          apiClient.getSubgraph({
            center_concept_id: nodeId,
            depth: searchParams.depth,
          })
        );

        const neighborhoods = await Promise.all(neighborhoodPromises);

        // Step 4: Merge all neighborhoods + path
        const allNodes = new Map();
        const allLinks: any[] = [];

        // Add path nodes
        bestPath.nodes.forEach((node: any) => {
          allNodes.set(node.id, {
            concept_id: node.id,
            label: node.label,
            ontology: 'default',
          });
        });

        // Add path links
        for (let i = 0; i < bestPath.nodes.length - 1; i++) {
          allLinks.push({
            from_id: bestPath.nodes[i].id,
            to_id: bestPath.nodes[i + 1].id,
            relationship_type: bestPath.relationships[i] || 'PATH',
          });
        }

        // Add neighborhood nodes and links
        neighborhoods.forEach((neighborhood) => {
          neighborhood.nodes.forEach((node: any) => {
            if (!allNodes.has(node.concept_id)) {
              allNodes.set(node.concept_id, node);
            }
          });
          neighborhood.links.forEach((link: any) => {
            allLinks.push(link);
          });
        });

        // Return raw API data (transformation happens in explorer-specific dataTransformer)
        const enrichedData = { nodes: Array.from(allNodes.values()), links: allLinks };
        setEnrichedPathData(enrichedData);
      } catch (error) {
        console.error('Failed to enrich path:', error);
        setEnrichedPathData(null);
      } finally {
        setIsEnrichingPath(false);
      }
    };

    enrichPath();
  }, [searchParams.mode, searchParams.fromConceptId, searchParams.toConceptId, searchParams.maxHops, searchParams.depth]);

  // Update rawGraphData when query results come back (cache API data)
  useEffect(() => {
    const newData = conceptData || neighborhoodData || pathData || enrichedPathData;
    if (!newData) return;

    if (searchParams.loadMode === 'clean') {
      // Clear old transformed data immediately to prevent stale data being displayed
      setGraphData(null);
      // Store raw data (transformation happens in separate useEffect)
      setRawGraphData({ nodes: newData.nodes || [], links: newData.links || [] });
    } else if (searchParams.loadMode === 'add') {
      // Merge with existing raw data
      const currentRawData = useGraphStore.getState().rawGraphData;

      if (!currentRawData || !currentRawData.nodes || currentRawData.nodes.length === 0) {
        setRawGraphData({ nodes: newData.nodes || [], links: newData.links || [] });
      } else {
        // Simple merge - deduplicate by node ID
        const existingNodeIds = new Set(currentRawData.nodes.map((n: any) => n.id || n.concept_id));
        const newNodes = (newData.nodes || []).filter((n: any) => !existingNodeIds.has(n.id || n.concept_id));

        const existingLinkKeys = new Set(
          currentRawData.links.map((l: any) => `${l.from_id || l.source}->${l.to_id || l.target}`)
        );
        const newLinks = (newData.links || []).filter((l: any) =>
          !existingLinkKeys.has(`${l.from_id || l.source}->${l.to_id || l.target}`)
        );

        setRawGraphData({
          nodes: [...currentRawData.nodes, ...newNodes],
          links: [...currentRawData.links, ...newLinks],
        });
      }
    }
  }, [conceptData, neighborhoodData, pathData, enrichedPathData, searchParams.loadMode]);

  const isLoading = isLoadingConcept || isLoadingNeighborhood || isLoadingPath || isEnrichingPath;
  const error = pathError;
  const graphData = storeGraphData;

  // Get the current explorer plugin
  const explorerPlugin = getExplorer(selectedExplorer);

  // Transform rawGraphData using current explorer's dataTransformer
  useEffect(() => {
    if (!rawGraphData || !explorerPlugin) {
      console.log('⏸️ Skipping transform:', { hasRawData: !!rawGraphData, hasPlugin: !!explorerPlugin });
      return;
    }

    console.log('🔄 Transforming data for explorer:', selectedExplorer, 'Raw nodes:', rawGraphData.nodes?.length);
    const transformedData = explorerPlugin.dataTransformer(rawGraphData);
    console.log('✅ Transformed data:', { nodes: transformedData.nodes?.length, links: transformedData.links?.length });
    console.log('📊 Sample link:', transformedData.links?.[0]);
    setGraphData(transformedData);
  }, [rawGraphData, explorerPlugin, selectedExplorer]); // Re-transform when raw data or explorer changes

  // Local settings state for the current explorer
  const [explorerSettings, setExplorerSettings] = useState(
    explorerPlugin?.defaultSettings || {}
  );

  // Update settings when explorer changes
  useEffect(() => {
    if (explorerPlugin) {
      setExplorerSettings(explorerPlugin.defaultSettings);
    }
  }, [explorerPlugin, selectedExplorer]);

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
  const SettingsPanelComponent = explorerPlugin.settingsPanel;


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
  }, []); // Empty deps - uses getState() to avoid stale closures

  return (
    <AppLayout>
      <div className="h-full flex flex-col">
        {/* Search Bar / Query Interface */}
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
                    <li>• Use the search bar to find concepts</li>
                    <li>• Click nodes to explore connections</li>
                    <li>• Adjust settings in the right panel</li>
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
            />
          )}
        </div>
      </div>
    </AppLayout>
  );
};

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AppContent />} />
          <Route path="/callback" element={<OAuthCallback />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
