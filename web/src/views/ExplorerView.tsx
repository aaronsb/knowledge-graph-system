/**
 * Explorer View
 *
 * Encapsulates the explorer visualization functionality including:
 * - Search bar with query modes
 * - Graph data fetching
 * - Explorer rendering (2D/3D)
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { FileSpreadsheet } from 'lucide-react';
import { SearchBar } from '../components/shared/SearchBar';
import { useGraphStore } from '../store/graphStore';
import { useReportStore } from '../store/reportStore';
import type { GraphReportData } from '../store/reportStore';
import { useSubgraph, useFindConnection } from '../hooks/useGraphData';
import { getExplorer } from '../explorers';
import { apiClient } from '../api/client';
import { getZIndexValue } from '../config/zIndex';

interface ExplorerViewProps {
  explorerType: string;
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
    setSelectedExplorer,
    setSearchParams,
    setSimilarityThreshold,
  } = useGraphStore();
  const { addReport } = useReportStore();

  // Track if we're initializing from URL to prevent loops
  const initializingFromUrl = React.useRef(false);

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
      enabled: searchParams.mode === 'path' && !!searchParams.fromConceptId && !!searchParams.toConceptId && !searchParams.depth,
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
  const handleSendToReports = useCallback(() => {
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

    addReport({
      name: '', // Will auto-generate name based on content
      type: 'graph',
      data: reportData,
      sourceExplorer: explorerType === 'force-graph-3d' ? '3d' : '2d',
    });

    navigate('/report');
  }, [rawGraphData, searchParams, explorerType, addReport, navigate]);

  return (
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

        {/* Send to Reports button - shown when graph has data */}
        {rawGraphData && rawGraphData.nodes.length > 0 && !isLoading && (
          <button
            onClick={handleSendToReports}
            className="absolute bottom-4 right-4 flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 shadow-lg transition-colors z-20"
            title="Send to Reports"
          >
            <FileSpreadsheet className="w-4 h-4" />
            <span className="text-sm font-medium">Send to Reports</span>
          </button>
        )}
      </div>
    </div>
  );
};
