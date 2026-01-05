/**
 * Document Explorer Workspace (ADR-085)
 *
 * Radial visualization of document→concept relationships with
 * spreading activation decay.
 */

import React, { useState, useCallback } from 'react';
import { Search, FileText, Loader2 } from 'lucide-react';
import { apiClient } from '../../api/client';
import { DocumentExplorer } from '../../explorers/DocumentExplorer/DocumentExplorer';
import { DEFAULT_SETTINGS } from '../../explorers/DocumentExplorer/types';
import type { DocumentExplorerData, DocumentExplorerSettings } from '../../explorers/DocumentExplorer/types';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';

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
  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<DocumentSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Selected document state
  const [selectedDocument, setSelectedDocument] = useState<DocumentSearchResult | null>(null);
  const [explorerData, setExplorerData] = useState<DocumentExplorerData | null>(null);
  const [isLoadingConcepts, setIsLoadingConcepts] = useState(false);

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

  // Load document concepts
  const handleSelectDocument = useCallback(async (doc: DocumentSearchResult) => {
    setSelectedDocument(doc);
    setIsLoadingConcepts(true);

    try {
      const response = await apiClient.getDocumentConcepts(doc.document_id);

      // Transform to explorer data format
      const data: DocumentExplorerData = {
        document: {
          id: doc.document_id,
          type: 'document',
          label: doc.filename,
          ontology: doc.ontology,
          conceptCount: response.concepts.length,
        },
        concepts: response.concepts.map((c) => ({
          id: c.concept_id,
          type: 'concept' as const,
          label: c.name || c.concept_id,
          ontology: doc.ontology, // Use document's ontology
          hop: 0, // All direct concepts are hop 0
          grounding_strength: 0.5, // TODO: fetch grounding from concept details
          grounding_display: undefined,
          instanceCount: c.instance_count,
        })),
        links: response.concepts.map(c => ({
          source: doc.document_id,
          target: c.concept_id,
          type: 'EXTRACTED_FROM',
        })),
      };

      setExplorerData(data);
    } catch (error) {
      console.error('Failed to load document concepts:', error);
      setSearchError('Failed to load document concepts');
    } finally {
      setIsLoadingConcepts(false);
    }
  }, []);

  return (
    <div className="flex h-full">
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
          {isSearching ? (
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
              console.log('Clicked node:', nodeId);
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
    </div>
  );
};
