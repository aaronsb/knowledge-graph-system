/**
 * Two-tone faceted node material — principal edges only, flat or lit.
 *
 * Each node renders in its per-instance colour with the solid's *true*
 * edges and vertices darkened toward a lower-luminance shade of that same
 * colour. "True" is the point: the darkening traces only the polyhedron's
 * principal edges (sharp dihedral angles), never the triangulation edges
 * a mesher adds — a cube shows 12 edges, not the 6 face diagonals; an
 * icosphere shows none and reads as a smooth ball.
 *
 * Mechanism — a hard-edge barycentric wireframe, one draw call,
 * instancing-safe:
 * - `aBary` carries (1,0,0)/(0,1,0)/(0,0,1) per triangle vertex.
 * - `aEdgeHide` (flat per triangle) pushes the barycentric channel of any
 *   *soft* (coplanar / sub-triangulation) edge far out of range so the
 *   shader's min() never selects it. Only hard edges — and the vertices
 *   where two hard edges meet — darken.
 * - Hard/soft is decided by the dihedral angle between the two triangles
 *   sharing an edge, computed on a position-quantised adjacency map (so
 *   the toNonIndexed vertex duplication doesn't hide the sharing).
 *
 * Shading is selectable (ADR-pending UI toggle):
 * - **flat** — MeshBasicMaterial, unlit. Colour + two-tone edges only;
 *   the original engine look.
 * - **lit** — MeshLambertMaterial + a camera-tracking light (added in
 *   Scene). Faceted solids get genuine per-face shading (face normals);
 *   the icosphere gets smooth shading (its interpolated normals are kept).
 *
 * Per-instance colour survives both: three's color_vertex / color_fragment
 * chunks (USE_INSTANCING_COLOR → vColor → diffuseColor) are identical in
 * MeshBasic and MeshLambert — verified in three's ShaderLib — so the old
 * "a lit material breaks instanceColor" caveat does not apply here.
 *
 * Same-chroma: `rgb * uDark` is a *uniform* RGB scale = identical hue and
 * saturation in HSL, only lower lightness. Dimmer, never black.
 *
 * fwidth() is core in WebGL2 (GLSL ES 3.00); this codebase already
 * requires WebGL2 for the GPU sim, so no derivatives-extension guard.
 *
 * @verified 7b87c133
 */

import * as THREE from 'three';

/** Edge softness in pixels — fwidth-scaled so the dark line stays a
 *  crisp ~1.5px at any zoom. */
const EDGE_PX = 1.5;

/** Luminance multiplier for the dark tone (same hue, lower lightness). */
const DARK = 0.45;

/** Dihedral angle (degrees) above which an edge is "hard" (principal).
 *  Platonic solids: smallest is the icosahedron at ~41° between adjacent
 *  face normals — well above. A geodesic icosphere at detail ≥3 has
 *  facet dihedrals < ~12°, so every edge is soft → no wireframe, smooth
 *  ball. 25° sits cleanly between the two populations. */
const HARD_EDGE_DEG = 25;

/** Barycentric offset that removes a soft edge from the shader's min(). */
const HIDE = 10.0;

/** Quantise a coordinate so toNonIndexed's duplicated vertices rejoin
 *  when building edge adjacency (1e-4 world units ≈ exact for unit
 *  geometry). */
function q(n: number): number {
  return Math.round(n * 1e4);
}

/**
 * Convert to non-indexed, attach `aBary` + `aEdgeHide` (principal-edge
 * mask), and set normals for the chosen shading: face normals when the
 * geometry has hard edges (faceted), input normals kept otherwise (a
 * smooth icosphere stays smooth). Returns a NEW geometry for indexed
 * input — caller disposes the old one. Idempotent via the `aBary` guard.
 *
 * @verified 7b87c133
 */
