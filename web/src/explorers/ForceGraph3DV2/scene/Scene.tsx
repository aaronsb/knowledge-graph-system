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
import { EdgeLabels } from './EdgeLabels';
import { NodeLabels } from './NodeLabels';
import { CaretMarker, NodeLabel } from './Overlays';
import { NodeInfoOverlay, type NodeInfoData } from './NodeInfoOverlay';
import { useSim } from './useSim';
import { useDragHandler } from './useDragHandler';
import type { ForceSimHandle, ForceSimParams } from './useForceSim';

// Stable references used when the plugin doesn't wire pinnedIds — hooks
// expect a Set identity that doesn't change every render.
const EMPTY_SET: Set<string> = new Set();
const NOOP_SET_SETTER: (s: Set<string>) => void = () => {};
const EMPTY_INFOS: NodeInfoData[] = [];

export interface SceneProps {
  nodes: EngineNode[];
  edges: EngineEdge[];
  /** Per-node colors, parallel to `nodes` by index. Caller computes from
   *  whatever dimension (ontology/degree/centrality/...) they choose. */
  colors: string[];
  /** Optional edge-type palette; when provided, edges and arrows color by type. */
  edgePalette?: (edgeType: string) => string;
  hiddenIds?: Set<string>;
  pinnedIds?: Set<string>;
  highlightedIds?: Set<string>;
  /** When defined, items not in this set are dimmed. Driven by hover or
   *  right-click "Focus on node" in the consuming explorer. */
  activeIds?: Set<string>;
  /** Dim multiplier applied to non-active edges/arrows in edge-type mode.
   *  Node colors arrive pre-dimmed via the `colors` prop. */
  dimAlpha?: number;
  nodeSize?: number;
  edgeOpacity?: number;
  showArrows?: boolean;
  showEdgeLabels?: boolean;
  showNodeLabels?: boolean;
  labelVisibilityRadius?: number;
  physics?: ForceSimParams;
  selectedId?: string | null;
  hoveredId?: string | null;
  enableDrag?: boolean;
  enableZoom?: boolean;
  enablePan?: boolean;
  onSelect?: (id: string | null) => void;
  onHover?: (id: string | null) => void;
  onContextMenu?: (id: string, event: PointerEvent) => void;
  onPinnedIdsChange?: (ids: Set<string>) => void;
  activeNodeInfos?: NodeInfoData[];
  onDismissNodeInfo?: (nodeId: string) => void;
  /** Optional external handle to drive reheat/freeze/simmer from outside Canvas. */
  simHandleRef?: React.MutableRefObject<ForceSimHandle | null>;
}

/** V2 scene composition — physics + rendering + orbit controls.  @verified c17bbeb9 */
export function Scene({
  nodes,
  edges,
  colors,
  edgePalette,
  hiddenIds,
  pinnedIds,
  highlightedIds,
  activeIds,
  dimAlpha = 1,
  nodeSize,
  edgeOpacity,
  showArrows = true,
  showEdgeLabels = true,
  showNodeLabels = true,
  labelVisibilityRadius = 250,
  physics,
  selectedId,
  hoveredId,
  enableDrag = true,
  enableZoom = true,
  enablePan = true,
  onSelect,
  onHover,
  onContextMenu,
  onPinnedIdsChange,
  activeNodeInfos = EMPTY_INFOS,
  onDismissNodeInfo,
  simHandleRef,
}: SceneProps) {
  const sim = useSim(nodes, edges, { ...physics, hiddenIds, pinnedIds });
  const drag = useDragHandler({
    nodes,
    positionsRef: sim.positionsRef,
    pinnedIds: pinnedIds ?? EMPTY_SET,
    setPinnedIds: onPinnedIdsChange ?? NOOP_SET_SETTER,
  });

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
        colors={colors}
        edgePalette={edgePalette}
        hiddenIds={hiddenIds}
        opacity={edgeOpacity}
        activeIds={activeIds}
        dimAlpha={dimAlpha}
      />
      <Arrows
        nodes={nodes}
        edges={edges}
        positionsRef={sim.positionsRef}
        colors={colors}
        edgePalette={edgePalette}
        hiddenIds={hiddenIds}
        enabled={showArrows}
        nodeSize={nodeSize}
        activeIds={activeIds}
        dimAlpha={dimAlpha}
      />
      <Nodes
        nodes={nodes}
        positionsRef={sim.positionsRef}
        colors={colors}
        hiddenIds={hiddenIds}
        highlightedIds={highlightedIds}
        nodeSize={nodeSize}
        selectedId={selectedId}
        onSelect={onSelect}
        onHover={onHover}
        onContextMenu={onContextMenu}
        onDragStart={enableDrag ? drag.onDragStart : undefined}
        onDragMove={enableDrag ? drag.onDragMove : undefined}
        onDragEnd={enableDrag ? drag.onDragEnd : undefined}
      />
      <EdgeLabels
        nodes={nodes}
        edges={edges}
        positionsRef={sim.positionsRef}
        hiddenIds={hiddenIds}
        enabled={showEdgeLabels}
        visibilityRadius={labelVisibilityRadius}
        edgePalette={edgePalette}
        activeIds={activeIds}
      />
      <NodeLabels
        nodes={nodes}
        positionsRef={sim.positionsRef}
        colors={colors}
        hiddenIds={hiddenIds}
        enabled={showNodeLabels}
        visibilityRadius={labelVisibilityRadius}
        activeIds={activeIds}
      />
      {activeNodeInfos.map((info) => (
        <NodeInfoOverlay
          key={info.nodeId}
          info={info}
          nodes={nodes}
          positionsRef={sim.positionsRef}
          onDismiss={() => onDismissNodeInfo?.(info.nodeId)}
        />
      ))}
      <CaretMarker nodes={nodes} positionsRef={sim.positionsRef} nodeId={selectedId} />
      {/* Hover/select label is redundant when persistent node labels are
          rendering — only show it when persistent labels are off, OR when
          a node is explicitly selected (the selected pill is more
          prominent than the always-on label). */}
      {(!showNodeLabels || selectedId) && (
        <NodeLabel
          nodes={nodes}
          positionsRef={sim.positionsRef}
          nodeId={selectedId ?? hoveredId}
          variant={selectedId ? 'selected' : 'hover'}
        />
      )}
      <OrbitControls makeDefault enableZoom={enableZoom} enablePan={enablePan} />
    </>
  );
}
