/**
 * orientAndFrame — the reusable camera action.
 *
 * One verb, two callers: first-load fires `orient()` once as a "fake
 * zoom-extents" (task #27); a double-click fires `focus(id)` on the
 * clicked node (task #28). Both rotate the camera to face the graph's
 * broad face (pcaFrame + orientView) and ease into the new pose.
 *
 * Why a hook and not a helper: the pose math is pure (orientView, tested
 * separately), but the *action* needs live three state (camera, drei
 * controls, viewport) and owns a tween loop that must cancel the instant
 * the user grabs the controls. That all lives here.
 *
 * Decisions baked in (tasks #29/#30, user-confirmed):
 *  - Hybrid focus: orientation axes come from the whole visible graph
 *    (stable angle) while the framed extent is the clicked node's
 *    1-hop neighbourhood (tightens onto the region). The clicked node
 *    becomes the centred, nearest point with the bulk behind it.
 *  - Tweened for both: even first-load eases in (consistent motion),
 *    ~0.45s easeInOutCubic, cancellable on any controls interaction.
 *  - Near-spherical / 2D: no meaningful broad face → don't rotate, just
 *    reframe along the current view direction (deterministic, no jitter).
 *
 * @verified 726f5d45
 */

import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import type { EngineNode, EngineEdge, Projection } from '../types';
import { pcaFrame } from './pcaFrame';
import {
  orientedPerspectiveView,
  isNearSpherical,
  type CameraPose,
} from './orientView';

/** Tween duration — long enough to track the swing, short enough not to drag. */
const TWEEN_MS = 450;
/** Default overscan: graph fills the view, ~15% spilling off (user's ideal). */
const DEFAULT_FILL = 0.82;

export interface OrientAndFrameOptions {
  hiddenIds?: Set<string>;
  edges?: EngineEdge[];
  projection?: Projection;
  /** Overscan factor (<1 = closer / more spill). Defaults to DEFAULT_FILL. */
  fill?: number;
}

/** The reusable camera action: whole-graph orient, or focus on a node.  @verified 726f5d45 */
export interface OrientAndFrame {
  /** Whole-graph orient — first-load fake-zoom-extents / fit view. */
  orient(): void;
  /** Focus orient on a node id — double-click target. */
  focus(nodeId: string): void;
}

type Vec3T = [number, number, number];

const easeInOutCubic = (t: number) =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

interface Tween {
  fromPos: THREE.Vector3;
  toPos: THREE.Vector3;
  fromTarget: THREE.Vector3;
  toTarget: THREE.Vector3;
  fromZoom: number;
  toZoom: number;
  start: number;
}

/**
 * Build the action. The hook owns a single tween loop driven off
 * useFrame; it invalidates the demand loop while a tween is live and
 * stops dead the moment OrbitControls emits `start` (user grabbed it).
 *
 * @verified 726f5d45
 */
