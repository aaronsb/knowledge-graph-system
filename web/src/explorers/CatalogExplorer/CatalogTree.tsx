/**
 * Catalog Tree (ADR-501)
 *
 * Lazy-expanding folder tree over the ontology -> document -> concept
 * hierarchy. Each level is fetched on demand from /catalog/children via the
 * shared apiClient and cached in catalogExplorerStore so a browse session
 * survives navigation. Leaf concepts are not expandable.
 *
 * Reuses the project's design tokens (Tailwind semantic classes already used
 * across explorers) and lucide icons rather than introducing new styling.
 */

import React, { useCallback, useEffect } from 'react';
import {
  ChevronRight,
  ChevronDown,
  FolderTree,
  FileText,
  Image as ImageIcon,
  Circle,
  Loader2,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import {
  useCatalogExplorerStore,
  CATALOG_ROOT_KEY,
} from '../../store/catalogExplorerStore';
import type { CatalogNode, CatalogKind } from '../../types/catalog';
import type { CatalogExplorerSettings } from './types';

/** Which kind a node's children are, per the fixed hierarchy. */
const CHILD_KIND: Record<CatalogKind, CatalogKind | null> = {
  ontology: 'document',
  document: 'concept',
  concept: null,
};

function NodeIcon({ node }: { node: CatalogNode }) {
  if (node.kind === 'ontology') return <FolderTree className="w-4 h-4 text-amber-500" />;
  if (node.kind === 'document') {
    return node.content_type === 'image' ? (
      <ImageIcon className="w-4 h-4 text-sky-500" />
    ) : (
      <FileText className="w-4 h-4 text-sky-400" />
    );
  }
  return <Circle className="w-2.5 h-2.5 text-muted-foreground ml-0.5" />;
}

interface TreeRowProps {
  node: CatalogNode;
  depth: number;
  settings: CatalogExplorerSettings;
}

const TreeRow: React.FC<TreeRowProps> = ({ node, depth, settings }) => {
  const expanded = useCatalogExplorerStore((s) => s.expanded[node.id] || false);
  const children = useCatalogExplorerStore((s) => s.childrenByParent[node.id]);
  const total = useCatalogExplorerStore((s) => s.totalByParent[node.id]);
  const loading = useCatalogExplorerStore((s) => s.loading[node.id] || false);
  const selected = useCatalogExplorerStore((s) => s.selected?.id === node.id);
  const filter = useCatalogExplorerStore((s) => s.filter);
  const setChildren = useCatalogExplorerStore((s) => s.setChildren);
  const setExpanded = useCatalogExplorerStore((s) => s.setExpanded);
  const setLoading = useCatalogExplorerStore((s) => s.setLoading);
  const setSelected = useCatalogExplorerStore((s) => s.setSelected);
  const setStale = useCatalogExplorerStore((s) => s.setStale);

  const childKind = CHILD_KIND[node.kind];
  const expandable = childKind !== null;

  const fetchChildren = useCallback(async () => {
    if (!childKind) return;
    setLoading(node.id, true);
    try {
      const res = await apiClient.listCatalogChildren({
        parent: node.id,
        parent_kind: node.kind,
        q: filter || undefined,
        sort: settings.sort,
        limit: 200,
      });
      setChildren(node.id, res.nodes, res.total);
      setStale(res.stale);
    } finally {
      setLoading(node.id, false);
    }
  }, [node.id, node.kind, childKind, filter, settings.sort, setChildren, setLoading, setStale]);

  const toggle = useCallback(() => {
    if (!expandable) {
      setSelected(node);
      return;
    }
    const next = !expanded;
    setExpanded(node.id, next);
    setSelected(node);
    if (next && children === undefined) {
      void fetchChildren();
    }
  }, [expandable, expanded, node, children, setExpanded, setSelected, fetchChildren]);

  return (
    <div>
      <div
        className={`flex items-center gap-1.5 py-1 px-2 rounded cursor-pointer hover:bg-muted ${
          selected ? 'bg-muted' : ''
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={toggle}
      >
        <span className="w-4 flex-shrink-0">
          {expandable ? (
            loading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />
            ) : expanded ? (
              <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
            )
          ) : null}
        </span>
        <NodeIcon node={node} />
        <span className="text-sm truncate flex-1">{node.name}</span>
        {settings.showCounts && node.child_count != null && node.kind !== 'concept' && (
          <span className="text-xs text-muted-foreground tabular-nums">{node.child_count}</span>
        )}
      </div>

      {expanded && children && (
        <div>
          {children.length === 0 ? (
            <div
              className="text-xs text-muted-foreground italic py-1"
              style={{ paddingLeft: `${(depth + 1) * 16 + 28}px` }}
            >
              {filter ? 'no matches' : 'empty'}
            </div>
          ) : (
            children.map((child) => (
              <TreeRow key={`${child.kind}:${child.id}`} node={child} depth={depth + 1} settings={settings} />
            ))
          )}
          {total != null && children.length < total && (
            <div
              className="text-xs text-muted-foreground py-1"
              style={{ paddingLeft: `${(depth + 1) * 16 + 28}px` }}
            >
              showing {children.length} of {total}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

interface CatalogTreeProps {
  settings: CatalogExplorerSettings;
}

/** Root of the tree — fetches and renders the ontology level. */
export const CatalogTree: React.FC<CatalogTreeProps> = ({ settings }) => {
  const roots = useCatalogExplorerStore((s) => s.childrenByParent[CATALOG_ROOT_KEY]);
  const total = useCatalogExplorerStore((s) => s.totalByParent[CATALOG_ROOT_KEY]);
  const loading = useCatalogExplorerStore((s) => s.loading[CATALOG_ROOT_KEY] || false);
  const filter = useCatalogExplorerStore((s) => s.filter);
  const setChildren = useCatalogExplorerStore((s) => s.setChildren);
  const setLoading = useCatalogExplorerStore((s) => s.setLoading);
  const setStale = useCatalogExplorerStore((s) => s.setStale);

  const fetchRoots = useCallback(async () => {
    setLoading(CATALOG_ROOT_KEY, true);
    try {
      const res = await apiClient.listCatalogChildren({
        q: filter || undefined,
        sort: settings.sort,
        limit: 500,
      });
      setChildren(CATALOG_ROOT_KEY, res.nodes, res.total);
      setStale(res.stale);
    } finally {
      setLoading(CATALOG_ROOT_KEY, false);
    }
  }, [filter, settings.sort, setChildren, setLoading, setStale]);

  // Fetch root ontologies on mount, when the filter changes, or sort changes.
  useEffect(() => {
    void fetchRoots();
  }, [fetchRoots]);

  if (loading && roots === undefined) {
    return (
      <div className="flex items-center justify-center py-8 text-muted-foreground">
        <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading catalog…
      </div>
    );
  }

  if (roots && roots.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground text-sm">
        {filter ? `No ontologies match “${filter}”` : 'The knowledge graph is empty.'}
      </div>
    );
  }

  return (
    <div className="py-1">
      {(roots || []).map((node) => (
        <TreeRow key={`${node.kind}:${node.id}`} node={node} depth={0} settings={settings} />
      ))}
      {total != null && (roots?.length || 0) < total && (
        <div className="text-xs text-muted-foreground px-2 py-1">
          showing {roots?.length || 0} of {total} ontologies
        </div>
      )}
    </div>
  );
};
