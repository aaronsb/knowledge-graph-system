/**
 * Compressed-sparse-row adjacency for the GPU force sim.
 *
 * The shader walks per-node neighbors via an offset/count pair looked up
 * in the node texture, then indexes into a flat neighbor list texture.
 * This helper builds all three from the edge list.
 */

import type { EngineNode, EngineEdge } from '../types';

export interface NeighborCSR {
  offsets: Uint32Array;
  counts: Uint32Array;
  flat: Uint32Array;
  total: number;
  maxNeighbors: number;
}

/** Build CSR adjacency for the GPU shader's per-node edge walk.  @verified c17bbeb9 */
export function buildNeighborCSR(nodes: EngineNode[], edges: EngineEdge[]): NeighborCSR {
  const N = nodes.length;
  const nameIndex = new Map<string, number>();
  for (let i = 0; i < N; i++) nameIndex.set(nodes[i].id, i);

  const adj: number[][] = Array.from({ length: N }, () => []);
  for (const e of edges) {
    const a = nameIndex.get(e.from);
    const b = nameIndex.get(e.to);
    if (a == null || b == null) continue;
    adj[a].push(b);
    adj[b].push(a);
  }

  const offsets = new Uint32Array(N);
  const counts = new Uint32Array(N);
  let total = 0;
  let maxNeighbors = 0;
  for (let i = 0; i < N; i++) {
    offsets[i] = total;
    counts[i] = adj[i].length;
    total += adj[i].length;
    if (adj[i].length > maxNeighbors) maxNeighbors = adj[i].length;
  }

  const flat = new Uint32Array(Math.max(1, total));
  let p = 0;
  for (let i = 0; i < N; i++) {
    for (const n of adj[i]) flat[p++] = n;
  }
  return { offsets, counts, flat, total, maxNeighbors };
}
