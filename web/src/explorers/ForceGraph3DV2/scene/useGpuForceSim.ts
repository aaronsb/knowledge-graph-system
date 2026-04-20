/**
 * GPU force simulation hook.
 *
 * Runs the same force-directed layout as useForceSim but parallelizes
 * across fragment shaders via GPUComputationRenderer. Two RGBA float
 * render targets (position + velocity) ping-pong per frame. Edges are
 * encoded as a CSR-style neighbor texture; hidden nodes are signalled
 * via a per-node mask texture that both shaders consult.
 *
 * Requires WebGL2 + EXT_color_buffer_float (see gpuSimSupported). When
 * unavailable, the dispatcher in useSim.ts falls back to the CPU hook.
 *
 * Layouts agree with the CPU path within numerical tolerance — force
 * capping runs before alpha scaling, velStop clamps low-amplitude
 * oscillations, same decay curve. The only observable difference is
 * position readback is one frame behind GPU state to keep CPU/GPU
 * overlapped.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { GPUComputationRenderer } from 'three/examples/jsm/misc/GPUComputationRenderer.js';
import { seedSpherePositions, defaultSeedRadius } from './positions';
import type { EngineNode, EngineEdge } from '../types';
import type { PhysicsParams, ForceSimParams, ForceSimHandle } from './useForceSim';

const DEFAULTS: PhysicsParams = {
  repulsion: 120,
  attraction: 0.04,
  damping: 0.93,
  dt: 0.55,
  centerGravity: 0.004,
  maxForce: 40,
  alphaDecay: 0.0228,
  alphaMin: 0.001,
  alphaInitial: 1.0,
  alphaSimmer: 0.08,
  dampingSimmer: 0.70,
  centerGravitySimmer: 0.03,
  velStopSimmer: 0.3,
};

/** Capability detection — WebGL2 + EXT_color_buffer_float required.  @verified c17bbeb9 */
export const gpuSimSupported: boolean = (() => {
  if (typeof document === 'undefined') return false;
  try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl2');
    if (!gl) return false;
    const hasFloatRT = !!gl.getExtension('EXT_color_buffer_float');
    canvas.width = canvas.height = 0;
    return hasFloatRT;
  } catch {
    return false;
  }
})();

const velShaderBody = /* glsl */ `
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

const posShaderBody = /* glsl */ `
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

interface NeighborCSR {
  offsets: Uint32Array;
  counts: Uint32Array;
  flat: Uint32Array;
  total: number;
  maxNeighbors: number;
}

function buildNeighborCSR(nodes: EngineNode[], edges: EngineEdge[]): NeighborCSR {
  const N = nodes.length;
  const nameIndex = new Map<string, number>();
  for (let i = 0; i < N; i++) nameIndex.set(nodes[i].id, i);
  const adj: number[][] = Array.from({ length: N }, () => []);
  for (const e of edges) {
    const a = nameIndex.get(e.from);
    const b = nameIndex.get(e.to);
    if (a == null || b == null) continue;
    adj[a].push(b);
    adj[b].push(a);
  }
  const offsets = new Uint32Array(N);
  const counts = new Uint32Array(N);
  let total = 0;
  let maxNeighbors = 0;
  for (let i = 0; i < N; i++) {
    offsets[i] = total;
    counts[i] = adj[i].length;
    total += adj[i].length;
    if (adj[i].length > maxNeighbors) maxNeighbors = adj[i].length;
  }
  const flat = new Uint32Array(Math.max(1, total));
  let p = 0;
  for (let i = 0; i < N; i++) {
    for (const n of adj[i]) flat[p++] = n;
  }
  return { offsets, counts, flat, total, maxNeighbors };
}

// Shape of the long-lived GPU state between renders.
interface GpuState {
  gpuCompute: GPUComputationRenderer;
  // GPUComputationRenderer types are loose in three's type defs; we hold
  // the variable records as `any` for uniforms access since their shape
  // depends on the shader.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  posVar: any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  velVar: any;
  readbackBuf: Float32Array;
  texW: number;
  texH: number;
  N: number;
  offsetCountTex: THREE.DataTexture;
  neighborTex: THREE.DataTexture;
  zeroTex: THREE.DataTexture;
  hiddenMaskTex: THREE.DataTexture;
  nodes: EngineNode[];
}

