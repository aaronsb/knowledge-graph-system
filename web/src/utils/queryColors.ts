/**
 * Query Color Palette
 *
 * 10 distinguishable colors for multi-query passage search.
 * Used as ring strokes on graph nodes and highlight backgrounds in documents.
 */

import type { PassageQuery } from '../explorers/DocumentExplorer/types';

export const QUERY_PALETTE = [
  '#06b6d4',  // cyan
  '#f97316',  // orange
  '#a855f7',  // purple
  '#22c55e',  // green
  '#f43f5e',  // rose
  '#eab308',  // yellow
  '#3b82f6',  // blue
  '#ec4899',  // pink
  '#14b8a6',  // teal
  '#8b5cf6',  // violet
];

/** Pick the next unused color, cycling through the palette. */
export function getNextQueryColor(existingQueries: PassageQuery[]): string {
  const usedColors = new Set(existingQueries.map(q => q.color));
  for (const color of QUERY_PALETTE) {
    if (!usedColors.has(color)) return color;
  }
  // All used — cycle back
  return QUERY_PALETTE[existingQueries.length % QUERY_PALETTE.length];
}
