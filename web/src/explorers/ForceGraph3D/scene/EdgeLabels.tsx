/**
 * Distance-culled edge labels as 3D meshes.
 *
 * Each label is a PlaneGeometry mesh textured with a canvas-rendered
 * relationship type. Real geometry means depth ordering, foreshortening,
 * and integration with the rest of the scene come for free — labels sit
 * on the edge in world space and are masked per-pixel by 3D objects in
 * front of them (no HTML bounding-rect clipping artifacts).
 *
 * Each frame the mesh is positioned at the edge midpoint (curved per the
 * shared bundle bezier) and oriented so its width axis tracks the edge
 * direction while its normal points toward the camera — V1's "orient
 * labels to camera" mode, applied unconditionally because it's the only
 * mode that stays readable from arbitrary angles.
 *
 * Visibility is recomputed on a 5 Hz timer: candidates within
 * labelVisibilityRadius and not endpoint-hidden, sorted by distance,
 * capped at MAX_LABELS. A texture cache keyed by (type, borderColor)
 * means the canvas paint cost amortizes across the small kg vocabulary.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import type { EngineNode, EngineEdge } from '../types';
import { computeBundles, perpendicularBasis } from './bundles';

const UP = new THREE.Vector3(0, 1, 0);
const FALLBACK = new THREE.Vector3(1, 0, 0);
/** Throttle for re-scanning which edges qualify; ~5 Hz is imperceptible. */
const RESCAN_MS = 200;
/** Upper bound on simultaneously-mounted labels to bound per-frame cost. */
const MAX_LABELS = 80;
/** Label height in world units. Width is derived from the texture aspect. */
const LABEL_HEIGHT_WORLD = 1.25;
/** World-space offset along the label's local +Y so it sits above the edge
 *  line instead of on it. Just over half the label height keeps the bottom
 *  of the text from overlapping the line. */
const LABEL_OFFSET_LOCAL_Y = LABEL_HEIGHT_WORLD * 0.5;
/** Canvas font size for text rendering (high-res for crisp scaling). */
const TEXT_FONT_PX = 32;
const TEXT_PADDING_PX = 8;
const TEXT_FONT_FAMILY = "'SF Mono', 'Menlo', monospace";

interface CachedTexture {
  texture: THREE.CanvasTexture;
  aspect: number;
}

/** Render a transparent-background label texture; text takes the edge color. */
function makeLabelTexture(text: string, color: string): CachedTexture {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d')!;
  ctx.font = `${TEXT_FONT_PX}px ${TEXT_FONT_FAMILY}`;
  const metrics = ctx.measureText(text);
  const w = Math.max(2, Math.ceil(metrics.width + TEXT_PADDING_PX * 4));
  const h = Math.ceil(TEXT_FONT_PX + TEXT_PADDING_PX * 2);
  canvas.width = w;
  canvas.height = h;
  // Re-apply context state — canvas resize clears it.
  ctx.font = `${TEXT_FONT_PX}px ${TEXT_FONT_FAMILY}`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = color;
  ctx.fillText(text, w / 2, h / 2);

  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.needsUpdate = true;
  return { texture, aspect: w / h };
}

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
  /** When defined, labels for edges whose endpoints aren't both in this set
   *  are dimmed (material opacity reduced). */
  activeIds?: Set<string>;
}

interface EdgeMeta {
  edgeIndex: number;
  si: number;
  ti: number;
  curveAngle: number;
  curveMag: number;
  type: string;
}

/** 3D plane-mesh edge labels with camera-facing roll.  @verified e05014ea */
/** Dim opacity applied to labels whose endpoints aren't in activeIds. */
const DIM_LABEL_OPACITY = 0.15;

