/**
 * Multi-Mode Smart Search Component
 *
 * Top-level: Query mode selection via radio dial
 * - Smart Search (with sub-modes: Concept/Neighborhood/Path)
 * - Block Builder
 * - openCypher Editor
 */

import React, { useState } from 'react';
import { Search, Network, GitBranch, Blocks, Code, ChevronDown, ChevronRight } from 'lucide-react';
import { LoadingSpinner } from './LoadingSpinner';
import { useSearchConcepts } from '../../hooks/useGraphData';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useGraphStore } from '../../store/graphStore';
import { ModeDial } from './ModeDial';
import { apiClient } from '../../api/client';
import { BlockBuilder } from '../blocks/BlockBuilder';
import { getZIndexClass } from '../../config/zIndex';
import {
  ConceptSearchInput,
  SelectedConceptChip,
  SliderControl,
  LoadButtons,
  PathResults,
} from './search';

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

  // Collapsible state for Smart Search
  const [smartSearchExpanded, setSmartSearchExpanded] = useState(true);

  // Collapsible state for openCypher editor
  const [cypherEditorExpanded, setCypherEditorExpanded] = useState(true);

  const toggleSmartSearch = () => {
    setSmartSearchExpanded(!smartSearchExpanded);
    setTimeout(() => window.dispatchEvent(new Event('resize')), 100);
  };

  const toggleSection = (mode: SmartSearchSubMode) => {
    setExpandedSections(prev => ({ ...prev, [mode]: !prev[mode] }));
    setTimeout(() => window.dispatchEvent(new Event('resize')), 100);
  };

  const toggleCypherEditor = () => {
    setCypherEditorExpanded(!cypherEditorExpanded);
    setTimeout(() => window.dispatchEvent(new Event('resize')), 100);
  };

  const toggleBlockBuilder = () => {
    setBlockBuilderExpanded(!blockBuilderExpanded);
    setTimeout(() => window.dispatchEvent(new Event('resize')), 100);
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

  // Cypher editor state
  const [cypherQuery, setCypherQuery] = useState(`MATCH (c:Concept)-[r]->(n:Concept)
WHERE c.label CONTAINS 'organizational'
RETURN c, r, n
LIMIT 50`);
  const [isExecutingCypher, setIsExecutingCypher] = useState(false);
  const [cypherError, setCypherError] = useState<string | null>(null);

  const { setSearchParams, setRawGraphData, mergeRawGraphData, setGraphData } = useGraphStore();

  // Debounce values to prevent excessive API calls
  const debouncedConceptQuery = useDebouncedValue(conceptQuery, 800);
  const debouncedNeighborhoodQuery = useDebouncedValue(neighborhoodQuery, 800);
  const debouncedPathFromQuery = useDebouncedValue(pathFromQuery, 800);
  const debouncedPathToQuery = useDebouncedValue(pathToQuery, 800);
  const debouncedSimilarity = useDebouncedValue(similarity, 500);

  // Search hooks (gated by mode + selection state)
  const { data: conceptResults, isLoading: isLoadingConcepts } = useSearchConcepts(
    debouncedConceptQuery,
    {
      limit: 10,
      minSimilarity: debouncedSimilarity,
      enabled: queryMode === 'smart-search' && smartSearchMode === 'concept' && !selectedConcept,
    }
  );

  const { data: neighborhoodSearchResults, isLoading: isLoadingNeighborhoodSearch } = useSearchConcepts(
    debouncedNeighborhoodQuery,
    {
      limit: 10,
      minSimilarity: debouncedSimilarity,
      enabled: queryMode === 'smart-search' && smartSearchMode === 'neighborhood' && !selectedCenterConcept,
    }
  );

  const { data: pathFromSearchResults, isLoading: isLoadingPathFromSearch } = useSearchConcepts(
    debouncedPathFromQuery,
    {
      limit: 10,
      minSimilarity: debouncedSimilarity,
      enabled: queryMode === 'smart-search' && smartSearchMode === 'path' && !selectedFromConcept,
    }
  );

  const { data: pathToSearchResults, isLoading: isLoadingPathToSearch } = useSearchConcepts(
    debouncedPathToQuery,
    {
      limit: 10,
      minSimilarity: debouncedSimilarity,
      enabled: queryMode === 'smart-search' && smartSearchMode === 'path' && !selectedToConcept,
    }
  );

  // Selection handlers
  const handleSelectConcept = (concept: any) => {
    setSelectedConcept(concept);
    setConceptQuery('');
  };

  const handleSelectCenterConcept = (concept: any) => {
    setSelectedCenterConcept(concept);
    setNeighborhoodQuery('');
  };

  const handleSelectFromConcept = (concept: any) => {
    setSelectedFromConcept(concept);
    setPathFromQuery('');
  };

  const handleSelectToConcept = (concept: any) => {
    setSelectedToConcept(concept);
    setPathToQuery('');
  };

  // Load handlers
  const handleLoadConcept = (loadMode: 'clean' | 'add') => {
    if (!selectedConcept) return;
    setSearchParams({
      primaryConceptId: selectedConcept.concept_id,
      primaryConceptLabel: selectedConcept.label,
      depth: 1,
      maxHops: 5,
      loadMode,
    });
  };

  const handleLoadNeighborhood = (loadMode: 'clean' | 'add') => {
    if (!selectedCenterConcept) return;
    setSearchParams({
      primaryConceptId: selectedCenterConcept.concept_id,
      primaryConceptLabel: selectedCenterConcept.label,
      depth: neighborhoodDepth,
      maxHops: 5,
      loadMode,
    });
  };

  // Path search (manual, not auto)
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

      setPathResults({ error: errorMessage, count: 0, paths: [] });
    } finally {
      setIsLoadingPath(false);
    }
  };

  // Load selected path directly into graph
  const handleLoadPath = (loadMode: 'clean' | 'add') => {
    if (!selectedPath) return;

    // Extract Concept nodes only (skip Source/Ontology with empty IDs)
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
      const nodes = result.nodes.map((n: any) => ({
        concept_id: n.id,
        label: n.label,
        ontology: n.properties?.ontology || 'default',
      }));
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

  // Block builder → Cypher editor
  const handleSendToEditor = (compiledCypher: string) => {
    const hasExistingCode = cypherQuery.trim().length > 0;
    if (hasExistingCode) {
      const confirmed = window.confirm(
        'The openCypher editor already has code. Do you want to overwrite it with the compiled query from the block builder?'
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

  // "No results" content for concept search (with below-threshold suggestions)
  const conceptNoResults = conceptResults && conceptResults.results && conceptResults.results.length === 0 && (
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
  );

  // Similarity slider shorthand
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

      {/* Smart Search Mode */}
      {queryMode === 'smart-search' && (
        <div className="space-y-3">
          {/* Collapsible Header */}
          <button
            onClick={toggleSmartSearch}
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
            <>
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

              {/* ===== CONCEPT MODE ===== */}
              {smartSearchMode === 'concept' && (
                <div className="space-y-3">
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
                        <div className="space-y-3">
                          <ConceptSearchInput
                            query={conceptQuery}
                            onQueryChange={setConceptQuery}
                            placeholder="Search for a concept..."
                            icon={Search}
                            isLoading={isLoadingConcepts}
                            results={conceptResults?.results}
                            debouncedQuery={debouncedConceptQuery}
                            onSelect={handleSelectConcept}
                            noResultsContent={conceptNoResults}
                          />
                          {similaritySlider}
                        </div>
                      ) : (
                        <div className="space-y-3">
                          <SelectedConceptChip
                            label="Selected concept:"
                            conceptLabel={selectedConcept.label}
                            onClear={() => setSelectedConcept(null)}
                          />
                          {similaritySlider}
                          <LoadButtons
                            onLoadClean={() => handleLoadConcept('clean')}
                            onLoadAdd={() => handleLoadConcept('add')}
                          />
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}

              {/* ===== NEIGHBORHOOD MODE ===== */}
              {smartSearchMode === 'neighborhood' && (
                <div className="space-y-3">
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
                        <div className="space-y-3">
                          <ConceptSearchInput
                            query={neighborhoodQuery}
                            onQueryChange={setNeighborhoodQuery}
                            placeholder="Search for center concept..."
                            icon={Network}
                            isLoading={isLoadingNeighborhoodSearch}
                            results={neighborhoodSearchResults?.results}
                            debouncedQuery={debouncedNeighborhoodQuery}
                            onSelect={handleSelectCenterConcept}
                          />
                          {similaritySlider}
                        </div>
                      ) : (
                        <div className="space-y-3">
                          <SelectedConceptChip
                            label="Center concept:"
                            conceptLabel={selectedCenterConcept.label}
                            onClear={() => setSelectedCenterConcept(null)}
                          />
                          <SliderControl
                            label="Depth:"
                            value={neighborhoodDepth}
                            min={1}
                            max={5}
                            onChange={setNeighborhoodDepth}
                            unit={`hop${neighborhoodDepth > 1 ? 's' : ''}`}
                          />
                          <LoadButtons
                            onLoadClean={() => handleLoadNeighborhood('clean')}
                            onLoadAdd={() => handleLoadNeighborhood('add')}
                          />
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}

              {/* ===== PATH MODE ===== */}
              {smartSearchMode === 'path' && (
                <div className="space-y-3">
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
                      {/* Step 1: Select From concept */}
                      {!selectedFromConcept ? (
                        <div className="space-y-3">
                          <ConceptSearchInput
                            query={pathFromQuery}
                            onQueryChange={setPathFromQuery}
                            placeholder="Search for starting concept..."
                            icon={GitBranch}
                            isLoading={isLoadingPathFromSearch}
                            results={pathFromSearchResults?.results}
                            debouncedQuery={debouncedPathFromQuery}
                            onSelect={handleSelectFromConcept}
                          />
                          {similaritySlider}
                        </div>
                      ) : !selectedToConcept ? (
                        /* Step 2: Select To concept */
                        <div className="space-y-3">
                          <SelectedConceptChip
                            label="From concept:"
                            conceptLabel={selectedFromConcept.label}
                            onClear={() => setSelectedFromConcept(null)}
                          />
                          <ConceptSearchInput
                            query={pathToQuery}
                            onQueryChange={setPathToQuery}
                            placeholder="Search for target concept..."
                            icon={GitBranch}
                            isLoading={isLoadingPathToSearch}
                            results={pathToSearchResults?.results}
                            debouncedQuery={debouncedPathToQuery}
                            onSelect={handleSelectToConcept}
                          />
                        </div>
                      ) : (
                        /* Step 3: Both selected — configure and search */
                        <div className="space-y-3">
                          <div className="space-y-2">
                            <SelectedConceptChip
                              label="From concept:"
                              conceptLabel={selectedFromConcept.label}
                              onClear={() => {
                                setSelectedFromConcept(null);
                                setSelectedToConcept(null);
                              }}
                            />
                            <SelectedConceptChip
                              label="To concept:"
                              conceptLabel={selectedToConcept.label}
                              onClear={() => setSelectedToConcept(null)}
                            />
                          </div>

                          {similaritySlider}

                          <SliderControl
                            label="Max Hops:"
                            value={maxHops}
                            min={1}
                            max={10}
                            onChange={setMaxHops}
                          />

                          {/* Find Paths Button */}
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
                    </>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Block Builder Mode */}
      {queryMode === 'block-builder' && (
        <div className="space-y-3">
          <button
            onClick={toggleBlockBuilder}
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
            </>
          )}
        </div>
      )}
    </div>
  );
};
