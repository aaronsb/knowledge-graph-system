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

import React, { useState } from 'react';
import { Search, Loader2, Network, GitBranch, Blocks, Code, ChevronDown, ChevronRight } from 'lucide-react';
import { useSearchConcepts } from '../../hooks/useGraphData';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useGraphStore } from '../../store/graphStore';
import { ModeDial } from './ModeDial';
import { apiClient } from '../../api/client';
import { BlockBuilder } from '../blocks/BlockBuilder';
import { SearchResultsDropdown } from './SearchResultsDropdown';

type SmartSearchSubMode = 'concept' | 'neighborhood' | 'path';

export const SearchBar: React.FC = () => {
  // Top-level mode (dial): smart-search, block-builder, cypher-editor - use store
  const { queryMode, setQueryMode, blockBuilderExpanded, setBlockBuilderExpanded } = useGraphStore();

  // Smart Search sub-mode (pills)
  const [smartSearchMode, setSmartSearchMode] = useState<SmartSearchSubMode>('concept');

  // Collapsible sections state
  const [expandedSections, setExpandedSections] = useState<Record<SmartSearchSubMode, boolean>>({
    concept: true,
    neighborhood: true,
    path: true,
  });

  // Collapsible state for openCypher editor
  const [cypherEditorExpanded, setCypherEditorExpanded] = useState(true);

  const toggleSection = (mode: SmartSearchSubMode) => {
    setExpandedSections(prev => ({
      ...prev,
      [mode]: !prev[mode],
    }));

    // Trigger window resize event after a short delay to let the DOM update
    setTimeout(() => {
      window.dispatchEvent(new Event('resize'));
    }, 100);
  };

  const toggleCypherEditor = () => {
    setCypherEditorExpanded(!cypherEditorExpanded);

    // Trigger window resize event after a short delay to let the DOM update
    setTimeout(() => {
      window.dispatchEvent(new Event('resize'));
    }, 100);
  };

  const toggleBlockBuilder = () => {
    setBlockBuilderExpanded(!blockBuilderExpanded);

    // Trigger window resize event after a short delay to let the DOM update
    setTimeout(() => {
      window.dispatchEvent(new Event('resize'));
    }, 100);
  };

  // Shared controls - use global similarity threshold from store
  const { similarityThreshold: similarity, setSimilarityThreshold: setSimilarity } = useGraphStore();

  // Concept mode state
  const [conceptQuery, setConceptQuery] = useState('');
  const [selectedConcept, setSelectedConcept] = useState<any>(null);

  // Neighborhood mode state
  const [neighborhoodQuery, setNeighborhoodQuery] = useState('');
  const [selectedCenterConcept, setSelectedCenterConcept] = useState<any>(null);
  const [neighborhoodDepth, setNeighborhoodDepth] = useState(2);

  // Path mode state
  const [pathFromQuery, setPathFromQuery] = useState('');
  const [pathToQuery, setPathToQuery] = useState('');
  const [selectedFromConcept, setSelectedFromConcept] = useState<any>(null);
  const [selectedToConcept, setSelectedToConcept] = useState<any>(null);
  const [maxHops, setMaxHops] = useState(5);
  const [pathResults, setPathResults] = useState<any>(null);
  const [selectedPath, setSelectedPath] = useState<any>(null);
  const [isLoadingPath, setIsLoadingPath] = useState(false);
  const [pathEnrichmentDepth, setPathEnrichmentDepth] = useState(1); // Depth around each hop

  // Cypher editor state
  const [cypherQuery, setCypherQuery] = useState(`MATCH (c:Concept)-[r]->(n:Concept)
WHERE c.label CONTAINS 'organizational'
RETURN c, r, n
LIMIT 50`);
  const [isExecutingCypher, setIsExecutingCypher] = useState(false);
  const [cypherError, setCypherError] = useState<string | null>(null);

  const { setSearchParams } = useGraphStore();

  // Debounce values to prevent excessive API calls while user is typing/dragging sliders
  // 800ms for typing (embeddings are expensive), 500ms for sliders (cheaper operations)
  const debouncedConceptQuery = useDebouncedValue(conceptQuery, 800);
  const debouncedNeighborhoodQuery = useDebouncedValue(neighborhoodQuery, 800);
  const debouncedPathFromQuery = useDebouncedValue(pathFromQuery, 800);
  const debouncedPathToQuery = useDebouncedValue(pathToQuery, 800);
  const debouncedSimilarity = useDebouncedValue(similarity, 500);

  // Concept search results (only when no concept selected)
  // Uses debounced similarity to prevent search spam while dragging slider
  const { data: conceptResults, isLoading: isLoadingConcepts } = useSearchConcepts(
    debouncedConceptQuery,
    {
      limit: 10,
      minSimilarity: debouncedSimilarity,
      enabled: queryMode === 'smart-search' && smartSearchMode === 'concept' && !selectedConcept,
    }
  );

  // Neighborhood center search results (only when no center selected)
  const { data: neighborhoodSearchResults, isLoading: isLoadingNeighborhoodSearch } = useSearchConcepts(
    debouncedNeighborhoodQuery,
    {
      limit: 10,
      minSimilarity: debouncedSimilarity,
      enabled: queryMode === 'smart-search' && smartSearchMode === 'neighborhood' && !selectedCenterConcept,
    }
  );

  // Path From search results (only when no from concept selected)
  const { data: pathFromSearchResults, isLoading: isLoadingPathFromSearch } = useSearchConcepts(
    debouncedPathFromQuery,
    {
      limit: 10,
      minSimilarity: debouncedSimilarity,
      enabled: queryMode === 'smart-search' && smartSearchMode === 'path' && !selectedFromConcept,
    }
  );

  // Path To search results (only when no to concept selected)
  const { data: pathToSearchResults, isLoading: isLoadingPathToSearch } = useSearchConcepts(
    debouncedPathToQuery,
    {
      limit: 10,
      minSimilarity: debouncedSimilarity,
      enabled: queryMode === 'smart-search' && smartSearchMode === 'path' && !selectedToConcept,
    }
  );

  // Note: Path search is now manual (via button) instead of auto-search
  // This prevents the UI from appearing to hang during expensive path searches

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

  // Handler: Load concept (sets search parameters for App.tsx to react to)
  const handleLoadConcept = (loadMode: 'clean' | 'add') => {
    if (!selectedConcept) return;

    setSearchParams({
      mode: 'concept',
      conceptId: selectedConcept.concept_id,
      loadMode,
    });
  };

  // Handler: Load neighborhood (sets search parameters for App.tsx to react to)
  const handleLoadNeighborhood = (loadMode: 'clean' | 'add') => {
    if (!selectedCenterConcept) return;

    setSearchParams({
      mode: 'neighborhood',
      centerConceptId: selectedCenterConcept.concept_id,
      depth: neighborhoodDepth,
      loadMode,
    });
  };

  // Handler: Search for paths between selected concepts (stores results locally)
  const handleFindPaths = async () => {
    if (!selectedFromConcept || !selectedToConcept) return;

    setIsLoadingPath(true);
    setPathResults(null);
    setSelectedPath(null);

    try {
      const result = await apiClient.findConnection({
        from_id: selectedFromConcept.concept_id,
        to_id: selectedToConcept.concept_id,
        max_hops: maxHops,
      });
      setPathResults(result);
    } catch (error: any) {
      console.error('Failed to find paths:', error);

      let errorMessage = 'Failed to find paths';
      if (error.code === 'ECONNABORTED') {
        errorMessage = `Search timed out. Try reducing max hops.`;
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      } else if (error.message) {
        errorMessage = error.message;
      }

      setPathResults({
        error: errorMessage,
        count: 0,
        paths: []
      });
    } finally {
      setIsLoadingPath(false);
    }
  };

  // Handler: Load selected path with enriched neighborhoods
  const handleLoadPath = (loadMode: 'clean' | 'add') => {
    if (!selectedPath) return;

    setSearchParams({
      mode: 'path',
      fromConceptId: selectedFromConcept.concept_id,
      toConceptId: selectedToConcept.concept_id,
      maxHops,
      depth: pathEnrichmentDepth, // Add neighborhood context around each hop
      loadMode,
    });
  };

  // Handler: Execute openCypher query
  const handleExecuteCypher = async () => {
    if (!cypherQuery.trim()) return;

    setIsExecutingCypher(true);
    setCypherError(null);

    try {
      const result = await apiClient.executeCypherQuery({
        query: cypherQuery,
        limit: 100, // Default limit for safety
      });

      // Transform result to graph format and load
      const { transformForD3 } = await import('../../utils/graphTransform');

      // Convert CypherNode to our node format
      const nodes = result.nodes.map((n: any) => ({
        concept_id: n.id,
        label: n.label,
        ontology: n.properties?.ontology || 'default',
      }));

      // Convert CypherRelationship to our link format
      const links = result.relationships.map((r: any) => ({
        from_id: r.from_id,
        to_id: r.to_id,
        relationship_type: r.type,
      }));

      const graphData = transformForD3(nodes, links);
      useGraphStore.getState().setGraphData(graphData);

    } catch (error: any) {
      console.error('Failed to execute Cypher query:', error);
      setCypherError(error.response?.data?.detail || error.message || 'Query execution failed');
    } finally {
      setIsExecutingCypher(false);
    }
  };

  // Handler: Send compiled blocks to openCypher editor
  const handleSendToEditor = (compiledCypher: string) => {
    // Check if there's existing code in the editor
    const hasExistingCode = cypherQuery.trim().length > 0;

    if (hasExistingCode) {
      const confirmed = window.confirm(
        'The openCypher editor already has code. Do you want to overwrite it with the compiled query from the block builder?'
      );

      if (!confirmed) {
        return; // User cancelled
      }
    }

    // Load the compiled query into the editor
    setCypherQuery(compiledCypher);

    // Switch to cypher-editor mode
    setQueryMode('cypher-editor');
  };

  // Get mode-specific info for the header
  const getModeInfo = () => {
    switch (queryMode) {
      case 'smart-search':
        return {
          icon: Search,
          title: 'Smart Search',
          description: 'Find concepts using semantic similarity, explore neighborhoods, and discover paths between ideas',
        };
      case 'block-builder':
        return {
          icon: Blocks,
          title: 'Visual Block Builder',
          description: 'Drag-and-drop query construction with visual blocks that compile to openCypher',
        };
      case 'cypher-editor':
        return {
          icon: Code,
          title: 'openCypher Editor',
          description: 'Write raw graph queries using Apache AGE openCypher syntax for advanced exploration',
        };
    }
  };

  const modeInfo = getModeInfo();
  const ModeIcon = modeInfo.icon;

  return (
    <div className="space-y-4">
      {/* Header with Mode Info and Dial */}
      <div className="flex items-start justify-between gap-4">
        {/* Mode Description Panel */}
        <div className="flex gap-3 flex-1">
          <div className="flex-shrink-0">
            <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
              <ModeIcon className="w-6 h-6 text-primary" />
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-lg font-semibold">{modeInfo.title}</h2>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {modeInfo.description}
            </p>
          </div>
        </div>

        {/* Mode Dial and Collapse Button */}
        <div className="flex items-center gap-2">
          {queryMode === 'block-builder' && (
            <button
              onClick={toggleBlockBuilder}
              className="p-2 hover:bg-muted rounded transition-colors"
              title={blockBuilderExpanded ? "Collapse block builder" : "Expand block builder"}
            >
              {blockBuilderExpanded ? (
                <ChevronDown className="w-5 h-5" />
              ) : (
                <ChevronRight className="w-5 h-5" />
              )}
            </button>
          )}
          <ModeDial mode={queryMode} onChange={setQueryMode} />
        </div>
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
              {/* Collapsible Header */}
              <button
                onClick={() => toggleSection('concept')}
                className="w-full flex items-center justify-between p-2 rounded-lg hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Search className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Search for Concept</span>
                </div>
                {expandedSections.concept ? (
                  <ChevronDown className="w-4 h-4 text-muted-foreground" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-muted-foreground" />
                )}
              </button>

              {expandedSections.concept && (
                <>
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
                    <SearchResultsDropdown
                      results={conceptResults.results}
                      onSelect={handleSelectConcept}
                    />
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
                      onClick={() => handleLoadConcept('clean')}
                      className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-sm font-medium"
                    >
                      Load into Clean Graph
                    </button>
                    <button
                      onClick={() => handleLoadConcept('add')}
                      className="flex-1 px-4 py-2 bg-secondary text-secondary-foreground rounded-lg hover:bg-secondary/80 transition-colors text-sm font-medium"
                    >
                      Add to Existing Graph
                    </button>
                  </div>
                </div>
              )}
                </>
              )}
            </div>
          )}

          {/* Neighborhood Search */}
          {smartSearchMode === 'neighborhood' && (
            <div className="space-y-3">
              {/* Collapsible Header */}
              <button
                onClick={() => toggleSection('neighborhood')}
                className="w-full flex items-center justify-between p-2 rounded-lg hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Network className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Explore Neighborhood</span>
                </div>
                {expandedSections.neighborhood ? (
                  <ChevronDown className="w-4 h-4 text-muted-foreground" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-muted-foreground" />
                )}
              </button>

              {expandedSections.neighborhood && (
                <>
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
                    <SearchResultsDropdown
                      results={neighborhoodSearchResults.results}
                      onSelect={handleSelectCenterConcept}
                    />
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
                      onClick={() => handleLoadNeighborhood('clean')}
                      className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-sm font-medium"
                    >
                      Load into Clean Graph
                    </button>
                    <button
                      onClick={() => handleLoadNeighborhood('add')}
                      className="flex-1 px-4 py-2 bg-secondary text-secondary-foreground rounded-lg hover:bg-secondary/80 transition-colors text-sm font-medium"
                    >
                      Add to Existing Graph
                    </button>
                  </div>
                </div>
              )}
                </>
              )}
            </div>
          )}

          {/* Path Search */}
          {smartSearchMode === 'path' && (
            <div className="space-y-3">
              {/* Collapsible Header */}
              <button
                onClick={() => toggleSection('path')}
                className="w-full flex items-center justify-between p-2 rounded-lg hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <GitBranch className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Find Paths Between Concepts</span>
                </div>
                {expandedSections.path ? (
                  <ChevronDown className="w-4 h-4 text-muted-foreground" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-muted-foreground" />
                )}
              </button>

              {expandedSections.path && (
                <>
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
                    <SearchResultsDropdown
                      results={pathFromSearchResults.results}
                      onSelect={handleSelectFromConcept}
                    />
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
                      <SearchResultsDropdown
                        results={pathToSearchResults.results}
                        onSelect={handleSelectToConcept}
                      />
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
                          onClick={() => setSelectedToConcept(null)}
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

                  {/* Find Paths Button */}
                  <button
                    onClick={handleFindPaths}
                    disabled={isLoadingPath}
                    className="w-full px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    {isLoadingPath ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Searching...
                      </>
                    ) : (
                      'Find Paths'
                    )}
                  </button>

                  {/* Path Results */}
                  {pathResults && !isLoadingPath && (
                    <div className="space-y-3">
                      {pathResults.error ? (
                        <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-lg text-center text-destructive text-sm">
                          {pathResults.error}
                        </div>
                      ) : pathResults.count > 0 ? (
                        <>
                          <div className="text-sm text-muted-foreground">
                            Found {pathResults.count} path{pathResults.count > 1 ? 's' : ''} ({pathResults.paths[0].hops} hop{pathResults.paths[0].hops > 1 ? 's' : ''})
                          </div>

                          {/* Path Selection */}
                          <div className="space-y-2">
                            <div className="text-xs text-muted-foreground uppercase tracking-wide">Select a path:</div>
                            {pathResults.paths.map((path: any, index: number) => (
                              <button
                                key={index}
                                onClick={() => setSelectedPath(path)}
                                className={`w-full text-left p-3 rounded-lg border transition-colors ${
                                  selectedPath === path
                                    ? 'border-primary bg-primary/10'
                                    : 'border-border bg-muted hover:border-primary/50'
                                }`}
                              >
                                <div className="text-sm font-mono">
                                  {path.nodes.map((node: any, i: number) => (
                                    <span key={i}>
                                      {i > 0 && <span className="text-muted-foreground"> → </span>}
                                      <span className="font-medium">{node.label}</span>
                                    </span>
                                  ))}
                                </div>
                                {path.score && (
                                  <div className="text-xs text-muted-foreground mt-1">
                                    Score: {(path.score * 100).toFixed(1)}%
                                  </div>
                                )}
                              </button>
                            ))}
                          </div>

                          {/* Enrichment Depth Slider (only if path selected) */}
                          {selectedPath && (
                            <>
                              <div className="flex items-center gap-3 px-1">
                                <label className="text-sm text-muted-foreground whitespace-nowrap">
                                  Context Depth:
                                </label>
                                <input
                                  type="range"
                                  min="0"
                                  max="3"
                                  value={pathEnrichmentDepth}
                                  onChange={(e) => setPathEnrichmentDepth(parseInt(e.target.value))}
                                  className="flex-1 h-2 bg-muted rounded-lg appearance-none cursor-pointer
                                             [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
                                             [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary
                                             [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4
                                             [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-0"
                                />
                                <span className="text-sm font-medium min-w-[1ch] text-right">
                                  {pathEnrichmentDepth}
                                </span>
                              </div>
                              <div className="text-xs text-muted-foreground px-1">
                                {pathEnrichmentDepth === 0
                                  ? 'Show path only (no context)'
                                  : `Show ${pathEnrichmentDepth}-hop neighborhood around each node in path`}
                              </div>

                              {/* Load Buttons */}
                              <div className="flex gap-2">
                                <button
                                  onClick={() => handleLoadPath('clean')}
                                  className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-sm font-medium"
                                >
                                  Load into Clean Graph
                                </button>
                                <button
                                  onClick={() => handleLoadPath('add')}
                                  className="flex-1 px-4 py-2 bg-secondary text-secondary-foreground rounded-lg hover:bg-secondary/80 transition-colors text-sm font-medium"
                                >
                                  Add to Existing Graph
                                </button>
                              </div>
                            </>
                          )}
                        </>
                      ) : (
                        <div className="p-4 bg-muted rounded-lg text-center text-muted-foreground text-sm">
                          No paths found. Try lowering similarity or increasing max hops.
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
                </>
              )}
            </div>
          )}
        </div>
      )}

      {/* Block Builder Mode */}
      {queryMode === 'block-builder' && blockBuilderExpanded && (
        <div className="flex-1 min-h-0">
          <BlockBuilder onSendToEditor={handleSendToEditor} />
        </div>
      )}

      {/* openCypher Editor Mode */}
      {queryMode === 'cypher-editor' && (
        <div className="space-y-3">
          {/* Collapsible Header */}
          <button
            onClick={toggleCypherEditor}
            className="w-full flex items-center justify-between p-2 rounded-lg hover:bg-muted/50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Code className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm font-medium">Query Editor</span>
            </div>
            {cypherEditorExpanded ? (
              <ChevronDown className="w-4 h-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="w-4 h-4 text-muted-foreground" />
            )}
          </button>

          {cypherEditorExpanded && (
            <>
              {/* Query Editor (Textarea for now, can upgrade to Monaco later) */}
              <div className="space-y-2">
            <textarea
              value={cypherQuery}
              onChange={(e) => setCypherQuery(e.target.value)}
              placeholder="Enter openCypher query..."
              className="w-full h-48 px-3 py-2 font-mono text-sm rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-ring resize-y"
              spellCheck={false}
            />

            {/* Error Display */}
            {cypherError && (
              <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-lg text-sm text-destructive">
                {cypherError}
              </div>
            )}

            {/* Execute Button */}
            <button
              onClick={handleExecuteCypher}
              disabled={isExecutingCypher || !cypherQuery.trim()}
              className="w-full px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isExecutingCypher ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Executing Query...
                </>
              ) : (
                <>
                  <Code className="w-4 h-4" />
                  Execute Query
                </>
              )}
            </button>

            {/* Help Text */}
            <div className="text-xs text-muted-foreground space-y-1">
              <div className="font-medium">Example queries:</div>
              <div className="font-mono bg-muted p-2 rounded">
                <div>MATCH (c:Concept) WHERE c.label CONTAINS 'organizational' RETURN c LIMIT 10</div>
                <div className="mt-1">{'MATCH (c:Concept)-[r:IMPLIES]->(n:Concept) RETURN c, r, n LIMIT 50'}</div>
              </div>
              <div className="text-muted-foreground/70 mt-2">
                Results are automatically loaded into the graph visualization.
              </div>
            </div>
          </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};
