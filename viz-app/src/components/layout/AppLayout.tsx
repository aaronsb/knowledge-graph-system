/**
 * Main Application Layout
 *
 * Provides the overall structure:
 * - Sidebar with explorer selection
 * - Main visualization area
 * - Settings panel (collapsible)
 */

import React, { useState } from 'react';
import { User, ChevronRight } from 'lucide-react';
import { useGraphStore } from '../../store/graphStore';
import { getAllExplorers } from '../../explorers';

interface AppLayoutProps {
  children: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const { selectedExplorer, setSelectedExplorer } = useGraphStore();

  const explorers = getAllExplorers();

  return (
    <div className="flex h-screen bg-background text-foreground">
      {/* Sidebar - Explorer Selection */}
      <aside className="w-64 border-r border-border bg-card flex flex-col">
        <div className="p-4 border-b border-border">
          <h1 className="text-xl font-bold">Knowledge Graph</h1>
          <p className="text-sm text-muted-foreground">Visualization Explorer</p>
        </div>

        <nav className="flex-1 p-4">
          <h2 className="text-sm font-semibold text-muted-foreground mb-3 uppercase">
            Explorers
          </h2>

          <div className="space-y-2">
            {explorers.map((explorer) => {
              const Icon = explorer.config.icon;
              const isSelected = explorer.config.type === selectedExplorer;

              return (
                <button
                  key={explorer.config.id}
                  onClick={() => setSelectedExplorer(explorer.config.type)}
                  className={`
                    w-full flex items-center gap-3 px-3 py-2 rounded-lg
                    transition-colors text-left
                    ${
                      isSelected
                        ? 'bg-primary text-primary-foreground'
                        : 'hover:bg-accent hover:text-accent-foreground'
                    }
                  `}
                >
                  <Icon className="w-5 h-5" />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate">{explorer.config.name}</div>
                    <div className="text-xs opacity-80 truncate">
                      {explorer.config.description}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </nav>

        <div className="p-4 border-t border-border">
          <div className="text-xs text-muted-foreground">
            <div>API: localhost:8000</div>
            <div className="mt-1">Status: Connected</div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Toolbar */}
        <header className="h-14 border-b border-border bg-card px-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h2 className="font-semibold">
              {explorers.find((e) => e.config.type === selectedExplorer)?.config.name ||
                'Explorer'}
            </h2>
          </div>

          <button
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-accent hover:text-accent-foreground transition-colors"
            title="User Profile (Coming Soon)"
          >
            <User className="w-4 h-4" />
            <span>Profile</span>
          </button>
        </header>

        {/* Visualization Area */}
        <div className="flex-1 overflow-hidden">{children}</div>
      </main>
    </div>
  );
};
