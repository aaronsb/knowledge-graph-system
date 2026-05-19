/**
 * Scene composition — Nodes + Edges + camera controls + lighting.
 *
 * Owns the physics sim; the sim owns the positions buffer that Nodes
 * and Edges read. Projection dispatch picks the camera-controls flavor:
 * OrbitControls for 3D (rotate + zoom + pan) and MapControls for 2D
 * (pan + zoom, no rotation).
 */

import { useImperativeHandle, useMemo, useRef, type ReactElement } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
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
import { useFitCamera } from './useFitCamera';
import { useOrientAndFrame } from './useOrientAndFrame';
import type { ForceSimHandle, ForceSimParams } from './useForceSim';

// Stable references used when the plugin doesn't wire pinnedIds — hooks
// expect a Set identity that doesn't change every render.
const EMPTY_SET: Set<string> = new Set();
const NOOP_SET_SETTER: (s: Set<string>) => void = () => {};
const EMPTY_INFOS: NodeInfoData[] = [];

/**
 * Directional key light pinned to the camera. Each frame it copies the
 * camera position; its target stays at the world origin (the graph is
 * roughly centred there), so the lit side always faces the viewer as
 * they orbit — a static world-space light would look glued to one face
 * when the graph rotates. Only meaningful for the lit (Lambert)
 * material; rendered solely in lit mode so flat mode pays no per-frame
 * cost. Paired with the scene's ambient so the far side isn't black.
 */
