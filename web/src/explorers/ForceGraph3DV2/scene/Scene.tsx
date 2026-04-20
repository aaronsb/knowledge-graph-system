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
import { Arrows } from './Arrows';
import { useSim } from './useSim';
import type { ForceSimHandle, ForceSimParams } from './useForceSim';

export interface SceneProps {
  nodes: EngineNode[];
  edges: EngineEdge[];
  palette: (category: string) => string;
  /** Optional edge-type palette; when provided, edges and arrows color by type. */
  edgePalette?: (edgeType: string) => string;
  hiddenIds?: Set<string>;
  highlightedIds?: Set<string>;
  nodeSize?: number;
  edgeOpacity?: number;
  showArrows?: boolean;
  physics?: ForceSimParams;
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
  onHover?: (id: string | null) => void;
  onContextMenu?: (id: string, event: PointerEvent) => void;
  /** Optional external handle to drive reheat/freeze/simmer from outside Canvas. */
  simHandleRef?: React.MutableRefObject<ForceSimHandle | null>;
}

/** V2 scene composition — physics + rendering + orbit controls.  @verified c17bbeb9 */
export function Scene({
  nodes,
  edges,
  palette,
  edgePalette,
  hiddenIds,
  highlightedIds,
  nodeSize,
  edgeOpacity,
  showArrows = true,
  physics,
  selectedId,
  onSelect,
  onHover,
  onContextMenu,
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
        edgePalette={edgePalette}
        hiddenIds={hiddenIds}
        opacity={edgeOpacity}
      />
      <Arrows
        nodes={nodes}
        edges={edges}
        positionsRef={sim.positionsRef}
        palette={palette}
        edgePalette={edgePalette}
        hiddenIds={hiddenIds}
        enabled={showArrows}
      />
      <Nodes
        nodes={nodes}
        positionsRef={sim.positionsRef}
        palette={palette}
        hiddenIds={hiddenIds}
        highlightedIds={highlightedIds}
        nodeSize={nodeSize}
        selectedId={selectedId}
        onSelect={onSelect}
        onHover={onHover}
        onContextMenu={onContextMenu}
      />
      <OrbitControls makeDefault />
    </>
  );
}
