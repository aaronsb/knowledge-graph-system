/**
 * CPU force simulation hook.
 *
 * JavaScript force loop on the main thread. Must be called inside the
 * r3f Canvas tree because it uses useFrame. Owns the positions buffer
 * and mutates it in place each frame — the same buffer is read by the
 * Nodes and Edges renderers so there's no marshaling step.
 *
 * Demand-mode: invalidate() is called each frame while alpha is above
 * alphaMin. When alpha decays below alphaMin the hook stops pumping
 * frames, so a settled graph costs nothing. The API is shared with the
 * GPU hook (M2 task #9) so the dispatcher can swap implementations
 * without consumers noticing.
 *
 * Static-friction clamp (velStopSimmer) and pre-alpha force capping
 * mirror the GPU shader's behavior so the CPU and GPU paths produce
 * layouts that agree within numerical tolerance.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { seedSpherePositions, defaultSeedRadius } from './positions';
import type { EngineNode, EngineEdge } from '../types';

/** Tunable simulation parameters; see DEFAULTS below for meaning.  @verified c17bbeb9 */
export interface PhysicsParams {
  repulsion: number;
  attraction: number;
  damping: number;
  dt: number;
  centerGravity: number;
  maxForce: number;
  alphaDecay: number;
  alphaMin: number;
  alphaInitial: number;
  alphaSimmer: number;
  dampingSimmer: number;
  centerGravitySimmer: number;
  velStopSimmer: number;
}

const DEFAULTS: PhysicsParams = {
  repulsion: 120,
  attraction: 0.04,
  damping: 0.93,
  dt: 0.55,
  centerGravity: 0.004,
  maxForce: 40,
  alphaDecay: 0.0228,
  alphaMin: 0.001,
  alphaInitial: 1.0,
  alphaSimmer: 0.08,
  dampingSimmer: 0.70,
  centerGravitySimmer: 0.03,
  velStopSimmer: 0.3,
};

export interface ForceSimParams extends Partial<PhysicsParams> {
  hiddenIds?: Set<string>;
  /** Nodes held at their current position; sim skips integration for them. */
  pinnedIds?: Set<string>;
}

/** Handle returned by useForceSim; drives the sim and exposes its buffer.  @verified c17bbeb9 */
export interface ForceSimHandle {
  positionsRef: React.MutableRefObject<Float32Array | null>;
  dirtyRef: React.MutableRefObject<boolean>;
  alpha: number;
  reheat: () => void;
  freeze: () => void;
  simmer: (on: boolean) => void;
}