function CameraKeyLight() {
  const lightRef = useRef<THREE.DirectionalLight>(null);
  useFrame(({ camera }) => {
    lightRef.current?.position.copy(camera.position);
  });
  // The light's default target sits at the world origin with an identity
  // matrix, so direction = origin − cameraPos resolves correctly without
  // a target.updateMatrixWorld() call. If a future change moves the
  // target off origin, that update becomes required here.
  return <directionalLight ref={lightRef} intensity={1.1} />;
}

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
   *  provided, replaces the engine's degree-based default scale.
   *  Drives node mesh size AND scale-aware label offsets uniformly. */
  nodeScales?: Float32Array;
  /** Optional edge-type palette; when provided, edges and arrows color by type. */
  edgeColors?: string[];
  /** Optional per-edge render visibility (parallel to `edges`). When
   *  `false`, the edge is kept in the physics sim but rendered collapsed
   *  to a point. Used by Document Explorer for invisible clustering hints. */
  edgeVisible?: boolean[];
  hiddenIds?: Set<string>;
  pinnedIds?: Set<string>;
  highlightedIds?: Set<string>;
  /** When defined, items not in this set are dimmed. Driven by hover or
   *  right-click "Focus on node" in the consuming explorer. */
  activeIds?: Set<string>;
  /** Dim multiplier applied to non-active edges/arrows in edge-type mode.
   *  Node colors arrive pre-dimmed via the `colors` prop. */
  dimAlpha?: number;
  /** Plane opacity for out-of-set node/edge labels. Resolved from the
   *  active dim tier by the consumer (see dimModel). Default 1 (no dim).
   *  Pairs with `dimAlpha`: alpha dims the figures, this dims their
   *  text, and the dim model keeps the two coupled per tier. */
  dimLabelOpacity?: number;
  nodeSize?: number;
  edgeOpacity?: number;
  linkWidth?: number;
  /** Multiplier on the base world-space node-label height. Default 1. */
  nodeLabelSize?: number;
  /** Multiplier on the base world-space edge-label height. Default 1. */
  edgeLabelSize?: number;
  /** Optional per-node label color override (parallel to `nodes`). When
   *  omitted, labels use the node's mesh color (Force Graph default). */
  labelColors?: string[];
  /** Signed Y offset for node labels in world units. Default +1.4
   *  (above); negative drops below — used by Document Explorer. */
  nodeLabelOffsetY?: number;
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
  /** Shading mode. false (default) = flat unlit two-tone; true = real
   *  Lambert lighting with a camera-tracked key light. */
  lit?: boolean;
  /** First-load orient closeness (see useOrientAndFrame's pullback): 0 =
   *  camera at the cluster's near face, higher backs off. Per-explorer
   *  because node scale/layout differ — Document Explorer's large
   *  document nodes need more pull-back than Force Graph. Omit ⇒ the
   *  hook's Force-Graph-tuned default. */
  orientPullback?: number;
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
  edgeVisible,
  hiddenIds,
  pinnedIds,
  highlightedIds,
  activeIds,
  dimAlpha = 1,
  dimLabelOpacity = 1,
  nodeSize,
  edgeOpacity,
  linkWidth,
  nodeLabelSize = 1,
  edgeLabelSize = 1,
  labelColors,
  nodeLabelOffsetY,
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
  lit = false,
  orientPullback,
}: SceneProps) {
  const sim = useSim(nodes, edges, {
    ...physics,
    hiddenIds,
    pinnedIds,
    dimensions: projection === '2D' ? 2 : 3,
  });

  // Resolve per-node base scales here so Nodes and NodeLabels see the
  // same numbers — the plugin's override wins if provided, otherwise
  // the engine derives from degree. Sharing one resolved array is what
  // lets label positioning be scale-aware for every explorer (the
  // alternative is each consumer re-deriving and silently disagreeing).
  const resolvedNodeScales = useMemo(() => {
    if (nodeScales) return nodeScales;
    const out = new Float32Array(nodes.length);
    for (let i = 0; i < nodes.length; i++) {
      out[i] = 0.8 + Math.sqrt(nodes[i].degree || 1) * 0.3;
    }
    return out;
  }, [nodes, nodeScales]);
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

  // The shared PCA tangent-orient action: rotate to the graph's broad
  // face and ease in. Created here so both consumers share one instance
  // and one tween loop — first-load fake-zoom-extents (useFitCamera) and
  // (next) a double-click focus on a node. Shared Scene ⇒ Force Graph
  // and Document Explorer both get it from one implementation.
  const orientAction = useOrientAndFrame(sim.positionsRef, nodes, {
    hiddenIds,
    edges,
    projection,
    pullback: orientPullback,
  });

  // Fit once on the graph's first appearance (only): wait for physics to
  // settle, then fire the whole-graph orient as a "fake zoom-extents".
  useFitCamera(orientAction.orient, nodes);

  // Note: re-seeding and demand-mode kick on data change are now owned by
  // the sim hook (useForceSim / useGpuForceSim). It carries surviving
  // nodes' positions over and picks a gentle vs full reheat based on how
  // much changed, then invalidate()s itself. The old unconditional
  // sim.reheat() here slammed alpha to full on every poke — that was the
  // whole-graph "sproing". The manual Reheat button still calls
  // sim.reheat() for a deliberate full re-layout.

  return (
    <>
      <ambientLight intensity={0.5} />
      {lit && <CameraKeyLight />}
      <Edges
        nodes={nodes}
        edges={edges}
        positionsRef={sim.positionsRef}
        colors={colors}
        edgeColors={edgeColors}
        edgeVisible={edgeVisible}
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
        nodeScales={resolvedNodeScales}
        lit={lit}
        hiddenIds={hiddenIds}
        highlightedIds={highlightedIds}
        nodeSize={nodeSize}
        selectedId={selectedId}
        onSelect={onSelect}
        onNodeDoubleClick={orientAction.focus}
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
        dimLabelOpacity={dimLabelOpacity}
      />
      <NodeLabels
        nodes={nodes}
        positionsRef={sim.positionsRef}
        colors={colors}
        labelColors={labelColors}
        hiddenIds={hiddenIds}
        enabled={showNodeLabels}
        visibilityRadius={labelVisibilityRadius}
        activeIds={activeIds}
        projection={projection}
        sizeMultiplier={nodeLabelSize}
        labelOffsetY={nodeLabelOffsetY}
        nodeScales={resolvedNodeScales}
        nodeSize={nodeSize}
        dimLabelOpacity={dimLabelOpacity}
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
