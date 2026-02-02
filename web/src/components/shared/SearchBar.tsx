/**
 * Multi-Mode Search Component
 *
 * Top-level: Query mode selection via radio dial
 * - Smart Search (unified progressive interface)
 * - Block Builder
 * - openCypher Editor
 *
 * Smart Search is a single progressive flow:
 * 1. Search for a concept → select it
 * 2. Depth slider appears (1 = immediate, >1 = neighborhood)
 * 3. Optional: add destination concept for path finding
 * 4. Path mode: max hops + find paths + select + load
 */

import React, { useState, useEffect } from 'react';
import { Search, GitBranch, Blocks, Code, ChevronDown, ChevronRight, Plus, X } from 'lucide-react';
import { LoadingSpinner } from './LoadingSpinner';
import { useSearchConcepts } from '../../hooks/useGraphData';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useGraphStore } from '../../store/graphStore';
import { ModeDial } from './ModeDial';
import { apiClient } from '../../api/client';
import { BlockBuilder } from '../blocks/BlockBuilder';
import {
  ConceptSearchInput,
  SelectedConceptChip,
  SliderControl,
  LoadButtons,
  PathResults,
} from './search';

export const SearchBar: React.FC = () => {
  // Top-level mode (dial)
  const { queryMode, setQueryMode, blockBuilderExpanded, setBlockBuilderExpanded } = useGraphStore();

  // Collapsible state
  const [smartSearchExpanded, setSmartSearchExpanded] = useState(true);
  const [cypherEditorExpanded, setCypherEditorExpanded] = useState(true);

  const triggerResize = () => setTimeout(() => window.dispatchEvent(new Event('resize')), 100);

  // Shared controls from store
  const {
    similarityThreshold: similarity,
    setSimilarityThreshold: setSimilarity,
    searchParams,
    setSearchParams,
    setRawGraphData,
    mergeRawGraphData,
    setGraphData,
  } = useGraphStore();

  // === UNIFIED SEARCH STATE ===
  // Primary concept (the starting point for any search)
  const [primaryQuery, setPrimaryQuery] = useState('');
  const [selectedPrimary, setSelectedPrimary] = useState<any>(null);
  const [depth, setDepth] = useState(1);

  // Destination concept (optional — triggers path mode)
  const [destinationQuery, setDestinationQuery] = useState('');
  const [selectedDestination, setSelectedDestination] = useState<any>(null);
  const [showDestination, setShowDestination] = useState(false);
  const [maxHops, setMaxHops] = useState(5);

  // Path search state
  const [pathResults, setPathResults] = useState<any>(null);
  const [selectedPath, setSelectedPath] = useState<any>(null);
  const [isLoadingPath, setIsLoadingPath] = useState(false);

  // Cypher editor state
  const [cypherQuery, setCypherQuery] = useState(`MATCH (c:Concept)-[r]->(n:Concept)
WHERE c.label CONTAINS 'organizational'
RETURN c, r, n
LIMIT 50`);
  const [isExecutingCypher, setIsExecutingCypher] = useState(false);
  const [cypherError, setCypherError] = useState<string | null>(null);

  // Debounce values
  const debouncedPrimaryQuery = useDebouncedValue(primaryQuery, 800);
  const debouncedDestinationQuery = useDebouncedValue(destinationQuery, 800);
  const debouncedSimilarity = useDebouncedValue(similarity, 500);

  // Search hooks
  const { data: primaryResults, isLoading: isLoadingPrimary } = useSearchConcepts(
    debouncedPrimaryQuery,
    {
      limit: 10,
      minSimilarity: debouncedSimilarity,
      enabled: queryMode === 'smart-search' && !selectedPrimary,
    }
  );

  const { data: destinationResults, isLoading: isLoadingDestination } = useSearchConcepts(
    debouncedDestinationQuery,
    {
      limit: 10,
      minSimilarity: debouncedSimilarity,
      enabled: queryMode === 'smart-search' && showDestination && !selectedDestination,
    }
  );

  // Sync from store → local state when Follow Concept updates searchParams externally
  useEffect(() => {
    if (searchParams.primaryConceptId && searchParams.primaryConceptLabel) {
      // External update (e.g., node click) — sync to local state
      if (!selectedPrimary || selectedPrimary.concept_id !== searchParams.primaryConceptId) {
        setSelectedPrimary({
          concept_id: searchParams.primaryConceptId,
          label: searchParams.primaryConceptLabel,
        });
        setPrimaryQuery('');
        setDepth(searchParams.depth);
      }
    }
  }, [searchParams.primaryConceptId, searchParams.primaryConceptLabel]);

  // === HANDLERS ===

  const handleSelectPrimary = (concept: any) => {
    setSelectedPrimary(concept);
    setPrimaryQuery('');
  };

  const handleClearPrimary = () => {
    setSelectedPrimary(null);
    setSelectedDestination(null);
    setShowDestination(false);
    setPathResults(null);
    setSelectedPath(null);
    setDepth(1);
  };

  const handleSelectDestination = (concept: any) => {
    setSelectedDestination(concept);
    setDestinationQuery('');
  };

  const handleClearDestination = () => {
    setSelectedDestination(null);
    setPathResults(null);
    setSelectedPath(null);
  };

  const handleRemoveDestination = () => {
    setShowDestination(false);
    setSelectedDestination(null);
    setDestinationQuery('');
    setPathResults(null);
    setSelectedPath(null);
    setDepth(1); // Reset to explore default
  };

  // Load explore (concept or neighborhood depending on depth)
  const handleLoadExplore = (loadMode: 'clean' | 'add') => {
    if (!selectedPrimary) return;
    setSearchParams({
      primaryConceptId: selectedPrimary.concept_id,
      primaryConceptLabel: selectedPrimary.label,
      depth,
      maxHops: 5,
      loadMode,
    });
  };

  // Path search (manual)
  const handleFindPaths = async () => {
    if (!selectedPrimary || !selectedDestination) return;

    setIsLoadingPath(true);
    setPathResults(null);
    setSelectedPath(null);

    try {
      const result = await apiClient.findConnection({
        from_id: selectedPrimary.concept_id,
        to_id: selectedDestination.concept_id,
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

      setPathResults({ error: errorMessage, count: 0, paths: [] });
    } finally {
      setIsLoadingPath(false);
    }
  };

  // Load selected path directly into graph, with optional neighborhood enrichment
  const handleLoadPath = async (loadMode: 'clean' | 'add') => {
    if (!selectedPath) return;

    const conceptNodes: any[] = [];
    const conceptRelTypes: string[][] = [];
    let pendingRels: string[] = [];

    for (let i = 0; i < selectedPath.nodes.length; i++) {
      const node = selectedPath.nodes[i];
      if (node.id && node.id !== '') {
        conceptNodes.push(node);
        conceptRelTypes.push(pendingRels);
        pendingRels = [];
      }
      if (i < selectedPath.relationships.length) {
        pendingRels.push(selectedPath.relationships[i]);
      }
    }

    const nodes = conceptNodes.map((node: any) => ({
      concept_id: node.id,
      label: node.label,
      description: node.description,
      ontology: 'default',
      grounding_strength: node.grounding_strength,
    }));

    const links: any[] = [];
    for (let i = 0; i < conceptNodes.length - 1; i++) {
      const rels = conceptRelTypes[i + 1];
      const relType = rels.find(r => r !== 'APPEARS' && r !== 'SCOPED_BY') || rels[0] || 'CONNECTED';
      links.push({
        from_id: conceptNodes[i].id,
        to_id: conceptNodes[i + 1].id,
        relationship_type: relType,
      });
    }

    if (loadMode === 'clean') {
      setGraphData(null);
      setRawGraphData({ nodes, links });
    } else {
      mergeRawGraphData({ nodes, links });
    }

    // Enrich path nodes with neighborhood context
    if (depth > 0 && conceptNodes.length <= 50) {
      const enrichDepth = Math.min(depth, 2);
      const idsToEnrich = conceptNodes.map((n) => n.id).filter(Boolean);
      if (idsToEnrich.length > 0) {
        try {
          const enrichments = await Promise.all(
            idsToEnrich.map((id: string) =>
              apiClient.getSubgraph({ center_concept_id: id, depth: enrichDepth })
            )
          );
          for (const data of enrichments) {
            mergeRawGraphData({ nodes: data.nodes, links: data.links });
          }
        } catch (error) {
          console.error('Path enrichment failed:', error);
        }
      }
    }

    setPathResults(null);
    setSelectedPath(null);
  };

  // Cypher execution
  const handleExecuteCypher = async () => {
    if (!cypherQuery.trim()) return;

    setIsExecutingCypher(true);
    setCypherError(null);

    try {
      const result = await apiClient.executeCypherQuery({
        query: cypherQuery,
        limit: 100,
      });

      const { transformForD3 } = await import('../../utils/graphTransform');
      const graphNodes = result.nodes.map((n: any) => ({
        concept_id: n.id,
        label: n.label,
        ontology: n.properties?.ontology || 'default',
      }));
      const graphLinks = result.relationships.map((r: any) => ({
        from_id: r.from_id,
        to_id: r.to_id,
        relationship_type: r.type,
      }));

      const graphData = transformForD3(graphNodes, graphLinks);
      useGraphStore.getState().setGraphData(graphData);
    } catch (error: any) {
      console.error('Failed to execute Cypher query:', error);
      setCypherError(error.response?.data?.detail || error.message || 'Query execution failed');
    } finally {
      setIsExecutingCypher(false);
    }
  };

  // Block builder → Cypher editor
  const handleSendToEditor = (compiledCypher: string) => {
    if (cypherQuery.trim().length > 0) {
      const confirmed = window.confirm(
        'The openCypher editor already has code. Do you want to overwrite it?'
      );
      if (!confirmed) return;
    }
    setCypherQuery(compiledCypher);
    setQueryMode('cypher-editor');
  };

  // Mode info for header
  const getModeInfo = () => {
    switch (queryMode) {
      case 'smart-search':
        return {
          icon: Search,
          title: 'Smart Search',
          description: 'Find concepts, explore neighborhoods, and discover paths between ideas',
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

  // No-results content with below-threshold suggestions
  const noResultsContent = primaryResults && primaryResults.results && primaryResults.results.length === 0 && (
    <div className="absolute top-full left-0 right-0 mt-2 bg-card border border-border rounded-lg shadow-lg p-4 z-50">
      <div className="text-center">
        {primaryResults.below_threshold_count ? (
          <div className="space-y-3">
            <div className="text-muted-foreground">
              <div className="font-medium mb-2">No results at {(similarity * 100).toFixed(0)}% similarity</div>
              <div className="text-sm">
                Found {primaryResults.below_threshold_count} concept{primaryResults.below_threshold_count > 1 ? 's' : ''} at lower similarity
              </div>
            </div>
            {primaryResults.suggested_threshold && (
              <button
                onClick={() => setSimilarity(primaryResults.suggested_threshold)}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-sm font-medium"
              >
                Try {(primaryResults.suggested_threshold * 100).toFixed(0)}% Similarity
              </button>
            )}
            {primaryResults.top_match && (
              <div className="text-left p-3 bg-muted rounded-lg">
                <div className="text-xs text-muted-foreground mb-1">Top match:</div>
                <div className="font-medium">{primaryResults.top_match.label}</div>
                <div className="text-sm text-muted-foreground mt-1">
                  {(primaryResults.top_match.score * 100).toFixed(0)}% similarity
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="text-muted-foreground">No results found</div>
        )}
      </div>
    </div>
  );

  // Reusable similarity slider
  const similaritySlider = (
    <SliderControl
      label="Similarity:"
      value={Math.round(similarity * 100)}
      min={0}
      max={100}
      onChange={(v) => setSimilarity(v / 100)}
      displayValue={`${(similarity * 100).toFixed(0)}%`}
    />
  );

  return (
    <div className="relative space-y-4">
      {/* Header with Mode Info and Dial */}
      <div className="flex items-start justify-between gap-4">
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
        <ModeDial mode={queryMode} onChange={setQueryMode} />
      </div>

      {/* ===== SMART SEARCH (Unified Progressive) ===== */}
      {queryMode === 'smart-search' && (
        <div className="space-y-3">
          <button
            onClick={() => { setSmartSearchExpanded(!smartSearchExpanded); triggerResize(); }}
            className="w-full flex items-center justify-between p-2 rounded-lg hover:bg-muted/50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Search className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm font-medium">Smart Search</span>
            </div>
            {smartSearchExpanded ? (
              <ChevronDown className="w-4 h-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="w-4 h-4 text-muted-foreground" />
            )}
          </button>

          {smartSearchExpanded && (
            <div className="space-y-3">
              {/* Stage 1: Search for primary concept */}
              {!selectedPrimary ? (
                <div className="space-y-3">
                  <ConceptSearchInput
                    query={primaryQuery}
                    onQueryChange={setPrimaryQuery}
                    placeholder="Search for a concept..."
                    icon={Search}
                    isLoading={isLoadingPrimary}
                    results={primaryResults?.results}
                    debouncedQuery={debouncedPrimaryQuery}
                    onSelect={handleSelectPrimary}
                    noResultsContent={noResultsContent}
                  />
                  {similaritySlider}
                </div>
              ) : (
                /* Stage 2+: Primary selected — show controls */
                <div className="space-y-3">
                  <SelectedConceptChip
                    label="Concept:"
                    conceptLabel={selectedPrimary.label}
                    onClear={handleClearPrimary}
                  />

                  {similaritySlider}

                  <SliderControl
                    label={showDestination ? "Context:" : "Depth:"}
                    value={depth}
                    min={showDestination ? 0 : 1}
                    max={showDestination ? 2 : 5}
                    onChange={setDepth}
                    unit={showDestination && depth === 0 ? 'none' : `hop${depth !== 1 ? 's' : ''}`}
                  />

                  {/* Load buttons (explore mode — no destination) */}
                  {!showDestination && (
                    <LoadButtons
                      onLoadClean={() => handleLoadExplore('clean')}
                      onLoadAdd={() => handleLoadExplore('add')}
                    />
                  )}

                  {/* Destination toggle / search */}
                  {!showDestination ? (
                    <button
                      onClick={() => { setShowDestination(true); setDepth(0); }}
                      className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground border border-dashed border-border rounded-lg hover:border-primary/50 transition-colors"
                    >
                      <Plus className="w-4 h-4" />
                      Find path to another concept
                    </button>
                  ) : (
                    <div className="space-y-3 pt-2 border-t border-border">
                      {/* Destination header with close button */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <GitBranch className="w-4 h-4" />
                          <span className="font-medium">Path Destination</span>
                        </div>
                        <button
                          onClick={handleRemoveDestination}
                          className="text-muted-foreground hover:text-foreground p-1"
                          title="Remove destination"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>

                      {!selectedDestination ? (
                        /* Search for destination */
                        <ConceptSearchInput
                          query={destinationQuery}
                          onQueryChange={setDestinationQuery}
                          placeholder="Search for destination concept..."
                          icon={GitBranch}
                          isLoading={isLoadingDestination}
                          results={destinationResults?.results}
                          debouncedQuery={debouncedDestinationQuery}
                          onSelect={handleSelectDestination}
                        />
                      ) : (
                        /* Both selected — path controls */
                        <div className="space-y-3">
                          <SelectedConceptChip
                            label="Destination:"
                            conceptLabel={selectedDestination.label}
                            onClear={handleClearDestination}
                          />

                          <SliderControl
                            label="Max Hops:"
                            value={maxHops}
                            min={1}
                            max={10}
                            onChange={setMaxHops}
                          />

                          <button
                            onClick={handleFindPaths}
                            disabled={isLoadingPath}
                            className="w-full px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                          >
                            {isLoadingPath ? (
                              <>
                                <LoadingSpinner className="text-primary-foreground" />
                                Searching...
                              </>
                            ) : (
                              'Find Paths'
                            )}
                          </button>

                          <PathResults
                            pathResults={pathResults}
                            selectedPath={selectedPath}
                            isLoading={false}
                            onSelectPath={setSelectedPath}
                            onLoadClean={() => handleLoadPath('clean')}
                            onLoadAdd={() => handleLoadPath('add')}
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Block Builder Mode */}
      {queryMode === 'block-builder' && (
        <div className="space-y-3">
          <button
            onClick={() => { setBlockBuilderExpanded(!blockBuilderExpanded); triggerResize(); }}
            className="w-full flex items-center justify-between p-2 rounded-lg hover:bg-muted/50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Blocks className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm font-medium">Visual Block Builder</span>
            </div>
            {blockBuilderExpanded ? (
              <ChevronDown className="w-4 h-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="w-4 h-4 text-muted-foreground" />
            )}
          </button>

          {blockBuilderExpanded && (
            <div className="w-full">
              <BlockBuilder onSendToEditor={handleSendToEditor} />
            </div>
          )}
        </div>
      )}

      {/* openCypher Editor Mode */}
      {queryMode === 'cypher-editor' && (
        <div className="space-y-3">
          <button
            onClick={() => { setCypherEditorExpanded(!cypherEditorExpanded); triggerResize(); }}
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
            <div className="space-y-2">
              <textarea
                value={cypherQuery}
                onChange={(e) => setCypherQuery(e.target.value)}
                placeholder="Enter openCypher query..."
                className="w-full h-48 px-3 py-2 font-mono text-sm rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-ring resize-y"
                spellCheck={false}
              />

              {cypherError && (
                <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-lg text-sm text-destructive">
                  {cypherError}
                </div>
              )}

              <button
                onClick={handleExecuteCypher}
                disabled={isExecutingCypher || !cypherQuery.trim()}
                className="w-full px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {isExecutingCypher ? (
                  <>
                    <LoadingSpinner className="text-primary-foreground" />
                    Executing Query...
                  </>
                ) : (
                  <>
                    <Code className="w-4 h-4" />
                    Execute Query
                  </>
                )}
              </button>

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
          )}
        </div>
      )}
    </div>
  );
};
