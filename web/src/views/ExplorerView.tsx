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
import { FolderOpen, Settings, Eraser } from 'lucide-react';
import { SearchBar } from '../components/shared/SearchBar';
import { IconRailPanel } from '../components/shared/IconRailPanel';
import { SavedQueriesPanel } from '../components/shared/SavedQueriesPanel';
import { useQueryReplay } from '../hooks/useQueryReplay';
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
import { stepToCypher, generateCypher, parseCypherStatements } from '../utils/cypherGenerator';
import type { RawGraphNode, RawGraphLink } from '../utils/cypherResultMapper';
import type { VisualizationType } from '../types/explorer';

interface ExplorerViewProps {
  explorerType: VisualizationType;
}

/** Main explorer view — search bar, graph renderer, saved queries panel, and Cypher editor.  @verified 7b5be48d */
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
    clearSearchParams,
    setSimilarityThreshold,
    explorationSession,
    clearExploration,
  } = useGraphStore();
  const { addReport } = useReportStore();
  const {
    createDefinition: createSavedQuery,
  } = useQueryDefinitionStore();
  const { replayQuery, isReplaying } = useQueryReplay();

  // UI state for IconRailPanel
  const [activeTab, setActiveTab] = useState('history');

  // Track if we've already initialized from URL (run once on mount)
  const hasInitializedFromUrl = React.useRef(false);

  // Derive mode from current params
  const mode = deriveMode(searchParams);


  // Set the explorer type when this view mounts
  useEffect(() => {
    setSelectedExplorer(explorerType);
  }, [explorerType, setSelectedExplorer]);

  // Initialize from URL parameters once on mount
  useEffect(() => {
    if (hasInitializedFromUrl.current) return;

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
      hasInitializedFromUrl.current = true;
      setSearchParams({
        primaryConceptId: legacyFromId,
        destinationConceptId: destId || undefined,
        depth: depth || 1,
        maxHops,
        loadMode: 'clean',
      });
    } else if (primaryId) {
      hasInitializedFromUrl.current = true;

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
    } else {
      // No URL params — clear any persisted searchParams so stale queries
      // don't re-fire. The graph data stays visible until the next search.
      hasInitializedFromUrl.current = true;
      clearSearchParams();
    }
  }, [urlParams, setSearchParams, setSimilarityThreshold, clearSearchParams]);

  // Sync store state → URL parameters
  useEffect(() => {
    if (!hasInitializedFromUrl.current && mode !== 'idle') {
      // First store change — mark as initialized to prevent URL→store loop
      hasInitializedFromUrl.current = true;
    }
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
      .map((n: RawGraphNode) => n.concept_id)
      .filter(Boolean);
  }, [mode, pathData]);

  const { data: enrichmentData, isLoading: isLoadingEnrichment } = usePathEnrichment(
    pathNodeIds,
    searchParams.depth,
    { enabled: mode === 'path' && pathNodeIds.length > 0 }
  );

  // Track loadMode via ref so the data effect reads the intended mode
  // without re-running when loadMode changes independently of data.
  const loadModeRef = React.useRef(searchParams.loadMode);
  useEffect(() => {
    loadModeRef.current = searchParams.loadMode;
  }, [searchParams.loadMode]);

  // Track last-processed data to avoid re-processing on remount or unrelated rerenders.
  // Initialize to current query data so cached results from a previous mount are skipped —
  // this preserves rawGraphData in Zustand when toggling between 2D/3D/analysis views.
  const lastProcessedData = React.useRef<{ nodes?: unknown[]; links?: unknown[] } | undefined>(mode === 'path' ? pathData : exploreData);

  // Track searchParams identity to detect user-initiated loads.
  // When the user clicks Load, setSearchParams creates a new object reference.
  // On remount (view switch), the reference is the same Zustand object.
  const lastSearchParamsRef = React.useRef(searchParams);

  // Update rawGraphData when query results come back
  useEffect(() => {
    const newData = mode === 'path' ? pathData : exploreData;
    if (!newData) return;

    // Skip if same data AND not a new user-initiated search.
    // User-initiated searches produce a new searchParams reference.
    const isNewSearch = searchParams !== lastSearchParamsRef.current;
    lastSearchParamsRef.current = searchParams;

    if (newData === lastProcessedData.current && !isNewSearch) return;
    lastProcessedData.current = newData;

    const graphPayload = { nodes: newData.nodes || [], links: newData.links || [] };

    if (loadModeRef.current === 'add') {
      mergeRawGraphData(graphPayload);
    } else {
      setGraphData(null);
      setRawGraphData(graphPayload);
    }
  }, [exploreData, pathData, mode, searchParams]);

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

  /** Follow Concept: load clicked node's neighborhood and record the step */
  const handleNodeClick = useCallback((nodeId: string) => {
    const store = useGraphStore.getState();

    const nodeLabel = store.rawGraphData?.nodes?.find(
      (n: RawGraphNode) => n.concept_id === nodeId
    )?.label || nodeId;

    store.addExplorationStep({
      action: 'add-adjacent',
      op: '+',
      cypher: stepToCypher({ action: 'add-adjacent', conceptLabel: nodeLabel, depth: 2 }),
      conceptId: nodeId,
      conceptLabel: nodeLabel,
      depth: 2,
    });

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
      nodes: rawGraphData.nodes.map((n: RawGraphNode) => ({
        id: n.concept_id,
        label: n.label,
        description: n.description,
        ontology: n.ontology,
        grounding_strength: n.grounding_strength,
        diversity_score: n.diversity_score,
        evidence_count: n.evidence_count,
      })),
      links: rawGraphData.links.map((l: RawGraphLink) => ({
        source: l.from_id,
        target: l.to_id,
        type: l.relationship_type || 'RELATED',
        grounding_strength: l.grounding_strength,
      })),
      searchParams: {
        mode: mode === 'idle' ? 'graph' : mode,
        query: searchParams.primaryConceptLabel || undefined,
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

  // Save current exploration as a query definition
  const handleSaveExploration = useCallback(async () => {
    if (!explorationSession || explorationSession.steps.length === 0) return;

    const cypherScript = generateCypher(explorationSession);
    const statements = parseCypherStatements(cypherScript);

    const name = explorationSession.name
      || `Exploration ${new Date().toLocaleDateString()} ${new Date().toLocaleTimeString()}`;

    await createSavedQuery({
      name,
      definition_type: 'exploration',
      definition: { statements },
      metadata: {
        stepCount: explorationSession.steps.length,
        createdFrom: explorerType,
      },
    });
  }, [explorationSession, createSavedQuery, explorerType]);

  // Export current exploration to Cypher editor
  const handleExportToEditor = useCallback(() => {
    if (!explorationSession || explorationSession.steps.length === 0) return;
    const script = generateCypher(explorationSession);
    useGraphStore.getState().setCypherEditorContent(script);
  }, [explorationSession]);

  // Saved queries panel content — uses shared SavedQueriesPanel component
  const savedQueriesPanelContent = (
    <SavedQueriesPanel
      onLoadQuery={replayQuery}
      onSaveExploration={handleSaveExploration}
      onExportToEditor={handleExportToEditor}
      currentExploration={explorationSession?.steps.length ? { stepCount: explorationSession.steps.length } : null}
      definitionTypeFilter="exploration"
    />
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

  // Clear graph and search state
  const handleClearGraph = useCallback(() => {
    clearExploration();
    clearSearchParams();
    setUrlParams(new URLSearchParams(), { replace: true });
  }, [clearExploration, clearSearchParams, setUrlParams]);

  // Tab definitions for IconRailPanel
  const tabs = [
    {
      id: 'history',
      label: 'Saved Queries',
      icon: FolderOpen,
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
        actions={[
          {
            id: 'clear',
            icon: Eraser,
            label: 'Clear Graph',
            onClick: handleClearGraph,
          },
        ]}
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
          {(isLoading || isReplaying) && (
            <div className="absolute inset-0 flex items-center justify-center bg-background/50 z-10">
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
                <p className="text-muted-foreground">
                  {isReplaying ? 'Replaying exploration steps...' : 'Loading graph data...'}
                </p>
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