export function EdgeLabels({
  nodes,
  edges,
  positionsRef,
  hiddenIds,
  visibilityRadius = 250,
  enabled = true,
  edgePalette,
  activeIds,
}: EdgeLabelsProps) {
  const camera = useThree((state) => state.camera);

  const edgeMeta: EdgeMeta[] = useMemo(() => {
    const nodeIndex = new Map<string, number>();
    for (let i = 0; i < nodes.length; i++) nodeIndex.set(nodes[i].id, i);
    const usable = edges.filter((e) => nodeIndex.has(e.from) && nodeIndex.has(e.to));
    const { angles, magnitudes } = computeBundles(usable);
    return usable.map((e, i) => ({
      edgeIndex: i,
      si: nodeIndex.get(e.from)!,
      ti: nodeIndex.get(e.to)!,
      curveAngle: angles[i],
      curveMag: magnitudes[i],
      type: e.type,
    }));
  }, [nodes, edges]);

  const [visibleIndices, setVisibleIndices] = useState<number[]>([]);
  const meshRefs = useRef<(THREE.Mesh | null)[]>([]);
  const materialRefs = useRef<(THREE.MeshBasicMaterial | null)[]>([]);
  const textureCache = useRef<Map<string, CachedTexture>>(new Map());
  const lastScanRef = useRef(0);

  useEffect(() => {
    meshRefs.current = new Array(MAX_LABELS).fill(null);
    materialRefs.current = new Array(MAX_LABELS).fill(null);
  }, []);

  // Drop stale indices when the edge set changes (e.g. vocab-type filter
  // toggled). Without this the next frame would index edgeMeta with values
  // that no longer exist.
  useEffect(() => {
    setVisibleIndices([]);
  }, [edgeMeta]);

  // Shared geometry for all label meshes — per-slot scale provides per-text
  // sizing, so one PlaneGeometry suffices.
  const geometry = useMemo(() => new THREE.PlaneGeometry(1, 1), []);
  useEffect(() => () => geometry.dispose(), [geometry]);

  // Texture cache cleanup on unmount — disposes GPU memory.
  useEffect(() => {
    const cache = textureCache.current;
    return () => {
      cache.forEach((entry) => entry.texture.dispose());
      cache.clear();
    };
  }, []);

  // When the visible set changes (or palette/edgeMeta), assign each slot's
  // material a texture and scale the mesh to the texture's aspect ratio.
  // `enabled` is in the deps so the effect re-runs after the user toggles
  // labels off then on — without it the meshes remount but their newly-
  // assigned material refs never get a map, rendering as white squares.
  useEffect(() => {
    if (!enabled) return;
    const hasActive = !!activeIds && activeIds.size > 0;
    for (let slot = 0; slot < visibleIndices.length; slot++) {
      const meta = edgeMeta[visibleIndices[slot]];
      if (!meta) continue;
      const color = edgePalette ? edgePalette(meta.type) : '#8899aa';
      const key = `${meta.type}|${color}`;
      let entry = textureCache.current.get(key);
      if (!entry) {
        entry = makeLabelTexture(meta.type, color);
        textureCache.current.set(key, entry);
      }
      const mat = materialRefs.current[slot];
      const mesh = meshRefs.current[slot];
      const dimmed =
        hasActive &&
        (!activeIds!.has(nodes[meta.si].id) || !activeIds!.has(nodes[meta.ti].id));
      if (mat) {
        mat.map = entry.texture;
        mat.opacity = dimmed ? DIM_LABEL_OPACITY : 1;
        mat.needsUpdate = true;
      }
      if (mesh) {
        mesh.scale.set(entry.aspect * LABEL_HEIGHT_WORLD, LABEL_HEIGHT_WORLD, 1);
      }
    }
  }, [visibleIndices, edgeMeta, edgePalette, enabled, activeIds, nodes]);

  // Scratch vectors reused across the frame loop.
  const scratch = useMemo(
    () => ({
      s: new THREE.Vector3(),
      t: new THREE.Vector3(),
      mid: new THREE.Vector3(),
      e1: new THREE.Vector3(),
      e2: new THREE.Vector3(),
      offsetDir: new THREE.Vector3(),
      edgeDir: new THREE.Vector3(),
      ctrl: new THREE.Vector3(),
      camPos: new THREE.Vector3(),
      toCam: new THREE.Vector3(),
      normal: new THREE.Vector3(),
      up: new THREE.Vector3(),
      basis: new THREE.Matrix4(),
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

    // Per-frame: position + orient currently-visible meshes.
    for (let slot = 0; slot < visibleIndices.length; slot++) {
      const mesh = meshRefs.current[slot];
      if (!mesh) continue;
      const meta = edgeMeta[visibleIndices[slot]];
      if (!meta) {
        mesh.visible = false;
        continue;
      }
      if (hasHidden && (hiddenIds!.has(nodes[meta.si].id) || hiddenIds!.has(nodes[meta.ti].id))) {
        mesh.visible = false;
        continue;
      }
      const a = meta.si * 3;
      const b = meta.ti * 3;
      scratch.s.set(positions[a], positions[a + 1], positions[a + 2]);
      scratch.t.set(positions[b], positions[b + 1], positions[b + 2]);
      scratch.mid.copy(scratch.s).add(scratch.t).multiplyScalar(0.5);

      // Edge direction (used as both the bezier perpendicular basis seed
      // and the label's local +X axis). Tangent of a quadratic bezier at
      // u=0.5 reduces to t-s, so the same vector serves both straight and
      // curved edges.
      scratch.edgeDir.subVectors(scratch.t, scratch.s);
      const edgeLen = scratch.edgeDir.length();
      if (edgeLen < 1e-4) {
        mesh.visible = false;
        continue;
      }
      scratch.edgeDir.multiplyScalar(1 / edgeLen);

      if (meta.curveMag !== 0) {
        // Re-derive the bezier midpoint using the same offset basis as Edges.
        perpendicularBasis(scratch.edgeDir, UP, FALLBACK, scratch.e1, scratch.e2);
        scratch.offsetDir
          .copy(scratch.e1)
          .multiplyScalar(Math.cos(meta.curveAngle));
        scratch.offsetDir.addScaledVector(scratch.e2, Math.sin(meta.curveAngle));
        scratch.ctrl.copy(scratch.mid).addScaledVector(scratch.offsetDir, meta.curveMag * edgeLen);
        // B(0.5) = 0.25 s + 0.5 ctrl + 0.25 t.
        scratch.mid
          .copy(scratch.s)
          .multiplyScalar(0.25)
          .addScaledVector(scratch.ctrl, 0.5)
          .addScaledVector(scratch.t, 0.25);
      }

      // Camera-facing roll around the edge axis: pick the perpendicular-
      // to-edge direction that points most toward the camera as the plane
      // normal. When the edge is nearly aligned with the view direction
      // the projection collapses; fall back to a world-axis perpendicular.
      scratch.toCam.subVectors(scratch.camPos, scratch.mid);
      const dotEC = scratch.toCam.dot(scratch.edgeDir);
      scratch.normal.copy(scratch.toCam).addScaledVector(scratch.edgeDir, -dotEC);
      if (scratch.normal.lengthSq() < 1e-6) {
        const fb = Math.abs(scratch.edgeDir.y) > 0.99 ? FALLBACK : UP;
        scratch.normal.copy(fb).addScaledVector(scratch.edgeDir, -fb.dot(scratch.edgeDir));
      }
      scratch.normal.normalize();
      // up = normal × right (right-handed: right × up = normal).
      scratch.up.copy(scratch.normal).cross(scratch.edgeDir);

      scratch.basis.makeBasis(scratch.edgeDir, scratch.up, scratch.normal);
      mesh.visible = true;
      // Offset along the label's local +Y (which is `scratch.up` in world
      // space — perpendicular to the edge in the camera-facing plane) so
      // the label sits above the edge instead of crossing it.
      mesh.position
        .copy(scratch.mid)
        .addScaledVector(scratch.up, LABEL_OFFSET_LOCAL_Y);
      mesh.quaternion.setFromRotationMatrix(scratch.basis);
    }

    // Rescan the visible set on a timer.
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
    candidates.sort((x, y) => x.dist2 - y.dist2);
    const selected = candidates.slice(0, MAX_LABELS).map((c) => c.idx);

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
        if (!meta) return null;
        return (
          <mesh
            key={`label-${slot}`}
            ref={(m) => {
              meshRefs.current[slot] = m;
            }}
            geometry={geometry}
            renderOrder={1}
          >
            <meshBasicMaterial
              ref={(m) => {
                materialRefs.current[slot] = m;
              }}
              transparent
              depthTest
              depthWrite={false}
              side={THREE.DoubleSide}
              toneMapped={false}
            />
          </mesh>
        );
      })}
    </>
  );
}
