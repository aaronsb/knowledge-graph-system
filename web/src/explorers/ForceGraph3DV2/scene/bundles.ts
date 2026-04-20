/**
 * Multigraph bundle computation.
 *
 * Shared by Edges (bezier sampling), Arrows (curve tangent at target),
 * and EdgeLabels (label midpoint on the curve). Canonicalizes each edge
 * to an unordered pair so A→B and B→A count toward the same bundle.
 *
 * Each bundle member's curve plane is rotated around the edge axis so
 * parallel edges spread in distinct planes rather than stacking on a
 * single perpendicular direction. In 3D, two members offset in opposite
 * directions along one perpendicular still project onto the same line
 * from many camera angles — rotating the plane avoids that.
 */

import type { EngineEdge } from '../types';

/** Curve magnitude as a fraction of edge length. */
export const CURVE_STRENGTH = 0.22;

export interface BundleInfo {
  /** Perpendicular-plane angle (radians) for each edge, in [0, π). */
  angles: Float32Array;
  /** Curve magnitude per edge; 0 for straight (bundle size 1) edges. */
  magnitudes: Float32Array;
  /** Largest bundle size across the graph; drives segment-count selection. */
  maxBundleSize: number;
}

/** Compute per-edge curve plane angles by canonical endpoint pair.  @verified c17bbeb9 */
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

  const angles = new Float32Array(edges.length);
  const magnitudes = new Float32Array(edges.length);
  let maxBundleSize = 1;
  for (const list of bundles.values()) {
    const size = list.length;
    if (size > maxBundleSize) maxBundleSize = size;
    if (size === 1) {
      // Straight line — angle is unused, magnitude zero.
      angles[list[0]] = 0;
      magnitudes[list[0]] = 0;
      continue;
    }
    // Distribute curve planes around the edge axis. Using π (half circle)
    // rather than 2π avoids a wasted angular slot at the top where the
    // curve would coincide with the first slot flipped — half a rotation
    // is enough to give each member a visually distinct plane when
    // combined with the consistent magnitude.
    for (let k = 0; k < size; k++) {
      angles[list[k]] = (k / size) * Math.PI;
      magnitudes[list[k]] = CURVE_STRENGTH;
    }
  }
  return { angles, magnitudes, maxBundleSize };
}

/**
 * Build the orthonormal basis (e1, e2) of the plane perpendicular to an
 * edge direction. Both outputs are unit-length and mutually perpendicular
 * to the given `edgeDir`. `edgeDir` must already be normalized.
 *
 * The basis is stable but arbitrary — rotating the whole basis around
 * edgeDir doesn't change which plane it spans, only which direction each
 * angle resolves to. What matters is that `angles` from computeBundles
 * use the same basis across all renderers (Edges, Arrows, EdgeLabels),
 * which they do because they call this helper with the same inputs.
 */
export function perpendicularBasis(
  edgeDir: { x: number; y: number; z: number },
  up: { x: number; y: number; z: number },
  fallback: { x: number; y: number; z: number },
  out1: { x: number; y: number; z: number; normalize(): unknown; crossVectors(a: unknown, b: unknown): unknown; lengthSq(): number },
  out2: { x: number; y: number; z: number; normalize(): unknown; crossVectors(a: unknown, b: unknown): unknown }
): void {
  // e1 = normalize(edgeDir × up); fall back if edge is parallel to up.
  out1.crossVectors(edgeDir, up);
  if (out1.lengthSq() < 1e-4) out1.crossVectors(edgeDir, fallback);
  out1.normalize();
  // e2 = normalize(edgeDir × e1); guaranteed orthogonal, unit length.
  out2.crossVectors(edgeDir, out1);
  out2.normalize();
}
