/**
 * Screen-space overlays — CaretMarker for selection, NodeLabel for hover.
 *
 * Both use @react-three/drei's <Html> helper with `center` positioning so
 * the DOM element sits exactly at a node's world position but stays a
 * constant pixel size regardless of camera distance. That's the
 * CaretMarker pattern ADR-702 inherits from the atlassian-graph
 * reference — a fixed-size selection indicator at a moving 3D position.
 *
 * Position is updated each frame via a group ref rather than by passing
 * a fresh `position` prop on every render; no React re-renders per frame.
 * Html overlays don't z-sort against scene depth (a documented trade-off
 * in the ADR) so they'll show even when occluded by other nodes.
 */

import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import * as THREE from 'three';
import type { EngineNode } from '../types';

interface OverlayBaseProps {
  nodes: EngineNode[];
  positionsRef: React.MutableRefObject<Float32Array | null>;
  nodeId: string | null | undefined;
}

/** Follows a target node each frame via a group transform (no re-render). */
function useNodeFollowerRef(nodes: EngineNode[], nodeId: string | null | undefined) {
  const groupRef = useRef<THREE.Group>(null);
  const nodeIndex = useMemo(() => {
    const m = new Map<string, number>();
    for (let i = 0; i < nodes.length; i++) m.set(nodes[i].id, i);
    return m;
  }, [nodes]);
  return { groupRef, nodeIndex };
}

interface CaretMarkerProps extends OverlayBaseProps {
  color?: string;
}

/** Four-corner brackets + center ring at the selected node's world pos.  @verified c17bbeb9 */
export function CaretMarker({
  nodes,
  positionsRef,
  nodeId,
  color = '#ffffff',
}: CaretMarkerProps) {
  const { groupRef, nodeIndex } = useNodeFollowerRef(nodes, nodeId);

  useFrame(() => {
    const g = groupRef.current;
    if (!g) return;
    const idx = nodeId != null ? nodeIndex.get(nodeId) : undefined;
    const positions = positionsRef.current;
    if (idx == null || !positions) {
      g.visible = false;
      return;
    }
    g.visible = true;
    g.position.set(positions[idx * 3], positions[idx * 3 + 1], positions[idx * 3 + 2]);
  });

  if (nodeId == null) return null;

  const corner = {
    position: 'absolute' as const,
    width: 10,
    height: 10,
    borderColor: color,
    borderStyle: 'solid' as const,
    filter: `drop-shadow(0 0 8px rgba(255,255,255,0.9)) drop-shadow(0 0 18px rgba(255,255,255,0.5))`,
  };

  return (
    <group ref={groupRef}>
      <Html
        center
        zIndexRange={[100, 0]}
        wrapperClass="pointer-events-none"
        style={{ pointerEvents: 'none' }}
      >
        <div style={{ position: 'relative', width: 52, height: 52, pointerEvents: 'none' }}>
          <div style={{ ...corner, top: 0, left: 0, borderWidth: '2px 0 0 2px' }} />
          <div style={{ ...corner, top: 0, right: 0, borderWidth: '2px 2px 0 0' }} />
          <div style={{ ...corner, bottom: 0, left: 0, borderWidth: '0 0 2px 2px' }} />
          <div style={{ ...corner, bottom: 0, right: 0, borderWidth: '0 2px 2px 0' }} />
          <div
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              width: 22,
              height: 22,
              transform: 'translate(-50%, -50%)',
              border: `1px solid ${color}`,
              borderRadius: '50%',
              boxShadow: `0 0 10px rgba(255,255,255,0.6), inset 0 0 6px rgba(255,255,255,0.25)`,
            }}
          />
        </div>
      </Html>
    </group>
  );
}

interface NodeLabelProps extends OverlayBaseProps {
  variant?: 'hover' | 'selected';
}

/** Hover/selection label showing node.label (not node.id) — finding #3.  @verified c17bbeb9 */
export function NodeLabel({
  nodes,
  positionsRef,
  nodeId,
  variant = 'hover',
}: NodeLabelProps) {
  const { groupRef, nodeIndex } = useNodeFollowerRef(nodes, nodeId);

  useFrame(() => {
    const g = groupRef.current;
    if (!g) return;
    const idx = nodeId != null ? nodeIndex.get(nodeId) : undefined;
    const positions = positionsRef.current;
    if (idx == null || !positions) {
      g.visible = false;
      return;
    }
    g.visible = true;
    g.position.set(positions[idx * 3], positions[idx * 3 + 1], positions[idx * 3 + 2]);
  });

  if (nodeId == null) return null;
  const node = nodes.find((n) => n.id === nodeId);
  if (!node) return null;

  const style =
    variant === 'selected'
      ? {
          background: 'rgba(10,10,15,0.95)',
          border: '1px solid #7aa2f7',
          color: '#d7d7e0',
        }
      : {
          background: 'rgba(10,10,15,0.85)',
          border: '1px solid #26263a',
          color: '#d7d7e0',
        };

  return (
    <group ref={groupRef}>
      <Html
        center
        zIndexRange={[90, 0]}
        wrapperClass="pointer-events-none"
        style={{ pointerEvents: 'none' }}
      >
        <div
          style={{
            ...style,
            padding: '3px 8px',
            borderRadius: 3,
            fontSize: 11,
            fontFamily: 'SF Mono, Menlo, monospace',
            whiteSpace: 'nowrap',
            transform: 'translate(0, -260%)',
            pointerEvents: 'none',
          }}
        >
          {node.label}
        </div>
      </Html>
    </group>
  );
}
