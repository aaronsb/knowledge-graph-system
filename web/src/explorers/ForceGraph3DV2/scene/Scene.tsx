/**
 * Scene composition — Nodes + Edges + camera controls + lighting.
 *
 * Owns the physics sim; the sim owns the positions buffer that Nodes
 * and Edges read. M2 task #8 adds CPU force sim; M2 task #9 adds the
 * GPU sim and a dispatcher. Both expose the same handle shape so the
 * scene composition doesn't change between them.
 */

import { useEffect, useImperativeHandle } from 'react';
import { OrbitControls } from '@react-three/drei';
import type { EngineNode, EngineEdge } from '../types';
import { Nodes } from './Nodes';
import { Edges } from './Edges';
import { useSim } from './useSim';
import type { ForceSimHandle, ForceSimParams } from './useForceSim';

export interface SceneProps {
  nodes: EngineNode[];
  edges: EngineEdge[];
  palette: (category: string) => string;
  hiddenIds?: Set<string>;
  highlightedIds?: Set<string>;
  nodeSize?: number;
  edgeOpacity?: number;
  physics?: ForceSimParams;
  /** Optional external handle to drive reheat/freeze/simmer from outside Canvas. */
  simHandleRef?: React.MutableRefObject<ForceSimHandle | null>;
}

/** V2 scene composition — physics + rendering + orbit controls.  @verified c17bbeb9 */
export function Scene({
  nodes,
  edges,
  palette,
  hiddenIds,
  highlightedIds,
  nodeSize,
  edgeOpacity,
  physics,
  simHandleRef,
}: SceneProps) {
  const sim = useSim(nodes, edges, { ...physics, hiddenIds });

  // Expose the sim handle outside the Canvas tree (e.g. to a settings
  // panel that lives in the plugin component). useImperativeHandle is
  // the idiomatic way even though we pass a MutableRefObject ourselves.
  useImperativeHandle(simHandleRef, () => sim, [sim]);

  useEffect(() => {
    // Kick a frame when the data set changes so demand-mode picks up
    // the reseeded buffers immediately rather than next user interaction.
    sim.reheat();
  }, [nodes.length]);

  return (
    <>
      <ambientLight intensity={0.5} />
      <Edges
        nodes={nodes}
        edges={edges}
        positionsRef={sim.positionsRef}
        palette={palette}
        hiddenIds={hiddenIds}
        opacity={edgeOpacity}
      />
      <Nodes
        nodes={nodes}
        positionsRef={sim.positionsRef}
        palette={palette}
        hiddenIds={hiddenIds}
        highlightedIds={highlightedIds}
        nodeSize={nodeSize}
      />
      <OrbitControls makeDefault />
    </>
  );
}
