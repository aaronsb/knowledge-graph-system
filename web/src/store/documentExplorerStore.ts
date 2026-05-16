/**
 * Document Explorer Session Store
 *
 * Holds in-memory state for the Document Explorer workspace so the
 * loaded graph survives navigation away and back. Mirrors the Force
 * Graph pattern: the data lives in a Zustand store (survives mount /
 * unmount within the session) but is NOT persisted to localStorage —
 * a stale snapshot of document-keyed concept graphs goes wrong the
 * moment the database is re-ingested or the user moves to a different
 * deploy. If we want cross-session persistence later, the saved
 * exploration query is the durable record and the pipeline can replay
 * it on next load (same as Force Graph's autosave).
 *
 * Scope is deliberately narrow: only the state that defines "what was
 * I looking at" lives here. Ephemeral pipeline state (`isLoading`,
 * `error`) and per-mount UI (open document viewer) stay local to the
 * workspace component.
 */

import { create } from 'zustand';
import type { DocumentExplorerData } from '../explorers/DocumentExplorer/types';

export interface SidebarDocument {
  document_id: string;
  filename: string;
  ontology: string;
  content_type: string;
  /** Concepts overlapping with the active query. */
  concept_ids: string[];
  /** All concepts for this document (after hydration). */
  totalConceptCount: number;
}

interface DocumentExplorerStore {
  /** The multi-document concept graph the user loaded. Null until a
   *  saved query is replayed. */
  explorerData: DocumentExplorerData | null;
  /** Document list shown in the sidebar. */
  sidebarDocs: SidebarDocument[];
  /** Currently-focused document id (drives the dim-everything-else mode
   *  in the graph). Null when nothing is focused. */
  focusedDocId: string | null;

  setExplorerData: (data: DocumentExplorerData | null) => void;
  setSidebarDocs: (docs: SidebarDocument[]) => void;
  setFocusedDocId: (id: string | null) => void;
  /** Atomic reset, used at the start of a new query load so we don't
   *  flash partial old state before the new data arrives. */
  reset: () => void;
}

export const useDocumentExplorerStore = create<DocumentExplorerStore>((set) => ({
  explorerData: null,
  sidebarDocs: [],
  focusedDocId: null,
  setExplorerData: (explorerData) => set({ explorerData }),
  setSidebarDocs: (sidebarDocs) => set({ sidebarDocs }),
  setFocusedDocId: (focusedDocId) => set({ focusedDocId }),
  reset: () => set({ explorerData: null, sidebarDocs: [], focusedDocId: null }),
}));
