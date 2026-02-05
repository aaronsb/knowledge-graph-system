/**
 * usePassageSearch — Multi-query passage search hook.
 *
 * Manages the committed query stack, ring data derivation, document highlights,
 * and visible result aggregation for the Document Explorer workspace.
 */

import { useState, useCallback, useMemo, useRef } from 'react';
import { apiClient } from '../api/client';
import { getNextQueryColor } from '../utils/queryColors';
import type { PassageQuery, PassageSearchResult, DocumentHighlight } from '../explorers/DocumentExplorer/types';

/** Minimal document info needed for scoped passage search. */
interface SearchableDocument {
  document_id: string;
  filename: string;
  ontology: string;
}

/** Ring entry for a single query hit on a node. */
export interface NodeRingEntry {
  color: string;
  hitCount: number;
  maxHitCount: number;
  bestSimilarity: number;
}

export function usePassageSearch(
  sidebarDocs: SearchableDocument[],
  viewingDocumentId: string | null,
) {
  const [passageQueries, setPassageQueries] = useState<PassageQuery[]>([]);
  const [pendingQueryText, setPendingQueryText] = useState('');
  const [isCommittingQuery, setIsCommittingQuery] = useState(false);
  const queriesRef = useRef(passageQueries);
  queriesRef.current = passageQueries;
  const queryIdRef = useRef(0);

  /** Reset all queries (e.g. when a new exploration loads). */
  const resetQueries = useCallback(() => {
    setPassageQueries([]);
    setPendingQueryText('');
  }, []);

  /** Commit a passage search query — Enter key handler. */
  const handleCommitQuery = useCallback(async () => {
    const text = pendingQueryText.trim();
    if (!text || sidebarDocs.length === 0) return;

    // Read current queries from ref to avoid stale closure on rapid commits
    const currentQueries = queriesRef.current;
    if (currentQueries.some(q => q.text === text)) {
      setPendingQueryText('');
      return;
    }

    setIsCommittingQuery(true);
    try {
      const docIds = sidebarDocs.map(d => d.document_id);
      // Very short queries (1-2 chars) produce noisy embeddings — raise threshold
      const minSim = text.length <= 2 ? 0.7 : 0.5;
      // Over-fetch to allow per-document diversification
      const response = await apiClient.searchSources({
        query: text,
        document_ids: docIds,
        limit: 50,
        min_similarity: minSim,
        include_concepts: true,
        include_full_text: false,
      });

      const docLookup = new Map(sidebarDocs.map(d => [d.document_id, d]));
      const allResults: PassageSearchResult[] = (response.results || []).map((r: any) => {
        const doc = docLookup.get(r.document_id) || sidebarDocs.find(d => d.ontology === r.document);
        return {
          sourceId: r.source_id,
          documentId: doc?.document_id || '',
          documentFilename: doc?.filename || r.document,
          paragraph: r.paragraph,
          chunkText: r.matched_chunk?.chunk_text || '',
          similarity: r.similarity,
          startOffset: r.matched_chunk?.start_offset ?? 0,
          endOffset: r.matched_chunk?.end_offset ?? 0,
          concepts: (r.concepts || []).map((c: any) => ({
            conceptId: c.concept_id,
            label: c.label,
          })),
        };
      });

      // Per-document cap: max 3 passages per document to prevent large-doc bias.
      // Results are already sorted by similarity from the API.
      const perDocCount = new Map<string, number>();
      const MAX_PER_DOC = 3;
      const results = allResults.filter(r => {
        const count = perDocCount.get(r.documentId) || 0;
        if (count >= MAX_PER_DOC) return false;
        perDocCount.set(r.documentId, count + 1);
        return true;
      }).slice(0, 20);

      const newQuery: PassageQuery = {
        id: String(++queryIdRef.current),
        text,
        color: getNextQueryColor(queriesRef.current),
        visible: true,
        results,
      };

      setPassageQueries(prev => [...prev, newQuery]);
      setPendingQueryText('');
    } catch (err) {
      console.warn('Passage search failed:', err);
    } finally {
      setIsCommittingQuery(false);
    }
  }, [pendingQueryText, sidebarDocs]);

  const handleToggleQuery = useCallback((id: string) => {
    setPassageQueries(prev =>
      prev.map(q => q.id === id ? { ...q, visible: !q.visible } : q)
    );
  }, []);

  const handleDeleteQuery = useCallback((id: string) => {
    setPassageQueries(prev => prev.filter(q => q.id !== id));
  }, []);

  // ---------------------------------------------------------------------------
  // Ring data — derived from visible queries
  // ---------------------------------------------------------------------------

  const passageRings = useMemo(() => {
    const countMap = new Map<string, Map<string, { color: string; hitCount: number; bestSimilarity: number }>>();

    for (const query of passageQueries) {
      if (!query.visible) continue;

      const queryWords = query.text.toLowerCase().split(/\s+/).filter(w => w.length > 0);
      const wordPatterns = queryWords.map(w =>
        new RegExp(`\\b${w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i')
      );

      const addHit = (nodeId: string, similarity: number) => {
        let nodeEntries = countMap.get(nodeId);
        if (!nodeEntries) { nodeEntries = new Map(); countMap.set(nodeId, nodeEntries); }
        const existing = nodeEntries.get(query.color);
        if (existing) {
          existing.hitCount++;
          existing.bestSimilarity = Math.max(existing.bestSimilarity, similarity);
        } else {
          nodeEntries.set(query.color, { color: query.color, hitCount: 1, bestSimilarity: similarity });
        }
      };

      for (const result of query.results) {
        if (result.documentId) addHit(result.documentId, result.similarity);
        for (const concept of result.concepts) {
          if (wordPatterns.some(p => p.test(concept.label))) {
            addHit(concept.conceptId, result.similarity);
          }
        }
      }
    }

    let maxHitCount = 1;
    for (const nodeEntries of countMap.values()) {
      for (const entry of nodeEntries.values()) {
        if (entry.hitCount > maxHitCount) maxHitCount = entry.hitCount;
      }
    }

    const ringMap = new Map<string, NodeRingEntry[]>();
    for (const [nodeId, nodeEntries] of countMap) {
      ringMap.set(nodeId, Array.from(nodeEntries.values()).map(e => ({
        ...e,
        maxHitCount,
      })));
    }

    return ringMap;
  }, [passageQueries]);

  // Color → query text lookup for labeling rings in info dialogs
  const queryColorLabels = useMemo(() => {
    const map = new Map<string, string>();
    for (const q of passageQueries) {
      if (q.visible) map.set(q.color, q.text);
    }
    return map;
  }, [passageQueries]);

  // ---------------------------------------------------------------------------
  // Document highlights — derived from visible queries for the open document
  // ---------------------------------------------------------------------------

  const documentHighlights = useMemo<DocumentHighlight[]>(() => {
    if (!viewingDocumentId) return [];

    const highlights: DocumentHighlight[] = [];
    for (const query of passageQueries) {
      if (!query.visible) continue;
      for (const result of query.results) {
        if (result.documentId === viewingDocumentId && result.chunkText) {
          highlights.push({
            queryId: query.id,
            color: query.color,
            sourceId: result.sourceId,
            chunkText: result.chunkText,
            startOffset: result.startOffset,
            endOffset: result.endOffset,
          });
        }
      }
    }
    return highlights;
  }, [passageQueries, viewingDocumentId]);

  // ---------------------------------------------------------------------------
  // All passage results from visible queries (for sidebar display)
  // ---------------------------------------------------------------------------

  const allVisibleResults = useMemo(() => {
    const results: Array<PassageSearchResult & { queryColor: string }> = [];
    for (const query of passageQueries) {
      if (!query.visible) continue;
      for (const result of query.results) {
        results.push({ ...result, queryColor: query.color });
      }
    }
    return results;
  }, [passageQueries]);

  return {
    // State
    passageQueries,
    pendingQueryText,
    setPendingQueryText,
    isCommittingQuery,
    // Actions
    handleCommitQuery,
    handleToggleQuery,
    handleDeleteQuery,
    resetQueries,
    // Derived
    passageRings,
    queryColorLabels,
    documentHighlights,
    allVisibleResults,
  };
}
