/**
 * Instanced node rendering.
 *
 * One draw call for N nodes via InstancedMesh. Per-instance matrix
 * (position + uniform scale from degree) and per-instance color from
 * the palette. Reads positions each frame from a shared Float32Array
 * ref so physics and rendering stay on the same buffer.
 *
 * Pointer events on the mesh surface instanceId, which callers resolve
 * to node ids. Picking is uniform across sprite and poly modes per
 * ADR-702 — sprite mode (billboarded quad) will use the same
 * InstancedMesh primitive in M3.
 */

import { useEffect, useMemo, useRef } from 'react';
import { useFrame, useThree, type ThreeEvent } from '@react-three/fiber';
import * as THREE from 'three';
import type { EngineNode } from '../types';

const tmpMat = new THREE.Matrix4();
const tmpQuat = new THREE.Quaternion();
const tmpScale = new THREE.Vector3();
const tmpPos = new THREE.Vector3();
const tmpColor = new THREE.Color();

export interface NodesProps {
  nodes: EngineNode[];
  positionsRef: React.MutableRefObject<Float32Array | null>;
  palette: (category: string) => string;
  hiddenIds?: Set<string>;
  highlightedIds?: Set<string>;
  nodeSize?: number;
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
  onHover?: (id: string | null) => void;
  onContextMenu?: (id: string, event: PointerEvent) => void;
}

/** Instanced icosahedron node mesh — one draw call for all nodes.  @verified c17bbeb9 */
export function Nodes({
  nodes,
  positionsRef,
  palette,
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
}: NodesProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const invalidate = useThree((state) => state.invalidate);

  const scales = useMemo(() => {
    const out = new Float32Array(nodes.length);
    for (let i = 0; i < nodes.length; i++) {
      out[i] = (0.8 + Math.sqrt(nodes[i].degree || 1) * 0.3) * nodeSize;
    }
    return out;
  }, [nodes, nodeSize]);

  useFrame(() => {
    const mesh = meshRef.current;
    const positions = positionsRef.current;
    if (!mesh || !positions) return;

    const hasHidden = !!hiddenIds && hiddenIds.size > 0;
    const hasHighlight = !!highlightedIds && highlightedIds.size > 0;

    for (let i = 0; i < nodes.length; i++) {
      tmpPos.set(positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2]);
      if (hasHidden && hiddenIds!.has(nodes[i].id)) {
        // Zero scale collapses the mesh to a point — invisible and not
        // pickable, while leaving the physics index intact.
        tmpScale.setScalar(0);
      } else {
        const boost = hasHighlight && highlightedIds!.has(nodes[i].id) ? 1.8 : 1.0;
        tmpScale.setScalar(scales[i] * boost);
      }
      tmpMat.compose(tmpPos, tmpQuat, tmpScale);
      mesh.setMatrixAt(i, tmpMat);
    }
    mesh.instanceMatrix.needsUpdate = true;
  });

  useEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    for (let i = 0; i < nodes.length; i++) {
      tmpColor.set(palette(nodes[i].category));
      mesh.setColorAt(i, tmpColor);
    }
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    invalidate();
  }, [nodes, palette, invalidate]);

  // Drag bookkeeping — keep pointer-down position so a tiny jitter between
  // down and up still resolves as a click rather than a drag.
  const downRef = useRef<{ id: string; x: number; y: number; moved: boolean } | null>(null);
  const DRAG_THRESHOLD = 4;

  const handleOver = (e: ThreeEvent<PointerEvent>) => {
    e.stopPropagation();
    if (e.instanceId == null) return;
    const id = nodes[e.instanceId]?.id;
    if (!id) return;
    if (hiddenIds && hiddenIds.has(id)) return;
    onHover?.(id);
  };
  const handleOut = (e: ThreeEvent<PointerEvent>) => {
    e.stopPropagation();
    onHover?.(null);
  };
  const handlePointerDown = (e: ThreeEvent<PointerEvent>) => {
    if (e.instanceId == null) return;
    const id = nodes[e.instanceId]?.id;
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
    if (e.instanceId == null) return;
    const id = nodes[e.instanceId]?.id;
    if (!id) return;
    if (hiddenIds && hiddenIds.has(id)) return;
    onContextMenu?.(id, e.nativeEvent as unknown as PointerEvent);
  };

  return (
    <instancedMesh
      ref={meshRef}
      args={[undefined, undefined, nodes.length]}
      onPointerOver={handleOver}
      onPointerOut={handleOut}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onContextMenu={handleContextMenu}
    >
      <icosahedronGeometry args={[1, 1]} />
      {/* vertexColors=false is intentional: per-instance colors come from
          setColorAt/instanceColor, which three injects via the
          USE_INSTANCING_COLOR shader chunk independent of the vertexColors
          flag. Switching to a lit material silently breaks this. */}
      <meshBasicMaterial vertexColors={false} />
    </instancedMesh>
  );
}
