/**
 * Unit tests for orientView — PCA frame → perspective camera pose.
 *
 * These lock down the non-obvious geometry: the camera looks along the
 * minor axis with the mid axis up (deterministic roll), the fit distance
 * honours the tighter of the two screen axes plus overscan, and — the
 * part the user cares about most — focus mode puts the clicked node in
 * front with the bulk behind it, flipping sides when the node is on the
 * far face even if that "whips the camera around".
 */

import { describe, it, expect } from 'vitest';
import {
  orientedPerspectiveView,
  isNearSpherical,
  type OrientViewOptions,
} from './orientView';
import type { PcaFrame, Vec3 } from './pcaFrame';

/** A world-aligned PCA frame: major→X, mid→Y, minor→Z, centred at C. */
function frame(
  hx: number,
  hy: number,
  hz: number,
  center: Vec3 = [0, 0, 0],
  variances: [number, number, number] = [9, 4, 1]
): PcaFrame {
  return {
    center,
    axes: [
      [1, 0, 0],
      [0, 1, 0],
      [0, 0, 1],
    ],
    variances,
    bounds: { min: [-hx, -hy, -hz], max: [hx, hy, hz] },
  };
}

// fov=90° ⇒ tan(vFov/2)=1; aspect=1 ⇒ hFov=vFov. With hMajor=hMid=R the
// fit distance is exactly R on each axis → easy to assert in closed form.
const SQUARE: OrientViewOptions = { fovDeg: 90, aspect: 1, fill: 1 };

describe('isNearSpherical', () => {
  it('flags a ball-shaped cloud (variances within ratio)', () => {
    expect(isNearSpherical(frame(1, 1, 1, [0, 0, 0], [1.2, 1.1, 1]))).toBe(true);
  });
  it('passes an elongated cloud (well-defined broad face)', () => {
    expect(isNearSpherical(frame(1, 1, 1, [0, 0, 0], [10, 4, 2]))).toBe(false);
  });
  it('treats a flat slab (zero minor variance) as well-defined', () => {
    expect(isNearSpherical(frame(1, 1, 0, [0, 0, 0], [10, 5, 0]))).toBe(false);
  });
  it('treats a no-spread cloud as degenerate', () => {
    expect(isNearSpherical(frame(0, 0, 0, [0, 0, 0], [0, 0, 0]))).toBe(true);
  });
});

describe('orientedPerspectiveView', () => {
  it('looks along the minor axis with the mid axis up', () => {
    const pose = orientedPerspectiveView(frame(10, 10, 0), SQUARE);
    expect(pose.up).toEqual([0, 1, 0]); // mid → screen-up
    expect(pose.target).toEqual([0, 0, 0]); // box centre
    // Camera on +Z (default side), looking back toward origin.
    expect(pose.position[0]).toBeCloseTo(0, 6);
    expect(pose.position[1]).toBeCloseTo(0, 6);
    expect(pose.position[2]).toBeGreaterThan(0);
  });

  it('depth-anchored: a deep cluster stands at its near face (hMinor+guard)', () => {
    // Deep cluster (hMinor=40), small floor (fill=0.2). exactFit=10 ⇒
    // floor=2; depth anchor = 40 + NEAR_GUARD(1) = 41 dominates. This is
    // the "fills the viewport, spills slightly" framing the user picked.
    const pose = orientedPerspectiveView(frame(10, 10, 40), {
      ...SQUARE,
      fill: 0.2,
    });
    expect(pose.position[2]).toBeCloseTo(41, 5);
  });

  it('pullback eases the camera back by a fraction of the face-on fit', () => {
    // Deep cluster so the depth anchor dominates. exactFit=10.
    const tight = orientedPerspectiveView(frame(10, 10, 40), {
      ...SQUARE,
      fill: 0.2,
    }); // pullback default 0 ⇒ 40 + 1
    const eased = orientedPerspectiveView(frame(10, 10, 40), {
      ...SQUARE,
      fill: 0.2,
      pullback: 0.2,
    }); // + exactFit(10) × 0.2 = +2
    expect(tight.position[2]).toBeCloseTo(41, 5);
    expect(eased.position[2]).toBeCloseTo(43, 5);
    expect(eased.position[2] - tight.position[2]).toBeCloseTo(2, 5);
  });

  it('viewport floor catches a flat cluster instead of collapsing', () => {
    // Flat cluster (hMinor=0): depth anchor = 0+1 = 1 would drop the
    // camera into the focal node. exactFit=10, fill=0.2 ⇒ floor=2 wins,
    // so the camera is held at a viewport-sane distance, not 1.
    const flat = orientedPerspectiveView(frame(10, 10, 0), {
      ...SQUARE,
      fill: 0.2,
    });
    expect(flat.position[2]).toBeCloseTo(2, 5);
    // And the floor scales with fill (it is `fill × exactFit`).
    const tighter = orientedPerspectiveView(frame(10, 10, 0), {
      ...SQUARE,
      fill: 0.1,
    });
    expect(tighter.position[2]).toBeCloseTo(1, 5);
    expect(tighter.position[2]).toBeLessThan(flat.position[2]);
  });

  it('non-focus: currentOffset picks the side the camera is already on', () => {
    const back = orientedPerspectiveView(frame(10, 10, 0), {
      ...SQUARE,
      currentOffset: [0, 0, -50],
    });
    expect(back.position[2]).toBeLessThan(0); // stayed on −Z side
  });

  it('focus: clicked node is centred and nearest, bulk behind it', () => {
    // Centroid at origin; clicked node displaced toward +Z. Camera must
    // sit beyond the node on +Z so the node is closest and the bulk
    // (around origin) is behind it.
    const node: Vec3 = [2, 0, 8];
    const pose = orientedPerspectiveView(frame(10, 10, 1), {
      ...SQUARE,
      focusPoint: node,
    });
    expect(pose.target).toEqual(node); // looks AT the node
    expect(pose.position[2]).toBeGreaterThan(node[2]); // camera beyond node
    // Node sits between camera and the bulk centroid (origin).
    expect(node[2]).toBeGreaterThan(0);
  });

  it('focus: node on the far face flips the camera around', () => {
    // Same orientation, but the node is on the −Z face. The user
    // explicitly accepts the camera "whipping around" so the node is
    // still the nearest, bulk-behind point.
    const node: Vec3 = [0, 0, -8];
    const pose = orientedPerspectiveView(frame(10, 10, 1), {
      ...SQUARE,
      focusPoint: node,
      currentOffset: [0, 0, +50], // would say +Z; focus must override
    });
    expect(pose.position[2]).toBeLessThan(node[2]); // flipped to −Z
  });
});
