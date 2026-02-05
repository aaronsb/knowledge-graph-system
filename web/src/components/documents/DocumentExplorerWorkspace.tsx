/**
 * Document Explorer Workspace (ADR-085)
 *
 * Radial visualization of document→concept relationships with
 * spreading activation decay.
 */

import React, { useState, useCallback, useEffect } from 'react';
import { Search, FileText, Loader2, Layers, FolderOpen } from 'lucide-react';
import { apiClient } from '../../api/client';
import { DocumentExplorer } from '../../explorers/DocumentExplorer/DocumentExplorer';
import { DEFAULT_SETTINGS } from '../../explorers/DocumentExplorer/types';
import type { DocumentExplorerData, DocumentExplorerSettings, ConceptTreeNode } from '../../explorers/DocumentExplorer/types';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { DocumentViewer } from '../shared/DocumentViewer';
import { IconRailPanel } from '../shared/IconRailPanel';
import { SavedQueriesPanel } from '../shared/SavedQueriesPanel';
import { useQueryReplay, type ReplayableDefinition } from '../../hooks/useQueryReplay';
import { useGraphStore } from '../../store/graphStore';

interface DocumentSearchResult {
  document_id: string;
  filename: string;
  ontology: string;
  content_type: string;
  best_similarity: number;
  source_count: number;
  concept_ids: string[];
}

