/**
 * Unit tests for seedWithCarryover — the core of incremental layout.
 *
 * The behaviour these lock down is exactly what stops the whole-graph
 * "sproing" on every poke: a node that survived a graph change must keep
 * its prior position to the bit, only genuinely new nodes get a fresh
 * sphere seed, and carriedCount must let the sim hook tell a fresh graph
 * (full reheat) apart from an incremental poke (gentle reheat).
 */

import { describe, it, expect } from 'vitest';
import { seedWithCarryover } from './positions';

const RADIUS = 120;

describe('seedWithCarryover', () => {
  it('treats an empty prior as a fresh graph (carriedCount 0)', () => {
    const r = seedWithCarryover(['a', 'b', 'c'], [], null, RADIUS);
    expect(r.carriedCount).toBe(0);
    expect(r.positions).toHaveLength(9);
    // Every node is sphere-seeded within the radius.
    for (let i = 0; i < 3; i++) {
      const d = Math.hypot(
        r.positions[i * 3],
        r.positions[i * 3 + 1],
        r.positions[i * 3 + 2]
      );
      expect(d).toBeLessThanOrEqual(RADIUS + 1e-6);
    }
  });

  it('carries every surviving node position to the bit', () => {
    const priorIds = ['a', 'b'];
    const priorPos = new Float32Array([1, 2, 3, 4, 5, 6]);
    const r = seedWithCarryover(['a', 'b'], priorIds, priorPos, RADIUS);
    expect(r.carriedCount).toBe(2);
    expect(Array.from(r.positions)).toEqual([1, 2, 3, 4, 5, 6]);
  });

  it('keeps survivors exact and sphere-seeds only new nodes', () => {
    const priorIds = ['a', 'b'];
    const priorPos = new Float32Array([10, 11, 12, 20, 21, 22]);
    // 'b' survives, 'a' dropped, 'c' is new — and order changed.
    const r = seedWithCarryover(['c', 'b'], priorIds, priorPos, RADIUS);
    expect(r.carriedCount).toBe(1);
    // 'b' lands at its prior position regardless of its new index.
    expect(Array.from(r.positions.subarray(3, 6))).toEqual([20, 21, 22]);
    // 'c' is sphere-seeded (not zero, within radius).
    const cDist = Math.hypot(r.positions[0], r.positions[1], r.positions[2]);
    expect(cDist).toBeGreaterThan(0);
    expect(cDist).toBeLessThanOrEqual(RADIUS + 1e-6);
  });

  it('falls back to a fresh seed when the prior buffer is undersized', () => {
    // priorIds claims 2 nodes but the buffer only has room for 1 — a
    // torn snapshot. Must not read out of bounds; treat as fresh.
    const r = seedWithCarryover(
      ['a', 'b'],
      ['a', 'b'],
      new Float32Array([1, 2, 3]),
      RADIUS
    );
    expect(r.carriedCount).toBe(0);
  });
});
