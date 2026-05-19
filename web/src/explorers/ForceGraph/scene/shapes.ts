/**
 * Platonic-solid glyph encoding for graph nodes.
 *
 * Colour already carries the ontology palette; shape adds a second,
 * lower-resolution read of the same axis so a graph reads as a coherent
 * family of geometric solids rather than a field of identical dots. The
 * solids were chosen for family resemblance — all read as "a solid" at
 * similar visual mass — and they reduce cleanly to flat SVG silhouettes
 * for legends and inline use.
 *
 * Scope (per ADR-203): until a node-class *facet* exists in the schema,
 * shape is derived from the existing `category` (ontology) string — the
 * same axis colour uses. This is the deliberate "no-schema rendering
 * first" step; when the facet lands, `shapeFor` switches to keying off
 * it and shape becomes a genuinely second axis.
 *
 * @verified 7b87c133
 */

import type { ReactElement } from 'react';
import { createElement } from 'react';

/** The solid family. Order is the hash codomain — appending a shape is
 *  safe; reordering or removing one re-buckets every category. */
export const SHAPE_NAMES = [
  'icosahedron',
  'octahedron',
  'tetrahedron',
  'dodecahedron',
] as const;

export type ShapeName = (typeof SHAPE_NAMES)[number];

/** djb2 — small, fast, well-distributed string hash. Stable across
 *  reloads and processes (pure function of the bytes) so a given
 *  category always lands on the same solid. */
function djb2(s: string): number {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  return h >>> 0;
}

/** Map a category/ontology string to a stable solid. */
export function shapeFor(category: string | null | undefined): ShapeName {
  return SHAPE_NAMES[djb2(category || '') % SHAPE_NAMES.length];
}

/** Unit-radius geometry JSX for `geometryByClass`. Subdivision 0 (no
 *  detail): the hard-edge material masks coplanar sub-triangulation
 *  anyway, so extra triangles only cost fill rate — detail 0 keeps each
 *  solid at its true face count and crisp principal edges. Per-instance
 *  scale handles real size. */
export function shapeGeometry(name: ShapeName): ReactElement {
  switch (name) {
    case 'octahedron':
      return createElement('octahedronGeometry', { args: [1, 0] });
    case 'tetrahedron':
      return createElement('tetrahedronGeometry', { args: [1, 0] });
    case 'dodecahedron':
      return createElement('dodecahedronGeometry', { args: [1, 0] });
    case 'icosahedron':
    default:
      return createElement('icosahedronGeometry', { args: [1, 0] });
  }
}

/** `geometryByClass` for the full solid family — pass straight to Scene. */
export function shapeGeometryByClass(): Record<string, ReactElement> {
  const out: Record<string, ReactElement> = {};
  for (const name of SHAPE_NAMES) out[name] = shapeGeometry(name);
  return out;
}

/**
 * Flat 2D silhouettes (viewBox 0 0 12 12) for the Node Types legend and
 * any inline list/web use. Projection-flat abstractions, not true
 * orthographic renders — just enough to be self-documenting. If a solid
 * is added to SHAPE_NAMES, add its silhouette here too.
 */
export const SHAPE_GLYPH_POLYS: Record<ShapeName, string> = {
  // Hexagonal silhouette (icosahedron viewed face-on)
  icosahedron: '6,1 11,4 11,8 6,11 1,8 1,4',
  // Diamond (octahedron viewed point-up)
  octahedron: '6,1 11,6 6,11 1,6',
  // Triangle (tetrahedron viewed face-on)
  tetrahedron: '6,1 11,11 1,11',
  // Pentagonal silhouette (dodecahedron viewed face-on)
  dodecahedron: '6,1 10,4 9,10 3,10 2,4',
};
