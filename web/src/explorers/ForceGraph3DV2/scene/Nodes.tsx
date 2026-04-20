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
  const handleClick = (e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    if (e.instanceId == null) return;
    const id = nodes[e.instanceId]?.id;
    if (!id) return;
    if (hiddenIds && hiddenIds.has(id)) return;
    // Toggle: clicking the already-selected node clears selection.
    onSelect?.(selectedId === id ? null : id);
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
      onClick={handleClick}
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
