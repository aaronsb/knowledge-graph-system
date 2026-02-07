/**
 * Document Explorer Workspace v2
 *
 * Query-driven multi-document concept graph.
 * The saved exploration query drives everything: concepts, documents, edges.
 * Sidebar shows document list + multi-query passage search with ring visualization.
 */

import React, { useState, useCallback, useMemo } from 'react';
import { Search, FileText, Loader2, FolderOpen, BookOpen, Settings } from 'lucide-react';
import { apiClient } from '../../api/client';
import { DocumentExplorer } from '../../explorers/DocumentExplorer/DocumentExplorer';
import { ProfilePanel } from '../../explorers/DocumentExplorer/ProfilePanel';
import { PassageQueryLegend } from '../../explorers/DocumentExplorer/PassageQueryLegend';
import { DEFAULT_SETTINGS } from '../../explorers/DocumentExplorer/types';
import type {
  DocumentExplorerData,
  DocumentExplorerSettings,
  DocExplorerDocument,
  DocGraphNode,
  DocGraphLink,
} from '../../explorers/DocumentExplorer/types';
import { DocumentViewer } from '../shared/DocumentViewer';
import { IconRailPanel } from '../shared/IconRailPanel';
import { SavedQueriesPanel } from '../shared/SavedQueriesPanel';
import { useQueryReplay, type ReplayableDefinition } from '../../hooks/useQueryReplay';
import { usePassageSearch } from '../../hooks/usePassageSearch';
import { useGraphStore } from '../../store/graphStore';
import { mapWorkingGraphToRawGraph } from '../../utils/cypherResultMapper';
import { cypherToStatement } from '../../utils/programBuilder';

/** Sidebar document entry (from findDocumentsByConcepts). */
interface SidebarDocument {
  document_id: string;
  filename: string;
  ontology: string;
  content_type: string;
  concept_ids: string[];       // concepts overlapping with query
  totalConceptCount: number;   // ALL concepts for this doc (after hydration)
}

