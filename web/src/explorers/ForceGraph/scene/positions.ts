/**
 * Position seeding for the unified rendering engine.
 *
 * The engine owns a single Float32Array of length 3N holding x,y,z for
 * every node, shared by the simulation and the renderer. M1 static mode
 * seeds it once; M2 (CPU/GPU force sim) mutates it in place each frame.
 * z is always present — 2D mode (phase 2) will clamp z to 0 rather than
 * carry a separate buffer shape.
 *
 * Incremental layout (seedWithCarryover): when the graph is "poked" —
 * a node expanded, a concept followed, a filter toggled — the node array
 * is rebuilt and the sim hook re-seeds. Re-seeding every node from a
 * fresh sphere is what caused the whole graph to explode on each change.
 * seedWithCarryover keeps every node that survived the change at its
 * settled position and only sphere-seeds genuinely new nodes, so the
 * existing layout holds and new nodes fly in toward it.
 */

/** Place one node's xyz at out[i*3..] uniformly inside a sphere.  @verified f8ee93b9 */
function seedOne(out: Float32Array, i: number, radius: number): void {
  const u = Math.random();
  const v = Math.random();
  const theta = 2 * Math.PI * u;
  const phi = Math.acos(2 * v - 1);
  const r = radius * Math.cbrt(Math.random());
  out[i * 3] = r * Math.sin(phi) * Math.cos(theta);
  out[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
  out[i * 3 + 2] = r * Math.cos(phi);
}

/** Seed N positions uniformly inside a sphere.  @verified f8ee93b9 */
export function seedSpherePositions(count: number, radius = 120): Float32Array {
  const positions = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) seedOne(positions, i, radius);
  return positions;
}

/** Result of a carry-over seed: the buffer plus how many nodes kept
 *  their prior position. carriedCount === 0 means *treat as a fresh
 *  graph* (full reheat) — this intentionally covers not just "no prior
 *  at all" but also "a prior existed yet nothing survived" (a full
 *  filter swap, or the graph emptied then repopulated). Zero overlap is
 *  a new layout by definition, so the gentle incremental reheat would
 *  have nothing to preserve anyway.
 *  @verified f8ee93b9 */
export interface CarryoverSeed {
  positions: Float32Array;
  carriedCount: number;
}

/**
 * Seed a new node set, preserving prior positions for nodes that
 * survived the change.
 *
 * `ids` is the new generation's node ids (index-parallel to the output
 * buffer). `priorIds` / `priorPositions` are the previous generation's
 * id list and its last-known flat xyz buffer. Any node whose id is in
 * `priorIds` keeps that exact position; the rest are sphere-seeded so
 * they animate in toward the settled layout. carriedCount lets the sim
 * hook pick a gentle reheat (incremental) vs a full one (fresh graph).
 *
 * @verified f8ee93b9
 */
export function seedWithCarryover(
  ids: string[],
  priorIds: string[],
  priorPositions: Float32Array | null,
  radius: number
): CarryoverSeed {
  const n = ids.length;
  const out = new Float32Array(n * 3);
  const havePrior =
    !!priorPositions &&
    priorIds.length > 0 &&
    priorPositions.length >= priorIds.length * 3;

  if (!havePrior) {
    for (let i = 0; i < n; i++) seedOne(out, i, radius);
    return { positions: out, carriedCount: 0 };
  }

  const priorIndex = new Map<string, number>();
  for (let i = 0; i < priorIds.length; i++) priorIndex.set(priorIds[i], i);

  let carried = 0;
  for (let i = 0; i < n; i++) {
    const p = priorIndex.get(ids[i]);
    if (p !== undefined) {
      out[i * 3] = priorPositions![p * 3];
      out[i * 3 + 1] = priorPositions![p * 3 + 1];
      out[i * 3 + 2] = priorPositions![p * 3 + 2];
      carried++;
    } else {
      seedOne(out, i, radius);
    }
  }
  return { positions: out, carriedCount: carried };
}

/** Radius heuristic — grows gently with node count so graphs stay visible.  @verified f8ee93b9 */
export function defaultSeedRadius(count: number): number {
  return Math.max(120, Math.cbrt(count) * 15);
}
