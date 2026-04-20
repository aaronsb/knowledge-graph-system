/**
 * Distance-culled edge labels.
 *
 * Renders relationship_type text as an <Html> overlay at the midpoint of
 * each edge within labelVisibilityRadius of the camera. Edges outside
 * the radius are unmounted — the visible set is recomputed on a timer
 * (every ~200ms) so label DOM churn stays bounded even with thousands
 * of edges. Within the visible set, each slot's world position is
 * updated per frame via a group-follower ref — no React re-render per
 * frame.
 *
 * Honors the same bundle bezier offsets as Edges so the label sits on
 * the curve, not on the straight-line midpoint. Hidden endpoints drop
 * the label from the visible set automatically.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import * as THREE from 'three';
import type { EngineNode, EngineEdge } from '../types';
import { computeBundles } from './bundles';

const UP = new THREE.Vector3(0, 1, 0);
const FALLBACK = new THREE.Vector3(1, 0, 0);
/** Throttle for re-scanning which edges qualify; ~5 Hz is imperceptible. */
const RESCAN_MS = 200;
/** Upper bound on simultaneously-mounted labels to bound DOM cost. */
const MAX_LABELS = 80;

export interface EdgeLabelsProps {
  nodes: EngineNode[];
  edges: EngineEdge[];
  positionsRef: React.MutableRefObject<Float32Array | null>;
  hiddenIds?: Set<string>;
  /** Labels past this world-space distance from the camera are unmounted. */
  visibilityRadius?: number;
  enabled?: boolean;
  /** If provided, color label border by edge type. */
  edgePalette?: (edgeType: string) => string;
}

interface EdgeMeta {
  edgeIndex: number;
  si: number;
  ti: number;
  curveOffset: number;
  type: string;
}

