/**
 * Multigraph bundle computation.
 *
 * Shared by Edges (for bezier control-point offsets) and Arrows (for
 * matching curve tangents at the target end). Canonicalizes each edge
 * to an unordered pair so A→B and B→A count toward the same bundle.
 */

import type { EngineEdge } from '../types';

/** Perpendicular offset as a fraction of edge length, per bundle slot. */
export const CURVE_STRENGTH = 0.18;

export interface BundleInfo {
  /** Signed perpendicular offset per edge, scaled for bezier control points. */
  offsets: Float32Array;
  /** Largest bundle size across the graph; drives segment-count selection. */
  maxBundleSize: number;
}

/** Compute per-edge curve offsets by canonical endpoint pair.  @verified c17bbeb9 */
export function computeBundles(edges: EngineEdge[]): BundleInfo {
  const bundles = new Map<string, number[]>();
  for (let i = 0; i < edges.length; i++) {
    const a = edges[i].from;
    const b = edges[i].to;
    const key = a < b ? `${a}\x01${b}` : `${b}\x01${a}`;
    const list = bundles.get(key);
    if (list) list.push(i);
    else bundles.set(key, [i]);
  }

  const offsets = new Float32Array(edges.length);
  let maxBundleSize = 1;
  for (const list of bundles.values()) {
    const size = list.length;
    if (size > maxBundleSize) maxBundleSize = size;
    if (size === 1) continue;
    // Distribute edges evenly across [-CURVE_STRENGTH, CURVE_STRENGTH]
    // centered on zero. Odd-count bundles have a true-straight middle edge.
    for (let k = 0; k < size; k++) {
      const t = (k - (size - 1) / 2) / (size - 1);
      offsets[list[k]] = t * CURVE_STRENGTH * 2;
    }
  }
  return { offsets, maxBundleSize };
}
