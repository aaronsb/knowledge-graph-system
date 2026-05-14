/**
 * GLSL shader bodies for the GPU force simulation.
 *
 * `resolution`, `texturePosition`, `textureVelocity` are injected by
 * GPUComputationRenderer. MAX_NODES / MAX_NEIGHBORS are prepended as
 * `#define`s per-graph so the loop bounds stay compile-time constants.
 */

export const velShaderBody = /* glsl */ `
uniform float alpha;
uniform float repulsion;
uniform float attraction;
uniform float damping;
uniform float centerGravity;
uniform float maxForce;
uniform float velStop;
uniform int nodeCount;
uniform sampler2D neighborOffsetCount;
uniform sampler2D neighborList;
uniform sampler2D hiddenMask;
uniform vec2 neighborRes;

vec2 idxToUV(int idx, vec2 res) {
  float fx = mod(float(idx), res.x);
  float fy = floor(float(idx) / res.x);
  return (vec2(fx, fy) + 0.5) / res;
}

void main() {
  vec2 uv = gl_FragCoord.xy / resolution;
  int myIdx = int(floor(gl_FragCoord.y) * resolution.x + floor(gl_FragCoord.x));
  if (myIdx >= nodeCount) {
    gl_FragColor = vec4(0.0);
    return;
  }

  float selfVis = texture2D(hiddenMask, uv).r;
  if (selfVis < 0.5) {
    gl_FragColor = vec4(0.0);
    return;
  }

  vec3 pos = texture2D(texturePosition, uv).xyz;
  vec3 vel = texture2D(textureVelocity, uv).xyz;

  vec3 force = vec3(0.0);

  for (int j = 0; j < MAX_NODES; j++) {
    if (j >= nodeCount) break;
    if (j == myIdx) continue;
    vec2 juv = idxToUV(j, resolution);
    if (texture2D(hiddenMask, juv).r < 0.5) continue;
    vec3 pj = texture2D(texturePosition, juv).xyz;
    vec3 d = pos - pj;
    float d2 = max(dot(d, d), 0.01);
    float dist = sqrt(d2);
    force += (d / dist) * (repulsion / d2);
  }

  vec4 meta = texture2D(neighborOffsetCount, uv);
  int off = int(meta.r + 0.5);
  int cnt = int(meta.g + 0.5);
  for (int k = 0; k < MAX_NEIGHBORS; k++) {
    if (k >= cnt) break;
    int ni = off + k;
    vec2 nuv = idxToUV(ni, neighborRes);
    int neighborIdx = int(texture2D(neighborList, nuv).r + 0.5);
    vec2 puv = idxToUV(neighborIdx, resolution);
    if (texture2D(hiddenMask, puv).r < 0.5) continue;
    vec3 pn = texture2D(texturePosition, puv).xyz;
    vec3 d = pn - pos;
    force += d * attraction;
  }

  force -= pos * centerGravity;

  // Cap raw force before alpha scaling so alpha actually governs dynamics
  // for high-degree hubs; see useForceSim.ts for the CPU equivalent.
  float m = length(force);
  if (m > maxForce) force *= (maxForce / m);
  force *= alpha;

  vec3 newVel = (vel + force) * damping;
  if (velStop > 0.0 && length(newVel) < velStop) newVel = vec3(0.0);
  gl_FragColor = vec4(newVel, 1.0);
}
`;

export const posShaderBody = /* glsl */ `
uniform float dt;
uniform int nodeCount;
uniform sampler2D hiddenMask;

void main() {
  vec2 uv = gl_FragCoord.xy / resolution;
  int myIdx = int(floor(gl_FragCoord.y) * resolution.x + floor(gl_FragCoord.x));
  vec3 pos = texture2D(texturePosition, uv).xyz;
  if (myIdx >= nodeCount) {
    gl_FragColor = vec4(pos, 1.0);
    return;
  }
  if (texture2D(hiddenMask, uv).r < 0.5) {
    gl_FragColor = vec4(pos, 1.0);
    return;
  }
  vec3 vel = texture2D(textureVelocity, uv).xyz;
  gl_FragColor = vec4(pos + vel * dt, 1.0);
}
`;