/** Distance-culled relationship-type labels on edges.  @verified c17bbeb9 */
export function EdgeLabels({
  nodes,
  edges,
  positionsRef,
  hiddenIds,
  visibilityRadius = 250,
  enabled = true,
  edgePalette,
}: EdgeLabelsProps) {
  const camera = useThree((state) => state.camera);

  const edgeMeta: EdgeMeta[] = useMemo(() => {
    const nodeIndex = new Map<string, number>();
    for (let i = 0; i < nodes.length; i++) nodeIndex.set(nodes[i].id, i);
    const usable = edges.filter((e) => nodeIndex.has(e.from) && nodeIndex.has(e.to));
    const { offsets } = computeBundles(usable);
    return usable.map((e, i) => ({
      edgeIndex: i,
      si: nodeIndex.get(e.from)!,
      ti: nodeIndex.get(e.to)!,
      curveOffset: offsets[i],
      type: e.type,
    }));
  }, [nodes, edges]);

  // React state is the visible set; updated on a timer so mount/unmount
  // happens at 5Hz, not 60Hz.
  const [visibleIndices, setVisibleIndices] = useState<number[]>([]);
  const groupRefs = useRef<(THREE.Group | null)[]>([]);
  const lastScanRef = useRef(0);

  useEffect(() => {
    groupRefs.current = new Array(MAX_LABELS).fill(null);
  }, []);

  // Scratch vectors reused across the frame loop.
  const scratch = useMemo(
    () => ({
      s: new THREE.Vector3(),
      t: new THREE.Vector3(),
      mid: new THREE.Vector3(),
      perp: new THREE.Vector3(),
      edgeDir: new THREE.Vector3(),
      ctrl: new THREE.Vector3(),
      camPos: new THREE.Vector3(),
    }),
    []
  );

  useFrame((state) => {
    if (!enabled) return;
    const positions = positionsRef.current;
    if (!positions) return;
    camera.getWorldPosition(scratch.camPos);
    const radius2 = visibilityRadius * visibilityRadius;
    const hasHidden = !!hiddenIds && hiddenIds.size > 0;

    // Per-frame: update position of currently-visible label slots.
    for (let slot = 0; slot < visibleIndices.length; slot++) {
      const g = groupRefs.current[slot];
      if (!g) continue;
      const meta = edgeMeta[visibleIndices[slot]];
      if (!meta) {
        g.visible = false;
        continue;
      }
      if (hasHidden && (hiddenIds!.has(nodes[meta.si].id) || hiddenIds!.has(nodes[meta.ti].id))) {
        g.visible = false;
        continue;
      }
      const a = meta.si * 3;
      const b = meta.ti * 3;
      scratch.s.set(positions[a], positions[a + 1], positions[a + 2]);
      scratch.t.set(positions[b], positions[b + 1], positions[b + 2]);
      scratch.mid.copy(scratch.s).add(scratch.t).multiplyScalar(0.5);

      if (meta.curveOffset !== 0) {
        // Match the bezier midpoint (u=0.5): B(0.5) = 0.25 s + 0.5 ctrl + 0.25 t.
        scratch.edgeDir.subVectors(scratch.t, scratch.s);
        const edgeLen = scratch.edgeDir.length();
        if (edgeLen > 1e-4) {
          scratch.edgeDir.multiplyScalar(1 / edgeLen);
          scratch.perp.crossVectors(scratch.edgeDir, UP);
          if (scratch.perp.lengthSq() < 1e-4) scratch.perp.crossVectors(scratch.edgeDir, FALLBACK);
          scratch.perp.normalize();
          scratch.ctrl.copy(scratch.mid).addScaledVector(scratch.perp, meta.curveOffset * edgeLen);
          scratch.mid
            .copy(scratch.s)
            .multiplyScalar(0.25)
            .addScaledVector(scratch.ctrl, 0.5)
            .addScaledVector(scratch.t, 0.25);
        }
      }

      g.visible = true;
      g.position.copy(scratch.mid);
    }

    // Rescan the visible set on a timer. An edge qualifies if its midpoint
    // is within the radius and neither endpoint is hidden.
    const nowMs = state.clock.elapsedTime * 1000;
    if (nowMs - lastScanRef.current < RESCAN_MS) return;
    lastScanRef.current = nowMs;

    const candidates: { idx: number; dist2: number }[] = [];
    for (let i = 0; i < edgeMeta.length; i++) {
      const m = edgeMeta[i];
      if (hasHidden && (hiddenIds!.has(nodes[m.si].id) || hiddenIds!.has(nodes[m.ti].id))) continue;
      const a = m.si * 3;
      const b = m.ti * 3;
      const mx = (positions[a] + positions[b]) * 0.5;
      const my = (positions[a + 1] + positions[b + 1]) * 0.5;
      const mz = (positions[a + 2] + positions[b + 2]) * 0.5;
      const dx = mx - scratch.camPos.x;
      const dy = my - scratch.camPos.y;
      const dz = mz - scratch.camPos.z;
      const d2 = dx * dx + dy * dy + dz * dz;
      if (d2 < radius2) candidates.push({ idx: i, dist2: d2 });
    }
    // Closest-first; cap at MAX_LABELS.
    candidates.sort((x, y) => x.dist2 - y.dist2);
    const selected = candidates.slice(0, MAX_LABELS).map((c) => c.idx);

    // Only trigger re-render when the visible set actually changes.
    if (
      selected.length !== visibleIndices.length ||
      selected.some((v, i) => v !== visibleIndices[i])
    ) {
      setVisibleIndices(selected);
    }
  });

  if (!enabled || visibleIndices.length === 0) return null;

  return (
    <>
      {visibleIndices.map((edgeIdx, slot) => {
        const meta = edgeMeta[edgeIdx];
        const color = edgePalette ? edgePalette(meta.type) : '#8899aa';
        return (
          <group
            key={`label-${slot}`}
            ref={(g) => {
              groupRefs.current[slot] = g;
            }}
          >
            <Html
              center
              zIndexRange={[50, 0]}
              wrapperClass="pointer-events-none"
              style={{ pointerEvents: 'none' }}
            >
              <div
                style={{
                  padding: '1px 5px',
                  borderRadius: 2,
                  background: 'rgba(10, 10, 15, 0.75)',
                  border: `1px solid ${color}`,
                  color: '#d7d7e0',
                  fontSize: 9,
                  fontFamily: 'SF Mono, Menlo, monospace',
                  whiteSpace: 'nowrap',
                  letterSpacing: 0.4,
                  pointerEvents: 'none',
                }}
              >
                {meta.type}
              </div>
            </Html>
          </group>
        );
      })}
    </>
  );
}
