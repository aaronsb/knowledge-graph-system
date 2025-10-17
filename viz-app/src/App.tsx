/**
 * Main Application Component
 *
 * Integrates React Query, Zustand store, and explorer system.
 * Follows ADR-034 architecture.
 */

import React, { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppLayout } from './components/layout/AppLayout';
import { SearchBar } from './components/shared/SearchBar';
import { useGraphStore } from './store/graphStore';
import { useSubgraph } from './hooks/useGraphData';
import { getExplorer } from './explorers';
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
  const { selectedExplorer, focusedNodeId, graphData: storeGraphData } = useGraphStore();

  // Fetch graph data when a concept is focused (but only if store doesn't have data)
  const { data: fetchedGraphData, isLoading, error } = useSubgraph(focusedNodeId, {
    depth: 2,
    limit: 500,
    enabled: !storeGraphData && !!focusedNodeId, // Only fetch if store is empty
  });

  // Prefer store data over fetched data (allows manual loading via SearchBar)
  const graphData = storeGraphData || fetchedGraphData;

  // Get the current explorer plugin
  const explorerPlugin = getExplorer(selectedExplorer);

  // Local settings state for the current explorer
  const [explorerSettings, setExplorerSettings] = useState(
    explorerPlugin?.defaultSettings || {}
  );

  if (!explorerPlugin) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <h2 className="text-xl font-semibold mb-2">No Explorer Selected</h2>
          <p className="text-muted-foreground">Select an explorer from the sidebar</p>
        </div>
      </div>
    );
  }

  const ExplorerComponent = explorerPlugin.component;
  const SettingsPanelComponent = explorerPlugin.settingsPanel;

  return (
    <AppLayout
      settingsPanel={
        <SettingsPanelComponent settings={explorerSettings} onChange={setExplorerSettings} />
      }
    >
      <div className="h-full flex flex-col">
        {/* Search Bar */}
        <div className="p-4 border-b border-border bg-card">
          <SearchBar />
        </div>

        {/* Visualization Area */}
        <div className="flex-1 relative">
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-background/50 z-10">
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
                <p className="text-muted-foreground">Loading graph data...</p>
              </div>
            </div>
          )}

          {error && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <h3 className="text-lg font-semibold mb-2">Error Loading Data</h3>
                <p className="text-muted-foreground">{(error as Error).message}</p>
              </div>
            </div>
          )}

          {!graphData && !isLoading && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center max-w-md">
                <h3 className="text-xl font-semibold mb-2">Welcome to Knowledge Graph Visualization</h3>
                <p className="text-muted-foreground mb-4">
                  Search for a concept above to start exploring the graph
                </p>
                <div className="text-sm text-muted-foreground">
                  <p>Tips:</p>
                  <ul className="mt-2 space-y-1 text-left">
                    <li>• Use the search bar to find concepts</li>
                    <li>• Click nodes to explore connections</li>
                    <li>• Adjust settings in the right panel</li>
                    <li>• Drag nodes to reposition them</li>
                  </ul>
                </div>
              </div>
            </div>
          )}

          {graphData && !isLoading && (
            <ExplorerComponent
              data={graphData}
              settings={explorerSettings}
              onNodeClick={(nodeId) => {
                // Update focused node when clicking
                useGraphStore.getState().setFocusedNodeId(nodeId);
              }}
            />
          )}
        </div>
      </div>
    </AppLayout>
  );
};

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}

export default App;
