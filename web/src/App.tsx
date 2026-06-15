/**
 * Main Application Component
 *
 * Integrates React Query, Zustand store, and workstation routing.
 * Follows ADR-710 and ADR-714 architecture.
 */

import React, { useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { Loader2 } from 'lucide-react';
import { OAuthCallback } from './components/auth/OAuthCallback';
import { ProtectedView } from './components/auth/ProtectedView';
import { useVocabularyStore } from './store/vocabularyStore';
import { useAuthStore } from './store/authStore';
import { useThemeStore } from './store/themeStore';
import { useThemeHarmony } from './hooks/useThemeHarmony';
import { apiClient } from './api/client';

// Explorer view (existing functionality)
import { ExplorerView } from './views/ExplorerView';

// Workspace components
import { BlockEditorWorkspace } from './components/blocks/BlockEditorWorkspace';
import { IngestWorkspace } from './components/ingest/IngestWorkspace';
import { JobsWorkspace } from './components/jobs/JobsWorkspace';
import { ReportWorkspace } from './components/report/ReportWorkspace';
import { PolarityExplorerWorkspace } from './components/polarity/PolarityExplorerWorkspace';
import { GraphEditor } from './components/edit/GraphEditor';
import { PreferencesWorkspace } from './components/preferences/PreferencesWorkspace';
import { AdminDashboard } from './components/admin/AdminDashboard';
import { HomeWorkspace } from './components/home/HomeWorkspace';
import { EdgeExplorerWorkspace } from './components/vocabulary/EdgeExplorerWorkspace';
import { VocabularyChordWorkspace } from './components/vocabulary/VocabularyChordWorkspace';
import { EmbeddingLandscapeWorkspace } from './components/embeddings';
import { DocumentExplorerWorkspace } from './components/documents/DocumentExplorerWorkspace';
import { CatalogExplorerWorkspace } from './components/catalog/CatalogExplorerWorkspace';

import './explorers'; // Import to register explorers

// Create React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

const AppContent: React.FC = () => {
  const { setTypes, setLoading, setError } = useVocabularyStore();
  const { checkAuth, sessionStatus, hydrated } = useAuthStore();
  const isAuthenticated = sessionStatus === 'authenticated';  // ADR-705
  const { theme, setTheme } = useThemeStore();

  // Initialize theme harmony (applies stored color settings)
  useThemeHarmony();

  // Initialize theme on mount
  useEffect(() => {
    setTheme(theme);
  }, []);

  // Check authentication status on mount
  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  // Load vocabulary only when authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      return; // Don't load vocabulary until authenticated
    }

    const loadVocabulary = async () => {
      setLoading(true);
      try {
        // First load existing vocabulary (include inactive types that may still be in use)
        const response = await apiClient.getVocabularyTypes({
          include_inactive: true, // Include all types, even inactive ones
          include_builtin: true,
        });
        const types = response.types || [];

        // Check if any types (active or inactive but with edge_count > 0) are missing categories
        const typesWithoutCategory = types.filter((t: any) =>
          t.edge_count > 0 && !t.category
        );

        if (typesWithoutCategory.length > 0) {
          console.log(`⚠️ Found ${typesWithoutCategory.length} types without categories, refreshing...`);

          // Trigger category refresh
          await apiClient.refreshVocabularyCategories({ only_computed: true });

          // Reload vocabulary after refresh (include inactive again)
          const refreshedResponse = await apiClient.getVocabularyTypes({
            include_inactive: true,
            include_builtin: true,
          });
          setTypes(refreshedResponse.types || []);
          console.log(`✅ Refreshed and loaded ${refreshedResponse.types?.length || 0} vocabulary types`);
        } else {
          setTypes(types);
          console.log(`✅ Loaded ${types.length} vocabulary types (all have categories)`);
        }

        // Log category distribution
        const categoryCount: Record<string, number> = {};
        const currentTypes = useVocabularyStore.getState().types;
        currentTypes.forEach((t: any) => {
          categoryCount[t.category] = (categoryCount[t.category] || 0) + 1;
        });
        console.log('📊 Category distribution:', categoryCount);
      } catch (error) {
        console.error('❌ Failed to load vocabulary:', error);
        setError(error instanceof Error ? error.message : 'Failed to load vocabulary');
      }
    };
    loadVocabulary();
  }, [isAuthenticated]); // Re-run when authentication changes

  // ADR-705: until the initial checkAuth (including any token refresh) resolves,
  // sessionStatus is still the default 'anonymous'. Render a neutral loader
  // rather than flashing signed-out content (LoggedOutView / guest banner) to an
  // already-authenticated user on a hard load.
  if (!hydrated) {
    return (
      <div className="h-screen flex items-center justify-center bg-background text-muted-foreground">
        <Loader2 className="w-6 h-6 animate-spin" />
      </div>
    );
  }

  return (
    <AppLayout>
      <Routes>
        {/* Home - welcome and login page (its own signed-out welcome) */}
        <Route path="/" element={<HomeWorkspace />} />

        {/* Content routes are wrapped in <ProtectedView> (ADR-705): when signed
            out, the workspace doesn't mount/fetch/401 — a consistent
            LoggedOutView (with the workstation guide) renders instead. */}

        {/* Explorers */}
        <Route path="/explore/graph" element={<ProtectedView what="the graph"><ExplorerView explorerType="force-graph" /></ProtectedView>} />
        {/* Legacy public routes — preserve bookmarks. The unified plugin
            owns projection via its settings panel, so the URL no longer
            encodes 2D vs 3D. Search params (concept ids, depth, etc.) carry over. */}
        <Route path="/explore/2d" element={<RedirectPreservingSearch to="/explore/graph" />} />
        <Route path="/explore/3d" element={<RedirectPreservingSearch to="/explore/graph" />} />
        <Route path="/explore/documents" element={<ProtectedView what="documents"><DocumentExplorerWorkspace /></ProtectedView>} />
        <Route path="/explore/catalog" element={<ProtectedView what="the catalog"><CatalogExplorerWorkspace /></ProtectedView>} />

        {/* Block Editor */}
        <Route path="/blocks" element={<ProtectedView what="the block editor"><BlockEditorWorkspace /></ProtectedView>} />
        <Route path="/blocks/:diagramId" element={<ProtectedView what="the block editor"><BlockEditorWorkspace /></ProtectedView>} />

        {/* Ingest */}
        <Route path="/ingest" element={<ProtectedView what="ingestion"><IngestWorkspace /></ProtectedView>} />

        {/* Jobs */}
        <Route path="/jobs" element={<ProtectedView what="jobs"><JobsWorkspace /></ProtectedView>} />

        {/* Report */}
        <Route path="/report" element={<ProtectedView what="reports"><ReportWorkspace /></ProtectedView>} />

        {/* Polarity Explorer (ADR-813) */}
        <Route path="/polarity" element={<ProtectedView what="polarity"><PolarityExplorerWorkspace /></ProtectedView>} />

        {/* Vocabulary Explorer (ADR-611) */}
        <Route path="/vocabulary" element={<ProtectedView what="the vocabulary graph"><EdgeExplorerWorkspace /></ProtectedView>} />
        <Route path="/vocabulary/chord" element={<ProtectedView what="vocabulary analysis"><VocabularyChordWorkspace /></ProtectedView>} />

        {/* Embedding Landscape (ADR-717) */}
        <Route path="/embeddings" element={<ProtectedView what="the embedding landscape"><EmbeddingLandscapeWorkspace /></ProtectedView>} />

        {/* Edit */}
        <Route path="/edit" element={<ProtectedView what="the graph editor"><GraphEditor /></ProtectedView>} />

        {/* Preferences */}
        <Route path="/preferences" element={<ProtectedView what="preferences"><PreferencesWorkspace /></ProtectedView>} />

        {/* Admin */}
        <Route path="/admin" element={<ProtectedView what="administration"><AdminDashboard /></ProtectedView>} />
      </Routes>
    </AppLayout>
  );
};

/** Redirect that preserves the incoming `?…` search string. Used to keep
 *  legacy explorer routes (`/explore/2d`, `/explore/3d`) honoring their
 *  bookmarked concept-id and depth query params after consolidation. */
const RedirectPreservingSearch: React.FC<{ to: string }> = ({ to }) => {
  const { search } = useLocation();
  return <Navigate to={`${to}${search}`} replace />;
};

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/callback" element={<OAuthCallback />} />
          <Route path="/*" element={<AppContent />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