export function useOrientAndFrame(
  positionsRef: React.MutableRefObject<Float32Array | null>,
  nodes: EngineNode[],
  opts: OrientAndFrameOptions = {}
): OrientAndFrame {
  const camera = useThree((s) => s.camera);
  const controls = useThree((s) => s.controls) as
    | (THREE.EventDispatcher & {
        target: THREE.Vector3;
        update: () => void;
      })
    | null;
  const size = useThree((s) => s.size);
  const invalidate = useThree((s) => s.invalidate);

  const { hiddenIds, edges, projection = '3D', fill = DEFAULT_FILL } = opts;

  // 1-hop adjacency for Hybrid focus extents. Rebuilt only when the edge
  // set changes; a focus click reads it without touching the sim.
  const adjacency = useMemo(() => {
    const adj = new Map<string, Set<string>>();
    if (!edges) return adj;
    for (const e of edges) {
      (adj.get(e.from) ?? adj.set(e.from, new Set()).get(e.from)!).add(e.to);
      (adj.get(e.to) ?? adj.set(e.to, new Set()).get(e.to)!).add(e.from);
    }
    return adj;
  }, [edges]);

  const tweenRef = useRef<Tween | null>(null);

  // Cancel an in-flight tween the instant the user touches the controls,
  // and whenever a new orient supersedes it. drei's controls emit a
  // 'start' event on the first interaction of a gesture.
  useEffect(() => {
    if (!controls) return;
    const cancel = () => {
      tweenRef.current = null;
    };
    controls.addEventListener('start', cancel);
    return () => controls.removeEventListener('start', cancel);
  }, [controls]);

  // Indices of nodes that are actually visible (drive orientation PCA).
  const visibleIndices = useCallback((): number[] => {
    const has = !!hiddenIds && hiddenIds.size > 0;
    const out: number[] = [];
    for (let i = 0; i < nodes.length; i++) {
      if (has && hiddenIds!.has(nodes[i].id)) continue;
      out.push(i);
    }
    return out;
  }, [nodes, hiddenIds]);

  // Translate a target pose into a tween from the camera's current pose.
  const startTween = useCallback(
    (pose: CameraPose, zoom: number) => {
      // Deliberately DO NOT adopt pose.up (the cloud's mid axis). A force
      // layout has no inherent orientation, so the user's mental model is
      // "Y is up". Snapping camera.up to the PCA mid axis would (1) roll
      // the view instantly at t=0 — the exact disorientation the tween
      // exists to prevent — and (2) leave OrbitControls with a tilted
      // orbit pole, so all later rotation feels off-gravity. Keeping
      // world-Y up and letting lookAt resolve roll costs only a slightly
      // conservative fit (a touch more spill), which is harmless.
      // pose.up stays part of the geometric contract (and orientView's
      // tests) as the broad-face up; the hook just doesn't apply it.
      if (!controls) {
        // No controls yet (early first-load) — snap; the tween loop has
        // nothing to lerp the target against. Rare; caller retries.
        camera.position.set(...pose.position);
        camera.lookAt(...pose.target);
        if (camera instanceof THREE.OrthographicCamera) camera.zoom = zoom;
        camera.updateProjectionMatrix();
        invalidate();
        return;
      }
      tweenRef.current = {
        fromPos: camera.position.clone(),
        toPos: new THREE.Vector3(...pose.position),
        fromTarget: controls.target.clone(),
        toTarget: new THREE.Vector3(...pose.target),
        fromZoom: camera.zoom,
        toZoom: zoom,
        start: performance.now(),
      };
      invalidate();
    },
    [camera, controls, invalidate]
  );

  // Frame-only fallback (2D ortho, or a near-spherical 3D blob): don't
  // rotate — keep the current view direction, just re-fit distance/zoom
  // to the extent set's bounding sphere along that direction.
  const frameAlongCurrentDir = useCallback(
    (extentIdx: number[], positions: Float32Array): void => {
      const min = new THREE.Vector3(Infinity, Infinity, Infinity);
      const max = new THREE.Vector3(-Infinity, -Infinity, -Infinity);
      for (const i of extentIdx) {
        const x = positions[i * 3];
        const y = positions[i * 3 + 1];
        const z = positions[i * 3 + 2];
        min.min(new THREE.Vector3(x, y, z));
        max.max(new THREE.Vector3(x, y, z));
      }
      if (!Number.isFinite(min.x)) return;
      const center = min.clone().add(max).multiplyScalar(0.5);
      const radius = Math.max(0.5 * min.distanceTo(max), 1);

      if (camera instanceof THREE.OrthographicCamera) {
        const minPx = Math.min(size.width, size.height);
        const zoom = minPx / (2 * radius * fill);
        startTween(
          {
            position: [center.x, center.y, camera.position.z],
            target: [center.x, center.y, 0],
            up: [camera.up.x, camera.up.y, camera.up.z],
          },
          zoom
        );
        return;
      }
      const cam = camera as THREE.PerspectiveCamera;
      const vFov = (cam.fov * Math.PI) / 180;
      const hFov = 2 * Math.atan(Math.tan(vFov / 2) * cam.aspect);
      const dist =
        Math.max(radius / Math.sin(vFov / 2), radius / Math.sin(hFov / 2)) *
        fill;
      const dir = cam.position.clone();
      if (controls) dir.sub(controls.target);
      if (dir.lengthSq() < 1e-6) dir.set(0, 0, 1);
      dir.normalize();
      const pos = center.clone().addScaledVector(dir, dist);
      startTween(
        {
          position: [pos.x, pos.y, pos.z],
          target: [center.x, center.y, center.z],
          up: [camera.up.x, camera.up.y, camera.up.z],
        },
        camera.zoom
      );
    },
    [camera, controls, size, fill, startTween]
  );

  const run = useCallback(
    (focusNodeId?: string): void => {
      const positions = positionsRef.current;
      if (!positions) return;
      const orientIdx = visibleIndices();
      if (orientIdx.length === 0) return;

      // Extent set: focus → clicked node + its 1-hop neighbours (Hybrid);
      // whole-graph → the visible set itself.
      let extentIdx = orientIdx;
      let focusPoint: Vec3T | undefined;
      if (focusNodeId) {
        const idById = new Map<string, number>();
        for (const i of orientIdx) idById.set(nodes[i].id, i);
        const fi = idById.get(focusNodeId);
        if (fi != null) {
          focusPoint = [
            positions[fi * 3],
            positions[fi * 3 + 1],
            positions[fi * 3 + 2],
          ];
          const set = new Set<number>([fi]);
          for (const nid of adjacency.get(focusNodeId) ?? []) {
            const ni = idById.get(nid);
            if (ni != null) set.add(ni);
          }
          extentIdx = [...set];
        }
      }

      // 2D is z-flat: no broad face to find — frame only, never rotate
      // (rotating an ortho/pan view breaks its semantics).
      if (projection === '2D' || camera instanceof THREE.OrthographicCamera) {
        frameAlongCurrentDir(extentIdx, positions);
        return;
      }

      const frame = pcaFrame(positions, orientIdx, extentIdx);
      if (isNearSpherical(frame)) {
        // Ball-shaped: eigenvectors jitter between calls → don't rotate.
        frameAlongCurrentDir(extentIdx, positions);
        return;
      }

      const cam = camera as THREE.PerspectiveCamera;
      const currentOffset: Vec3T = [
        camera.position.x - frame.center[0],
        camera.position.y - frame.center[1],
        camera.position.z - frame.center[2],
      ];
      const pose = orientedPerspectiveView(frame, {
        fovDeg: cam.fov,
        aspect: cam.aspect,
        fill,
        currentOffset,
        focusPoint,
      });
      startTween(pose, camera.zoom);
    },
    [
      positionsRef,
      nodes,
      adjacency,
      visibleIndices,
      projection,
      camera,
      fill,
      frameAlongCurrentDir,
      startTween,
    ]
  );

  useFrame(() => {
    const tw = tweenRef.current;
    if (!tw) return;
    const t = Math.min(1, (performance.now() - tw.start) / TWEEN_MS);
    const e = easeInOutCubic(t);
    camera.position.lerpVectors(tw.fromPos, tw.toPos, e);
    if (controls) {
      controls.target.lerpVectors(tw.fromTarget, tw.toTarget, e);
    }
    if (camera instanceof THREE.OrthographicCamera) {
      camera.zoom = tw.fromZoom + (tw.toZoom - tw.fromZoom) * e;
    }
    camera.updateProjectionMatrix();
    controls?.update();
    if (t >= 1) tweenRef.current = null;
    invalidate(); // keep the demand loop pumping until the ease completes
  });

  return useMemo<OrientAndFrame>(
    () => ({
      orient: () => run(),
      focus: (nodeId: string) => run(nodeId),
    }),
    [run]
  );
}
