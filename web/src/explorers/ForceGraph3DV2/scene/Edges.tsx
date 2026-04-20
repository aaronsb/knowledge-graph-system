/**
 * Indexed line-segment edge rendering.
 *
 * One draw call for M edges via a single BufferGeometry with position
 * and color attributes. Position attribute is updated each frame from
 * the shared positions buffer; color attribute is set once per edge
 * from the palette.
 *
 * M3 extends this to support bezier curves for parallel edges and an
 * optional edge-type palette. M1 ships straight edges with endpoint-
 * gradient coloring.
 */

import { useEffect, useMemo, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import type { EngineNode, EngineEdge } from '../types';

export interface EdgesProps {
  nodes: EngineNode[];
  edges: EngineEdge[];
  positionsRef: React.MutableRefObject<Float32Array | null>;
  palette: (category: string) => string;
  hiddenIds?: Set<string>;
  opacity?: number;
}

/** Indexed lineSegments edge mesh — one draw call for all edges.  @verified c17bbeb9 */
export function Edges({
  nodes,
  edges,
  positionsRef,
  palette,
  hiddenIds,
  opacity = 0.7,
}: EdgesProps) {
  const lineRef = useRef<THREE.LineSegments>(null);
  const invalidate = useThree((state) => state.invalidate);

  const { geometry, material, indexPairs } = useMemo(() => {
    const nodeIndex = new Map<string, number>();
    for (let i = 0; i < nodes.length; i++) nodeIndex.set(nodes[i].id, i);

    const usable = edges.filter((e) => nodeIndex.has(e.from) && nodeIndex.has(e.to));
    const posArr = new Float32Array(usable.length * 6);
    const colArr = new Float32Array(usable.length * 6);
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

    return { geometry: geom, material: mat, indexPairs: pairs };
  }, [nodes, edges, opacity]);

  useEffect(() => {
    return () => {
      geometry.dispose();
      material.dispose();
    };
  }, [geometry, material]);

  // Endpoint-gradient coloring: each vertex gets its endpoint's category
  // color. Task #12 (M3) adds an edgePalette path that colors by edge type.
  useEffect(() => {
    const colAttr = geometry.getAttribute('color') as THREE.BufferAttribute;
    const arr = colAttr.array as Float32Array;
    const sc = new THREE.Color();
    const tc = new THREE.Color();
    const pairCount = indexPairs.length / 2;
    for (let i = 0; i < pairCount; i++) {
      const si = indexPairs[i * 2];
      const ti = indexPairs[i * 2 + 1];
      sc.set(palette(nodes[si].category));
      tc.set(palette(nodes[ti].category));
      arr[i * 6] = sc.r;
      arr[i * 6 + 1] = sc.g;
      arr[i * 6 + 2] = sc.b;
      arr[i * 6 + 3] = tc.r;
      arr[i * 6 + 4] = tc.g;
      arr[i * 6 + 5] = tc.b;
    }
    colAttr.needsUpdate = true;
    invalidate();
  }, [geometry, indexPairs, nodes, palette, invalidate]);

  useFrame(() => {
    const line = lineRef.current;
    const positions = positionsRef.current;
    if (!line || !positions) return;
    const posAttr = line.geometry.getAttribute('position') as THREE.BufferAttribute;
    const arr = posAttr.array as Float32Array;
    const pairCount = indexPairs.length / 2;
    const hasHidden = !!hiddenIds && hiddenIds.size > 0;

    for (let i = 0; i < pairCount; i++) {
      const si = indexPairs[i * 2];
      const ti = indexPairs[i * 2 + 1];
      const sHidden = hasHidden && hiddenIds!.has(nodes[si].id);
      const tHidden = hasHidden && hiddenIds!.has(nodes[ti].id);
      if (sHidden || tHidden) {
        // Collapse to a zero-length segment at the visible endpoint.
        const keepIdx = sHidden ? ti : si;
        const k3 = keepIdx * 3;
        arr[i * 6] = positions[k3];
        arr[i * 6 + 1] = positions[k3 + 1];
        arr[i * 6 + 2] = positions[k3 + 2];
        arr[i * 6 + 3] = positions[k3];
        arr[i * 6 + 4] = positions[k3 + 1];
        arr[i * 6 + 5] = positions[k3 + 2];
        continue;
      }
      arr[i * 6] = positions[si * 3];
      arr[i * 6 + 1] = positions[si * 3 + 1];
      arr[i * 6 + 2] = positions[si * 3 + 2];
      arr[i * 6 + 3] = positions[ti * 3];
      arr[i * 6 + 4] = positions[ti * 3 + 1];
      arr[i * 6 + 5] = positions[ti * 3 + 2];
    }
    posAttr.needsUpdate = true;
  });

  return <lineSegments ref={lineRef} geometry={geometry} material={material} />;
}
