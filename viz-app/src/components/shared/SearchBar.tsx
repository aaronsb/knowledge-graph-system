/**
 * Multi-Mode Smart Search Component
 *
 * Top-level: Query mode selection via radio dial
 * - Smart Search (with sub-modes: Concept/Neighborhood/Path)
 * - Block Builder (future)
 * - openCypher Editor (future)
 *
 * Within Smart Search:
 * - Concept: Semantic search for individual concepts (IMPLEMENTED)
 * - Neighborhood: Explore concepts within N hops (IMPLEMENTED)
 * - Path: Find paths connecting two concepts (IMPLEMENTED)
 */

import React, { useState, useEffect } from 'react';
import { Search, Loader2, Network, GitBranch, Blocks, Code } from 'lucide-react';
import { useSearchConcepts } from '../../hooks/useGraphData';
import { useGraphStore } from '../../store/graphStore';
import { ModeDial } from './ModeDial';
import type { QueryMode } from './ModeDial';
import { apiClient } from '../../api/client';
import { transformForD3 } from '../../utils/graphTransform';

type SmartSearchSubMode = 'concept' | 'neighborhood' | 'path';

export const SearchBar: React.FC = () => {
  // Top-level mode (dial): smart-search, block-builder, cypher-editor
  const [queryMode, setQueryMode] = useState<QueryMode>('smart-search');

  // Smart Search sub-mode (pills)
  const [smartSearchMode, setSmartSearchMode] = useState<SmartSearchSubMode>('concept');

  // Shared controls
  const [similarity, setSimilarity] = useState(0.5); // 50% default

  // Concept mode state
  const [conceptQuery, setConceptQuery] = useState('');
  const [debouncedConceptQuery, setDebouncedConceptQuery] = useState('');
  const [selectedConcept, setSelectedConcept] = useState<any>(null);
  const [isLoadingConcept, setIsLoadingConcept] = useState(false);

  // Neighborhood mode state
  const [neighborhoodQuery, setNeighborhoodQuery] = useState('');
  const [debouncedNeighborhoodQuery, setDebouncedNeighborhoodQuery] = useState('');
  const [selectedCenterConcept, setSelectedCenterConcept] = useState<any>(null);
  const [neighborhoodDepth, setNeighborhoodDepth] = useState(2);
  const [isLoadingNeighborhood, setIsLoadingNeighborhood] = useState(false);

  // Path mode state
  const [pathFromQuery, setPathFromQuery] = useState('');
  const [pathToQuery, setPathToQuery] = useState('');
  const [debouncedPathFromQuery, setDebouncedPathFromQuery] = useState('');
  const [debouncedPathToQuery, setDebouncedPathToQuery] = useState('');
  const [selectedFromConcept, setSelectedFromConcept] = useState<any>(null);
  const [selectedToConcept, setSelectedToConcept] = useState<any>(null);
  const [maxHops, setMaxHops] = useState(5);
  const [pathResults, setPathResults] = useState<any>(null);
  const [isLoadingPath, setIsLoadingPath] = useState(false);

  const { setFocusedNodeId, setGraphData, graphData } = useGraphStore();

  // Concept search results (only when no concept selected)
  const { data: conceptResults, isLoading: isLoadingConcepts } = useSearchConcepts(
    debouncedConceptQuery,
    {
      limit: 10,
      minSimilarity: similarity,
      enabled: smartSearchMode === 'concept' && !selectedConcept,
    }
  );

  // Neighborhood center search results (only when no center selected)
  const { data: neighborhoodSearchResults, isLoading: isLoadingNeighborhoodSearch } = useSearchConcepts(
    debouncedNeighborhoodQuery,
    {
      limit: 10,
      minSimilarity: similarity,
      enabled: smartSearchMode === 'neighborhood' && !selectedCenterConcept,
    }
  );

  // Path From search results (only when no from concept selected)
  const { data: pathFromSearchResults, isLoading: isLoadingPathFromSearch } = useSearchConcepts(
    debouncedPathFromQuery,
    {
      limit: 10,
      minSimilarity: similarity,
      enabled: smartSearchMode === 'path' && !selectedFromConcept,
    }
  );

  // Path To search results (only when no to concept selected)
  const { data: pathToSearchResults, isLoading: isLoadingPathToSearch } = useSearchConcepts(
    debouncedPathToQuery,
    {
      limit: 10,
      minSimilarity: similarity,
      enabled: smartSearchMode === 'path' && !selectedToConcept,
    }
  );

  // Debounce queries
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedConceptQuery(conceptQuery), 300);
    return () => clearTimeout(timer);
  }, [conceptQuery]);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedNeighborhoodQuery(neighborhoodQuery), 300);
    return () => clearTimeout(timer);
  }, [neighborhoodQuery]);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedPathFromQuery(pathFromQuery), 300);
    return () => clearTimeout(timer);
  }, [pathFromQuery]);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedPathToQuery(pathToQuery), 300);
    return () => clearTimeout(timer);
  }, [pathToQuery]);

  // Auto-search paths when both concepts are selected
  useEffect(() => {
    if (smartSearchMode === 'path' && selectedFromConcept && selectedToConcept) {
      searchPaths();
    }
  }, [selectedFromConcept, selectedToConcept, similarity, maxHops]);

  // Handler: Select concept in Concept mode
  const handleSelectConcept = (concept: any) => {
    setSelectedConcept(concept);
    setConceptQuery('');
  };

  // Handler: Select center concept in Neighborhood mode
  const handleSelectCenterConcept = (concept: any) => {
    setSelectedCenterConcept(concept);
    setNeighborhoodQuery('');
  };

  // Handler: Select From concept in Path mode
  const handleSelectFromConcept = (concept: any) => {
    setSelectedFromConcept(concept);
    setPathFromQuery('');
  };

  // Handler: Select To concept in Path mode
  const handleSelectToConcept = (concept: any) => {
    setSelectedToConcept(concept);
    setPathToQuery('');
  };

  // Helper: Merge new graph data with existing (deduplicate nodes/links)
  // Works with D3 format: {id, label, ...} and {source, target, type, ...}
  // IMPORTANT: Preserves existing node positions to prevent force explosion
  const mergeGraphData = (newData: any) => {
    if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {
      return newData;
    }

    // Create map of existing nodes with their positions
    const existingNodesMap = new Map(
      graphData.nodes.map((n: any) => [n.id, n])
    );

    const mergedNodes: any[] = [];

    // First, add all existing nodes (preserving positions)
    graphData.nodes.forEach((node: any) => {
      mergedNodes.push(node);
    });

    // Then add new nodes (they'll get positioned by force simulation)
    newData.nodes.forEach((node: any) => {
      if (!existingNodesMap.has(node.id)) {
        // New node - add it but position it near the center of existing graph
        // to avoid explosive initial forces
        const existingPositions = graphData.nodes
          .filter((n: any) => n.x !== undefined && n.y !== undefined)
          .map((n: any) => ({ x: n.x, y: n.y }));

        if (existingPositions.length > 0) {
          // Calculate centroid of existing nodes
          const centerX = existingPositions.reduce((sum, p) => sum + p.x, 0) / existingPositions.length;
          const centerY = existingPositions.reduce((sum, p) => sum + p.y, 0) / existingPositions.length;

          // Add small random offset to avoid exact overlap
          node.x = centerX + (Math.random() - 0.5) * 50;
          node.y = centerY + (Math.random() - 0.5) * 50;
        }

        mergedNodes.push(node);
      }
    });

    // Merge links (deduplicate by source -> target -> type)
    const existingLinks = graphData.links || [];
    const existingLinkKeys = new Set(
      existingLinks.map((l: any) => {
        const sourceId = typeof l.source === 'string' ? l.source : l.source.id;
        const targetId = typeof l.target === 'string' ? l.target : l.target.id;
        return `${sourceId}->${targetId}:${l.type}`;
      })
    );
    const mergedLinks = [...existingLinks];

    const newLinks = newData.links || [];
    newLinks.forEach((link: any) => {
      const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
      const targetId = typeof link.target === 'string' ? link.target : link.target.id;
      const key = `${sourceId}->${targetId}:${link.type}`;
      if (!existingLinkKeys.has(key)) {
        mergedLinks.push(link);
        existingLinkKeys.add(key);
      }
    });

    return {
      nodes: mergedNodes,
      links: mergedLinks,
    };
  };

  // Load: Concept into graph (clean or add)
  const loadConcept = async (mode: 'clean' | 'add') => {
    if (!selectedConcept) return;

    setIsLoadingConcept(true);
    try {
      const response = await apiClient.getSubgraph({
        center_concept_id: selectedConcept.concept_id,
        depth: 1, // Load immediate neighbors
      });

      // Transform API data to D3 format
      const transformedData = transformForD3(response.nodes, response.links);

      if (mode === 'clean') {
        setGraphData(transformedData);
      } else {
        setGraphData(mergeGraphData(transformedData));
      }

      setFocusedNodeId(selectedConcept.concept_id);
    } catch (error) {
      console.error('Failed to load concept:', error);
    } finally {
      setIsLoadingConcept(false);
    }
  };

  // Load: Neighborhood into graph (clean or add)
  const loadNeighborhood = async (mode: 'clean' | 'add') => {
    if (!selectedCenterConcept) return;

    setIsLoadingNeighborhood(true);
    try {
      const response = await apiClient.getSubgraph({
        center_concept_id: selectedCenterConcept.concept_id,
        depth: neighborhoodDepth,
      });

      // Transform API data to D3 format
      const transformedData = transformForD3(response.nodes, response.links);

      if (mode === 'clean') {
        setGraphData(transformedData);
      } else {
        setGraphData(mergeGraphData(transformedData));
      }

      setFocusedNodeId(selectedCenterConcept.concept_id);
    } catch (error) {
      console.error('Failed to load neighborhood:', error);
    } finally {
      setIsLoadingNeighborhood(false);
    }
  };

  // Search: Find paths between selected concepts
  const searchPaths = async () => {
    if (!selectedFromConcept || !selectedToConcept) return;

    setIsLoadingPath(true);
    try {
      const result = await apiClient.findConnectionBySearch({
        from_query: selectedFromConcept.label,
        to_query: selectedToConcept.label,
        max_hops: maxHops,
        threshold: similarity,
      });
      setPathResults(result);
    } catch (error: any) {
      console.error('Failed to find paths:', error);
      setPathResults({ error: error.response?.data?.detail || 'Failed to find paths' });
    } finally {
      setIsLoadingPath(false);
    }
  };

  // Load: Path into graph (clean or add)
  const loadPath = (mode: 'clean' | 'add') => {
    if (!pathResults || !pathResults.paths || pathResults.paths.length === 0) return;

    // Build subgraph from paths (API format)
    const allNodes = new Map();
    const allLinks: any[] = [];

    pathResults.paths.forEach((path: any) => {
      path.nodes.forEach((node: any) => {
        allNodes.set(node.id, {
          concept_id: node.id,
          label: node.label,
          ontology: 'default',
        });
      });

      // Build links from relationships
      for (let i = 0; i < path.nodes.length - 1; i++) {
        allLinks.push({
          from_id: path.nodes[i].id,
          to_id: path.nodes[i + 1].id,
          relationship_type: path.relationships[i] || 'RELATED',
        });
      }
    });

    // Transform API data to D3 format
    const transformedData = transformForD3(
      Array.from(allNodes.values()),
      allLinks
    );

    if (mode === 'clean') {
      setGraphData(transformedData);
    } else {
      setGraphData(mergeGraphData(transformedData));
    }

    if (pathResults.from_concept) {
      setFocusedNodeId(pathResults.from_concept.id);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header with Mode Dial */}
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h2 className="text-lg font-semibold">Query Builder</h2>
          <p className="text-sm text-muted-foreground">Search and explore the knowledge graph</p>
        </div>

        {/* Mode Dial */}
        <ModeDial mode={queryMode} onChange={setQueryMode} />
      </div>

      {/* Smart Search Mode */}
      {queryMode === 'smart-search' && (
        <div className="space-y-3">
          {/* Sub-mode Selector (Pill Buttons) */}
          <div className="flex gap-1 p-1 bg-muted rounded-lg">
            <button
              onClick={() => setSmartSearchMode('concept')}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                smartSearchMode === 'concept'
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <Search className="w-4 h-4" />
              Concept
            </button>
            <button
              onClick={() => setSmartSearchMode('neighborhood')}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                smartSearchMode === 'neighborhood'
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <Network className="w-4 h-4" />
              Neighborhood
            </button>
            <button
              onClick={() => setSmartSearchMode('path')}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                smartSearchMode === 'path'
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <GitBranch className="w-4 h-4" />
              Path
            </button>
          </div>

          {/* Concept Search */}
          {smartSearchMode === 'concept' && (
            <div className="space-y-3">
              {!selectedConcept ? (
                <div className="relative space-y-3">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <input
                      type="text"
                      value={conceptQuery}
                      onChange={(e) => setConceptQuery(e.target.value)}
                      placeholder="Search for a concept..."
                      className="w-full pl-10 pr-10 py-2 rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                    {isLoadingConcepts && (
                      <Loader2 className="absolute right-3 top-1/2 transform -translate-y-1/2 w-5 h-5 animate-spin text-muted-foreground" />
                    )}
                  </div>

                  {/* Similarity Slider */}
                  <div className="flex items-center gap-3 px-1">
                    <label className="text-sm text-muted-foreground whitespace-nowrap">
                      Similarity:
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={similarity * 100}
                      onChange={(e) => setSimilarity(parseInt(e.target.value) / 100)}
                      className="flex-1 h-2 bg-muted rounded-lg appearance-none cursor-pointer
                                 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
                                 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary
                                 [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4
                                 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-0"
                    />
                    <span className="text-sm font-medium min-w-[3ch] text-right">
                      {(similarity * 100).toFixed(0)}%
                    </span>
                  </div>

                  {/* Search Results */}
                  {debouncedConceptQuery && conceptResults && conceptResults.results && conceptResults.results.length > 0 && (
                    <div className="absolute top-full left-0 right-0 mt-2 bg-card border border-border rounded-lg shadow-lg max-h-80 overflow-y-auto z-50">
                      {conceptResults.results.map((result: any) => (
                        <button
                          key={result.concept_id}
                          onClick={() => handleSelectConcept(result)}
                          className="w-full text-left px-4 py-3 hover:bg-accent transition-colors border-b border-border last:border-b-0"
                        >
                          <div className="font-medium">{result.label}</div>
                          <div className="text-sm text-muted-foreground mt-1">
                            Similarity: {(result.score * 100).toFixed(0)}% • {result.evidence_count} instances
                          </div>
                        </button>
                      ))}
                    </div>
                  )}

                  {/* No Results with Smart Recommendations */}
                  {debouncedConceptQuery && conceptResults && conceptResults.results && conceptResults.results.length === 0 && (
                    <div className="absolute top-full left-0 right-0 mt-2 bg-card border border-border rounded-lg shadow-lg p-4 z-50">
                      <div className="text-center">
                        {conceptResults.below_threshold_count ? (
                          <div className="space-y-3">
                            <div className="text-muted-foreground">
                              <div className="font-medium mb-2">No results at {(similarity * 100).toFixed(0)}% similarity</div>
                              <div className="text-sm">
                                Found {conceptResults.below_threshold_count} concept{conceptResults.below_threshold_count > 1 ? 's' : ''} at lower similarity
                              </div>
                            </div>
                            {conceptResults.suggested_threshold && (
                              <button
                                onClick={() => setSimilarity(conceptResults.suggested_threshold)}
                                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-sm font-medium"
                              >
                                Try {(conceptResults.suggested_threshold * 100).toFixed(0)}% Similarity
                              </button>
                            )}
                            {conceptResults.top_match && (
                              <div className="text-left p-3 bg-muted rounded-lg">
                                <div className="text-xs text-muted-foreground mb-1">Top match:</div>
                                <div className="font-medium">{conceptResults.top_match.label}</div>
                                <div className="text-sm text-muted-foreground mt-1">
                                  {(conceptResults.top_match.score * 100).toFixed(0)}% similarity
                                </div>
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="text-muted-foreground">No results found</div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  {/* Selected Concept */}
                  <div className="p-3 bg-muted rounded-lg">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="text-xs text-muted-foreground mb-1">Selected concept:</div>
                        <div className="font-medium">{selectedConcept.label}</div>
                      </div>
                      <button
                        onClick={() => setSelectedConcept(null)}
                        className="text-sm text-muted-foreground hover:text-foreground"
                      >
                        Change
                      </button>
                    </div>
                  </div>

                  {/* Similarity Slider */}
                  <div className="flex items-center gap-3 px-1">
                    <label className="text-sm text-muted-foreground whitespace-nowrap">
                      Similarity:
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={similarity * 100}
                      onChange={(e) => setSimilarity(parseInt(e.target.value) / 100)}
                      className="flex-1 h-2 bg-muted rounded-lg appearance-none cursor-pointer
                                 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
                                 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary
                                 [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4
                                 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-0"
                    />
                    <span className="text-sm font-medium min-w-[3ch] text-right">
                      {(similarity * 100).toFixed(0)}%
                    </span>
                  </div>

                  {/* Load Buttons */}
                  <div className="flex gap-2">
                    <button
                      onClick={() => loadConcept('clean')}
                      disabled={isLoadingConcept}
                      className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      {isLoadingConcept ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        'Load into Clean Graph'
                      )}
                    </button>
                    <button
                      onClick={() => loadConcept('add')}
                      disabled={isLoadingConcept}
                      className="flex-1 px-4 py-2 bg-secondary text-secondary-foreground rounded-lg hover:bg-secondary/80 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      {isLoadingConcept ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        'Add to Existing Graph'
                      )}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Neighborhood Search */}
          {smartSearchMode === 'neighborhood' && (
            <div className="space-y-3">
              {!selectedCenterConcept ? (
                <div className="relative space-y-3">
                  <div className="relative">
                    <Network className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <input
                      type="text"
                      value={neighborhoodQuery}
                      onChange={(e) => setNeighborhoodQuery(e.target.value)}
                      placeholder="Search for center concept..."
                      className="w-full pl-10 pr-10 py-2 rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                    {isLoadingNeighborhoodSearch && (
                      <Loader2 className="absolute right-3 top-1/2 transform -translate-y-1/2 w-5 h-5 animate-spin text-muted-foreground" />
                    )}
                  </div>

                  {/* Similarity Slider */}
                  <div className="flex items-center gap-3 px-1">
                    <label className="text-sm text-muted-foreground whitespace-nowrap">
                      Similarity:
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={similarity * 100}
                      onChange={(e) => setSimilarity(parseInt(e.target.value) / 100)}
                      className="flex-1 h-2 bg-muted rounded-lg appearance-none cursor-pointer
                                 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
                                 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary
                                 [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4
                                 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-0"
                    />
                    <span className="text-sm font-medium min-w-[3ch] text-right">
                      {(similarity * 100).toFixed(0)}%
                    </span>
                  </div>

                  {/* Search Results */}
                  {debouncedNeighborhoodQuery && neighborhoodSearchResults && neighborhoodSearchResults.results && neighborhoodSearchResults.results.length > 0 && (
                    <div className="absolute top-full left-0 right-0 mt-2 bg-card border border-border rounded-lg shadow-lg max-h-80 overflow-y-auto z-50">
                      {neighborhoodSearchResults.results.map((result: any) => (
                        <button
                          key={result.concept_id}
                          onClick={() => handleSelectCenterConcept(result)}
                          className="w-full text-left px-4 py-3 hover:bg-accent transition-colors border-b border-border last:border-b-0"
                        >
                          <div className="font-medium">{result.label}</div>
                          <div className="text-sm text-muted-foreground mt-1">
                            Similarity: {(result.score * 100).toFixed(0)}% • {result.evidence_count} instances
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  {/* Selected Center Concept */}
                  <div className="p-3 bg-muted rounded-lg">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="text-xs text-muted-foreground mb-1">Center concept:</div>
                        <div className="font-medium">{selectedCenterConcept.label}</div>
                      </div>
                      <button
                        onClick={() => setSelectedCenterConcept(null)}
                        className="text-sm text-muted-foreground hover:text-foreground"
                      >
                        Change
                      </button>
                    </div>
                  </div>

                  {/* Depth Slider */}
                  <div className="flex items-center gap-3 px-1">
                    <label className="text-sm text-muted-foreground whitespace-nowrap">
                      Depth:
                    </label>
                    <input
                      type="range"
                      min="1"
                      max="5"
                      value={neighborhoodDepth}
                      onChange={(e) => setNeighborhoodDepth(parseInt(e.target.value))}
                      className="flex-1 h-2 bg-muted rounded-lg appearance-none cursor-pointer
                                 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
                                 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary
                                 [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4
                                 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-0"
                    />
                    <span className="text-sm font-medium min-w-[1ch] text-right">
                      {neighborhoodDepth}
                    </span>
                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                      hop{neighborhoodDepth > 1 ? 's' : ''}
                    </span>
                  </div>

                  {/* Load Buttons */}
                  <div className="flex gap-2">
                    <button
                      onClick={() => loadNeighborhood('clean')}
                      disabled={isLoadingNeighborhood}
                      className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      {isLoadingNeighborhood ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        'Load into Clean Graph'
                      )}
                    </button>
                    <button
                      onClick={() => loadNeighborhood('add')}
                      disabled={isLoadingNeighborhood}
                      className="flex-1 px-4 py-2 bg-secondary text-secondary-foreground rounded-lg hover:bg-secondary/80 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      {isLoadingNeighborhood ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        'Add to Existing Graph'
                      )}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Path Search */}
          {smartSearchMode === 'path' && (
            <div className="space-y-3">
              {/* Step 1: Search for From concept */}
              {!selectedFromConcept ? (
                <div className="relative space-y-3">
                  <div className="relative">
                    <GitBranch className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <input
                      type="text"
                      value={pathFromQuery}
                      onChange={(e) => setPathFromQuery(e.target.value)}
                      placeholder="Search for starting concept..."
                      className="w-full pl-10 pr-10 py-2 rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                    {isLoadingPathFromSearch && (
                      <Loader2 className="absolute right-3 top-1/2 transform -translate-y-1/2 w-5 h-5 animate-spin text-muted-foreground" />
                    )}
                  </div>

                  {/* Similarity Slider */}
                  <div className="flex items-center gap-3 px-1">
                    <label className="text-sm text-muted-foreground whitespace-nowrap">
                      Similarity:
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={similarity * 100}
                      onChange={(e) => setSimilarity(parseInt(e.target.value) / 100)}
                      className="flex-1 h-2 bg-muted rounded-lg appearance-none cursor-pointer
                                 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
                                 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary
                                 [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4
                                 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-0"
                    />
                    <span className="text-sm font-medium min-w-[3ch] text-right">
                      {(similarity * 100).toFixed(0)}%
                    </span>
                  </div>

                  {/* From Search Results */}
                  {debouncedPathFromQuery && pathFromSearchResults && pathFromSearchResults.results && pathFromSearchResults.results.length > 0 && (
                    <div className="absolute top-full left-0 right-0 mt-2 bg-card border border-border rounded-lg shadow-lg max-h-80 overflow-y-auto z-50">
                      {pathFromSearchResults.results.map((result: any) => (
                        <button
                          key={result.concept_id}
                          onClick={() => handleSelectFromConcept(result)}
                          className="w-full text-left px-4 py-3 hover:bg-accent transition-colors border-b border-border last:border-b-0"
                        >
                          <div className="font-medium">{result.label}</div>
                          <div className="text-sm text-muted-foreground mt-1">
                            Similarity: {(result.score * 100).toFixed(0)}% • {result.evidence_count} instances
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ) : !selectedToConcept ? (
                <div className="space-y-3">
                  {/* Selected From Concept */}
                  <div className="p-3 bg-muted rounded-lg">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="text-xs text-muted-foreground mb-1">From concept:</div>
                        <div className="font-medium">{selectedFromConcept.label}</div>
                      </div>
                      <button
                        onClick={() => setSelectedFromConcept(null)}
                        className="text-sm text-muted-foreground hover:text-foreground"
                      >
                        Change
                      </button>
                    </div>
                  </div>

                  {/* Step 2: Search for To concept */}
                  <div className="relative space-y-3">
                    <div className="relative">
                      <GitBranch className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-muted-foreground rotate-180" />
                      <input
                        type="text"
                        value={pathToQuery}
                        onChange={(e) => setPathToQuery(e.target.value)}
                        placeholder="Search for target concept..."
                        className="w-full pl-10 pr-10 py-2 rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-ring"
                      />
                      {isLoadingPathToSearch && (
                        <Loader2 className="absolute right-3 top-1/2 transform -translate-y-1/2 w-5 h-5 animate-spin text-muted-foreground" />
                      )}
                    </div>

                    {/* To Search Results */}
                    {debouncedPathToQuery && pathToSearchResults && pathToSearchResults.results && pathToSearchResults.results.length > 0 && (
                      <div className="absolute top-full left-0 right-0 mt-2 bg-card border border-border rounded-lg shadow-lg max-h-80 overflow-y-auto z-50">
                        {pathToSearchResults.results.map((result: any) => (
                          <button
                            key={result.concept_id}
                            onClick={() => handleSelectToConcept(result)}
                            className="w-full text-left px-4 py-3 hover:bg-accent transition-colors border-b border-border last:border-b-0"
                          >
                            <div className="font-medium">{result.label}</div>
                            <div className="text-sm text-muted-foreground mt-1">
                              Similarity: {(result.score * 100).toFixed(0)}% • {result.evidence_count} instances
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  {/* Selected From and To Concepts */}
                  <div className="space-y-2">
                    <div className="p-3 bg-muted rounded-lg">
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="text-xs text-muted-foreground mb-1">From concept:</div>
                          <div className="font-medium">{selectedFromConcept.label}</div>
                        </div>
                        <button
                          onClick={() => {
                            setSelectedFromConcept(null);
                            setSelectedToConcept(null);
                            setPathResults(null);
                          }}
                          className="text-sm text-muted-foreground hover:text-foreground"
                        >
                          Change
                        </button>
                      </div>
                    </div>
                    <div className="p-3 bg-muted rounded-lg">
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="text-xs text-muted-foreground mb-1">To concept:</div>
                          <div className="font-medium">{selectedToConcept.label}</div>
                        </div>
                        <button
                          onClick={() => {
                            setSelectedToConcept(null);
                            setPathResults(null);
                          }}
                          className="text-sm text-muted-foreground hover:text-foreground"
                        >
                          Change
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Similarity Slider */}
                  <div className="flex items-center gap-3 px-1">
                    <label className="text-sm text-muted-foreground whitespace-nowrap">
                      Similarity:
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={similarity * 100}
                      onChange={(e) => setSimilarity(parseInt(e.target.value) / 100)}
                      className="flex-1 h-2 bg-muted rounded-lg appearance-none cursor-pointer
                                 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
                                 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary
                                 [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4
                                 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-0"
                    />
                    <span className="text-sm font-medium min-w-[3ch] text-right">
                      {(similarity * 100).toFixed(0)}%
                    </span>
                  </div>

                  {/* Max Hops Slider */}
                  <div className="flex items-center gap-3 px-1">
                    <label className="text-sm text-muted-foreground whitespace-nowrap">
                      Max Hops:
                    </label>
                    <input
                      type="range"
                      min="1"
                      max="10"
                      value={maxHops}
                      onChange={(e) => setMaxHops(parseInt(e.target.value))}
                      className="flex-1 h-2 bg-muted rounded-lg appearance-none cursor-pointer
                                 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
                                 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary
                                 [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4
                                 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-0"
                    />
                    <span className="text-sm font-medium min-w-[2ch] text-right">
                      {maxHops}
                    </span>
                  </div>

                  {/* Path Results */}
                  {isLoadingPath && (
                    <div className="p-4 bg-muted rounded-lg flex items-center justify-center gap-2">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span className="text-sm text-muted-foreground">Searching for paths...</span>
                    </div>
                  )}

                  {pathResults && (
                    <div className="p-4 bg-muted rounded-lg space-y-3">
                      {pathResults.error ? (
                        <div className="text-center text-destructive text-sm">{pathResults.error}</div>
                      ) : pathResults.count > 0 ? (
                        <>
                          <div className="text-sm text-muted-foreground">
                            Found {pathResults.count} path{pathResults.count > 1 ? 's' : ''} ({pathResults.paths[0].hops} hop{pathResults.paths[0].hops > 1 ? 's' : ''})
                          </div>
                        </>
                      ) : (
                        <div className="text-center text-muted-foreground text-sm">
                          No paths found. Try lowering similarity or increasing max hops.
                        </div>
                      )}
                    </div>
                  )}

                  {/* Load Buttons (only if paths found) */}
                  {pathResults && pathResults.count > 0 && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => loadPath('clean')}
                        disabled={isLoadingPath}
                        className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                      >
                        Load into Clean Graph
                      </button>
                      <button
                        onClick={() => loadPath('add')}
                        disabled={isLoadingPath}
                        className="flex-1 px-4 py-2 bg-secondary text-secondary-foreground rounded-lg hover:bg-secondary/80 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                      >
                        Add to Existing Graph
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Block Builder Mode (Future - ADR-036 Phase 4) */}
      {queryMode === 'block-builder' && (
        <div className="text-center py-12 text-muted-foreground">
          <Blocks className="w-16 h-16 mx-auto mb-4 opacity-30" />
          <div className="text-lg font-medium">Visual Block Builder</div>
          <div className="text-sm mt-1">Drag-and-drop query construction</div>
          <div className="text-xs mt-3 text-muted-foreground/70">Phase 4 - Coming soon</div>
        </div>
      )}

      {/* openCypher Editor Mode (Future - ADR-036 Phase 3) */}
      {queryMode === 'cypher-editor' && (
        <div className="text-center py-12 text-muted-foreground">
          <Code className="w-16 h-16 mx-auto mb-4 opacity-30" />
          <div className="text-lg font-medium">openCypher Editor</div>
          <div className="text-sm mt-1">Raw graph query editing with syntax support</div>
          <div className="text-xs mt-3 text-muted-foreground/70">Phase 3 - Coming soon</div>
        </div>
      )}
    </div>
  );
};
