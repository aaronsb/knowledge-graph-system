/**
 * Two-tone faceted node material.
 *
 * Each node renders in its per-instance colour, with the solid's edges
 * and vertices darkened toward a lower-luminance shade of that same
 * colour — a two-tone, same-hue look that reads the polyhedral structure
 * without lighting. The darkening is a barycentric in-shader wireframe:
 * an `aBary` attribute carries (1,0,0)/(0,1,0)/(0,0,1) per triangle
 * vertex, the fragment shader takes the min barycentric (→0 on edges,
 * →0 at vertices where two go to zero) and lerps the fragment toward a
 * scaled-down copy of itself.
 *
 * Why this technique:
 * - One draw call, no extra geometry/lines — works with InstancedMesh.
 * - Built on MeshBasicMaterial via onBeforeCompile so three's
 *   USE_INSTANCING_COLOR chunk (per-instance colour) is untouched. The
 *   engine deliberately stays on an unlit basic material (see Nodes.tsx);
 *   switching to a lit material silently breaks instance colour.
 * - The effect intensifies on complex solids for free: a dodecahedron
 *   has 5× the edges of a tetrahedron, so more dark structure per
 *   silhouette — exactly the requested behaviour.
 *
 * Same-chroma claim: `rgb * uDark` is a *uniform* RGB scale. In HSL that
 * is identical hue and identical saturation with lower lightness (the
 * max/min channel ratios that define H and S are preserved) — so the
 * dark tone genuinely is the same colour, just dimmer, never black.
 *
 * The edge AA uses fwidth(), which is core in WebGL2 (GLSL ES 3.00).
 * This codebase already requires WebGL2 for the GPU force sim, and r3f's
 * Canvas is WebGL2 on every current browser, so no derivatives-extension
 * guard is needed.
 *
 * @verified 7b87c133
 */

import * as THREE from 'three';

/** Edge softness in pixels — fwidth-scaled so the dark line stays a
 *  crisp ~1.5px at any zoom instead of aliasing when far / bloating when
 *  near. */
const EDGE_PX = 1.5;

/** Luminance multiplier for the dark tone. Below 1 so edges/vertices
 *  recede; well above 0 so they read as "darker colour", not black. */
const DARK = 0.45;

/**
 * Add a per-triangle barycentric attribute (`aBary`). Indexed geometry
 * is converted to non-indexed first (a barycentric wireframe needs
 * unshared vertices), returning a NEW geometry — the caller owns
 * disposing the old one. Non-indexed input is annotated in place.
 * Idempotent: a geometry that already has `aBary` is returned as-is.
 *
 * @verified 7b87c133
 */
export function ensureBarycentric(
  geo: THREE.BufferGeometry
): THREE.BufferGeometry {
  if (geo.getAttribute('aBary')) return geo;
  const g = geo.index ? geo.toNonIndexed() : geo;
  const count = g.getAttribute('position').count; // multiple of 3
  const bary = new Float32Array(count * 3);
  for (let i = 0; i < count; i += 3) {
    // v0 = (1,0,0), v1 = (0,1,0), v2 = (0,0,1)
    bary[i * 3 + 0] = 1;
    bary[(i + 1) * 3 + 1] = 1;
    bary[(i + 2) * 3 + 2] = 1;
  }
  g.setAttribute('aBary', new THREE.BufferAttribute(bary, 3));
  return g;
}

/**
 * Build the shared faceted material. Stateless across instances and
 * classes — one material can back every node mesh.
 *
 * @verified 7b87c133
 */
export function createFacetedNodeMaterial(): THREE.MeshBasicMaterial {
  // vertexColors=false is intentional: per-instance colour arrives via
  // instanceColor / USE_INSTANCING_COLOR, which three injects
  // independent of the vertexColors flag.
  const material = new THREE.MeshBasicMaterial({ vertexColors: false });

  material.onBeforeCompile = (shader) => {
    shader.uniforms.uEdgePx = { value: EDGE_PX };
    shader.uniforms.uDark = { value: DARK };

    shader.vertexShader =
      'attribute vec3 aBary;\nvarying vec3 vBary;\n' +
      shader.vertexShader.replace(
        '#include <begin_vertex>',
        '#include <begin_vertex>\n  vBary = aBary;'
      );

    shader.fragmentShader =
      'varying vec3 vBary;\nuniform float uEdgePx;\nuniform float uDark;\n' +
      shader.fragmentShader.replace(
        '#include <opaque_fragment>',
        `#include <opaque_fragment>
        {
          // Distance to the nearest triangle edge in barycentric space;
          // ~0 on an edge, exactly 0 at a vertex.
          float b = min(min(vBary.x, vBary.y), vBary.z);
          // fwidth() gives screen-space derivative → constant px width.
          float aa = max(fwidth(b) * uEdgePx, 1e-5);
          float edge = 1.0 - smoothstep(0.0, aa, b);
          // If aBary is absent the attribute reads (0,0,0) → b=0 → fully
          // darkened; the engine always injects it (Nodes.tsx), but guard
          // anyway: a zero attribute would otherwise paint nodes solid
          // dark. Treat the degenerate all-zero case as "no edge".
          if (vBary.x + vBary.y + vBary.z < 0.5) edge = 0.0;
          gl_FragColor.rgb = mix(gl_FragColor.rgb, gl_FragColor.rgb * uDark, edge);
        }`
      );
  };

  // onBeforeCompile patches can collide in three's program cache with an
  // unpatched basic material; pin a distinct key. Bump the suffix if the
  // shader body changes.
  material.customProgramCacheKey = () => 'kg-two-tone-faceted-v1';

  return material;
}
