/**
 * Explorer View
 *
 * Encapsulates the explorer visualization functionality including:
 * - Search bar with query modes
 * - Graph data fetching
 * - Explorer rendering (2D/3D)
 * - Saved queries management (ADR-083)
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { History, Settings, Trash2 } from 'lucide-react';
import { SearchBar } from '../components/shared/SearchBar';
import { IconRailPanel } from '../components/shared/IconRailPanel';
import { useGraphStore, deriveMode } from '../store/graphStore';
import { useReportStore } from '../store/reportStore';
import { useQueryDefinitionStore } from '../store/queryDefinitionStore';
import type { GraphReportData } from '../store/reportStore';
import { useSubgraph, useFindConnection, usePathEnrichment } from '../hooks/useGraphData';
import { getExplorer } from '../explorers';
import { GraphSettingsPanel } from '../explorers/common/GraphSettingsPanel';
import { Settings3DPanel } from '../explorers/common/3DSettingsPanel';
import { SLIDER_RANGES as SLIDER_RANGES_2D } from '../explorers/ForceGraph2D/types';
import { SLIDER_RANGES as SLIDER_RANGES_3D } from '../explorers/ForceGraph3D/types';
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

  // Derive mode from current params
  const mode = deriveMode(searchParams);

  // Load saved queries on mount
  useEffect(() => {
    loadSavedQueries();
  }, [loadSavedQueries]);

  // Set the explorer type when this view mounts
  useEffect(() => {
    setSelectedExplorer(explorerType);
  }, [explorerType, setSelectedExplorer]);

  // Initialize from URL parameters on mount (supports both new and legacy URL formats)
  useEffect(() => {
    // New format: c=conceptId, to=destId, d=depth, h=maxHops, s=similarity
    // Legacy format: mode=concept|neighborhood|path, conceptId=X, fromConceptId=X, etc.
    const primaryId = urlParams.get('c') || urlParams.get('conceptId');
    const destId = urlParams.get('to') || urlParams.get('toConceptId');
    const depth = parseInt(urlParams.get('d') || urlParams.get('depth') || '0');
    const maxHops = parseInt(urlParams.get('h') || urlParams.get('maxHops') || '5');
    const similarity = urlParams.get('s') || urlParams.get('similarity');

    // Legacy path mode used fromConceptId instead of conceptId
    const legacyMode = urlParams.get('mode');
    const legacyFromId = urlParams.get('fromConceptId');

    if (legacyMode === 'path' && legacyFromId) {
      // Legacy path URL
      initializingFromUrl.current = true;
      setSearchParams({
        primaryConceptId: legacyFromId,
        destinationConceptId: destId || undefined,
        depth: depth || 1,
        maxHops,
        loadMode: 'clean',
      });
      setTimeout(() => { initializingFromUrl.current = false; }, 100);
    } else if (primaryId) {
      // New format or legacy concept/neighborhood URL
      initializingFromUrl.current = true;

      const effectiveDepth = depth || (legacyMode === 'neighborhood' ? 2 : 1);

      setSearchParams({
        primaryConceptId: primaryId,
        destinationConceptId: destId || undefined,
        depth: effectiveDepth,
        maxHops,
        loadMode: 'clean',
      });

      if (similarity) {
        setSimilarityThreshold(parseFloat(similarity));
      }

      setTimeout(() => { initializingFromUrl.current = false; }, 100);
    }
  }, [urlParams, setSearchParams, setSimilarityThreshold]);

  // Sync store state → URL parameters
  useEffect(() => {
    if (initializingFromUrl.current) return;
    if (mode === 'idle') return;

    const newParams = new URLSearchParams();

    if (searchParams.primaryConceptId) {
      newParams.set('c', searchParams.primaryConceptId);
      newParams.set('d', searchParams.depth.toString());

      if (searchParams.destinationConceptId) {
        newParams.set('to', searchParams.destinationConceptId);
        newParams.set('h', searchParams.maxHops.toString());
      }

      newParams.set('s', similarityThreshold.toString());
    }

    const currentParams = urlParams.toString();
    const updatedParams = newParams.toString();
    if (currentParams !== updatedParams) {
      setUrlParams(newParams, { replace: true });
    }
  }, [searchParams, similarityThreshold, mode, urlParams, setUrlParams]);

  // Explore mode: subgraph around primary concept (covers old concept + neighborhood)
  const { data: exploreData, isLoading: isLoadingExplore } = useSubgraph(
    mode === 'explore' ? searchParams.primaryConceptId || null : null,
    {
      depth: searchParams.depth,
      enabled: mode === 'explore' && !!searchParams.primaryConceptId,
    }
  );

  // Path mode: find paths between primary and destination
  const { data: pathData, isLoading: isLoadingPath, error: pathError } = useFindConnection(
    mode === 'path' ? searchParams.primaryConceptId || null : null,
    mode === 'path' ? searchParams.destinationConceptId || null : null,
    {
      maxHops: searchParams.maxHops,
      enabled: mode === 'path' && !!searchParams.primaryConceptId && !!searchParams.destinationConceptId,
    }
  );

  // Path enrichment: expand neighborhoods around path nodes when depth > 0
  const pathNodeIds = useMemo(() => {
    if (mode !== 'path' || !pathData?.nodes) return [];
    return pathData.nodes
      .map((n: any) => n.concept_id || n.id)
      .filter(Boolean);
  }, [mode, pathData]);

  const { data: enrichmentData, isLoading: isLoadingEnrichment } = usePathEnrichment(
    pathNodeIds,
    searchParams.depth,
    { enabled: mode === 'path' && pathNodeIds.length > 0 }
  );

  // Update rawGraphData when query results come back
  useEffect(() => {
    const newData = mode === 'path' ? pathData : exploreData;
    if (!newData) return;

    const graphPayload = { nodes: newData.nodes || [], links: newData.links || [] };

    if (searchParams.loadMode === 'clean') {
      setGraphData(null);
      setRawGraphData(graphPayload);
    } else if (searchParams.loadMode === 'add') {
      mergeRawGraphData(graphPayload);
    }
  }, [exploreData, pathData, searchParams.loadMode, mode]);

  // Merge path enrichment data when it arrives
  useEffect(() => {
    if (!enrichmentData) return;
    mergeRawGraphData(enrichmentData);
  }, [enrichmentData]);

  const isLoading = isLoadingExplore || isLoadingPath || isLoadingEnrichment;
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

  // Slider ranges for the current explorer's settings panel
  const sliderRanges = explorerType === 'force-3d' ? SLIDER_RANGES_3D : SLIDER_RANGES_2D;

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

  // Follow Concept: load clicked node's neighborhood
  const handleNodeClick = useCallback((nodeId: string) => {
    const store = useGraphStore.getState();

    // Resolve label from current graph data for SearchBar display
    const nodeLabel = store.rawGraphData?.nodes?.find(
      (n: any) => (n.concept_id || n.id) === nodeId
    )?.label;

    store.setFocusedNodeId(nodeId);
    store.setSearchParams({
      primaryConceptId: nodeId,
      primaryConceptLabel: nodeLabel,
      depth: 2,
      maxHops: 5,
      loadMode: 'add',
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
        mode: mode === 'idle' ? 'unknown' : mode,
        conceptId: searchParams.primaryConceptId,
        depth: searchParams.depth,
      },
    };

    await addReport({
      name: '',
      type: 'graph',
      data: reportData,
      sourceExplorer: explorerType === 'force-3d' ? '3d' : '2d',
    });

    navigate('/report');
  }, [rawGraphData, searchParams, mode, explorerType, addReport, navigate]);

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

  // Settings panel content — graph settings (physics, visual, interaction)
  const settingsPanelContent = (
    <div className="p-3 space-y-4">
      {explorerSettings?.physics ? (
        <>
          <GraphSettingsPanel
            settings={explorerSettings}
            onChange={setExplorerSettings}
            sliderRanges={sliderRanges}
            embedded
          />
          {explorerType === 'force-3d' && explorerSettings.camera && (
            <Settings3DPanel
              camera={explorerSettings.camera}
              onCameraChange={(camera) =>
                setExplorerSettings({ ...explorerSettings, camera })
              }
              embedded
            />
          )}
        </>
      ) : (
        <div className="text-center text-muted-foreground text-sm py-4">
          <p>No settings for this explorer</p>
        </div>
      )}
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
          <div className="p-4 min-w-0">
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
                    <li>Search for a concept above to find concepts</li>
                    <li>Click nodes to explore connections</li>
                    <li>Use the sidebar for saved queries and settings</li>
                    <li>Drag nodes to reposition them</li>
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
