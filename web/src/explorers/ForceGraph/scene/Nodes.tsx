/**
 * Instanced node rendering.
 *
 * One InstancedMesh per node class. When `nodeClasses`/`geometryByClass`
 * are omitted, the engine renders a single mesh with the default
 * icosahedron geometry — that's the Force Graph path. When provided, the
 * engine partitions nodes by class key and renders one mesh per class
 * with the explorer-provided geometry — that's how Document Explorer
 * gets document nodes as squared glyphs alongside concept dots.
 *
 * Per-instance state (matrix from position + scale, color) lives on each
 * mesh. Positions come from the shared sim buffer each frame; colors
 * arrive parallel to `nodes` from the plugin.
 *
 * Pointer events on a mesh surface instanceId; each mesh's handler
 * resolves to the global node id via a class-local index map.
 */

import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  type ReactElement,
} from 'react';
import { useFrame, useThree, type ThreeEvent } from '@react-three/fiber';
import type { DragHandlers } from './useDragHandler';
import * as THREE from 'three';
import type { EngineNode } from '../types';
import { createFacetedNodeMaterial, ensureBarycentric } from './facetedMaterial';

const DEFAULT_CLASS = '__default__';

const tmpMat = new THREE.Matrix4();
const tmpQuat = new THREE.Quaternion();
const tmpScale = new THREE.Vector3();
const tmpPos = new THREE.Vector3();
const tmpColor = new THREE.Color();

export interface NodesProps {
  nodes: EngineNode[];
  positionsRef: React.MutableRefObject<Float32Array | null>;
  /** Per-node colors, parallel to `nodes` by index. */
  colors: string[];
  /** Per-node class key, parallel to `nodes` by index. When provided,
   *  the engine renders one InstancedMesh per distinct class with the
   *  geometry from `geometryByClass`. When undefined, a single mesh
   *  uses the default icosahedron. */
  nodeClasses?: string[];
  /** Geometry element per class key. Required when `nodeClasses` is set
   *  (engine clones the JSX into the per-class mesh). Each geometry
   *  should be unit-sized — per-instance scale handles real-world size. */
  geometryByClass?: Record<string, ReactElement>;
  /** Optional per-node base scale (parallel to `nodes`). When provided,
   *  replaces the engine's default `0.8 + sqrt(degree) * 0.3` formula.
   *  `nodeSize` still multiplies the final value. */
  nodeScales?: Float32Array;
  hiddenIds?: Set<string>;
  highlightedIds?: Set<string>;
  nodeSize?: number;
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
  onHover?: (id: string | null) => void;
  onContextMenu?: (id: string, event: PointerEvent) => void;
  onDragStart?: DragHandlers['onDragStart'];
  onDragMove?: DragHandlers['onDragMove'];
  onDragEnd?: DragHandlers['onDragEnd'];
}

/** Instanced node meshes — one draw call per geometry class.  @verified c17bbeb9 */
export function Nodes(props: NodesProps) {
  // nodeSize is intentionally not destructured here — each NodeClassMesh
  // reads it from the spread props and applies it per-frame.
  const { nodes, nodeClasses, geometryByClass, nodeScales } = props;

  // Partition nodes by class. Single-class fallback keeps the default
  // path identical to the pre-multi-class behaviour.
  const partitions = useMemo(() => {
    const classKeys = nodeClasses ?? null;
    const buckets = new Map<string, number[]>();
    for (let i = 0; i < nodes.length; i++) {
      const key = classKeys ? classKeys[i] ?? DEFAULT_CLASS : DEFAULT_CLASS;
      let bucket = buckets.get(key);
      if (!bucket) {
        bucket = [];
        buckets.set(key, bucket);
      }
      bucket.push(i);
    }
    return Array.from(buckets.entries()).map(([key, indices]) => ({
      key,
      indices: Uint32Array.from(indices),
    }));
  }, [nodes, nodeClasses]);

  // Pre-compute per-node base scales once per (nodes, nodeScales) change.
  // The engine's degree-based default applies when the explorer doesn't
  // override; the per-frame loop in each mesh multiplies by `nodeSize` and
  // the optional highlight boost.
  const baseScales = useMemo(() => {
    const out = new Float32Array(nodes.length);
    if (nodeScales) {
      out.set(nodeScales);
    } else {
      for (let i = 0; i < nodes.length; i++) {
        out[i] = 0.8 + Math.sqrt(nodes[i].degree || 1) * 0.3;
      }
    }
    return out;
  }, [nodes, nodeScales]);

  // One shared faceted material backs every class mesh — it carries no
  // per-instance state (colour is instanceColor, structure is the
  // barycentric attribute), so a single instance is correct and cheapest.
  // Deliberately NOT disposed on unmount: under React StrictMode the
  // effect cleanup fires while useMemo keeps returning the same handle,
  // so a dispose() here would hand every later render a dead material
  // (black / failed program compile). One material lives for the app's
  // lifetime — the standard pattern for a shared three material.
  const material = useMemo(() => createFacetedNodeMaterial(), []);

  return (
    <>
      {partitions.map((partition) => (
        <NodeClassMesh
          key={partition.key}
          classKey={partition.key}
          indices={partition.indices}
          baseScales={baseScales}
          geometry={geometryByClass?.[partition.key]}
          material={material}
          {...props}
        />
      ))}
    </>
  );
}