export const DocumentExplorerWorkspace: React.FC = () => {
  const { replayQuery } = useQueryReplay();
  const [activeRailTab, setActiveRailTab] = useState('savedQueries');
  const [isLoadingFromQuery, setIsLoadingFromQuery] = useState(false);

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<DocumentSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Selected document state
  const [selectedDocument, setSelectedDocument] = useState<DocumentSearchResult | null>(null);
  const [explorerData, setExplorerData] = useState<DocumentExplorerData | null>(null);
  const [isLoadingConcepts, setIsLoadingConcepts] = useState(false);

  // Hop expansion control
  const [maxHops, setMaxHops] = useState<0 | 1 | 2>(0);

  // Document viewer state
  const [viewingDocument, setViewingDocument] = useState<{
    document_id: string;
    filename: string;
    content_type: string;
  } | null>(null);

  // Explorer settings
  const [settings, setSettings] = useState<DocumentExplorerSettings>(DEFAULT_SETTINGS);

  // Debounced search
  const debouncedQuery = useDebouncedValue(searchQuery, 300);

  // Search documents
  const handleSearch = useCallback(async () => {
    if (!debouncedQuery.trim()) {
      setSearchResults([]);
      return;
    }

    setIsSearching(true);
    setSearchError(null);

    try {
      const response = await apiClient.searchDocuments({
        query: debouncedQuery,
        limit: 20,
        min_similarity: 0.5,
      });
      setSearchResults(response.documents);
    } catch (error) {
      console.error('Document search failed:', error);
      setSearchError('Failed to search documents');
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  }, [debouncedQuery]);

  // Trigger search on debounced query change
  React.useEffect(() => {
    handleSearch();
  }, [handleSearch]);

  /**
   * Load a saved exploration query, then reverse-lookup documents
   * from the concepts in the resulting working graph (W).
   */
  const handleLoadExplorationQuery = useCallback(async (query: ReplayableDefinition) => {
    setIsLoadingFromQuery(true);
    setSearchError(null);
    setSearchQuery('');
    setSelectedDocument(null);
    setExplorerData(null);

    try {
      // 1. Replay the exploration → populates rawGraphData (W)
      await replayQuery(query);

      // 2. Extract concept_ids from the working graph
      const rawData = useGraphStore.getState().rawGraphData;
      if (!rawData || rawData.nodes.length === 0) {
        setSearchResults([]);
        return;
      }

      const conceptIds = rawData.nodes.map(n => n.concept_id);

      // 3. Reverse-lookup: find documents containing these concepts
      const response = await apiClient.findDocumentsByConcepts({
        concept_ids: conceptIds,
        limit: 50,
      });

      setSearchResults(response.documents);
    } catch (error) {
      console.error('Failed to load documents from exploration query:', error);
      setSearchError('Failed to find documents for exploration');
      setSearchResults([]);
    } finally {
      setIsLoadingFromQuery(false);
    }
  }, [replayQuery]);

  // Load document concepts with hop expansion
  const loadDocumentData = useCallback(async (doc: DocumentSearchResult, hops: number) => {
    setIsLoadingConcepts(true);

    try {
      const response = await apiClient.getDocumentConcepts(doc.document_id);

      // Base concepts (hop 0) - deduplicate by name (same concept from multiple chunks)
      const conceptsByName = new Map<string, typeof response.concepts[0]>();
      for (const c of response.concepts) {
        const name = c.name || c.concept_id;
        const existing = conceptsByName.get(name);
        if (!existing || c.instance_count > existing.instance_count) {
          // Keep the one with more instances (more significant)
          conceptsByName.set(name, c);
        }
      }

      const hop0Concepts = Array.from(conceptsByName.values()).map((c) => ({
        id: c.concept_id,
        type: 'concept' as const,
        label: c.name || c.concept_id,
        ontology: doc.ontology,
        hop: 0,
        grounding_strength: 0.5,
        grounding_display: undefined,
        instanceCount: c.instance_count,
        parentId: doc.document_id, // Parent is the document
      }));

      const allConcepts = [...hop0Concepts];
      const allLinks = response.concepts.map(c => ({
        source: doc.document_id,
        target: c.concept_id,
        type: 'EXTRACTED_FROM',
      }));

      // Map to track children for each concept (for tree building)
      const childrenMap = new Map<string, typeof allConcepts>();
      hop0Concepts.forEach(c => childrenMap.set(c.id, []));

      // Fetch related concepts for hop 1-2 if requested
      if (hops > 0 && hop0Concepts.length > 0) {
        const seenIds = new Set(hop0Concepts.map(c => c.id));
        seenIds.add(doc.document_id);

        // Fetch related for all hop-0 concepts in parallel for performance
        const relatedResults = await Promise.all(
          hop0Concepts.map(async (concept) => {
            try {
              const related = await apiClient.getRelatedConcepts({
                concept_id: concept.id,
                max_depth: hops,
              });
              return { concept, related };
            } catch (e) {
              console.warn(`Failed to get related for ${concept.id}:`, e);
              return { concept, related: { nodes: [], links: [] } };
            }
          })
        );

        // Process results
        for (const { concept, related } of relatedResults) {
          // Add hop-1 concepts
          if (related.nodes) {
            for (const node of related.nodes) {
              if (!seenIds.has(node.concept_id)) {
                seenIds.add(node.concept_id);
                const newConcept = {
                  id: node.concept_id,
                  type: 'concept' as const,
                  label: node.name || node.concept_id,  // Use 'name' not 'label' (label is relationship type)
                  ontology: node.ontology || doc.ontology,
                  hop: 1,
                  grounding_strength: node.grounding_strength ?? 0.5,
                  grounding_display: node.grounding_display,
                  instanceCount: 1,
                  parentId: concept.id, // Parent is the hop-0 concept
                };
                allConcepts.push(newConcept);

                // Track as child of parent concept
                const siblings = childrenMap.get(concept.id) || [];
                siblings.push(newConcept);
                childrenMap.set(concept.id, siblings);
              }
            }
          }

          // Add links
          if (related.links) {
            for (const link of related.links) {
              allLinks.push({
                source: link.from_id || link.source,
                target: link.to_id || link.target,
                type: link.relationship_type || link.type || 'RELATED',
              });
            }
          }
        }
      }

      // Build tree structure for radial tidy tree layout
      const buildTreeNode = (concept: typeof allConcepts[0]): ConceptTreeNode => {
        const children = childrenMap.get(concept.id) || [];
        return {
          id: concept.id,
          type: 'concept',
          label: concept.label,
          ontology: concept.ontology,
          hop: concept.hop,
          grounding_strength: concept.grounding_strength,
          grounding_display: concept.grounding_display,
          instanceCount: concept.instanceCount,
          children: children.map(buildTreeNode),
        };
      };

      const treeRoot: ConceptTreeNode = {
        id: doc.document_id,
        type: 'document',
        label: doc.filename,
        ontology: doc.ontology,
        hop: -1, // Document is "before" hop 0
        grounding_strength: 1.0,
        children: hop0Concepts.map(buildTreeNode),
      };

      const data: DocumentExplorerData = {
        document: {
          id: doc.document_id,
          type: 'document',
          label: doc.filename,
          ontology: doc.ontology,
          conceptCount: allConcepts.length,
        },
        concepts: allConcepts,
        links: allLinks,
        treeRoot,
      };

      setExplorerData(data);
    } catch (error) {
      console.error('Failed to load document concepts:', error);
      setSearchError('Failed to load document concepts');
    } finally {
      setIsLoadingConcepts(false);
    }
  }, []);

  // Handle document selection
  const handleSelectDocument = useCallback(async (doc: DocumentSearchResult) => {
    setSelectedDocument(doc);
    await loadDocumentData(doc, maxHops);
  }, [loadDocumentData, maxHops]);

  // Reload when maxHops changes
  useEffect(() => {
    if (selectedDocument) {
      loadDocumentData(selectedDocument, maxHops);
    }
  }, [maxHops, selectedDocument, loadDocumentData]);

  return (
    <div className="flex h-full">
      {/* Left rail with saved queries */}
      <IconRailPanel
        tabs={[
          {
            id: 'savedQueries',
            icon: FolderOpen,
            label: 'Saved Queries',
            content: (
              <SavedQueriesPanel
                onLoadQuery={handleLoadExplorationQuery}
                definitionTypeFilter="exploration"
              />
            ),
          },
        ]}
        activeTab={activeRailTab}
        onTabChange={setActiveRailTab}
      />

      {/* Left sidebar - search and results */}
      <div className="w-80 border-r border-border bg-card flex flex-col">
        {/* Search input */}
        <div className="p-4 border-b border-border">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search documents..."
              className="w-full pl-10 pr-4 py-2 bg-background border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          {searchError && (
            <p className="mt-2 text-xs text-destructive">{searchError}</p>
          )}
        </div>

        {/* Hop expansion control */}
        <div className="p-4 border-b border-border">
          <div className="flex items-center gap-2 mb-2">
            <Layers className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">Expansion Depth</span>
          </div>
          <div className="flex gap-1">
            {[0, 1, 2].map((hop) => (
              <button
                key={hop}
                onClick={() => setMaxHops(hop as 0 | 1 | 2)}
                className={`flex-1 px-3 py-1.5 text-sm rounded-md transition-colors ${
                  maxHops === hop
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted hover:bg-muted/80 text-muted-foreground'
                }`}
              >
                {hop === 0 ? 'Direct' : `+${hop} hop${hop > 1 ? 's' : ''}`}
              </button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            {maxHops === 0
              ? 'Show only concepts from document'
              : `Expand ${maxHops} level${maxHops > 1 ? 's' : ''} of related concepts`}
          </p>
        </div>

        {/* Search results */}
        <div className="flex-1 overflow-y-auto">
          {(isSearching || isLoadingFromQuery) ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : searchResults.length > 0 ? (
            <div className="divide-y divide-border">
              {searchResults.map((doc) => (
                <button
                  key={doc.document_id}
                  onClick={() => handleSelectDocument(doc)}
                  className={`w-full p-3 text-left hover:bg-accent transition-colors ${
                    selectedDocument?.document_id === doc.document_id
                      ? 'bg-accent'
                      : ''
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <FileText className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium truncate">
                        {doc.filename}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {doc.ontology}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {doc.concept_ids.length} concepts •{' '}
                        {(doc.best_similarity * 100).toFixed(0)}% match
                      </p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          ) : debouncedQuery ? (
            <div className="text-center py-8 text-muted-foreground text-sm">
              No documents found
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground text-sm">
              Enter a search query to find documents
            </div>
          )}
        </div>
      </div>

      {/* Main area - explorer */}
      <div className="flex-1 relative">
        {isLoadingConcepts ? (
          <div className="absolute inset-0 flex items-center justify-center bg-background">
            <div className="text-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground mx-auto" />
              <p className="mt-2 text-sm text-muted-foreground">
                Loading concepts...
              </p>
            </div>
          </div>
        ) : explorerData ? (
          <DocumentExplorer
            data={explorerData}
            settings={settings}
            onSettingsChange={setSettings}
            onNodeClick={(nodeId) => {
              // Check if clicked on document node
              if (selectedDocument && nodeId === selectedDocument.document_id) {
                setViewingDocument({
                  document_id: selectedDocument.document_id,
                  filename: selectedDocument.filename,
                  content_type: selectedDocument.content_type,
                });
              } else {
                console.log('Clicked concept:', nodeId);
              }
            }}
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center bg-background">
            <div className="text-center text-muted-foreground">
              <FileText className="h-16 w-16 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium">Document Explorer</p>
              <p className="text-sm mt-1">
                Search and select a document to explore its concepts
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Document Viewer Modal */}
      <DocumentViewer
        document={viewingDocument}
        onClose={() => setViewingDocument(null)}
      />
    </div>
  );
};
