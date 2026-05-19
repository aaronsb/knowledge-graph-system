/**
 * From a PCA frame to a camera pose — the pure half of orientAndFrame.
 *
 * pcaFrame answers "where is the cloud, which way does it face, how big
 * is the part to frame". This turns that into a concrete perspective
 * camera pose: a position, a look-at target, and an up vector that puts
 * the broad face square to the screen and fills the viewport with the
 * caller's intended overscan.
 *
 * Kept pure and three.js-free so it unit-tests in isolation (like
 * pcaFrame / positions): the hook (useOrientAndFrame) owns the tween,
 * useThree wiring, OrbitControls cancellation, and the 2D/degenerate
 * fallbacks — this file owns only the geometry, which is the part with
 * non-obvious math worth locking down with tests.
 *
 * @verified 726f5d45
 */

import type { PcaFrame, Vec3 } from './pcaFrame';

/** A camera pose: where to stand, what to look at, which way is up.  @verified 726f5d45 */
export interface CameraPose {
  position: Vec3;
  target: Vec3;
  /** Up vector — the cloud's mid axis, so screen roll is deterministic. */
  up: Vec3;
}

/** Inputs describing the viewport + the caller's framing intent.  @verified 726f5d45 */
export interface OrientViewOptions {
  /** Vertical field of view, degrees (THREE.PerspectiveCamera.fov). */
  fovDeg: number;
  /** Viewport aspect (width / height). */
  aspect: number;
  /**
   * Overscan factor (<1 = closer, graph spills past the edges). The user
   * wants the graph to fill the view with ~15% spilling off-screen, so
   * the default pulls the camera ~20% inside an exact fit. Tunable; this
   * is the single knob that replaced the old useFitCamera FILL constant.
   */
  fill?: number;
  /**
   * The current camera position MINUS the box centre, in world space.
   * Used only on a non-focus orient (first-load / whole-graph): its
   * minor-axis component picks which side of the broad face the camera
   * lands on, so re-framing keeps the user roughly where they were.
   * Omit (or zero) on first load → deterministic +minor.
   */
  currentOffset?: Vec3;
  /**
   * Focus mode (double-click a node). The clicked node's world position.
   * When set it overrides `currentOffset` and changes the intent: the
   * camera looks AT this node (it becomes the centred, nearest point)
   * and the side is chosen so the *bulk of the graph orients behind it*
   * — camera on the side the node is displaced toward, away from the
   * orientation centroid. A near-centroid node (≈50/50 split) can't be
   * "in front" of anything; we take the deterministic side and let the
   * tween carry the user through the possibly-large swing without them
   * getting lost (user's stated intent).
   */
  focusPoint?: Vec3;
}

const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const add = (a: Vec3, b: Vec3): Vec3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const scale = (a: Vec3, s: number): Vec3 => [a[0] * s, a[1] * s, a[2] * s];

/**
 * Is the cloud too round for a meaningful broad face?
 *
 * When the largest and smallest variances are within `ratio` of each
 * other the blob is roughly spherical: the eigenvectors are numerically
 * unstable and Jacobi will hand back a basis that jitters between calls,
 * so every first-load would orient differently. The hook uses this to
 * fall back to a deterministic angle instead of a PCA one.
 *
 * @verified 726f5d45
 */
export function isNearSpherical(frame: PcaFrame, ratio = 1.5): boolean {
  const [vMax, , vMin] = frame.variances;
  if (vMax <= 1e-9) return true; // no spread at all → degenerate
  if (vMin <= 1e-9) return false; // flat/linear → broad face is well-defined
  return vMax / vMin < ratio;
}

/**
 * Compute the perspective camera pose that frames the PCA extent box
 * face-on with overscan.
 *
 * The camera looks along the minor axis (perpendicular to the broad
 * face); `up` is the mid axis so screen roll is fixed; the major axis
 * therefore runs across the screen horizontally. Distance is whichever
 * of the horizontal/vertical fits is tighter, scaled by `fill`, plus the
 * box's own minor-axis half-depth so it never clips the near side.
 *
 * Assumes the caller has already ruled out the near-spherical case
 * (isNearSpherical) — here the axes are taken as meaningful.
 *
 * @verified 726f5d45
 */
export function orientedPerspectiveView(
  frame: PcaFrame,
  opts: OrientViewOptions
): CameraPose {
  const { center, axes, bounds } = frame;
  const [major, mid, minor] = axes;
  const fill = opts.fill ?? 0.8;

  // Box centre in world space: orientation centroid + the extent box's
  // offset along each axis (the extent set need not be centred on it).
  const mid0 = (bounds.min[0] + bounds.max[0]) / 2;
  const mid1 = (bounds.min[1] + bounds.max[1]) / 2;
  const mid2 = (bounds.min[2] + bounds.max[2]) / 2;
  const boxCenter = add(
    center,
    add(add(scale(major, mid0), scale(mid, mid1)), scale(minor, mid2))
  );

  // Half-extents along major (screen-horizontal), mid (screen-vertical),
  // minor (toward camera). Floor so a single-node focus still frames.
  const hMajor = Math.max((bounds.max[0] - bounds.min[0]) / 2, 0.5);
  const hMid = Math.max((bounds.max[1] - bounds.min[1]) / 2, 0.5);
  const hMinor = Math.max((bounds.max[2] - bounds.min[2]) / 2, 0);

  const vFov = (opts.fovDeg * Math.PI) / 180;
  const hFov = 2 * Math.atan(Math.tan(vFov / 2) * opts.aspect);
  // Distance at which the box just fits each screen axis; take the
  // tighter (larger) so neither axis overflows, then apply overscan.
  const fitV = hMid / Math.tan(vFov / 2);
  const fitH = hMajor / Math.tan(hFov / 2);
  const dist = Math.max(fitV, fitH) * fill + hMinor;

  // Side selection.
  //  - Focus (a node was clicked): put the camera on the side the node
  //    is displaced toward relative to the orientation centroid, so the
  //    node is nearest and the bulk falls behind it. dot ≈ 0 ⇒ the node
  //    sits in the middle (≈50/50) ⇒ deterministic +side, tween covers
  //    the swing.
  //  - Otherwise: stay on whichever side the camera is already on
  //    (default +minor on first load when no offset given).
  let side: number;
  if (opts.focusPoint) {
    const fx = opts.focusPoint[0] - center[0];
    const fy = opts.focusPoint[1] - center[1];
    const fz = opts.focusPoint[2] - center[2];
    side = fx * minor[0] + fy * minor[1] + fz * minor[2] < 0 ? -1 : 1;
  } else {
    side = opts.currentOffset && dot(opts.currentOffset, minor) < 0 ? -1 : 1;
  }

  // Focus looks AT the clicked node (centred, nearest); a whole-graph
  // orient looks at the extent box centre.
  const target = opts.focusPoint ?? boxCenter;

  return {
    position: add(target, scale(minor, side * dist)),
    target,
    up: mid,
  };
}
