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
import { stepToCypher, parseCypherStatements } from '../../utils/cypherGenerator';
import { mapWorkingGraphToRawGraph, extractGraphFromPath } from '../../utils/cypherResultMapper';
import type { PathResult } from '../../utils/cypherResultMapper';
import { statementsToProgram } from '../../utils/programBuilder';
import {
  ConceptSearchInput,
  SliderControl,
  LoadButtons,
  PathResults,
} from './search';

export const SearchBar: React.FC = () => {
  // Top-level mode (dial)
  const { queryMode, setQueryMode, blockBuilderExpanded, setBlockBuilderExpanded, cypherEditorContent, setCypherEditorContent } = useGraphStore();

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
  const [selectedPrimary, setSelectedPrimary] = useState<{ concept_id: string; label: string } | null>(null);
  const [depth, setDepth] = useState(1);

  // Destination concept (optional — triggers path mode)
  const [destinationQuery, setDestinationQuery] = useState('');
  const [selectedDestination, setSelectedDestination] = useState<{ concept_id: string; label: string } | null>(null);
  const [showDestination, setShowDestination] = useState(false);
  const [maxHops, setMaxHops] = useState(5);

  // Path search state
  const [pathResults, setPathResults] = useState<{ paths: PathResult[]; count: number; error?: string } | null>(null);
  const [selectedPath, setSelectedPath] = useState<PathResult | null>(null);
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
        setPrimaryQuery(searchParams.primaryConceptLabel);
        setDepth(searchParams.depth);
      }
    }
  }, [searchParams.primaryConceptId, searchParams.primaryConceptLabel]);

  // Consume exported Cypher from ExplorerView "Export to Editor" action
  useEffect(() => {
    if (cypherEditorContent !== null) {
      setCypherQuery(cypherEditorContent);
      setCypherEditorContent(null);
      setQueryMode('cypher-editor');
      setCypherEditorExpanded(true);
    }
  }, [cypherEditorContent, setCypherEditorContent, setQueryMode]);

  // === HANDLERS ===

  /** Select a primary concept from search results and lock the search input */
  const handleSelectPrimary = (concept: { concept_id: string; label: string }) => {
    setSelectedPrimary(concept);
    setPrimaryQuery(concept.label);
  };

  /** Select a destination concept from search results (path mode) */
  const handleSelectDestination = (concept: { concept_id: string; label: string }) => {
    setSelectedDestination(concept);
    setDestinationQuery(concept.label);
  };

  /** Clear the destination concept and collapse path mode back to explore mode */
  const handleRemoveDestination = () => {
    setShowDestination(false);
    setSelectedDestination(null);
    setDestinationQuery('');
    setPathResults(null);
    setSelectedPath(null);
    setDepth(1); // Reset to explore default
  };

  /** Load explore — fetch subgraph around selected concept and record the step */
  const handleLoadExplore = (loadMode: 'clean' | 'add') => {
    if (!selectedPrimary) return;

    const stepParams = {
      action: 'explore' as const,
      conceptLabel: selectedPrimary.label,
      depth,
    };

    useGraphStore.getState().addExplorationStep({
      action: 'explore',
      op: '+',
      cypher: stepToCypher(stepParams),
      conceptId: selectedPrimary.concept_id,
      conceptLabel: selectedPrimary.label,
      depth,
    });

    setSearchParams({
      primaryConceptId: selectedPrimary.concept_id,
      primaryConceptLabel: selectedPrimary.label,
      depth,
      maxHops: 5,
      loadMode,
    });
  };

  /** Find paths between primary and destination concepts via the API */
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
    } catch (error: unknown) {
      console.error('Failed to find paths:', error);

      const err = error as { code?: string; response?: { data?: { detail?: string } }; message?: string };
      let errorMessage = 'Failed to find paths';
      if (err.code === 'ECONNABORTED') {
        errorMessage = `Search timed out. Try reducing max hops.`;
      } else if (err.response?.data?.detail) {
        errorMessage = err.response.data.detail;
      } else if (err.message) {
        errorMessage = err.message;
      }

      setPathResults({ error: errorMessage, count: 0, paths: [] });
    } finally {
      setIsLoadingPath(false);
    }
  };

  /** Load selected path into graph and record the step */
  const handleLoadPath = async (loadMode: 'clean' | 'add') => {
    if (!selectedPath || !selectedPrimary || !selectedDestination) return;

    const stepParams = {
      action: 'load-path' as const,
      conceptLabel: selectedPrimary.label,
      depth,
      destinationConceptLabel: selectedDestination.label,
      maxHops,
    };

    useGraphStore.getState().addExplorationStep({
      action: 'load-path',
      op: '+',
      cypher: stepToCypher(stepParams),
      conceptId: selectedPrimary.concept_id,
      conceptLabel: selectedPrimary.label,
      depth,
      destinationConceptId: selectedDestination.concept_id,
      destinationConceptLabel: selectedDestination.label,
      maxHops,
    });

    const { nodes, links, conceptNodeIds } = extractGraphFromPath(selectedPath);

    if (loadMode === 'clean') {
      setGraphData(null);
      setRawGraphData({ nodes, links });
    } else {
      mergeRawGraphData({ nodes, links });
    }

    // Enrich path nodes with neighborhood context
    if (depth > 0 && conceptNodeIds.length <= 50) {
      const enrichDepth = Math.min(depth, 2);
      if (conceptNodeIds.length > 0) {
        try {
          const enrichments = await Promise.all(
            conceptNodeIds.map((id) =>
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

  // Execute Cypher program — parses +/- prefixed multi-statement scripts,
  // routes results through the rawGraphData pipeline (not setGraphData directly),
  // and records each statement as an exploration step for save/export round-trip.
  // Plain Cypher without operators is treated as a single additive statement.
  const handleExecuteCypher = async () => {
    if (!cypherQuery.trim()) return;

    setIsExecutingCypher(true);
    setCypherError(null);

    try {
      let statements = parseCypherStatements(cypherQuery);

      // Plain Cypher without +/- operators → treat as single additive statement
      if (statements.length === 0) {
        const cypher = cypherQuery.trim().replace(/;\s*$/, '');
        if (cypher) {
          statements = [{ op: '+', cypher }];
        }
      }

      if (statements.length === 0) return;

      const store = useGraphStore.getState();

      // Start fresh — clear graph and reset exploration session
      setGraphData(null);
      setRawGraphData(null);
      store.resetExplorationSession();

      // Execute all statements as a single GraphProgram (ADR-500)
      const program = statementsToProgram(statements);
      const programResult = await apiClient.executeProgram({ program: program as unknown as Record<string, unknown> });
      const mapped = mapWorkingGraphToRawGraph(programResult.result);

      // Record exploration steps for save/export round-trip
      for (const stmt of statements) {
        store.addExplorationStep({
          action: 'cypher',
          op: stmt.op,
          cypher: stmt.cypher,
        });
      }

      // Load the complete result
      mergeRawGraphData(mapped);
    } catch (error: unknown) {
      console.error('Failed to execute Cypher query:', error);
      const err = error as { response?: { data?: { detail?: string } }; message?: string };
      setCypherError(err.response?.data?.detail || err.message || 'Query execution failed');
    } finally {
      setIsExecutingCypher(false);
    }
  };

  /** Receive compiled Cypher from the block builder and switch to the Cypher editor */
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
    <div className="relative space-y-4 min-w-0">
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
              {/* Search input — always visible */}
              <ConceptSearchInput
                query={primaryQuery}
                onQueryChange={(q) => {
                  setPrimaryQuery(q);
                  if (selectedPrimary) {
                    // User is typing — clear selection to restart search
                    setSelectedPrimary(null);
                    setSelectedDestination(null);
                    setShowDestination(false);
                    setPathResults(null);
                    setSelectedPath(null);
                  }
                }}
                placeholder="Search for a concept..."
                icon={Search}
                isLoading={isLoadingPrimary}
                results={primaryResults?.results}
                debouncedQuery={debouncedPrimaryQuery}
                onSelect={handleSelectPrimary}
                noResultsContent={noResultsContent}
              />

              {similaritySlider}

              {/* Controls appear when a concept is selected */}
              {selectedPrimary && (
                <div className="space-y-3">
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

                      <ConceptSearchInput
                        query={destinationQuery}
                        onQueryChange={(q) => {
                          setDestinationQuery(q);
                          if (selectedDestination) {
                            setSelectedDestination(null);
                            setPathResults(null);
                            setSelectedPath(null);
                          }
                        }}
                        placeholder="Search for destination concept..."
                        icon={GitBranch}
                        isLoading={isLoadingDestination}
                        results={destinationResults?.results}
                        debouncedQuery={debouncedDestinationQuery}
                        onSelect={handleSelectDestination}
                      />

                      {selectedDestination && (
                        <div className="space-y-3">
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
                <div className="font-medium">Syntax:</div>
                <div className="font-mono bg-muted p-2 rounded space-y-1">
                  <div className="text-muted-foreground/70">{'-- Single query (plain Cypher):'}</div>
                  <div>{'MATCH (c:Concept)-[r]->(n) RETURN c, r, n LIMIT 50'}</div>
                  <div className="text-muted-foreground/70 mt-2">{'-- Multi-statement with set operators:'}</div>
                  <div>{'+ MATCH (c:Concept)-[r]-(n) WHERE c.label = \'X\' RETURN c, r, n;'}</div>
                  <div>{'- MATCH (c:Concept) WHERE c.label = \'Noise\' RETURN c;'}</div>
                </div>
                <div className="text-muted-foreground/70 mt-2">
                  Prefix lines with <code className="bg-muted px-1 rounded">+</code> (add) or <code className="bg-muted px-1 rounded">-</code> (subtract) for set algebra. Statements execute in order.
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
