/**
 * Unit tests for ensureFacetGeometry's hard-edge extraction.
 *
 * The regression that matters is exactly the user's own example: a cube
 * face is two triangles sharing a diagonal; that diagonal is a
 * triangulation artefact, NOT a principal edge, and must be masked
 * (soft) while the 12 real cube edges stay hard. The icosphere case
 * locks the smooth-default partition the sphere look depends on.
 */

import { describe, it, expect } from 'vitest';
import * as THREE from 'three';
import { ensureFacetGeometry } from './facetedMaterial';

// aEdgeHide channels are 0 for a hard (principal) edge, a large constant
// (~10) for a soft/hidden one. Test in thresholds so the private HIDE
// constant isn't imported.
const isHard = (v: number) => v < 0.5;

function hideTriples(geo: THREE.BufferGeometry): Array<[boolean, boolean, boolean]> {
  const a = geo.getAttribute('aEdgeHide') as THREE.BufferAttribute;
  const triCount = a.count / 3;
  const out: Array<[boolean, boolean, boolean]> = [];
  for (let t = 0; t < triCount; t++) {
    // Flat per triangle — vertex 0 of each tri carries the values.
    const i = t * 3;
    out.push([isHard(a.getX(i)), isHard(a.getY(i)), isHard(a.getZ(i))]);
  }
  return out;
}

describe('ensureFacetGeometry — hard-edge extraction', () => {
  it('a cube keeps its 12 edges, masks the 6 face diagonals', () => {
    const g = ensureFacetGeometry(new THREE.BoxGeometry(1, 1, 1));
    const tris = hideTriples(g);
    // Box = 6 faces × 2 triangles. Per triangle: the two legs are real
    // cube edges (hard), the hypotenuse is the shared face diagonal
    // (soft). So every triangle has exactly two hard channels + one soft.
    expect(tris).toHaveLength(12);
    for (const [x, y, z] of tris) {
      const hard = [x, y, z].filter(Boolean).length;
      expect(hard).toBe(2);
    }
    // Total soft channels = 12 (one per triangle) = the 6 diagonals
    // counted from both adjacent triangles.
    const soft = tris.reduce(
      (n, [x, y, z]) => n + [x, y, z].filter((h) => !h).length,
      0
    );
    expect(soft).toBe(12);
  });

  it('a geodesic icosphere has no hard edges (smooth, no wireframe)', () => {
    // detail 3 → facet dihedrals well under the 25° threshold.
    const g = ensureFacetGeometry(new THREE.IcosahedronGeometry(1, 3));
    const tris = hideTriples(g);
    const anyHard = tris.some(([x, y, z]) => x || y || z);
    expect(anyHard).toBe(false);
  });

  it('a bare icosahedron is all hard edges (faceted)', () => {
    const g = ensureFacetGeometry(new THREE.IcosahedronGeometry(1, 0));
    const tris = hideTriples(g);
    // Every one of the 20 faces borders non-coplanar neighbours.
    for (const [x, y, z] of tris) {
      expect([x, y, z].every(Boolean)).toBe(true);
    }
  });

  it('attaches aBary + normals and is idempotent', () => {
    const g = ensureFacetGeometry(new THREE.OctahedronGeometry(1, 0));
    expect(g.getAttribute('aBary')).toBeTruthy();
    expect(g.getAttribute('aEdgeHide')).toBeTruthy();
    expect(g.getAttribute('normal')).toBeTruthy();
    // Second pass is a no-op (same object back, attrs intact).
    expect(ensureFacetGeometry(g)).toBe(g);
  });
});
