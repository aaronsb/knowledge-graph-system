/**
 * Distance-culled node labels as 3D meshes.
 *
 * Persistent labels for nodes within labelVisibilityRadius of the camera.
 * Same canvas-texture-on-PlaneGeometry pattern as EdgeLabels — real depth
 * ordering, foreshortening, and per-pixel occlusion against the rest of
 * the scene. Unlike edge labels these are screen-aligned billboards: the
 * label normal faces the camera and its "up" is locked to camera.up so
 * text stays horizontal in the viewport regardless of camera tilt.
 *
 * Visible set is recomputed on a 5 Hz timer; per frame we just position
 * and orient the meshes that are already mounted. Texture cache keyed by
 * (label, color) keeps canvas paint cost amortized across the dataset.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import type { EngineNode } from '../types';

/** Throttle for re-scanning which nodes qualify; ~5 Hz is imperceptible. */
const RESCAN_MS = 200;
/** Upper bound on simultaneously-mounted labels to bound per-frame cost. */
const MAX_LABELS = 120;
/** Label height in world units. Width derived from texture aspect. */
const LABEL_HEIGHT_WORLD = 1.0;
/** Vertical offset above the node (world up before billboard rotation). */
const LABEL_OFFSET_ABOVE = 1.4;
/** Canvas font size for text rendering (high-res for crisp scaling). */
const TEXT_FONT_PX = 32;
const TEXT_PADDING_PX = 8;
const TEXT_FONT_FAMILY = "'SF Mono', 'Menlo', monospace";

interface CachedTexture {
  texture: THREE.CanvasTexture;
  aspect: number;
}

/** Render a transparent-background label texture; text takes the node color. */
function makeLabelTexture(text: string, color: string): CachedTexture {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d')!;
  ctx.font = `${TEXT_FONT_PX}px ${TEXT_FONT_FAMILY}`;
  const metrics = ctx.measureText(text);
  const w = Math.max(2, Math.ceil(metrics.width + TEXT_PADDING_PX * 4));
  const h = Math.ceil(TEXT_FONT_PX + TEXT_PADDING_PX * 2);
  canvas.width = w;
  canvas.height = h;
  ctx.font = `${TEXT_FONT_PX}px ${TEXT_FONT_FAMILY}`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  // Subtle dark stroke for legibility against light/colored backgrounds.
  ctx.strokeStyle = 'rgba(10, 10, 15, 0.85)';
  ctx.lineWidth = 4;
  ctx.strokeText(text, w / 2, h / 2);
  ctx.fillStyle = color;
  ctx.fillText(text, w / 2, h / 2);

  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.needsUpdate = true;
  return { texture, aspect: w / h };
}

export interface NodeLabelsProps {
  nodes: EngineNode[];
  positionsRef: React.MutableRefObject<Float32Array | null>;
  /** Per-node colors, parallel to `nodes` by index. */
  colors: string[];
  hiddenIds?: Set<string>;
  /** Labels past this world-space distance from the camera are unmounted. */
  visibilityRadius?: number;
  enabled?: boolean;
  /** When defined, labels for nodes not in this set are dimmed. */
  activeIds?: Set<string>;
}

/** Dim opacity applied to labels for nodes outside activeIds. */
const DIM_LABEL_OPACITY = 0.15;

