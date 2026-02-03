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
import { FolderOpen, Save, Settings, Trash2 } from 'lucide-react';
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
import { apiClient } from '../api/client';
import { stepToCypher, generateCypher, parseCypherStatements } from '../utils/cypherGenerator';
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
    explorationSession,
    subtractRawGraphData,
  } = useGraphStore();
  const { addReport } = useReportStore();
  const {
    definitions: savedQueriesMap,
    definitionIds: savedQueryIds,
    loadDefinitions: loadSavedQueries,
    createDefinition: createSavedQuery,
    deleteDefinition: deleteSavedQuery,
    isLoading: isLoadingQueries,
  } = useQueryDefinitionStore();

  // Convert to array for rendering
  const savedQueries = savedQueryIds.map(id => savedQueriesMap[id]).filter(Boolean);

  // UI state for IconRailPanel
  const [activeTab, setActiveTab] = useState('history');

  // Track if we've already initialized from URL (run once on mount)
  const hasInitializedFromUrl = React.useRef(false);

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
    }
  }, [urlParams, setSearchParams, setSimilarityThreshold]);

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
      .map((n: any) => n.concept_id || n.id)
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
  const lastProcessedData = React.useRef<any>(mode === 'path' ? pathData : exploreData);

  // Update rawGraphData when query results come back
  useEffect(() => {
    const newData = mode === 'path' ? pathData : exploreData;
    if (!newData || newData === lastProcessedData.current) return;
    lastProcessedData.current = newData;

    const graphPayload = { nodes: newData.nodes || [], links: newData.links || [] };

    if (loadModeRef.current === 'add') {
      mergeRawGraphData(graphPayload);
    } else {
      setGraphData(null);
      setRawGraphData(graphPayload);
    }
  }, [exploreData, pathData, mode]);

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
      (n: any) => (n.concept_id || n.id) === nodeId
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

  // Load a saved query
  const handleLoadQuery = useCallback(async (query: any) => {
    const definition = query.definition;

    // Exploration-type: replay +/- Cypher statements
    if (query.definition_type === 'exploration' && definition?.statements) {
      setGraphData(null);
      setRawGraphData(null);

      for (const stmt of definition.statements as Array<{ op: '+' | '-'; cypher: string }>) {
        try {
          const result = await apiClient.executeCypherQuery({ query: stmt.cypher, limit: 500 });

          // Build AGE internal ID → concept_id map
          const internalToConceptId = new Map<string, string>();
          (result.nodes || []).forEach((n: any) => {
            const conceptId = n.properties?.concept_id || n.id;
            internalToConceptId.set(n.id, conceptId);
          });

          const nodes = (result.nodes || []).map((n: any) => ({
            concept_id: n.properties?.concept_id || n.id,
            label: n.label,
            ontology: n.properties?.ontology || 'default',
            search_terms: n.properties?.search_terms || [],
            grounding_strength: n.properties?.grounding_strength,
          }));
          const links = (result.relationships || []).map((r: any) => ({
            from_id: internalToConceptId.get(r.from_id) || r.from_id,
            to_id: internalToConceptId.get(r.to_id) || r.to_id,
            relationship_type: r.type,
            category: r.properties?.category,
            confidence: r.confidence,
          }));

          if (stmt.op === '+') {
            mergeRawGraphData({ nodes, links });
          } else {
            subtractRawGraphData({ nodes, links });
          }
        } catch (error) {
          console.error('Failed to replay statement:', stmt.cypher, error);
        }
      }
      return;
    }

    // Legacy: searchParams-based queries
    if (definition?.searchParams) {
      setSearchParams(definition.searchParams);
      if (definition.similarityThreshold) {
        setSimilarityThreshold(definition.similarityThreshold);
      }
    }
  }, [setGraphData, setRawGraphData, mergeRawGraphData, subtractRawGraphData, setSearchParams, setSimilarityThreshold]);

  // Delete a saved query
  const handleDeleteQuery = useCallback(async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    await deleteSavedQuery(id);
  }, [deleteSavedQuery]);

  const hasExploration = explorationSession && explorationSession.steps.length > 0;

  // Saved queries panel content
  const savedQueriesPanelContent = (
    <div className="p-3">
      {hasExploration && (
        <button
          onClick={handleSaveExploration}
          className="w-full flex items-center gap-2 px-3 py-2 mb-3 text-sm font-medium rounded-lg border border-primary/30 bg-primary/5 hover:bg-primary/10 text-primary transition-colors"
        >
          <Save className="w-4 h-4" />
          Save Current Exploration ({explorationSession.steps.length} steps)
        </button>
      )}
      {isLoadingQueries ? (
        <div className="text-center text-muted-foreground text-sm py-4">
          Loading...
        </div>
      ) : savedQueries.length === 0 ? (
        <div className="text-center text-muted-foreground text-sm py-4">
          <FolderOpen className="w-8 h-8 mx-auto mb-2 opacity-50" />
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
                    {query.definition_type === 'exploration'
                      ? `${(query.definition as any)?.statements?.length || 0} steps`
                      : query.definition_type}
                    {' \u00b7 '}
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
