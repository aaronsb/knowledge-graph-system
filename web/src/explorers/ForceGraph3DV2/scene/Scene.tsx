/**
 * Scene composition — Nodes + Edges + camera controls + lighting.
 *
 * Owns the shared positions buffer for the frame. M1 seeds positions
 * once (static); M2 swaps the seeded init for a force-sim hook that
 * mutates the same buffer each frame, without changes to Nodes/Edges.
 */

import { useEffect, useMemo, useRef } from 'react';
import { OrbitControls } from '@react-three/drei';
import { useThree } from '@react-three/fiber';
import type { EngineNode, EngineEdge } from '../types';
import { Nodes } from './Nodes';
import { Edges } from './Edges';
import { seedSpherePositions, defaultSeedRadius } from './positions';

export interface SceneProps {
  nodes: EngineNode[];
  edges: EngineEdge[];
  palette: (category: string) => string;
  hiddenIds?: Set<string>;
  highlightedIds?: Set<string>;
  nodeSize?: number;
  edgeOpacity?: number;
}

/** V2 scene composition — Nodes + Edges + OrbitControls + lighting.  @verified c17bbeb9 */
export function Scene({
  nodes,
  edges,
  palette,
  hiddenIds,
  highlightedIds,
  nodeSize,
  edgeOpacity,
}: SceneProps) {
  const positionsRef = useRef<Float32Array | null>(null);
  const invalidate = useThree((state) => state.invalidate);

  // Reseed whenever node count changes. Preserves existing positions when
  // count is unchanged (M1 static) so simple re-renders don't disturb layout.
  useMemo(() => {
    if (!positionsRef.current || positionsRef.current.length !== nodes.length * 3) {
      positionsRef.current = seedSpherePositions(
        nodes.length,
        defaultSeedRadius(nodes.length)
      );
    }
  }, [nodes.length]);

  useEffect(() => {
    invalidate();
  }, [nodes, edges, invalidate]);

  return (
    <>
      <ambientLight intensity={0.5} />
      <Edges
        nodes={nodes}
        edges={edges}
        positionsRef={positionsRef}
        palette={palette}
        hiddenIds={hiddenIds}
        opacity={edgeOpacity}
      />
      <Nodes
        nodes={nodes}
        positionsRef={positionsRef}
        palette={palette}
        hiddenIds={hiddenIds}
        highlightedIds={highlightedIds}
        nodeSize={nodeSize}
      />
      <OrbitControls makeDefault />
    </>
  );
}
