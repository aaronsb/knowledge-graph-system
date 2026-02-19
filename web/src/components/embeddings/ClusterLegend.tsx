/**
 * ClusterLegend — interactive legend for DBSCAN cluster visualization.
 *
 * Shows palette switcher, sortable cluster list with toggle-to-highlight,
 * and noise count. Extracted from EmbeddingLandscapeWorkspace for clarity.
 */

import type { ClusterPalette } from './types';

/** 20-color palettes designed for dark backgrounds. */
export const CLUSTER_PALETTES: Record<ClusterPalette, { label: string; colors: string[] }> = {
  bold: {
    label: 'Bold',
    colors: [
      '#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4',
      '#42d4f4', '#f032e6', '#bfef45', '#fabed4', '#469990',
      '#dcbeff', '#9a6324', '#fffac8', '#800000', '#aaffc3',
      '#808000', '#ffd8b1', '#000075', '#a9a9a9', '#ffe119',
    ],
  },
  'warm-cool': {
    label: 'Warm → Cool',
    colors: [
      '#ff1744', '#ff5722', '#ff9100', '#ffab00', '#ffd600',
      '#c6ff00', '#76ff03', '#00e676', '#1de9b6', '#00e5ff',
      '#00b0ff', '#2979ff', '#3d5afe', '#651fff', '#d500f9',
      '#ff4081', '#ff6e40', '#ffab40', '#69f0ae', '#40c4ff',
    ],
  },
  earth: {
    label: 'Earth',
    colors: [
      '#bf360c', '#e65100', '#f57f17', '#827717', '#33691e',
      '#1b5e20', '#004d40', '#006064', '#01579b', '#0d47a1',
      '#1a237e', '#311b92', '#4a148c', '#880e4f', '#b71c1c',
      '#3e2723', '#455a64', '#546e7a', '#78909c', '#8d6e63',
    ],
  },
};
export const CLUSTER_PALETTE_ORDER: ClusterPalette[] = ['bold', 'warm-cool', 'earth'];
export const NOISE_COLOR = '#555555';

/** Get the palette color for a cluster id. */
export function clusterColor(palette: ClusterPalette, clusterId: number): string {
  const colors = CLUSTER_PALETTES[palette].colors;
  return colors[clusterId % colors.length];
}

export type ClusterSortKey = 'color' | 'count' | 'name';

interface Props {
  clusterCount: number;
  clusterSizes: Record<string, number>;
  clusterNames: Record<string, string>;
  noiseCount: number;
  highlightedClusters: Set<number> | null;
  onHighlightChange: (clusters: Set<number> | null) => void;
  palette: ClusterPalette;
  onPaletteChange: (palette: ClusterPalette) => void;
  sort: { key: ClusterSortKey; desc: boolean };
  onSortChange: (sort: { key: ClusterSortKey; desc: boolean }) => void;
}

