/**
 * Auto-frame the camera on first layout (and on every dataset change).
 *
 * The camera mounts at a fixed distance; a freshly-seeded graph settles
 * into a cluster that is usually tiny and off-centre in that fixed view,
 * so the user has to manually zoom every time. This hook waits for the
 * layout to stop moving, then frames the visible nodes — perspective by
 * distance, orthographic by zoom — and re-points the orbit/pan target at
 * the cluster centre so rotation pivots correctly.
 *
 * Settle detection is a bounding-radius delta, not a sim-alpha read: it
 * is mode-agnostic (works while simmering, reheated, or idle, and
 * survives future sim modes) and needs no sim internals — "the thing I
 * am framing has stopped growing" is exactly the signal. A frame cap
 * guarantees a fit even if the layout never fully stabilises.
 *
 * Lives in the shared Scene, so Force Graph and Document Explorer both
 * get it from one implementation.
 *
 * @verified 50606a37
 */

import { useEffect, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import type { EngineNode } from '../types';

/** Consecutive near-stable frames before we accept the layout as settled. */
const STABLE_FRAMES = 5;
/** Hard cap so a never-settling layout still gets framed (~10s at 60fps). */
const MAX_FRAMES = 600;
/**
 * View-fill factor. We frame the cluster's bounding *sphere* (half the
 * box diagonal), which over-estimates a typically-irregular force layout
 * — fitting that sphere exactly already leaves the visible graph small
 * with padding. The user wants the opposite: the graph filling the view
 * and spilling ~15% past the edges. <1 is deliberate overscan; 0.7
 * pulls the camera ~30% closer than a pure sphere-fit so the actual
 * node spread fills the viewport and the outermost nodes/labels sit
 * just outside it. Tunable to taste — lower = closer. Provisional: the
 * planned PCA tangent-orient action will compute the true projected
 * extent and largely supersede this single-constant heuristic.
 */
const FILL = 0.5;

const tmpMin = new THREE.Vector3();
const tmpMax = new THREE.Vector3();
const tmpCenter = new THREE.Vector3();
const tmpDir = new THREE.Vector3();

/** Auto-frames the visible nodes once the layout settles.  @verified 50606a37 */
export function useFitCamera(
  positionsRef: React.MutableRefObject<Float32Array | null>,
  nodes: EngineNode[],
  hiddenIds?: Set<string>
): void {
  const camera = useThree((s) => s.camera);
  const controls = useThree((s) => s.controls) as
    | (THREE.EventDispatcher & { target: THREE.Vector3; update: () => void })
    | null;
  const size = useThree((s) => s.size);
  const invalidate = useThree((s) => s.invalidate);

  const armedRef = useRef(true);
  const framesRef = useRef(0);
  const lastRadiusRef = useRef(-1);
  const stableRef = useRef(0);
  // Whether the previous render had any nodes. We fit only on a 0→N
  // transition: first appearance, or a fresh graph after the prior one
  // was cleared (search/replace). Incremental growth (Add Adjacent),
  // filters, and follow keep N>0 throughout, so they never re-arm —
  // the camera stays where the user left it (a manual "Fit view" is the
  // intended escape hatch). Re-fitting on every change would yank the
  // view ~when the layout re-settles, the camera-side of the trap
  // incremental physics (PR #371) fixed for the sim.
  const hadNodesRef = useRef(false);

  useEffect(() => {
    const has = nodes.length > 0;
    if (has && !hadNodesRef.current) {
      armedRef.current = true;
      framesRef.current = 0;
      lastRadiusRef.current = -1;
      stableRef.current = 0;
      invalidate();
    }
    hadNodesRef.current = has;
  }, [nodes.length, invalidate]);

  useFrame(() => {
    if (!armedRef.current) return;
    // Keep demand-frameloop pumping while we're waiting to fit. The sim
    // stops invalidating once it quiesces; without this, settle/timeout
    // could be reached after frames have already stopped and the fit
    // would never fire. Cleared implicitly when we disarm below.
    invalidate();
    const positions = positionsRef.current;
    const n = nodes.length;
    if (!positions || n === 0 || positions.length < n * 3) return;

    const hasHidden = !!hiddenIds && hiddenIds.size > 0;
    tmpMin.set(Infinity, Infinity, Infinity);
    tmpMax.set(-Infinity, -Infinity, -Infinity);
    let visible = 0;
    for (let i = 0; i < n; i++) {
      if (hasHidden && hiddenIds!.has(nodes[i].id)) continue;
      const x = positions[i * 3];
      const y = positions[i * 3 + 1];
      const z = positions[i * 3 + 2];
      if (x < tmpMin.x) tmpMin.x = x;
      if (y < tmpMin.y) tmpMin.y = y;
      if (z < tmpMin.z) tmpMin.z = z;
      if (x > tmpMax.x) tmpMax.x = x;
      if (y > tmpMax.y) tmpMax.y = y;
      if (z > tmpMax.z) tmpMax.z = z;
      visible++;
    }
    if (visible === 0) return;

    tmpCenter.addVectors(tmpMin, tmpMax).multiplyScalar(0.5);
    // Bounding-sphere radius from the box centre; floor so a single node
    // (or a degenerate co-located cluster) still yields a sane frame.
    const radius = Math.max(0.5 * tmpMax.distanceTo(tmpMin), 1);

    framesRef.current++;
    const last = lastRadiusRef.current;
    lastRadiusRef.current = radius;
    // Relative delta so the threshold scales with graph size.
    if (last > 0 && Math.abs(radius - last) / radius < 0.01) {
      stableRef.current++;
    } else {
      stableRef.current = 0;
    }

    const settled = stableRef.current >= STABLE_FRAMES;
    const timedOut = framesRef.current >= MAX_FRAMES;
    if (!settled && !timedOut) return;
    // Orbit/pan target must be re-pointed for the framing to read right,
    // so prefer waiting for drei's controls to mount — but only briefly
    // (~2s). If they're still absent we fit anyway with a lookAt
    // fallback rather than stall forever.
    if (!controls && framesRef.current < 120 && !timedOut) return;

    if (camera instanceof THREE.OrthographicCamera) {
      // r3f's ortho frustum is the canvas in pixels; zoom = pixels per
      // world unit. Fit the sphere's diameter into the smaller viewport
      // axis with margin.
      const minPx = Math.min(size.width, size.height);
      camera.zoom = minPx / (2 * radius * FILL);
      camera.position.set(tmpCenter.x, tmpCenter.y, camera.position.z);
      camera.updateProjectionMatrix();
    } else if (camera instanceof THREE.PerspectiveCamera) {
      const vFov = (camera.fov * Math.PI) / 180;
      const hFov = 2 * Math.atan(Math.tan(vFov / 2) * camera.aspect);
      const dist =
        Math.max(radius / Math.sin(vFov / 2), radius / Math.sin(hFov / 2)) *
        FILL;
      // Preserve the current viewing direction; fall back to looking
      // down -Z if the camera and target coincide.
      tmpDir.copy(camera.position);
      if (controls) tmpDir.sub(controls.target);
      if (tmpDir.lengthSq() < 1e-6) tmpDir.set(0, 0, 1);
      tmpDir.normalize();
      camera.position.copy(tmpCenter).addScaledVector(tmpDir, dist);
      camera.updateProjectionMatrix();
    }

    if (controls) {
      controls.target.copy(tmpCenter);
      controls.update();
    } else {
      camera.lookAt(tmpCenter);
    }

    armedRef.current = false;
    invalidate();
  });
}
