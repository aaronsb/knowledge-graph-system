/**
 * Scene composition — Nodes + Edges + camera controls + lighting.
 *
 * Owns the physics sim; the sim owns the positions buffer that Nodes
 * and Edges read. Projection dispatch picks the camera-controls flavor:
 * OrbitControls for 3D (rotate + zoom + pan) and MapControls for 2D
 * (pan + zoom, no rotation).
 */

import { useEffect, useImperativeHandle, type ReactElement } from 'react';
import * as THREE from 'three';
import { OrbitControls } from '@react-three/drei';
import type { EngineNode, EngineEdge, Projection } from '../types';
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
  /** Optional per-node class key (parallel to `nodes`). When provided
   *  with `geometryByClass`, the engine renders one InstancedMesh per
   *  class — Document Explorer uses this to render document nodes as
   *  larger squared glyphs alongside concept dots. */
  nodeClasses?: string[];
  /** Geometry element per class key, used when `nodeClasses` is set. */
  geometryByClass?: Record<string, ReactElement>;
  /** Optional per-node base scale override (parallel to `nodes`). When
   *  provided, replaces the engine's degree-based default scale. */
  nodeScales?: Float32Array;
  /** Optional edge-type palette; when provided, edges and arrows color by type. */
  edgeColors?: string[];
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
  linkWidth?: number;
  /** Multiplier on the base world-space node-label height. Default 1. */
  nodeLabelSize?: number;
  /** Multiplier on the base world-space edge-label height. Default 1. */
  edgeLabelSize?: number;
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
  /** Camera + sim projection. Drives camera-controls flavor, sim
   *  dimensionality, and drag-plane construction. Defaults '3D'. */
  projection?: Projection;
}

/** Scene composition — physics + rendering + camera controls.  @verified c17bbeb9 */
export function Scene({
  nodes,
  edges,
  colors,
  nodeClasses,
  geometryByClass,
  nodeScales,
  edgeColors,
  hiddenIds,
  pinnedIds,
  highlightedIds,
  activeIds,
  dimAlpha = 1,
  nodeSize,
  edgeOpacity,
  linkWidth,
  nodeLabelSize = 1,
  edgeLabelSize = 1,
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
  projection = '3D',
}: SceneProps) {
  const sim = useSim(nodes, edges, {
    ...physics,
    hiddenIds,
    pinnedIds,
    dimensions: projection === '2D' ? 2 : 3,
  });
  const drag = useDragHandler({
    nodes,
    positionsRef: sim.positionsRef,
    pinnedIds: pinnedIds ?? EMPTY_SET,
    setPinnedIds: onPinnedIdsChange ?? NOOP_SET_SETTER,
    projection,
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
        edgeColors={edgeColors}
        hiddenIds={hiddenIds}
        opacity={edgeOpacity}
        linkWidth={linkWidth}
        activeIds={activeIds}
        dimAlpha={dimAlpha}
      />
      <Arrows
        nodes={nodes}
        edges={edges}
        positionsRef={sim.positionsRef}
        colors={colors}
        edgeColors={edgeColors}
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
        nodeClasses={nodeClasses}
        geometryByClass={geometryByClass}
        nodeScales={nodeScales}
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
        edgeColors={edgeColors}
        activeIds={activeIds}
        projection={projection}
        sizeMultiplier={edgeLabelSize}
      />
      <NodeLabels
        nodes={nodes}
        positionsRef={sim.positionsRef}
        colors={colors}
        hiddenIds={hiddenIds}
        enabled={showNodeLabels}
        visibilityRadius={labelVisibilityRadius}
        activeIds={activeIds}
        projection={projection}
        sizeMultiplier={nodeLabelSize}
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
      {projection === '2D' ? (
        // 2D bindings match the d3 force-graph viewer: left-click drag
        // pans, scroll-wheel zooms, right-click reserved for the
        // explorer's context menu. Rotation is disabled (z-locked
        // layout). The default OrbitControls binding (LEFT=ROTATE,
        // RIGHT=PAN) doesn't fit a 2D viewer, so we remap. Node-mesh
        // pointer handlers stopPropagation on a node hit, so left-click
        // on a node drives drag/select while left-click on background
        // pans.
        <OrbitControls
          makeDefault
          enableZoom={enableZoom}
          enablePan={enablePan}
          enableRotate={false}
          mouseButtons={{
            LEFT: THREE.MOUSE.PAN,
            MIDDLE: THREE.MOUSE.DOLLY,
            // RIGHT mapped to ROTATE, then gated off by enableRotate=false
            // — leaves right-click un-consumed so the wrapper div's
            // onContextMenu can open the explorer's context menu.
            RIGHT: THREE.MOUSE.ROTATE,
          }}
        />
      ) : (
        <OrbitControls makeDefault enableZoom={enableZoom} enablePan={enablePan} />
      )}
    </>
  );
}