/** CPU force sim hook — must be called inside an r3f Canvas tree.  @verified c17bbeb9 */
export function useForceSim(
  nodes: EngineNode[],
  edges: EngineEdge[],
  params: ForceSimParams = {}
): ForceSimHandle {
  const { hiddenIds, pinnedIds, ...tuning } = params;
  const cfg: PhysicsParams = { ...DEFAULTS, ...tuning };
  const nodeCount = nodes.length;
  const invalidate = useThree((state) => state.invalidate);

  const positionsRef = useRef<Float32Array | null>(null);
  const velocitiesRef = useRef<Float32Array | null>(null);
  const edgeIndicesRef = useRef<Uint32Array | null>(null);
  const alphaRef = useRef(cfg.alphaInitial);
  const [alphaDisplay, setAlphaDisplay] = useState(cfg.alphaInitial);
  const dirtyRef = useRef(false);
  const frameCounterRef = useRef(0);
  const simmerRef = useRef(false);

  // Seed positions when node count changes. useMemo keeps the allocation
  // out of the render commit phase; we don't actually consume its return.
  useMemo(() => {
    positionsRef.current = seedSpherePositions(nodeCount, defaultSeedRadius(nodeCount));
    velocitiesRef.current = new Float32Array(nodeCount * 3);
    alphaRef.current = cfg.alphaInitial;
    setAlphaDisplay(cfg.alphaInitial);
    dirtyRef.current = true;
  }, [nodeCount, cfg.alphaInitial]);

  // Rebuild the edge index array whenever nodes or edges change. The sim
  // loop walks this flat Uint32Array pair-wise for cache-friendly access.
  useEffect(() => {
    const nameIndex = new Map<string, number>();
    for (let i = 0; i < nodeCount; i++) nameIndex.set(nodes[i].id, i);
    const usable = edges.filter((e) => nameIndex.has(e.from) && nameIndex.has(e.to));
    const arr = new Uint32Array(usable.length * 2);
    for (let i = 0; i < usable.length; i++) {
      arr[i * 2] = nameIndex.get(usable[i].from)!;
      arr[i * 2 + 1] = nameIndex.get(usable[i].to)!;
    }
    edgeIndicesRef.current = arr;
  }, [nodes, edges, nodeCount]);

  useFrame(() => {
    const alpha = alphaRef.current;
    if (alpha < cfg.alphaMin) {
      dirtyRef.current = false;
      return;
    }
    invalidate();

    const positions = positionsRef.current;
    const velocities = velocitiesRef.current;
    const edgeIdx = edgeIndicesRef.current;
    if (!positions || !velocities || !edgeIdx) return;

    const N = nodeCount;
    const { repulsion, attraction, dt, maxForce } = cfg;
    const damping = simmerRef.current ? cfg.dampingSimmer : cfg.damping;
    const centerGravity = simmerRef.current ? cfg.centerGravitySimmer : cfg.centerGravity;
    const velStop = simmerRef.current ? cfg.velStopSimmer : 0;

    const forces = new Float32Array(N * 3);
    const hasHidden = !!hiddenIds && hiddenIds.size > 0;
    const hasPinned = !!pinnedIds && pinnedIds.size > 0;
    const isHidden = hasHidden ? (i: number) => hiddenIds!.has(nodes[i].id) : () => false;
    // Physics-frozen: hidden (excluded from sim entirely) OR pinned (user is
    // dragging — sim shouldn't clobber the position).
    const isFrozen =
      hasHidden || hasPinned
        ? (i: number) => {
            const id = nodes[i].id;
            return (hasHidden && hiddenIds!.has(id)) || (hasPinned && pinnedIds!.has(id));
          }
        : () => false;

    // Repulsion — O(N²) upper-triangular, applies equal and opposite to each pair.
    for (let i = 0; i < N; i++) {
      if (isHidden(i)) continue;
      const ix3 = i * 3;
      const xi = positions[ix3];
      const yi = positions[ix3 + 1];
      const zi = positions[ix3 + 2];
      for (let j = i + 1; j < N; j++) {
        if (isHidden(j)) continue;
        const jx3 = j * 3;
        const dx = xi - positions[jx3];
        const dy = yi - positions[jx3 + 1];
        const dz = zi - positions[jx3 + 2];
        let dist2 = dx * dx + dy * dy + dz * dz;
        if (dist2 < 0.01) dist2 = 0.01;
        const dist = Math.sqrt(dist2);
        const f = repulsion / dist2;
        const fx = (dx / dist) * f;
        const fy = (dy / dist) * f;
        const fz = (dz / dist) * f;
        forces[ix3] += fx;
        forces[ix3 + 1] += fy;
        forces[ix3 + 2] += fz;
        forces[jx3] -= fx;
        forces[jx3 + 1] -= fy;
        forces[jx3 + 2] -= fz;
      }
      forces[ix3] -= xi * centerGravity;
      forces[ix3 + 1] -= yi * centerGravity;
      forces[ix3 + 2] -= zi * centerGravity;
    }

    // Edge attraction.
    const eLen = edgeIdx.length;
    for (let e = 0; e < eLen; e += 2) {
      const a = edgeIdx[e];
      const b = edgeIdx[e + 1];
      if (isHidden(a) || isHidden(b)) continue;
      const ax = a * 3;
      const bx = b * 3;
      const dx = positions[bx] - positions[ax];
      const dy = positions[bx + 1] - positions[ax + 1];
      const dz = positions[bx + 2] - positions[ax + 2];
      forces[ax] += dx * attraction;
      forces[ax + 1] += dy * attraction;
      forces[ax + 2] += dz * attraction;
      forces[bx] -= dx * attraction;
      forces[bx + 1] -= dy * attraction;
      forces[bx + 2] -= dz * attraction;
    }

    // Integrate. Cap force before alpha scaling so alpha actually governs
    // the dynamics for high-degree nodes (matches GPU shader behavior).
    // Frozen nodes (hidden or pinned) skip integration so their position
    // stays where the caller / drag handler put it.
    for (let i = 0; i < N; i++) {
      if (isFrozen(i)) continue;
      const ix3 = i * 3;
      let fx = forces[ix3];
      let fy = forces[ix3 + 1];
      let fz = forces[ix3 + 2];
      const mag = Math.sqrt(fx * fx + fy * fy + fz * fz);
      if (mag > maxForce) {
        const s = maxForce / mag;
        fx *= s;
        fy *= s;
        fz *= s;
      }
      fx *= alpha;
      fy *= alpha;
      fz *= alpha;
      let nvx = (velocities[ix3] + fx) * damping;
      let nvy = (velocities[ix3 + 1] + fy) * damping;
      let nvz = (velocities[ix3 + 2] + fz) * damping;
      // Static-friction clamp — kills low-amplitude oscillations that
      // would otherwise decay asymptotically.
      if (velStop > 0) {
        const vm2 = nvx * nvx + nvy * nvy + nvz * nvz;
        if (vm2 < velStop * velStop) {
          nvx = 0;
          nvy = 0;
          nvz = 0;
        }
      }
      velocities[ix3] = nvx;
      velocities[ix3 + 1] = nvy;
      velocities[ix3 + 2] = nvz;
      positions[ix3] += nvx * dt;
      positions[ix3 + 1] += nvy * dt;
      positions[ix3 + 2] += nvz * dt;
    }

    const decayed = alpha * (1 - cfg.alphaDecay);
    alphaRef.current = simmerRef.current ? Math.max(cfg.alphaSimmer, decayed) : decayed;
    dirtyRef.current = true;

    frameCounterRef.current++;
    if (frameCounterRef.current % 10 === 0) {
      setAlphaDisplay(alphaRef.current);
    }
  });

  const reheat = useCallback(() => {
    alphaRef.current = cfg.alphaInitial;
    setAlphaDisplay(cfg.alphaInitial);
    dirtyRef.current = true;
    invalidate();
  }, [cfg.alphaInitial, invalidate]);

  const freeze = useCallback(() => {
    alphaRef.current = 0;
    setAlphaDisplay(0);
    simmerRef.current = false;
    const vel = velocitiesRef.current;
    if (vel) vel.fill(0);
    dirtyRef.current = false;
    invalidate();
  }, [invalidate]);

  const simmer = useCallback(
    (on: boolean) => {
      simmerRef.current = on;
      if (on) {
        if (alphaRef.current < cfg.alphaSimmer) {
          alphaRef.current = cfg.alphaSimmer;
          setAlphaDisplay(cfg.alphaSimmer);
        }
        dirtyRef.current = true;
        invalidate();
      }
    },
    [cfg.alphaSimmer, invalidate]
  );

  return { positionsRef, dirtyRef, alpha: alphaDisplay, reheat, freeze, simmer };
}