/** Persistent billboarded node labels with distance culling.  @verified e05014ea */
export function NodeLabels({
  nodes,
  positionsRef,
  colors,
  hiddenIds,
  visibilityRadius = 250,
  enabled = true,
  activeIds,
}: NodeLabelsProps) {
  const camera = useThree((state) => state.camera);

  const [visibleIndices, setVisibleIndices] = useState<number[]>([]);
  const meshRefs = useRef<(THREE.Mesh | null)[]>([]);
  const materialRefs = useRef<(THREE.MeshBasicMaterial | null)[]>([]);
  const textureCache = useRef<Map<string, CachedTexture>>(new Map());
  const lastScanRef = useRef(0);

  useEffect(() => {
    meshRefs.current = new Array(MAX_LABELS).fill(null);
    materialRefs.current = new Array(MAX_LABELS).fill(null);
  }, []);

  // Drop stale indices when the node set changes.
  useEffect(() => {
    setVisibleIndices([]);
  }, [nodes]);

  const geometry = useMemo(() => new THREE.PlaneGeometry(1, 1), []);
  useEffect(() => () => geometry.dispose(), [geometry]);

  useEffect(() => {
    const cache = textureCache.current;
    return () => {
      cache.forEach((entry) => entry.texture.dispose());
      cache.clear();
    };
  }, []);

  // Apply texture + scale to each visible slot. `enabled` is in deps so
  // the effect re-runs after toggle-off → toggle-on — without it the
  // remounted meshes get white-square materials with no map.
  useEffect(() => {
    if (!enabled) return;
    const hasActive = !!activeIds && activeIds.size > 0;
    for (let slot = 0; slot < visibleIndices.length; slot++) {
      const idx = visibleIndices[slot];
      const node = nodes[idx];
      if (!node) continue;
      const color = colors[idx] ?? '#d7d7e0';
      const key = `${node.label}|${color}`;
      let entry = textureCache.current.get(key);
      if (!entry) {
        entry = makeLabelTexture(node.label, color);
        textureCache.current.set(key, entry);
      }
      const mat = materialRefs.current[slot];
      const mesh = meshRefs.current[slot];
      const dimmed = hasActive && !activeIds!.has(node.id);
      if (mat) {
        mat.map = entry.texture;
        mat.opacity = dimmed ? DIM_LABEL_OPACITY : 1;
        mat.needsUpdate = true;
      }
      if (mesh) {
        mesh.scale.set(entry.aspect * LABEL_HEIGHT_WORLD, LABEL_HEIGHT_WORLD, 1);
      }
    }
  }, [visibleIndices, nodes, colors, enabled, activeIds]);

  const scratch = useMemo(
    () => ({
      pos: new THREE.Vector3(),
      camPos: new THREE.Vector3(),
      labelPos: new THREE.Vector3(),
      normal: new THREE.Vector3(),
      right: new THREE.Vector3(),
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

    // Per-frame: position + billboard-orient currently-visible meshes.
    for (let slot = 0; slot < visibleIndices.length; slot++) {
      const mesh = meshRefs.current[slot];
      if (!mesh) continue;
      const idx = visibleIndices[slot];
      const node = nodes[idx];
      if (!node) {
        mesh.visible = false;
        continue;
      }
      if (hasHidden && hiddenIds!.has(node.id)) {
        mesh.visible = false;
        continue;
      }
      const a = idx * 3;
      scratch.pos.set(positions[a], positions[a + 1], positions[a + 2]);

      // Offset above the node along world-up. Once the mesh faces the
      // camera (via lookAt) this stays "above" from the viewer's POV
      // because lookAt rotates around the node, not around world-up.
      scratch.labelPos.copy(scratch.pos);
      scratch.labelPos.y += LABEL_OFFSET_ABOVE;

      // Screen-aligned billboard: normal points at the camera, "up" locked
      // to the camera's world-up so text stays horizontal in the viewport
      // regardless of how the user tilts the camera. Differs from the
      // full lookAt() billboard, which tilts with the camera.
      scratch.normal.subVectors(scratch.camPos, scratch.labelPos).normalize();
      scratch.right.crossVectors(camera.up, scratch.normal);
      const rightLen = scratch.right.length();
      if (rightLen < 1e-6) {
        // Camera looking straight along its own up vector — degenerate.
        // Skip this frame; the next camera nudge will recover.
        mesh.visible = false;
        continue;
      }
      scratch.right.multiplyScalar(1 / rightLen);
      scratch.up.crossVectors(scratch.normal, scratch.right);
      scratch.basis.makeBasis(scratch.right, scratch.up, scratch.normal);

      mesh.visible = true;
      mesh.position.copy(scratch.labelPos);
      mesh.quaternion.setFromRotationMatrix(scratch.basis);
    }

    const nowMs = state.clock.elapsedTime * 1000;
    if (nowMs - lastScanRef.current < RESCAN_MS) return;
    lastScanRef.current = nowMs;

    const candidates: { idx: number; dist2: number }[] = [];
    for (let i = 0; i < nodes.length; i++) {
      if (hasHidden && hiddenIds!.has(nodes[i].id)) continue;
      const a = i * 3;
      const dx = positions[a] - scratch.camPos.x;
      const dy = positions[a + 1] - scratch.camPos.y;
      const dz = positions[a + 2] - scratch.camPos.z;
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
      {visibleIndices.map((idx, slot) => (
        <mesh
          key={`nodelabel-${slot}`}
          ref={(m) => {
            meshRefs.current[slot] = m;
          }}
          geometry={geometry}
          renderOrder={2}
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
      ))}
    </>
  );
}
