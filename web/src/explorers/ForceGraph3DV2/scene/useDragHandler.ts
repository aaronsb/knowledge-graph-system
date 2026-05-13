/**
 * Drag handler for node repositioning.
 *
 * Builds handlers for Nodes' onDragStart / onDragMove / onDragEnd. While
 * a drag is active the engine treats the dragged node as pinned (sim
 * skips integration). Drag motion is computed by raycasting a plane at
 * the node's current depth, perpendicular to the camera, and writing
 * the intersection point straight into the shared positions buffer.
 * Because the sim does not touch pinned nodes, the write sticks.
 *
 * On pointer-up the node is released. Pinning-past-release is not
 * handled here — a future settings toggle can wrap this hook to persist
 * the pin until the user explicitly unpins.
 */

import { useCallback, useMemo, useRef } from 'react';
import { useThree, type ThreeEvent } from '@react-three/fiber';
import * as THREE from 'three';
import type { EngineNode } from '../types';

export interface DragHandlers {
  onDragStart: (id: string, event: ThreeEvent<PointerEvent>) => void;
  onDragMove: (event: ThreeEvent<PointerEvent>) => void;
  onDragEnd: (event: ThreeEvent<PointerEvent>) => void;
}

export interface UseDragHandlerParams {
  nodes: EngineNode[];
  positionsRef: React.MutableRefObject<Float32Array | null>;
  pinnedIds: Set<string>;
  setPinnedIds: (next: Set<string>) => void;
}

/** Drag handlers that pin a node and follow the cursor on a camera plane.  @verified c17bbeb9 */
export function useDragHandler({
  nodes,
  positionsRef,
  pinnedIds,
  setPinnedIds,
}: UseDragHandlerParams): DragHandlers {
  const camera = useThree((state) => state.camera);
  const gl = useThree((state) => state.gl);

  const nodeIndex = useMemo(() => {
    const m = new Map<string, number>();
    for (let i = 0; i < nodes.length; i++) m.set(nodes[i].id, i);
    return m;
  }, [nodes]);

  const dragRef = useRef<{
    id: string;
    idx: number;
    plane: THREE.Plane;
    intersection: THREE.Vector3;
    raycaster: THREE.Raycaster;
  } | null>(null);

  const onDragStart = useCallback(
    (id: string, _e: ThreeEvent<PointerEvent>) => {
      const idx = nodeIndex.get(id);
      const positions = positionsRef.current;
      if (idx == null || !positions) return;
      const pos = new THREE.Vector3(
        positions[idx * 3],
        positions[idx * 3 + 1],
        positions[idx * 3 + 2]
      );
      // Plane perpendicular to the camera view direction, through the node.
      const normal = new THREE.Vector3();
      camera.getWorldDirection(normal).negate();
      const plane = new THREE.Plane(normal, -normal.dot(pos));
      dragRef.current = {
        id,
        idx,
        plane,
        intersection: new THREE.Vector3(),
        raycaster: new THREE.Raycaster(),
      };
      // Pin the node so the sim stops moving it while we drag.
      const next = new Set(pinnedIds);
      next.add(id);
      setPinnedIds(next);
    },
    [camera, nodeIndex, pinnedIds, positionsRef, setPinnedIds]
  );

  const onDragMove = useCallback(
    (e: ThreeEvent<PointerEvent>) => {
      const d = dragRef.current;
      const positions = positionsRef.current;
      if (!d || !positions) return;
      // Convert canvas-relative coords to NDC and raycast against the drag plane.
      const canvas = gl.domElement;
      const rect = canvas.getBoundingClientRect();
      const ndc = new THREE.Vector2(
        ((e.nativeEvent.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.nativeEvent.clientY - rect.top) / rect.height) * 2 + 1
      );
      d.raycaster.setFromCamera(ndc, camera);
      if (d.raycaster.ray.intersectPlane(d.plane, d.intersection)) {
        positions[d.idx * 3] = d.intersection.x;
        positions[d.idx * 3 + 1] = d.intersection.y;
        positions[d.idx * 3 + 2] = d.intersection.z;
      }
    },
    [camera, gl.domElement, positionsRef]
  );

  const onDragEnd = useCallback(
    (_e: ThreeEvent<PointerEvent>) => {
      const d = dragRef.current;
      if (!d) return;
      // Release pin — if the user wants to keep it pinned, that'll be a
      // future toggle in the plugin layer.
      const next = new Set(pinnedIds);
      next.delete(d.id);
      setPinnedIds(next);
      dragRef.current = null;
    },
    [pinnedIds, setPinnedIds]
  );

  return { onDragStart, onDragMove, onDragEnd };
}