/** GPU force sim hook — must be called inside an r3f Canvas tree.  @verified c17bbeb9 */
export function useGpuForceSim(
  nodes: EngineNode[],
  edges: EngineEdge[],
  params: ForceSimParams = {}
): ForceSimHandle {
  const { hiddenIds, ...tuning } = params;
  const cfg: PhysicsParams = { ...DEFAULTS, ...tuning };
  const gl = useThree((state) => state.gl);
  const invalidate = useThree((state) => state.invalidate);
  const nodeCount = nodes.length;

  const positionsRef = useRef<Float32Array | null>(null);
  const dirtyRef = useRef(false);
  const alphaRef = useRef(cfg.alphaInitial);
  const [alphaDisplay, setAlphaDisplay] = useState(cfg.alphaInitial);
  const frameCounterRef = useRef(0);
  const simmerRef = useRef(false);
  const gpuStateRef = useRef<GpuState | null>(null);

  useEffect(() => {
    if (nodeCount === 0) {
      positionsRef.current = new Float32Array(0);
      gpuStateRef.current = null;
      return;
    }

    const texSize = Math.max(1, Math.ceil(Math.sqrt(nodeCount)));
    const texW = texSize;
    const texH = texSize;
    const totalTexels = texW * texH;

    const seed = seedSpherePositions(nodeCount, defaultSeedRadius(nodeCount));
    const posOut = new Float32Array(nodeCount * 3);
    posOut.set(seed);
    positionsRef.current = posOut;

    const gpuCompute = new GPUComputationRenderer(texW, texH, gl);
    const posInit = gpuCompute.createTexture();
    const velInit = gpuCompute.createTexture();
    const posData = posInit.image.data as Float32Array;
    const velData = velInit.image.data as Float32Array;
    posData.fill(0);
    velData.fill(0);
    for (let i = 0; i < nodeCount; i++) {
      posData[i * 4] = seed[i * 3];
      posData[i * 4 + 1] = seed[i * 3 + 1];
      posData[i * 4 + 2] = seed[i * 3 + 2];
      posData[i * 4 + 3] = 1.0;
    }

    const { offsets, counts, flat, total, maxNeighbors } = buildNeighborCSR(nodes, edges);

    const neighborW = Math.max(1, Math.min(2048, total));
    const neighborH = Math.max(1, Math.ceil(total / neighborW));
    const neighborData = new Float32Array(neighborW * neighborH * 4);
    for (let i = 0; i < total; i++) neighborData[i * 4] = flat[i];
    const neighborTex = new THREE.DataTexture(
      neighborData,
      neighborW,
      neighborH,
      THREE.RGBAFormat,
      THREE.FloatType
    );
    neighborTex.minFilter = THREE.NearestFilter;
    neighborTex.magFilter = THREE.NearestFilter;
    neighborTex.needsUpdate = true;

    const ocData = new Float32Array(totalTexels * 4);
    for (let i = 0; i < nodeCount; i++) {
      ocData[i * 4] = offsets[i];
      ocData[i * 4 + 1] = counts[i];
    }
    const offsetCountTex = new THREE.DataTexture(
      ocData,
      texW,
      texH,
      THREE.RGBAFormat,
      THREE.FloatType
    );
    offsetCountTex.minFilter = THREE.NearestFilter;
    offsetCountTex.magFilter = THREE.NearestFilter;
    offsetCountTex.needsUpdate = true;

    // Hidden mask starts fully visible; updated in place by a separate
    // effect when hiddenIds changes (no sim rebuild required).
    const maskData = new Float32Array(totalTexels * 4);
    for (let i = 0; i < nodeCount; i++) maskData[i * 4] = 1.0;
    const hiddenMaskTex = new THREE.DataTexture(
      maskData,
      texW,
      texH,
      THREE.RGBAFormat,
      THREE.FloatType
    );
    hiddenMaskTex.minFilter = THREE.NearestFilter;
    hiddenMaskTex.magFilter = THREE.NearestFilter;
    hiddenMaskTex.needsUpdate = true;

    const defines =
      `#define MAX_NODES ${nodeCount}\n` +
      `#define MAX_NEIGHBORS ${Math.max(1, maxNeighbors)}\n`;
    const velShader = defines + velShaderBody;
    const posShader = defines + posShaderBody;

    const velVar = gpuCompute.addVariable('textureVelocity', velShader, velInit);
    const posVar = gpuCompute.addVariable('texturePosition', posShader, posInit);
    gpuCompute.setVariableDependencies(velVar, [velVar, posVar]);
    gpuCompute.setVariableDependencies(posVar, [velVar, posVar]);

    const vU = velVar.material.uniforms;
    vU.alpha = { value: cfg.alphaInitial };
    vU.repulsion = { value: cfg.repulsion };
    vU.attraction = { value: cfg.attraction };
    vU.damping = { value: cfg.damping };
    vU.centerGravity = { value: cfg.centerGravity };
    vU.maxForce = { value: cfg.maxForce };
    vU.velStop = { value: 0 };
    vU.nodeCount = { value: nodeCount };
    vU.neighborOffsetCount = { value: offsetCountTex };
    vU.neighborList = { value: neighborTex };
    vU.neighborRes = { value: new THREE.Vector2(neighborW, neighborH) };
    vU.hiddenMask = { value: hiddenMaskTex };

    const pU = posVar.material.uniforms;
    pU.dt = { value: cfg.dt };
    pU.nodeCount = { value: nodeCount };
    pU.hiddenMask = { value: hiddenMaskTex };

    const err = gpuCompute.init();
    if (err) {
      console.error('[useGpuForceSim] GPUComputationRenderer init failed:', err);
      gpuCompute.dispose();
      offsetCountTex.dispose();
      neighborTex.dispose();
      hiddenMaskTex.dispose();
      gpuStateRef.current = null;
      return;
    }

    const zeroData = new Float32Array(totalTexels * 4);
    const zeroTex = new THREE.DataTexture(
      zeroData,
      texW,
      texH,
      THREE.RGBAFormat,
      THREE.FloatType
    );
    zeroTex.minFilter = THREE.NearestFilter;
    zeroTex.magFilter = THREE.NearestFilter;
    zeroTex.needsUpdate = true;

    const readbackBuf = new Float32Array(totalTexels * 4);

    alphaRef.current = cfg.alphaInitial;
    setAlphaDisplay(cfg.alphaInitial);
    dirtyRef.current = true;
    frameCounterRef.current = 0;

    gpuStateRef.current = {
      gpuCompute,
      posVar,
      velVar,
      readbackBuf,
      texW,
      texH,
      N: nodeCount,
      offsetCountTex,
      neighborTex,
      zeroTex,
      hiddenMaskTex,
      nodes,
    };

    return () => {
      gpuCompute.dispose();
      offsetCountTex.dispose();
      neighborTex.dispose();
      hiddenMaskTex.dispose();
      zeroTex.dispose();
      gpuStateRef.current = null;
    };
    // cfg values are intentionally read inside; rebuilding state on every
    // slider change would re-seed positions. The useFrame loop pushes them
    // into uniforms every frame instead.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges, nodeCount, gl]);

  // Update the hidden mask in place on change; avoids rebuilding the sim.
  useEffect(() => {
    const s = gpuStateRef.current;
    if (!s) return;
    const data = s.hiddenMaskTex.image.data as Float32Array;
    for (let i = 0; i < s.N; i++) {
      const hidden = !!hiddenIds && hiddenIds.has(s.nodes[i].id);
      data[i * 4] = hidden ? 0.0 : 1.0;
    }
    s.hiddenMaskTex.needsUpdate = true;
    invalidate();
  }, [hiddenIds, nodes, invalidate]);

  useFrame(() => {
    const s = gpuStateRef.current;
    if (!s) return;
    const alpha = alphaRef.current;
    if (alpha < cfg.alphaMin) {
      dirtyRef.current = false;
      return;
    }
    invalidate();

    // Push live cfg into uniforms so slider changes take effect without
    // rebuilding the GPU compute state. Simmer variants override when on.
    const u = s.velVar.material.uniforms;
    u.alpha.value = alpha;
    u.repulsion.value = cfg.repulsion;
    u.attraction.value = cfg.attraction;
    u.maxForce.value = cfg.maxForce;
    u.damping.value = simmerRef.current ? cfg.dampingSimmer : cfg.damping;
    u.centerGravity.value = simmerRef.current ? cfg.centerGravitySimmer : cfg.centerGravity;
    u.velStop.value = simmerRef.current ? cfg.velStopSimmer : 0;

    // Compute current frame, then read back the alternate target (last
    // frame's output). One-frame lag keeps CPU and GPU overlapped —
    // imperceptible visually.
    s.gpuCompute.compute();

    const rt = s.gpuCompute.getAlternateRenderTarget(s.posVar);
    gl.readRenderTargetPixels(rt, 0, 0, s.texW, s.texH, s.readbackBuf);

    const out = positionsRef.current;
    if (out) {
      const buf = s.readbackBuf;
      for (let i = 0; i < s.N; i++) {
        out[i * 3] = buf[i * 4];
        out[i * 3 + 1] = buf[i * 4 + 1];
        out[i * 3 + 2] = buf[i * 4 + 2];
      }
    }

    const decayed = alpha * (1 - cfg.alphaDecay);
    alphaRef.current = simmerRef.current ? Math.max(cfg.alphaSimmer, decayed) : decayed;
    dirtyRef.current = true;

    frameCounterRef.current++;
    if (frameCounterRef.current % 10 === 0) {
      setAlphaDisplay(alphaRef.current);
    }
  });

  const reheat = useCallback(() => {
    alphaRef.current = cfg.alphaInitial;
    setAlphaDisplay(cfg.alphaInitial);
    dirtyRef.current = true;
    invalidate();
  }, [cfg.alphaInitial, invalidate]);

  const freeze = useCallback(() => {
    alphaRef.current = 0;
    setAlphaDisplay(0);
    simmerRef.current = false;
    const s = gpuStateRef.current;
    if (s) {
      s.gpuCompute.renderTexture(s.zeroTex, s.velVar.renderTargets[0]);
      s.gpuCompute.renderTexture(s.zeroTex, s.velVar.renderTargets[1]);
    }
    dirtyRef.current = false;
    invalidate();
  }, [invalidate]);

  const simmer = useCallback(
    (on: boolean) => {
      simmerRef.current = on;
      if (on) {
        if (alphaRef.current < cfg.alphaSimmer) {
          alphaRef.current = cfg.alphaSimmer;
          setAlphaDisplay(cfg.alphaSimmer);
        }
        dirtyRef.current = true;
        invalidate();
      }
    },
    [cfg.alphaSimmer, invalidate]
  );

  return { positionsRef, dirtyRef, alpha: alphaDisplay, reheat, freeze, simmer };
}
