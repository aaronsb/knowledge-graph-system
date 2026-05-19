/**
 * Unit tests for the platonic-solid glyph mapping.
 *
 * Locks the two properties the visual encoding depends on: shapeFor is
 * a pure deterministic function (same category → same solid, every
 * reload), and it actually spreads categories across the family (a
 * future "let's randomize / always icosahedron" regression breaks
 * here). Also guards the legend-glyph table against drifting out of
 * sync with SHAPE_NAMES.
 */

import { describe, it, expect } from 'vitest';
import {
  SHAPE_NAMES,
  SHAPE_GLYPH_POLYS,
  shapeFor,
} from './shapes';

describe('shapeFor', () => {
  it('is deterministic for a given category', () => {
    expect(shapeFor('foo')).toBe(shapeFor('foo'));
    expect(shapeFor('Software Engineering')).toBe(
      shapeFor('Software Engineering')
    );
  });

  it('always returns a member of the solid family', () => {
    for (const c of ['', 'a', 'Watergate', 'ITSM', 'Φ', '🜁', 'Unknown']) {
      expect(SHAPE_NAMES).toContain(shapeFor(c));
    }
  });

  it('treats null/undefined as the empty category (no throw)', () => {
    expect(SHAPE_NAMES).toContain(shapeFor(null));
    expect(SHAPE_NAMES).toContain(shapeFor(undefined));
    expect(shapeFor(null)).toBe(shapeFor(''));
  });

  it('distributes categories across more than one solid', () => {
    const cats = [
      'Alpha',
      'Beta',
      'Gamma',
      'Delta',
      'Epsilon',
      'Zeta',
      'Eta',
      'Theta',
      'Iota',
      'Kappa',
    ];
    const distinct = new Set(cats.map((c) => shapeFor(c)));
    // Not asserting all 4 (hash luck), just that it isn't degenerate.
    expect(distinct.size).toBeGreaterThan(1);
  });
});

describe('SHAPE_GLYPH_POLYS', () => {
  it('has a silhouette for every solid in the family', () => {
    for (const name of SHAPE_NAMES) {
      expect(SHAPE_GLYPH_POLYS[name]).toBeTruthy();
    }
    expect(Object.keys(SHAPE_GLYPH_POLYS).sort()).toEqual(
      [...SHAPE_NAMES].sort()
    );
  });
});
