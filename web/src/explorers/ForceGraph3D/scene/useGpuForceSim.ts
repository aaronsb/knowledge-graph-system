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
import { velShaderBody, posShaderBody } from './gpuShaders';
import { buildNeighborCSR } from './neighborCsr';
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
  simmerCycleMs: 24000,
  simmerAlphaLow: 0.02,
  simmerAlphaHigh: 0.35,
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
  const { hiddenIds, pinnedIds, enabled = true, ...tuning } = params;
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
  const simmerStartRef = useRef(0);
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

  // Update the hidden/frozen mask in place on change. Hidden and pinned
  // nodes both freeze in the shader (integration is skipped) — the
  // renderer consults hiddenIds separately to collapse hidden instances.
  useEffect(() => {
    const s = gpuStateRef.current;
    if (!s) return;
    const data = s.hiddenMaskTex.image.data as Float32Array;
    for (let i = 0; i < s.N; i++) {
      const id = s.nodes[i].id;
      const frozen =
        (!!hiddenIds && hiddenIds.has(id)) || (!!pinnedIds && pinnedIds.has(id));
      data[i * 4] = frozen ? 0.0 : 1.0;
    }
    s.hiddenMaskTex.needsUpdate = true;
    invalidate();
  }, [hiddenIds, pinnedIds, nodes, invalidate]);

  useFrame(() => {
    if (!enabled) {
      dirtyRef.current = false;
      return;
    }
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

    if (simmerRef.current) {
      // Stovetop thermal cycle — see useForceSim.ts for the rationale.
      const t = (performance.now() - simmerStartRef.current) / cfg.simmerCycleMs;
      const smooth = 0.5 - 0.5 * Math.cos(t * 2 * Math.PI);
      alphaRef.current = cfg.simmerAlphaLow + (cfg.simmerAlphaHigh - cfg.simmerAlphaLow) * smooth;
    } else {
      alphaRef.current = alpha * (1 - cfg.alphaDecay);
    }
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
        simmerStartRef.current = performance.now();
        alphaRef.current = cfg.simmerAlphaLow;
        setAlphaDisplay(cfg.simmerAlphaLow);
        dirtyRef.current = true;
        invalidate();
      }
    },
    [cfg.simmerAlphaLow, invalidate]
  );

  return { positionsRef, dirtyRef, alpha: alphaDisplay, reheat, freeze, simmer };
}