interface NodeClassMeshProps extends NodesProps {
  classKey: string;
  /** Global node indices that belong to this class. */
  indices: Uint32Array;
  baseScales: Float32Array;
  geometry?: ReactElement;
  /** Shared faceted two-tone material (see facetedMaterial.ts). */
  material: THREE.MeshBasicMaterial;
}

function NodeClassMesh({
  classKey,
  indices,
  baseScales,
  geometry,
  material,
  nodes,
  positionsRef,
  colors,
  hiddenIds,
  highlightedIds,
  nodeSize = 1,
  selectedId,
  onSelect,
  onHover,
  onContextMenu,
  onDragStart,
  onDragMove,
  onDragEnd,
}: NodeClassMeshProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const invalidate = useThree((state) => state.invalidate);
  const count = indices.length;

  // The faceted material's wireframe needs a per-triangle barycentric
  // attribute on non-indexed geometry. r3f sets the JSX geometry
  // declaratively; we swap in a non-indexed, annotated clone right after
  // mount (layout effect = before first paint/raycast). The mesh remounts
  // on the `${classKey}-${count}` key, so this re-runs with fresh
  // geometry whenever the partition resizes. Idempotent via
  // ensureBarycentric's own aBary guard.
  useLayoutEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    const original = mesh.geometry;
    const annotated = ensureBarycentric(original);
    if (annotated === original) return;
    mesh.geometry = annotated;
    // Dispose the detached JSX geometry now (idempotent — r3f also
    // disposes it on unmount; three's dispose just re-dispatches a
    // harmless event). Do NOT dispose `annotated` in cleanup: under
    // StrictMode the effect runs → cleanup → runs again against the
    // SAME mesh, whose geometry is now `annotated` with aBary already
    // present, so ensureBarycentric early-returns and the mesh would be
    // left rendering a disposed geometry. Leaking one BufferGeometry per
    // class unmount (rare, bounded) is the safe asymmetry.
    original.dispose();
  }, []);

  // Bounding-sphere refresh cadence — three.js InstancedMesh.raycast()
  // early-outs against the bounding sphere before testing instances.
  // The sphere is auto-computed from instanceMatrix on first query and
  // then cached. If the sim moves instances and we never invalidate it,
  // raycasts miss and pointer events silently stop firing. Recompute
  // every ~15 frames — O(N) but cheap, and the pointer-event cost of a
  // stale sphere is much higher.
  const bsFrameRef = useRef(0);

  useFrame(() => {
    const mesh = meshRef.current;
    const positions = positionsRef.current;
    if (!mesh || !positions) return;

    const hasHidden = !!hiddenIds && hiddenIds.size > 0;
    const hasHighlight = !!highlightedIds && highlightedIds.size > 0;

    for (let local = 0; local < count; local++) {
      const i = indices[local];
      tmpPos.set(positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2]);
      if (hasHidden && hiddenIds!.has(nodes[i].id)) {
        // Zero scale collapses the mesh to a point — invisible and not
        // pickable, while leaving the physics index intact.
        tmpScale.setScalar(0);
      } else {
        const boost = hasHighlight && highlightedIds!.has(nodes[i].id) ? 1.8 : 1.0;
        tmpScale.setScalar(baseScales[i] * nodeSize * boost);
      }
      tmpMat.compose(tmpPos, tmpQuat, tmpScale);
      mesh.setMatrixAt(local, tmpMat);
    }
    mesh.instanceMatrix.needsUpdate = true;

    bsFrameRef.current++;
    if (bsFrameRef.current % 15 === 0) {
      // Nulling triggers recomputation on the next raycast hit-test.
      mesh.boundingSphere = null;
    }
  });

  useEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    for (let local = 0; local < count; local++) {
      const i = indices[local];
      tmpColor.set(colors[i] ?? '#888888');
      mesh.setColorAt(local, tmpColor);
    }
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    // Stale bounding sphere kills raycasts (and therefore pointer events
    // including right-click). After data updates the new instance positions
    // can fall outside the cached sphere — null it so the next raycast
    // forces a recompute, and pump a frame so it actually happens before
    // the user's next click.
    mesh.boundingSphere = null;
    invalidate();
  }, [nodes, colors, indices, count, invalidate]);

  // Drag bookkeeping — keep pointer-down position so a tiny jitter between
  // down and up still resolves as a click rather than a drag.
  const downRef = useRef<{ id: string; x: number; y: number; moved: boolean } | null>(null);
  const DRAG_THRESHOLD = 4;

  const localToNodeId = (local: number | null | undefined): string | null => {
    if (local == null) return null;
    const i = indices[local];
    return nodes[i]?.id ?? null;
  };

  const handleOver = (e: ThreeEvent<PointerEvent>) => {
    e.stopPropagation();
    const id = localToNodeId(e.instanceId);
    if (!id) return;
    if (hiddenIds && hiddenIds.has(id)) return;
    onHover?.(id);
  };
  const handleOut = (e: ThreeEvent<PointerEvent>) => {
    e.stopPropagation();
    onHover?.(null);
  };
  const handlePointerDown = (e: ThreeEvent<PointerEvent>) => {
    const id = localToNodeId(e.instanceId);
    if (!id) return;
    if (hiddenIds && hiddenIds.has(id)) return;
    // Only left-button starts a drag; right-click falls through to onContextMenu.
    if (e.nativeEvent.button !== 0) return;
    e.stopPropagation();
    downRef.current = { id, x: e.nativeEvent.clientX, y: e.nativeEvent.clientY, moved: false };
    (e.target as Element).setPointerCapture?.(e.pointerId);
  };
  const handlePointerMove = (e: ThreeEvent<PointerEvent>) => {
    if (!downRef.current) return;
    const dx = e.nativeEvent.clientX - downRef.current.x;
    const dy = e.nativeEvent.clientY - downRef.current.y;
    if (!downRef.current.moved && dx * dx + dy * dy > DRAG_THRESHOLD * DRAG_THRESHOLD) {
      downRef.current.moved = true;
      onDragStart?.(downRef.current.id, e);
    }
    if (downRef.current.moved) {
      e.stopPropagation();
      onDragMove?.(e);
    }
  };
  const handlePointerUp = (e: ThreeEvent<PointerEvent>) => {
    const wasDragging = downRef.current?.moved ?? false;
    const clickedId = downRef.current?.id;
    downRef.current = null;
    if (wasDragging) {
      e.stopPropagation();
      onDragEnd?.(e);
    } else if (clickedId) {
      // Treated as a click — toggle selection.
      if (!hiddenIds || !hiddenIds.has(clickedId)) {
        onSelect?.(selectedId === clickedId ? null : clickedId);
      }
    }
  };
  const handleContextMenu = (e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    e.nativeEvent.preventDefault();
    const id = localToNodeId(e.instanceId);
    if (!id) return;
    if (hiddenIds && hiddenIds.has(id)) return;
    onContextMenu?.(id, e.nativeEvent as unknown as PointerEvent);
  };

  return (
    // `key={`${classKey}-${count}`}` forces a full remount on per-class
    // count change. three.js's InstancedMesh allocates `instanceMatrix`
    // once at construction sized for the initial `count`; reusing the
    // mesh when `args[2]` grows leaves the backing buffer too small.
    // `computeBoundingSphere` then reads past the array end, produces
    // NaN bounds, and three.js's raycaster early-outs against the bad
    // sphere — every pointer event silently misses, so left- and
    // right-clicks on nodes stop responding after the first action that
    // grows the graph (Add Adjacent / Follow / Load). The 15-frame
    // `boundingSphere = null` refresh in useFrame can't rescue this
    // because the underlying buffer is the wrong size.
    <instancedMesh
      key={`${classKey}-${count}`}
      ref={meshRef}
      args={[undefined, undefined, count]}
      onPointerOver={handleOver}
      onPointerOut={handleOut}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onContextMenu={handleContextMenu}
    >
      {geometry ?? <icosahedronGeometry args={[1, 1]} />}
      {/* Shared faceted two-tone material (facetedMaterial.ts). It's a
          patched MeshBasicMaterial so per-instance instanceColor still
          works; the layout effect above swaps in the barycentric
          geometry the material's wireframe needs. */}
      <primitive object={material} attach="material" />
    </instancedMesh>
  );
}
