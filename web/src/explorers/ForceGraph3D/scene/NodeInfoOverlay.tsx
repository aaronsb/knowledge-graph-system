/**
 * NodeInfoBox follower.
 *
 * Wraps the shared NodeInfoBox in a drei <Html> that follows a node's
 * world position via a group ref, updated in useFrame. The box itself
 * receives x=0, y=0 so its internal absolute positioning anchors to
 * the Html wrapper (which is placed at the node's screen projection by
 * drei). pointer-events are enabled on the wrapper because NodeInfoBox
 * is interactive (collapsible sections, dismiss button).
 */

import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import * as THREE from 'three';
import { NodeInfoBox } from '../../common/NodeInfoBox';
import type { EngineNode } from '../types';

export interface NodeInfoData {
  nodeId: string;
  label: string;
  group: string;
  degree: number;
}

export interface NodeInfoOverlayProps {
  info: NodeInfoData;
  nodes: EngineNode[];
  positionsRef: React.MutableRefObject<Float32Array | null>;
  onDismiss: () => void;
}

/** Selection-driven info panel that follows a node's world position.  @verified c17bbeb9 */
export function NodeInfoOverlay({ info, nodes, positionsRef, onDismiss }: NodeInfoOverlayProps) {
  const groupRef = useRef<THREE.Group>(null);
  const nodeIndex = useMemo(() => {
    const m = new Map<string, number>();
    for (let i = 0; i < nodes.length; i++) m.set(nodes[i].id, i);
    return m;
  }, [nodes]);

  useFrame(() => {
    const g = groupRef.current;
    if (!g) return;
    const idx = nodeIndex.get(info.nodeId);
    const positions = positionsRef.current;
    if (idx == null || !positions) {
      g.visible = false;
      return;
    }
    g.visible = true;
    g.position.set(positions[idx * 3], positions[idx * 3 + 1], positions[idx * 3 + 2]);
  });

  return (
    <group ref={groupRef}>
      <Html center zIndexRange={[80, 0]} style={{ pointerEvents: 'auto' }}>
        <NodeInfoBox
          info={{
            nodeId: info.nodeId,
            label: info.label,
            group: info.group,
            degree: info.degree,
            x: 0,
            y: 0,
          }}
          onDismiss={onDismiss}
        />
      </Html>
    </group>
  );
}