export function ensureFacetGeometry(
  geo: THREE.BufferGeometry
): THREE.BufferGeometry {
  if (geo.getAttribute('aBary')) return geo;
  const g = geo.index ? geo.toNonIndexed() : geo;
  const pos = g.getAttribute('position') as THREE.BufferAttribute;
  const triCount = pos.count / 3;

  // Per-triangle face normals + position-quantised edge → adjacent
  // triangle map. Each undirected edge collects the indices of the
  // triangles touching it.
  const faceNormal: THREE.Vector3[] = new Array(triCount);
  const edgeTris = new Map<string, number[]>();
  const vA = new THREE.Vector3();
  const vB = new THREE.Vector3();
  const vC = new THREE.Vector3();
  const e1 = new THREE.Vector3();
  const e2 = new THREE.Vector3();

  const key = (i: number) =>
    `${q(pos.getX(i))},${q(pos.getY(i))},${q(pos.getZ(i))}`;
  const edgeKey = (i: number, j: number) => {
    const a = key(i);
    const b = key(j);
    return a < b ? `${a}|${b}` : `${b}|${a}`;
  };

  for (let t = 0; t < triCount; t++) {
    const i0 = t * 3;
    vA.fromBufferAttribute(pos, i0);
    vB.fromBufferAttribute(pos, i0 + 1);
    vC.fromBufferAttribute(pos, i0 + 2);
    e1.subVectors(vB, vA);
    e2.subVectors(vC, vA);
    faceNormal[t] = new THREE.Vector3().crossVectors(e1, e2).normalize();
    // edge opposite v0 = (v1,v2); opposite v1 = (v2,v0); opposite v2 = (v0,v1)
    for (const [a, b] of [
      [i0 + 1, i0 + 2],
      [i0 + 2, i0],
      [i0, i0 + 1],
    ]) {
      const k = edgeKey(a, b);
      let arr = edgeTris.get(k);
      if (!arr) edgeTris.set(k, (arr = []));
      arr.push(t);
    }
  }

  const cosThresh = Math.cos((HARD_EDGE_DEG * Math.PI) / 180);
  const isHard = (i: number, j: number, t: number): boolean => {
    const tris = edgeTris.get(edgeKey(i, j));
    if (!tris || tris.length < 2) return true; // boundary edge → keep
    const other = tris.find((x) => x !== t);
    if (other === undefined) return true;
    // Hard when the two faces diverge past the threshold (dot below
    // cos(threshold)). Coplanar sub-triangulation (dot ≈ 1) → soft.
    return faceNormal[t].dot(faceNormal[other]) < cosThresh;
  };

  const count = pos.count;
  const bary = new Float32Array(count * 3);
  const hide = new Float32Array(count * 3);
  let hardCount = 0;

  for (let t = 0; t < triCount; t++) {
    const i0 = t * 3;
    bary[i0 * 3 + 0] = 1; // v0 → (1,0,0)
    bary[(i0 + 1) * 3 + 1] = 1; // v1 → (0,1,0)
    bary[(i0 + 2) * 3 + 2] = 1; // v2 → (0,0,1)

    // channel x ↔ edge (v1,v2), y ↔ (v2,v0), z ↔ (v0,v1)
    const hx = isHard(i0 + 1, i0 + 2, t) ? 0 : HIDE;
    const hy = isHard(i0 + 2, i0, t) ? 0 : HIDE;
    const hz = isHard(i0, i0 + 1, t) ? 0 : HIDE;
    if (hx === 0) hardCount++;
    if (hy === 0) hardCount++;
    if (hz === 0) hardCount++;
    for (let v = 0; v < 3; v++) {
      hide[(i0 + v) * 3 + 0] = hx;
      hide[(i0 + v) * 3 + 1] = hy;
      hide[(i0 + v) * 3 + 2] = hz;
    }
  }

  g.setAttribute('aBary', new THREE.BufferAttribute(bary, 3));
  g.setAttribute('aEdgeHide', new THREE.BufferAttribute(hide, 3));

  // Faceted geometry → per-face normals so lit mode shades each facet
  // flat. A geometry with no hard edges (icosphere) keeps its smooth
  // input normals; only recompute when there's facet structure to show.
  if (hardCount > 0 || !g.getAttribute('normal')) {
    g.computeVertexNormals(); // non-indexed ⇒ each vertex = its face normal
  }
  return g;
}

/** Back-compat alias — call sites updated to ensureFacetGeometry. */
export const ensureBarycentric = ensureFacetGeometry;

const VERT_PATCH = 'attribute vec3 aBary;\nattribute vec3 aEdgeHide;\nvarying vec3 vBary;\nvarying vec3 vEdgeHide;\n';
const FRAG_PATCH = 'varying vec3 vBary;\nvarying vec3 vEdgeHide;\nuniform float uEdgePx;\nuniform float uDark;\n';
const FRAG_BODY = `#include <opaque_fragment>
{
  // Soft edges get +HIDE on their channel so min() never picks them;
  // only hard (principal) edges and the vertices where two meet stay
  // near zero.
  vec3 bw = vBary + vEdgeHide;
  float b = min(min(bw.x, bw.y), bw.z);
  float aa = max(fwidth(b) * uEdgePx, 1e-5);
  float edge = 1.0 - smoothstep(0.0, aa, b);
  // Degenerate guard: if aBary is absent it reads (0,0,0); don't paint
  // the whole node dark.
  if (vBary.x + vBary.y + vBary.z < 0.5) edge = 0.0;
  gl_FragColor.rgb = mix(gl_FragColor.rgb, gl_FragColor.rgb * uDark, edge);
}`;

/** Apply the two-tone hard-edge patch to a basic OR lambert material. */
function patchTwoTone(material: THREE.Material): void {
  material.onBeforeCompile = (shader) => {
    shader.uniforms.uEdgePx = { value: EDGE_PX };
    shader.uniforms.uDark = { value: DARK };
    shader.vertexShader =
      VERT_PATCH +
      shader.vertexShader.replace(
        '#include <begin_vertex>',
        '#include <begin_vertex>\n  vBary = aBary;\n  vEdgeHide = aEdgeHide;'
      );
    shader.fragmentShader =
      FRAG_PATCH +
      shader.fragmentShader.replace('#include <opaque_fragment>', FRAG_BODY);
  };
}

/**
 * Shared faceted material. `lit=false` → unlit MeshBasicMaterial (the
 * default "flat" mode); `lit=true` → MeshLambertMaterial (real lighting,
 * needs a light in the scene). Stateless across instances/classes — one
 * per mode backs every node mesh. Distinct cache keys so three's program
 * cache never serves one variant the other's compiled program.
 *
 * @verified 7b87c133
 */
export function createFacetedNodeMaterial(
  lit = false
): THREE.MeshBasicMaterial | THREE.MeshLambertMaterial {
  // vertexColors=false is intentional: per-instance colour arrives via
  // instanceColor / USE_INSTANCING_COLOR, independent of that flag.
  const material = lit
    ? new THREE.MeshLambertMaterial({ vertexColors: false })
    : new THREE.MeshBasicMaterial({ vertexColors: false });
  patchTwoTone(material);
  const key = lit ? 'kg-two-tone-lit-v1' : 'kg-two-tone-flat-v1';
  material.customProgramCacheKey = () => key;
  return material;
}
