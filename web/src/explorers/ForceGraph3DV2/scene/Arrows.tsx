/**
 * Arrow-glyph rendering for directed edges.
 *
 * One instanced cone per edge, positioned near the target end with the
 * apex pointing along the tangent at u=uArrow (bezier) or the straight
 * direction (non-bezier). Apex sits at the target-node surface so the
 * arrow doesn't clip into the sphere. Bezier offsets and the bundle
 * segment-count source are shared with Edges via bundles.ts.
 *
 * Togglable via the showArrows engine prop (ADR-702 spike finding #2).
 */

import { useEffect, useMemo, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import type { EngineNode, EngineEdge } from '../types';
import { computeBundles, perpendicularBasis } from './bundles';

/** Position of the arrow apex along the curve, as t in (0, 1]. Using 1.0
 *  anchors the apex at the target node; we offset the apex further along
 *  the tangent below so it sits near the node's surface. */
const ARROW_T = 1.0;
/** Apex offset outward from target along the tangent, as fraction of edge length. */
const ARROW_APEX_OFFSET_RATIO = 0.0;
/** Arrow length as fraction of edge length (with absolute min/max). */
const ARROW_LEN_RATIO = 0.06;
const ARROW_LEN_MIN = 2;
const ARROW_LEN_MAX = 10;
/** Arrow base radius as fraction of arrow length. */
const ARROW_RADIUS_RATIO = 0.4;
/** Cone-axis direction before any instance rotation — ConeGeometry is +Y up. */
const CONE_AXIS = new THREE.Vector3(0, 1, 0);
const UP = new THREE.Vector3(0, 1, 0);
const FALLBACK = new THREE.Vector3(1, 0, 0);

const tmpMat = new THREE.Matrix4();
const tmpQuat = new THREE.Quaternion();
const tmpScale = new THREE.Vector3();
const tmpPos = new THREE.Vector3();
const tmpColor = new THREE.Color();

export interface ArrowsProps {
  nodes: EngineNode[];
  edges: EngineEdge[];
  positionsRef: React.MutableRefObject<Float32Array | null>;
  palette: (category: string) => string;
  /** If provided, color arrows by edge type; otherwise use target node category. */
  edgePalette?: (edgeType: string) => string;
  hiddenIds?: Set<string>;
  opacity?: number;
  /** Turn off arrow rendering entirely; default true per ADR-702. */
  enabled?: boolean;
}

/** Instanced cone arrow glyphs at edge target ends.  @verified c17bbeb9 */
export function Arrows({
  nodes,
  edges,
  positionsRef,
  palette,
  edgePalette,
  hiddenIds,
  opacity = 0.9,
  enabled = true,
}: ArrowsProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const invalidate = useThree((state) => state.invalidate);

  const { indexPairs, curveAngles, curveMags, usableCount, usableEdges } = useMemo(() => {
    const nodeIndex = new Map<string, number>();
    for (let i = 0; i < nodes.length; i++) nodeIndex.set(nodes[i].id, i);
    const usable = edges.filter((e) => nodeIndex.has(e.from) && nodeIndex.has(e.to));
    const pairs = new Uint32Array(usable.length * 2);
    for (let i = 0; i < usable.length; i++) {
      pairs[i * 2] = nodeIndex.get(usable[i].from)!;
      pairs[i * 2 + 1] = nodeIndex.get(usable[i].to)!;
    }
    const { angles, magnitudes } = computeBundles(usable);
    return {
      indexPairs: pairs,
      curveAngles: angles,
      curveMags: magnitudes,
      usableCount: usable.length,
      usableEdges: usable,
    };
  }, [nodes, edges]);

  // Color: edgePalette by edge type if available, else target node's category.
  useEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    for (let i = 0; i < usableCount; i++) {
      if (edgePalette) {
        tmpColor.set(edgePalette(usableEdges[i].type));
      } else {
        const ti = indexPairs[i * 2 + 1];
        tmpColor.set(palette(nodes[ti].category));
      }
      mesh.setColorAt(i, tmpColor);
    }
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    invalidate();
  }, [usableCount, indexPairs, nodes, palette, edgePalette, usableEdges, invalidate]);

  useFrame(() => {
    const mesh = meshRef.current;
    const positions = positionsRef.current;
    if (!mesh || !positions || !enabled) return;

    const hasHidden = !!hiddenIds && hiddenIds.size > 0;

    // Scratch allocations hoisted to avoid per-frame GC at 10k-edge scale.
    const s = new THREE.Vector3();
    const t = new THREE.Vector3();
    const tangent = new THREE.Vector3();
    const e1 = new THREE.Vector3();
    const e2 = new THREE.Vector3();
    const offsetDir = new THREE.Vector3();
    const ctrl = new THREE.Vector3();
    const mid = new THREE.Vector3();
    const apex = new THREE.Vector3();
    const center = new THREE.Vector3();

    for (let i = 0; i < usableCount; i++) {
      const si = indexPairs[i * 2];
      const ti = indexPairs[i * 2 + 1];

      if (hasHidden && (hiddenIds!.has(nodes[si].id) || hiddenIds!.has(nodes[ti].id))) {
        tmpScale.setScalar(0);
        tmpPos.setScalar(0);
        tmpQuat.identity();
        tmpMat.compose(tmpPos, tmpQuat, tmpScale);
        mesh.setMatrixAt(i, tmpMat);
        continue;
      }

      s.set(positions[si * 3], positions[si * 3 + 1], positions[si * 3 + 2]);
      t.set(positions[ti * 3], positions[ti * 3 + 1], positions[ti * 3 + 2]);
      const edgeLen = s.distanceTo(t);
      if (edgeLen < 1e-4) {
        tmpScale.setScalar(0);
        tmpMat.compose(s, tmpQuat.identity(), tmpScale);
        mesh.setMatrixAt(i, tmpMat);
        continue;
      }

      const curveMag = curveMags[i];
      const arrowLen = Math.max(
        ARROW_LEN_MIN,
        Math.min(edgeLen * ARROW_LEN_RATIO, ARROW_LEN_MAX)
      );

      if (curveMag === 0) {
        // Straight edge — tangent is just (t - s).normalize().
        tangent.subVectors(t, s).multiplyScalar(1 / edgeLen);
        apex.copy(t).addScaledVector(tangent, ARROW_APEX_OFFSET_RATIO * edgeLen);
      } else {
        // Bezier with angle-rotated perpendicular basis; matches Edges.tsx
        // so arrows sit on the same curve their edges follow. Tangent at
        // u=1 is 2(t - ctrl) (quadratic bezier).
        tangent.subVectors(t, s).multiplyScalar(1 / edgeLen);
        perpendicularBasis(tangent, UP, FALLBACK, e1, e2);
        offsetDir.copy(e1).multiplyScalar(Math.cos(curveAngles[i]));
        offsetDir.addScaledVector(e2, Math.sin(curveAngles[i]));
        mid.copy(s).add(t).multiplyScalar(0.5);
        ctrl.copy(mid).addScaledVector(offsetDir, curveMag * edgeLen);
        const u = ARROW_T;
        const mu = 1 - u;
        apex.copy(s).multiplyScalar(mu * mu);
        apex.addScaledVector(ctrl, 2 * mu * u);
        apex.addScaledVector(t, u * u);
        tangent.subVectors(t, ctrl).multiplyScalar(2).normalize();
        apex.addScaledVector(tangent, ARROW_APEX_OFFSET_RATIO * edgeLen);
      }

      // ConeGeometry apex at +Y (height/2 above center). Placing the cone
      // center at (apex - tangent * arrowLen/2) makes the apex land at `apex`.
      center.copy(apex).addScaledVector(tangent, -arrowLen / 2);
      tmpQuat.setFromUnitVectors(CONE_AXIS, tangent);
      tmpScale.set(arrowLen, arrowLen, arrowLen);
      tmpMat.compose(center, tmpQuat, tmpScale);
      mesh.setMatrixAt(i, tmpMat);
    }
    mesh.instanceMatrix.needsUpdate = true;
  });

  if (!enabled || usableCount === 0) return null;

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, usableCount]}>
      {/* Unit cone — radius ARROW_RADIUS_RATIO, height 1. Per-instance
          scale multiplies by the computed arrow length. */}
      <coneGeometry args={[ARROW_RADIUS_RATIO, 1, 8]} />
      <meshBasicMaterial vertexColors={false} transparent opacity={opacity} />
    </instancedMesh>
  );
}
