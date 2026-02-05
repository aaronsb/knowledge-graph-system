/**
 * Document Explorer Workspace (ADR-085)
 *
 * Force-directed concept cloud for a single document.
 * Shows inter-concept relationships with two-tone coloring
 * based on exploration query overlap.
 */

import React, { useState, useCallback } from 'react';
import { Search, FileText, Loader2, FolderOpen } from 'lucide-react';
import { apiClient } from '../../api/client';
import { DocumentExplorer } from '../../explorers/DocumentExplorer/DocumentExplorer';
import { DEFAULT_SETTINGS } from '../../explorers/DocumentExplorer/types';
import type { DocumentExplorerData, DocumentExplorerSettings } from '../../explorers/DocumentExplorer/types';
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
      await replayQuery(query);

      const rawData = useGraphStore.getState().rawGraphData;
      if (!rawData || rawData.nodes.length === 0) {
        setSearchResults([]);
        return;
      }

      const conceptIds = rawData.nodes.map(n => n.concept_id);
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

  /**
   * Load concept cloud for a document: concepts + inter-concept edges.
   * The doc's concept_ids (from the exploration query match) provide
   * the two-tone coloring signal.
   */
  const loadDocumentData = useCallback(async (doc: DocumentSearchResult) => {
    setIsLoadingConcepts(true);

    try {
      // 1. Fetch document's concepts
      const response = await apiClient.getDocumentConcepts(doc.document_id);

      // Deduplicate by name (same concept from multiple chunks)
      const conceptsByName = new Map<string, typeof response.concepts[0]>();
      for (const c of response.concepts) {
        const name = c.name || c.concept_id;
        const existing = conceptsByName.get(name);
        if (!existing || c.instance_count > existing.instance_count) {
          conceptsByName.set(name, c);
        }
      }

      const concepts = Array.from(conceptsByName.values()).map(c => ({
        id: c.concept_id,
        label: c.name || c.concept_id,
      }));

      if (concepts.length === 0) {
        setExplorerData(null);
        return;
      }

      // 2. Fetch inter-concept edges via Cypher
      const conceptIds = concepts.map(c => c.id);
      let links: { source: string; target: string; type: string }[] = [];

      try {
        const edgeResult = await apiClient.executeCypherQuery({
          query: `MATCH (c1:Concept)-[r]->(c2:Concept)
                  WHERE c1.concept_id IN $concept_ids AND c2.concept_id IN $concept_ids
                  RETURN c1.concept_id as source, c2.concept_id as target, type(r) as type`,
          limit: 500,
        });

        if (Array.isArray(edgeResult)) {
          links = edgeResult.map((row: Record<string, string>) => ({
            source: row.source,
            target: row.target,
            type: row.type || 'RELATED',
          }));
        }
      } catch (e) {
        console.warn('Failed to fetch inter-concept edges:', e);
        // Continue without edges — the cloud still shows concepts
      }

      // 3. Build explorer data with query overlap info
      setExplorerData({
        document: {
          id: doc.document_id,
          label: doc.filename,
          ontology: doc.ontology,
        },
        concepts,
        links,
        queryConceptIds: doc.concept_ids || [],
      });
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
    await loadDocumentData(doc);
  }, [loadDocumentData]);

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
              if (selectedDocument && nodeId === selectedDocument.document_id) {
                setViewingDocument({
                  document_id: selectedDocument.document_id,
                  filename: selectedDocument.filename,
                  content_type: selectedDocument.content_type,
                });
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
