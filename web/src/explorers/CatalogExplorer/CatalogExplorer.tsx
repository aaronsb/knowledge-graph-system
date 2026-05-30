/**
 * Catalog Explorer (ADR-501)
 *
 * Deterministic, folder-style browse of the knowledge graph:
 * ontology -> document -> concept. Answers "what's actually in here?" — the
 * structural complement to the semantic graph/search explorers.
 *
 * Self-fetching (like DocumentExplorer): it pulls each tree level from
 * /catalog on demand rather than consuming a preloaded rawGraphData blob, so
 * its ExplorerProps.data is unused.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Search, RefreshCw, FolderTree } from 'lucide-react';
import type { ExplorerProps } from '../../types/explorer';
import { useCatalogExplorerStore } from '../../store/catalogExplorerStore';
import { CatalogTree } from './CatalogTree';
import { CatalogDetailPanel } from './CatalogDetailPanel';
import type { CatalogExplorerData, CatalogExplorerSettings } from './types';
import { DEFAULT_SETTINGS } from './types';

export const CatalogExplorer: React.FC<
  ExplorerProps<CatalogExplorerData, CatalogExplorerSettings>
> = ({ settings }) => {
  const effective = settings || DEFAULT_SETTINGS;

  const filter = useCatalogExplorerStore((s) => s.filter);
  const setFilter = useCatalogExplorerStore((s) => s.setFilter);
  const selected = useCatalogExplorerStore((s) => s.selected);
  const stale = useCatalogExplorerStore((s) => s.stale);
  const reset = useCatalogExplorerStore((s) => s.reset);

  // Debounce the filter input into the store (which drives re-fetch). Reset
  // cached children when the filter changes so collapsed branches re-query
  // under the new fragment on next expand.
  const [input, setInput] = useState(filter);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => {
      if (input !== filter) {
        reset();
        setFilter(input);
      }
    }, 300);
    return () => {
      if (debounce.current) clearTimeout(debounce.current);
    };
  }, [input, filter, reset, setFilter]);

  const refresh = useCallback(() => {
    reset();
    setFilter(filter); // no-op value change; reset() already cleared caches
  }, [reset, setFilter, filter]);

  return (
    <div className="flex h-full">
      {/* Tree pane */}
      <div className="flex flex-col flex-1 min-w-0 border-r border-border">
        <div className="flex items-center gap-2 px-3 py-2 border-b border-border">
          <FolderTree className="w-4 h-4 text-amber-500 flex-shrink-0" />
          <span className="text-sm font-medium">Catalog</span>
          <div className="flex-1" />
          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Filter by name…"
              className="pl-7 pr-2 py-1 text-sm bg-background border border-border rounded w-48 focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <button
            onClick={refresh}
            title="Refresh from graph"
            className="p-1 rounded hover:bg-muted text-muted-foreground"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {stale && (
          <div className="px-3 py-1 text-xs text-amber-600 bg-amber-500/10 border-b border-border">
            Index is catching up to recent graph changes — counts may lag briefly.
          </div>
        )}

        <div className="flex-1 overflow-auto">
          <CatalogTree settings={effective} />
        </div>
      </div>

      {/* Detail pane */}
      <div className="w-80 flex-shrink-0 overflow-auto">
        <CatalogDetailPanel node={selected} />
      </div>
    </div>
  );
};
