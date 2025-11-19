/**
 * Main Application Component
 *
 * Integrates React Query, Zustand store, and workstation routing.
 * Follows ADR-034 and ADR-067 architecture.
 */

import React, { useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { OAuthCallback } from './components/auth/OAuthCallback';
import { useVocabularyStore } from './store/vocabularyStore';
import { useAuthStore } from './store/authStore';
import { useThemeStore } from './store/themeStore';
import { apiClient } from './api/client';

// Explorer view (existing functionality)
import { ExplorerView } from './views/ExplorerView';

// Workspace components
import { BlockEditorWorkspace } from './components/blocks/BlockEditorWorkspace';
import { IngestWorkspace } from './components/ingest/IngestWorkspace';
import { JobsWorkspace } from './components/jobs/JobsWorkspace';
import { ReportWorkspace } from './components/report/ReportWorkspace';
import { GraphEditor } from './components/edit/GraphEditor';
import { AdminDashboard } from './components/admin/AdminDashboard';

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
  const { checkAuth } = useAuthStore();
  const { theme, setTheme } = useThemeStore();

  // Initialize theme on mount
  useEffect(() => {
    setTheme(theme);
  }, []);

  // Check authentication status on mount
  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  // Load vocabulary on mount
  useEffect(() => {
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
  }, []); // Run once on mount

  return (
    <AppLayout>
      <Routes>
        {/* Default redirect to 2D explorer */}
        <Route path="/" element={<Navigate to="/explore/2d" replace />} />

        {/* Explorers */}
        <Route path="/explore/2d" element={<ExplorerView explorerType="force-2d" />} />
        <Route path="/explore/3d" element={<ExplorerView explorerType="force-3d" />} />

        {/* Block Editor */}
        <Route path="/blocks" element={<BlockEditorWorkspace />} />
        <Route path="/blocks/:diagramId" element={<BlockEditorWorkspace />} />

        {/* Ingest */}
        <Route path="/ingest" element={<IngestWorkspace />} />

        {/* Jobs */}
        <Route path="/jobs" element={<JobsWorkspace />} />

        {/* Report */}
        <Route path="/report" element={<ReportWorkspace />} />

        {/* Edit */}
        <Route path="/edit" element={<GraphEditor />} />

        {/* Admin */}
        <Route path="/admin" element={<AdminDashboard />} />
      </Routes>
    </AppLayout>
  );
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