export function ClusterLegend({
  clusterCount,
  clusterSizes,
  clusterNames,
  noiseCount,
  highlightedClusters,
  onHighlightChange,
  palette,
  onPaletteChange,
  sort,
  onSortChange,
}: Props) {
  if (clusterCount <= 0) {
    return (
      <div className="text-[10px] text-muted-foreground/60">
        No clusters — regenerate projection
      </div>
    );
  }

  const sortColumns = [
    { key: 'color' as const, label: '●', width: 'w-2.5', title: 'Sort by palette order' },
    { key: 'name' as const, label: 'Name', width: 'flex-1', title: 'Sort by name' },
    { key: 'count' as const, label: '#', width: 'w-6', title: 'Sort by count' },
  ] as const;

  const entries = Object.entries(clusterSizes)
    .map(([clusterId, size]) => ({
      id: parseInt(clusterId),
      name: clusterNames[clusterId] || `Cluster ${clusterId}`,
      size,
    }))
    .sort((a, b) => {
      let cmp: number;
      switch (sort.key) {
        case 'color':
          cmp = (a.id % CLUSTER_PALETTES[palette].colors.length)
              - (b.id % CLUSTER_PALETTES[palette].colors.length);
          break;
        case 'count':
          cmp = a.size - b.size;
          break;
        case 'name':
        default:
          cmp = a.name.localeCompare(b.name);
          break;
      }
      return sort.desc ? -cmp : cmp;
    });

  return (
    <div className="space-y-0.5">
      {/* Palette switcher */}
      <div className="flex gap-0.5 rounded overflow-hidden mb-1.5" style={{ width: '160px' }}>
        {CLUSTER_PALETTE_ORDER.map((p) => (
          <button
            key={p}
            onClick={() => onPaletteChange(p)}
            className={`flex-1 py-1 text-[10px] transition-colors ${
              palette === p
                ? 'bg-primary/30 text-primary'
                : 'bg-accent/30 text-muted-foreground hover:bg-accent/50'
            }`}
          >
            {CLUSTER_PALETTES[p].label}
          </button>
        ))}
      </div>

      {/* Clear filter button */}
      {highlightedClusters !== null && (
        <button
          onClick={() => onHighlightChange(null)}
          className="text-[10px] text-primary hover:text-primary/80 mb-1 underline"
        >
          Show all
        </button>
      )}

      {/* Sort header */}
      <div className="flex items-center gap-1.5 px-1 pb-1 mb-0.5 border-b border-border/30" style={{ maxWidth: '200px' }}>
        {sortColumns.map(col => (
          <button
            key={col.key}
            onClick={() => onSortChange(
              sort.key === col.key
                ? { key: col.key, desc: !sort.desc }
                : { key: col.key, desc: col.key === 'count' }
            )}
            className={`text-[9px] font-medium ${col.width} text-left transition-colors ${
              sort.key === col.key
                ? 'text-primary'
                : 'text-muted-foreground/50 hover:text-muted-foreground'
            }`}
            title={col.title}
          >
            {col.label}
            {sort.key === col.key && (
              <span className="ml-0.5">{sort.desc ? '↓' : '↑'}</span>
            )}
          </button>
        ))}
      </div>

      {/* Cluster list */}
      <div className="max-h-[60vh] overflow-y-auto space-y-0.5 pr-1" style={{ maxWidth: '200px' }}>
        {entries.map(({ id, name, size }) => {
          const isActive = highlightedClusters === null || highlightedClusters.has(id);
          return (
            <button
              key={id}
              onClick={() => {
                onHighlightChange(
                  (() => {
                    if (highlightedClusters === null) {
                      return new Set([id]);
                    }
                    const next = new Set(highlightedClusters);
                    if (next.has(id)) {
                      next.delete(id);
                      return next.size === 0 ? null : next;
                    } else {
                      next.add(id);
                      return next;
                    }
                  })()
                );
              }}
              className={`flex items-center gap-1.5 w-full text-left rounded px-1 py-0.5 transition-opacity ${
                isActive ? 'opacity-100' : 'opacity-30'
              } hover:bg-accent/30`}
              title={`${name} (${size} points) — click to toggle`}
            >
              <div
                className="w-2.5 h-2.5 rounded-sm flex-shrink-0"
                style={{ backgroundColor: clusterColor(palette, id) }}
              />
              <span className="text-[10px] text-muted-foreground truncate flex-1">
                {name}
              </span>
              <span className="text-[10px] text-muted-foreground/40 flex-shrink-0 tabular-nums">
                {size}
              </span>
            </button>
          );
        })}
      </div>

      {/* Noise row */}
      {noiseCount > 0 && (
        <div className="flex items-center gap-1.5 pt-1 mt-1 border-t border-border/30 px-1">
          <div
            className="w-2.5 h-2.5 rounded-sm flex-shrink-0"
            style={{ backgroundColor: NOISE_COLOR }}
          />
          <span className="text-[10px] text-muted-foreground/60 flex-1">
            noise
          </span>
          <span className="text-[10px] text-muted-foreground/40 tabular-nums">
            {noiseCount}
          </span>
        </div>
      )}
    </div>
  );
}
