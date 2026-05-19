/**
 * Unit tests for pcaFrame — the geometry that orients the camera to the
 * graph's broad face.
 *
 * What these lock down: the minor axis really is the thinnest direction
 * (look along it ⇒ face the bulk), the axes stay orthonormal even on
 * degenerate clouds, and the Hybrid split holds — orientation from one
 * point set, extent bounds from another, centred on the orientation
 * centroid (so a focus click tightens without spinning the view).
 */

import { describe, it, expect } from 'vitest';
import { pcaFrame, type Vec3 } from './pcaFrame';

/** |a·b| — sign of eigenvectors is arbitrary, so compare absolute alignment. */
const absDot = (a: Vec3, b: Vec3) =>
  Math.abs(a[0] * b[0] + a[1] * b[1] + a[2] * b[2]);
const len = (a: Vec3) => Math.hypot(a[0], a[1], a[2]);

describe('pcaFrame', () => {
  it('puts the minor axis along the thinnest direction (flat XY slab)', () => {
    // Wide in X, medium in Y, ~flat in Z → major≈X, mid≈Y, minor≈Z.
    const pts: number[] = [];
    for (let x = -10; x <= 10; x += 2)
      for (let y = -4; y <= 4; y += 2) pts.push(x, y, 0);
    const f = pcaFrame(pts);

    expect(absDot(f.axes[0], [1, 0, 0])).toBeGreaterThan(0.99); // major → X
    expect(absDot(f.axes[1], [0, 1, 0])).toBeGreaterThan(0.99); // mid   → Y
    expect(absDot(f.axes[2], [0, 0, 1])).toBeGreaterThan(0.99); // minor → Z
    expect(f.variances[0]).toBeGreaterThan(f.variances[1]);
    expect(f.variances[1]).toBeGreaterThan(f.variances[2]);
    expect(f.variances[2]).toBeCloseTo(0, 6); // perfectly flat ⇒ no Z spread
  });

  it('keeps axes orthonormal and centre correct', () => {
    const pts = [1, 2, 3, 5, 1, 0, -3, 4, 2, 2, -2, 7, 0, 0, 0];
    const f = pcaFrame(pts);
    const [a, b, c] = f.axes;
    for (const v of f.axes) expect(len(v)).toBeCloseTo(1, 6);
    expect(absDot(a, b)).toBeCloseTo(0, 6);
    expect(absDot(b, c)).toBeCloseTo(0, 6);
    expect(absDot(a, c)).toBeCloseTo(0, 6);
    // Centroid of the 5 points.
    expect(f.center[0]).toBeCloseTo((1 + 5 - 3 + 2 + 0) / 5, 6);
    expect(f.center[1]).toBeCloseTo((2 + 1 + 4 - 2 + 0) / 5, 6);
    expect(f.center[2]).toBeCloseTo((3 + 0 + 2 + 7 + 0) / 5, 6);
  });

  it('survives a degenerate cloud (single point) with a sane basis', () => {
    const f = pcaFrame([4, 4, 4]);
    for (const v of f.axes) expect(len(v)).toBeCloseTo(1, 6);
    expect(f.variances).toEqual([0, 0, 0]);
    expect(f.center).toEqual([4, 4, 4]);
    // Bounds collapse to the centre (zero-size box at the point).
    expect(f.bounds.min).toEqual([0, 0, 0]);
    expect(f.bounds.max).toEqual([0, 0, 0]);
  });

  it('Hybrid: orientation from the full cloud, extent from a subset', () => {
    // Full cloud is wide in X (defines the axes + centroid). The extent
    // subset is a tight pair near +X — bounds must reflect only those,
    // while the axes/centre still come from the whole cloud.
    const pts: number[] = [];
    for (let x = -20; x <= 20; x += 1) pts.push(x, 0, 0); // 41 nodes on X
    const all = pts.length / 3;
    const orient = Array.from({ length: all }, (_, i) => i);
    // Subset = the two right-most nodes (x = 19, 20 → indices 39,40).
    const extent = [39, 40];

    const f = pcaFrame(pts, orient, extent);

    expect(absDot(f.axes[0], [1, 0, 0])).toBeGreaterThan(0.99); // global major
    expect(f.center[0]).toBeCloseTo(0, 6); // global centroid (symmetric)

    // Extent bounds along the major axis: nodes 39,40 sit at x=19,20,
    // i.e. projection 19 and 20 relative to centre 0.
    const lo = Math.min(f.bounds.min[0], f.bounds.max[0]);
    const hi = Math.max(f.bounds.min[0], f.bounds.max[0]);
    expect(lo).toBeCloseTo(19, 5);
    expect(hi).toBeCloseTo(20, 5);
    // Off-axis spread of the subset is zero.
    expect(f.bounds.max[1] - f.bounds.min[1]).toBeCloseTo(0, 6);
  });

  it('handles a line cloud: one dominant axis, two collapsed', () => {
    // Points along the (1,1,0)/√2 direction → major along it, the other
    // two variances ~0 but axes still orthonormal.
    const pts: number[] = [];
    for (let t = -10; t <= 10; t++) pts.push(t, t, 0);
    const f = pcaFrame(pts);
    expect(absDot(f.axes[0], [Math.SQRT1_2, Math.SQRT1_2, 0])).toBeGreaterThan(
      0.99
    );
    expect(f.variances[0]).toBeGreaterThan(1);
    expect(f.variances[1]).toBeCloseTo(0, 6);
    expect(f.variances[2]).toBeCloseTo(0, 6);
    const [a, b, c] = f.axes;
    expect(absDot(a, b)).toBeCloseTo(0, 6);
    expect(absDot(b, c)).toBeCloseTo(0, 6);
    expect(absDot(a, c)).toBeCloseTo(0, 6);
  });
});