export const DocumentExplorerWorkspace: React.FC = () => {
  const { replayQuery } = useQueryReplay();
  const [activeRailTab, setActiveRailTab] = useState('savedQueries');

  // Pipeline state
  const [isLoading, setIsLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Document list (populated from query)
  const [sidebarDocs, setSidebarDocs] = useState<SidebarDocument[]>([]);

  // Graph data
  const [explorerData, setExplorerData] = useState<DocumentExplorerData | null>(null);

  // Focus state — which document is focused in the graph
  const [focusedDocId, setFocusedDocId] = useState<string | null>(null);

  // Document viewer
  const [viewingDocument, setViewingDocument] = useState<{
    document_id: string;
    filename: string;
    content_type: string;
  } | null>(null);

  // Settings
  const [settings, setSettings] = useState<DocumentExplorerSettings>(DEFAULT_SETTINGS);

  // Multi-query passage search (extracted hook)
  const {
    passageQueries,
    pendingQueryText,
    setPendingQueryText,
    isCommittingQuery,
    handleCommitQuery,
    handleToggleQuery,
    handleDeleteQuery,
    resetQueries,
    passageRings,
    queryColorLabels,
    documentHighlights,
    allVisibleResults,
  } = usePassageSearch(sidebarDocs, viewingDocument?.document_id ?? null);

  /**
   * Load a saved exploration query and build the full multi-document graph.
   */
  const handleLoadExplorationQuery = useCallback(async (query: ReplayableDefinition) => {
    setIsLoading(true);
    setError(null);
    setFocusedDocId(null);
    setExplorerData(null);
    setSidebarDocs([]);
    resetQueries();

    try {
      // Step 1: Replay the saved query
      setLoadingMessage('Replaying query...');
      const getGraphState = () => useGraphStore.getState().rawGraphData;
      await replayQuery(query);

      const rawData = getGraphState();
      if (!rawData || rawData.nodes.length === 0) {
        setError('Query produced no results');
        return;
      }

      const queryConceptIds = new Set(rawData.nodes.map(n => n.concept_id));

      // Step 2: Find documents
      setLoadingMessage('Finding documents...');
      const docResponse = await apiClient.findDocumentsByConcepts({
        concept_ids: Array.from(queryConceptIds),
        limit: 50,
      });

      if (docResponse.documents.length === 0) {
        setError('No documents found for these concepts');
        return;
      }

      const documentIds = docResponse.documents.map(d => d.document_id);

      // Step 3: Bulk fetch all concepts for each document
      setLoadingMessage('Hydrating document concepts...');
      const bulkResponse = await apiClient.getDocumentConceptsBulk(documentIds);

      // Build document metadata with concept counts
      const docsForSidebar: SidebarDocument[] = docResponse.documents.map(d => ({
        document_id: d.document_id,
        filename: d.filename,
        ontology: d.ontology,
        content_type: d.content_type,
        concept_ids: d.concept_ids || [],
        totalConceptCount: (bulkResponse.documents[d.document_id] || []).length,
      }));
      setSidebarDocs(docsForSidebar);

      // Step 4: Classify concepts
      setLoadingMessage('Building graph...');
      const allConceptsMap = new Map<string, { id: string; label: string; documentIds: string[] }>();

      for (const node of rawData.nodes) {
        allConceptsMap.set(node.concept_id, {
          id: node.concept_id,
          label: node.label,
          documentIds: [],
        });
      }

      for (const [docId, concepts] of Object.entries(bulkResponse.documents)) {
        for (const c of concepts) {
          const existing = allConceptsMap.get(c.concept_id);
          if (existing) {
            existing.documentIds.push(docId);
          } else {
            allConceptsMap.set(c.concept_id, {
              id: c.concept_id,
              label: c.label,
              documentIds: [docId],
            });
          }
        }
      }

      for (const doc of docResponse.documents) {
        for (const cid of doc.concept_ids || []) {
          const existing = allConceptsMap.get(cid);
          if (existing && !existing.documentIds.includes(doc.document_id)) {
            existing.documentIds.push(doc.document_id);
          }
        }
      }

      // Build nodes
      const nodes: DocGraphNode[] = [];

      for (const doc of docResponse.documents) {
        nodes.push({
          id: doc.document_id,
          label: doc.filename,
          type: 'document',
          documentIds: [],
          size: 24,
        });
      }

      for (const [cid, data] of allConceptsMap) {
        nodes.push({
          id: cid,
          label: data.label,
          type: queryConceptIds.has(cid) ? 'query-concept' : 'extended-concept',
          documentIds: data.documentIds,
          size: queryConceptIds.has(cid) ? 6 : 4,
        });
      }

      // Build links
      const links: DocGraphLink[] = [];

      for (const [docId, concepts] of Object.entries(bulkResponse.documents)) {
        for (const c of concepts) {
          if (allConceptsMap.has(c.concept_id)) {
            links.push({
              source: docId,
              target: c.concept_id,
              type: '__doc_cluster__',
              visible: false,
            });
          }
        }
      }

      // Step 5: Fetch all concept↔concept edges
      const allConceptIds = Array.from(allConceptsMap.keys());
      try {
        const idList = allConceptIds.map(id => `'${id.replace(/'/g, "''")}'`).join(', ');
        const edgeCypher = `MATCH (c1:Concept)-[r]->(c2:Concept)
                  WHERE c1.concept_id IN [${idList}] AND c2.concept_id IN [${idList}]
                  RETURN c1, r, c2 LIMIT 1000`;
        const stmt = cypherToStatement(edgeCypher, '+');
        const program = { version: 1 as const, statements: [stmt] };
        const programResult = await apiClient.executeProgram({
          program: program as unknown as Record<string, unknown>,
        });

        const mapped = mapWorkingGraphToRawGraph(programResult.result);
        const nodeIdSet = new Set(nodes.map(n => n.id));
        for (const link of mapped.links) {
          if (nodeIdSet.has(link.from_id) && nodeIdSet.has(link.to_id)) {
            links.push({
              source: link.from_id,
              target: link.to_id,
              type: link.relationship_type || 'RELATED',
              visible: true,
            });
          }
        }
      } catch (e) {
        console.warn('Failed to fetch inter-concept edges:', e);
      }

      // Step 6: Build DocumentExplorerData
      const docExplorerDocuments: DocExplorerDocument[] = docResponse.documents.map(d => ({
        id: d.document_id,
        label: d.filename,
        ontology: d.ontology,
        conceptIds: (bulkResponse.documents[d.document_id] || []).map(c => c.concept_id),
        queryConceptIds: d.concept_ids || [],
      }));

      setExplorerData({
        documents: docExplorerDocuments,
        nodes,
        links,
        queryConceptIds: Array.from(queryConceptIds),
      });

    } catch (err) {
      console.error('Failed to build document graph:', err);
      setError('Failed to build document graph');
    } finally {
      setIsLoading(false);
      setLoadingMessage('');
    }
  }, [replayQuery, resetQueries]);

  // ---------------------------------------------------------------------------
  // Callbacks
  // ---------------------------------------------------------------------------

  const handleFocusDocument = useCallback((docId: string) => {
    setFocusedDocId(prev => prev === docId ? null : docId);
  }, []);

  const handleViewDocument = useCallback((doc: SidebarDocument) => {
    setViewingDocument({
      document_id: doc.document_id,
      filename: doc.filename,
      content_type: doc.content_type,
    });
  }, []);

  const handleViewDocumentById = useCallback((docId: string) => {
    const doc = sidebarDocs.find(d => d.document_id === docId);
    if (doc) handleViewDocument(doc);
  }, [sidebarDocs, handleViewDocument]);

  const handleNodeClick = useCallback((nodeId: string) => {
    const doc = sidebarDocs.find(d => d.document_id === nodeId);
    if (doc) {
      handleFocusDocument(nodeId);
    }
  }, [sidebarDocs, handleFocusDocument]);

  const focusedDoc = useMemo(() => {
    if (!focusedDocId || !explorerData) return null;
    return explorerData.documents.find(d => d.id === focusedDocId) || null;
  }, [focusedDocId, explorerData]);

  // ---------------------------------------------------------------------------
  // Tab content: Documents (BookOpen icon)
  // ---------------------------------------------------------------------------
  const documentsTabContent = (
    <div className="flex flex-col h-full">
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-8 gap-2">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          <p className="text-xs text-muted-foreground">{loadingMessage}</p>
        </div>
      ) : sidebarDocs.length > 0 ? (
        <div className="divide-y divide-border">
          {sidebarDocs.map((doc) => (
            <div
              key={doc.document_id}
              className={`flex items-start gap-2 p-3 cursor-pointer hover:bg-accent transition-colors ${
                focusedDocId === doc.document_id ? 'bg-accent' : ''
              }`}
              onClick={() => handleFocusDocument(doc.document_id)}
            >
              <FileText className="h-4 w-4 mt-0.5 text-amber-500 shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium truncate">{doc.filename}</p>
                <p className="text-xs text-muted-foreground">{doc.ontology}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  {doc.concept_ids.length} query / {doc.totalConceptCount} total concepts
                </p>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); handleViewDocument(doc); }}
                className="shrink-0 p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground"
                title="View document"
              >
                <BookOpen className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-muted-foreground text-sm px-4">
          <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
          <p>Load a saved exploration query to discover documents.</p>
        </div>
      )}
    </div>
  );

  // ---------------------------------------------------------------------------
  // Tab content: Passage Search (Search icon)
  // ---------------------------------------------------------------------------
  const passagesTabContent = (
    <div className="flex flex-col h-full">
      {/* Search input — Enter to commit */}
      <div className="p-3 border-b border-border">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={pendingQueryText}
            onChange={(e) => setPendingQueryText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !isCommittingQuery) {
                e.preventDefault();
                handleCommitQuery();
              }
            }}
            placeholder={sidebarDocs.length > 0 ? 'Search passages... (Enter)' : 'Load a query first...'}
            disabled={sidebarDocs.length === 0 || isCommittingQuery}
            className="w-full pl-10 pr-4 py-2 bg-background border border-input rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
          />
          {isCommittingQuery && (
            <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-muted-foreground" />
          )}
        </div>
      </div>

      {/* Query legend */}
      <PassageQueryLegend
        queries={passageQueries}
        onToggle={handleToggleQuery}
        onDelete={handleDeleteQuery}
      />

      {/* Passage results */}
      <div className="flex-1 overflow-y-auto">
        {allVisibleResults.length > 0 ? (
          <div className="divide-y divide-border">
            {allVisibleResults.map((result, i) => (
              <button
                key={`${result.sourceId}-${i}`}
                className="w-full p-3 text-left hover:bg-accent transition-colors"
                onClick={() => handleFocusDocument(result.documentId)}
              >
                <div className="flex items-center gap-1.5 mb-1">
                  <span
                    className="inline-block w-2 h-2 rounded-full shrink-0"
                    style={{ background: result.queryColor }}
                  />
                  <p className="text-xs text-muted-foreground">
                    {result.documentFilename} ({(result.similarity * 100).toFixed(0)}%)
                  </p>
                </div>
                <p className="text-xs line-clamp-3">{result.chunkText}</p>
                {result.concepts.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {result.concepts.slice(0, 3).map(c => (
                      <span key={c.conceptId} className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400">
                        {c.label}
                      </span>
                    ))}
                  </div>
                )}
              </button>
            ))}
          </div>
        ) : sidebarDocs.length > 0 ? (
          <div className="text-center py-8 text-muted-foreground text-sm px-4">
            <Search className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p>Type a phrase and press Enter to search across documents.</p>
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground text-sm px-4">
            <Search className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p>Load a query first, then search passages.</p>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="flex h-full">
      {/* Left rail — all panels */}
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
          {
            id: 'documents',
            icon: BookOpen,
            label: 'Documents',
            content: documentsTabContent,
          },
          {
            id: 'passages',
            icon: Search,
            label: 'Passage Search',
            content: passagesTabContent,
          },
          {
            id: 'settings',
            icon: Settings,
            label: 'Settings',
            content: (
              <ProfilePanel
                settings={settings}
                onChange={setSettings}
              />
            ),
          },
        ]}
        activeTab={activeRailTab}
        onTabChange={setActiveRailTab}
        expandedWidth="w-80"
      />

      {/* Main area — graph */}
      <div className="flex-1 relative">
        {error && (
          <div className="absolute top-2 left-2 right-2 z-10 bg-destructive/10 border border-destructive/30 text-destructive text-sm rounded px-3 py-2">
            {error}
          </div>
        )}
        {isLoading ? (
          <div className="absolute inset-0 flex items-center justify-center bg-background">
            <div className="text-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground mx-auto" />
              <p className="mt-2 text-sm text-muted-foreground">{loadingMessage}</p>
            </div>
          </div>
        ) : explorerData ? (
          <DocumentExplorer
            data={explorerData}
            settings={settings}
            onSettingsChange={setSettings}
            onNodeClick={handleNodeClick}
            focusedDocumentId={focusedDocId}
            onFocusChange={setFocusedDocId}
            onViewDocument={handleViewDocumentById}
            passageRings={passageRings}
            queryColorLabels={queryColorLabels}
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center bg-background">
            <div className="text-center text-muted-foreground">
              <FileText className="h-16 w-16 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium">Document Explorer</p>
              <p className="text-sm mt-1">
                Load a saved exploration query to see<br />
                the multi-document concept graph
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Document Viewer Modal */}
      <DocumentViewer
        document={viewingDocument}
        onClose={() => setViewingDocument(null)}
        highlights={documentHighlights}
        queryLabels={queryColorLabels}
      />
    </div>
  );
};
