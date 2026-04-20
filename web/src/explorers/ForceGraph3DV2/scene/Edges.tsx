/**
 * Indexed line-segment edge rendering with optional bezier multi-edges.
 *
 * All edges render in one draw call via a single BufferGeometry. Edges
 * are detected as multigraph bundles by canonicalized endpoint pair;
 * each edge in a bundle of size > 1 gets a perpendicular offset on its
 * control point so parallel relationships fan out rather than
 * overlapping. Single-edge bundles render as straight lines (the
 * quadratic bezier with control point on the line segment degenerates
 * to a line), so the same shader/sampler pipeline handles both cases.
 *
 * Segment count is fixed at 1 when no bundle needs curving and at 12
 * otherwise — straight edges stay cheap on typical graphs.
 */

import { useEffect, useMemo, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import type { EngineNode, EngineEdge } from '../types';
import { computeBundles } from './bundles';

/** Number of line segments per edge when bezier bundles are present. */
const SEGMENTS_CURVED = 12;

const UP = new THREE.Vector3(0, 1, 0);
const FALLBACK = new THREE.Vector3(1, 0, 0);

export interface EdgesProps {
  nodes: EngineNode[];
  edges: EngineEdge[];
  positionsRef: React.MutableRefObject<Float32Array | null>;
  palette: (category: string) => string;
  /** If provided, color edges by edge type instead of endpoint-category gradient. */
  edgePalette?: (edgeType: string) => string;
  hiddenIds?: Set<string>;
  opacity?: number;
}

/** Indexed-line edge mesh — straight when no parallels, bezier otherwise.  @verified c17bbeb9 */
export function Edges({
  nodes,
  edges,
  positionsRef,
  palette,
  edgePalette,
  hiddenIds,
  opacity = 0.7,
}: EdgesProps) {
  const lineRef = useRef<THREE.LineSegments>(null);
  const invalidate = useThree((state) => state.invalidate);

  const { geometry, material, indexPairs, curveOffsets, segments, usableEdges } = useMemo(() => {
    const nodeIndex = new Map<string, number>();
    for (let i = 0; i < nodes.length; i++) nodeIndex.set(nodes[i].id, i);

    const usable = edges.filter((e) => nodeIndex.has(e.from) && nodeIndex.has(e.to));
    const { offsets: bundleOffsets, maxBundleSize } = computeBundles(usable);
    const segs = maxBundleSize > 1 ? SEGMENTS_CURVED : 1;

    // lineSegments renders every pair of adjacent vertices as a line,
    // so a single edge with `segs` segments costs 2*segs vertices.
    const vertsPerEdge = 2 * segs;
    const posArr = new Float32Array(usable.length * vertsPerEdge * 3);
    const colArr = new Float32Array(usable.length * vertsPerEdge * 3);
    const pairs = new Uint32Array(usable.length * 2);

    for (let i = 0; i < usable.length; i++) {
      pairs[i * 2] = nodeIndex.get(usable[i].from)!;
      pairs[i * 2 + 1] = nodeIndex.get(usable[i].to)!;
    }

    const geom = new THREE.BufferGeometry();
    const posAttr = new THREE.BufferAttribute(posArr, 3);
    posAttr.setUsage(THREE.DynamicDrawUsage);
    geom.setAttribute('position', posAttr);
    const colAttr = new THREE.BufferAttribute(colArr, 3);
    colAttr.setUsage(THREE.DynamicDrawUsage);
    geom.setAttribute('color', colAttr);

    const mat = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity,
      depthWrite: false,
    });

    return {
      geometry: geom,
      material: mat,
      indexPairs: pairs,
      curveOffsets: bundleOffsets,
      segments: segs,
      usableEdges: usable,
    };
  }, [nodes, edges, opacity]);

  useEffect(() => {
    return () => {
      geometry.dispose();
      material.dispose();
    };
  }, [geometry, material]);

  // Coloring. Two modes:
  //   - edgePalette provided → every vertex of an edge gets the same color
  //     derived from the edge's relationship type (flat edge coloring).
  //   - otherwise → endpoint-category gradient across the curve.
  useEffect(() => {
    const colAttr = geometry.getAttribute('color') as THREE.BufferAttribute;
    const arr = colAttr.array as Float32Array;
    const ec = new THREE.Color();
    const sc = new THREE.Color();
    const tc = new THREE.Color();
    const vc = new THREE.Color();
    const pairCount = indexPairs.length / 2;
    const vertsPerEdge = 2 * segments;

    for (let i = 0; i < pairCount; i++) {
      const base = i * vertsPerEdge * 3;

      if (edgePalette) {
        ec.set(edgePalette(usableEdges[i].type));
        for (let v = 0; v < vertsPerEdge; v++) {
          const off = base + v * 3;
          arr[off] = ec.r;
          arr[off + 1] = ec.g;
          arr[off + 2] = ec.b;
        }
        continue;
      }

      const si = indexPairs[i * 2];
      const ti = indexPairs[i * 2 + 1];
      sc.set(palette(nodes[si].category));
      tc.set(palette(nodes[ti].category));
      for (let v = 0; v < vertsPerEdge; v++) {
        // lineSegments pairs vertices (0,1)(2,3)... Each segment v spans
        // t values [v/segs, (v+1)/segs], so vertex position within the
        // segment alternates: even = segment start, odd = segment end.
        const segIndex = Math.floor(v / 2);
        const isEnd = v % 2 === 1;
        const t = (segIndex + (isEnd ? 1 : 0)) / segments;
        vc.copy(sc).lerp(tc, t);
        const off = base + v * 3;
        arr[off] = vc.r;
        arr[off + 1] = vc.g;
        arr[off + 2] = vc.b;
      }
    }
    colAttr.needsUpdate = true;
    invalidate();
  }, [geometry, indexPairs, nodes, palette, edgePalette, usableEdges, segments, invalidate]);

  useFrame(() => {
    const line = lineRef.current;
    const positions = positionsRef.current;
    if (!line || !positions) return;
    const posAttr = line.geometry.getAttribute('position') as THREE.BufferAttribute;
    const arr = posAttr.array as Float32Array;
    const pairCount = indexPairs.length / 2;
    const hasHidden = !!hiddenIds && hiddenIds.size > 0;
    const vertsPerEdge = 2 * segments;

    // Scratch vectors reused across the loop — allocating these per frame
    // would cost a few thousand Vector3 objects at 10k-edge scale.
    const s = new THREE.Vector3();
    const t = new THREE.Vector3();
    const edgeDir = new THREE.Vector3();
    const perp = new THREE.Vector3();
    const mid = new THREE.Vector3();
    const ctrl = new THREE.Vector3();
    const p = new THREE.Vector3();

    for (let i = 0; i < pairCount; i++) {
      const si = indexPairs[i * 2];
      const ti = indexPairs[i * 2 + 1];
      const base = i * vertsPerEdge * 3;

      if (hasHidden && (hiddenIds!.has(nodes[si].id) || hiddenIds!.has(nodes[ti].id))) {
        const keepIdx = hiddenIds!.has(nodes[si].id) ? ti : si;
        const k3 = keepIdx * 3;
        // Collapse every vertex to the same point so the edge disappears
        // without requiring geometry reallocation.
        for (let v = 0; v < vertsPerEdge; v++) {
          const off = base + v * 3;
          arr[off] = positions[k3];
          arr[off + 1] = positions[k3 + 1];
          arr[off + 2] = positions[k3 + 2];
        }
        continue;
      }

      s.set(positions[si * 3], positions[si * 3 + 1], positions[si * 3 + 2]);
      t.set(positions[ti * 3], positions[ti * 3 + 1], positions[ti * 3 + 2]);

      const curveOffset = curveOffsets[i];

      if (segments === 1 || curveOffset === 0) {
        // Straight-line fast path. When segments > 1 but this particular
        // edge has offset 0 (middle of a bundle), still emit every segment
        // so the per-vertex color table stays aligned — positions all walk
        // along the straight line from s to t.
        for (let v = 0; v < vertsPerEdge; v++) {
          const segIndex = Math.floor(v / 2);
          const isEnd = v % 2 === 1;
          const u = (segIndex + (isEnd ? 1 : 0)) / segments;
          p.copy(s).lerp(t, u);
          const off = base + v * 3;
          arr[off] = p.x;
          arr[off + 1] = p.y;
          arr[off + 2] = p.z;
        }
        continue;
      }

      // Bezier path. Control point offset perpendicular to the edge,
      // magnitude scaled by edge length and bundle slot.
      edgeDir.subVectors(t, s);
      const edgeLen = edgeDir.length();
      if (edgeLen < 1e-4) {
        // Degenerate edge — fill with the midpoint.
        mid.copy(s).add(t).multiplyScalar(0.5);
        for (let v = 0; v < vertsPerEdge; v++) {
          const off = base + v * 3;
          arr[off] = mid.x;
          arr[off + 1] = mid.y;
          arr[off + 2] = mid.z;
        }
        continue;
      }
      edgeDir.multiplyScalar(1 / edgeLen);

      // Pick a perpendicular direction. Crossing with world up works for
      // most edges; fall back when edge is near-vertical.
      perp.crossVectors(edgeDir, UP);
      if (perp.lengthSq() < 1e-4) perp.crossVectors(edgeDir, FALLBACK);
      perp.normalize();

      mid.copy(s).add(t).multiplyScalar(0.5);
      ctrl.copy(mid).addScaledVector(perp, curveOffset * edgeLen);

      // Sample the quadratic bezier B(u) = (1-u)² s + 2(1-u)u ctrl + u² t
      // at each segment boundary. Two vertices emitted per segment
      // (start + end) so lineSegments consumes adjacent pairs correctly.
      for (let v = 0; v < vertsPerEdge; v++) {
        const segIndex = Math.floor(v / 2);
        const isEnd = v % 2 === 1;
        const u = (segIndex + (isEnd ? 1 : 0)) / segments;
        const mu = 1 - u;
        const w0 = mu * mu;
        const w1 = 2 * mu * u;
        const w2 = u * u;
        p.copy(s).multiplyScalar(w0);
        p.addScaledVector(ctrl, w1);
        p.addScaledVector(t, w2);
        const off = base + v * 3;
        arr[off] = p.x;
        arr[off + 1] = p.y;
        arr[off + 2] = p.z;
      }
    }
    posAttr.needsUpdate = true;
  });

  return <lineSegments ref={lineRef} geometry={geometry} material={material} />;
}
