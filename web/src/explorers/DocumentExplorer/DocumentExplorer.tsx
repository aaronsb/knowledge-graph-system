/**
 * Document Explorer — Multi-Document Concept Graph
 *
 * Renders on the unified r3f engine (ADR-702) — same `<Scene>` as the
 * Force Graph explorer, but with two visual classes (documents as larger
 * boxed glyphs, concepts as smaller dots) and Document Explorer's own
 * palette + focus model. The engine handles physics, projection (2D/3D),
 * drag, hover/select, and labels; this plugin owns colors, scales,
 * geometry-per-class, focus-state, and the legend/info overlays.
 *
 * Workspace-only props (`focusedDocumentId`, `onFocusChange`,
 * `onViewDocument`, plus the deferred passage rings) preserve the
 * existing mount contract — DocumentExplorerWorkspace bypasses the
 * registry and constructs this component directly, so the plugin entry
 * point in `index.ts` is informational only.
 */

import React, { useCallback, useMemo, useRef, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import * as THREE from 'three';
import { RotateCcw } from 'lucide-react';
import type { ExplorerProps } from '../../types/explorer';
import type {
  DocumentExplorerSettings,
  DocumentExplorerData,
  DocNodeType,
  PassageQuery,
} from './types';
import { useThemeStore } from '../../store/themeStore';
import { StatsPanel, PanelStack } from '../common';
import { Scene } from '../ForceGraph/scene/Scene';
import { shapeGeometryByClass, type ShapeName } from '../ForceGraph/scene/shapes';
import { DIM_MODEL } from '../ForceGraph/scene/dimModel';
import type { EngineNode, EngineEdge } from '../ForceGraph/types';
import type { ForceSimHandle } from '../ForceGraph/scene/useForceSim';
import type { NodeInfoData } from '../ForceGraph/scene/NodeInfoOverlay';
import { ContextMenu, type ContextMenuItem } from '../../components/shared/ContextMenu';
import { FileText, Eye, EyeOff, Crosshair } from 'lucide-react';

// ---------------------------------------------------------------------------
// Visual constants
// ---------------------------------------------------------------------------

/** Fill colors per node type — same hues as the d3 implementation that
 *  preceded this port so saved screenshots and muscle memory carry over. */
const COLORS: Record<DocNodeType, string> = {
  'document':         '#f59e0b',
  'query-concept':    '#d97706',
  'extended-concept': '#6366f1',
};

// Document Explorer has *named* node types, so shape is a genuine second
// axis here (unlike Force Graph, where it currently mirrors ontology).
// A stable explicit map — NOT shapeFor()'s hash — so adding a future
// type can't silently re-bucket the existing three.
const TYPE_SHAPE: Record<DocNodeType, ShapeName> = {
  'document':         'dodecahedron',
  'query-concept':    'octahedron',
  'extended-concept': 'tetrahedron',
};

// ---------------------------------------------------------------------------
// Workspace-only props (passed by DocumentExplorerWorkspace, not by the
// generic ExplorerView mount path)
// ---------------------------------------------------------------------------

interface DocumentExplorerExtraProps {
  focusedDocumentId?: string | null;
  onFocusChange?: (docId: string | null) => void;
  onViewDocument?: (docId: string) => void;
  /** Passage search rings. Carried through for API stability; rendering
   *  is deferred to a follow-up after the engine port lands. */
  passageRings?: Map<string, Array<{ color: string; hitCount: number; maxHitCount: number; bestSimilarity: number }>>;
  /** Color → query text lookup. Carried through alongside `passageRings`. */
  queryColorLabels?: Map<string, string>;
  /** Active passage queries — carried through with `passageRings`. */
  passageQueries?: PassageQuery[];
}

/** Document Explorer entry — engine-backed multi-document concept graph.  @verified */
export const DocumentExplorer: React.FC<
  ExplorerProps<DocumentExplorerData, DocumentExplorerSettings> & DocumentExplorerExtraProps
> = ({
  data,
  settings,
  className,
  focusedDocumentId,
  onFocusChange,
  onViewDocument,
}) => {
  const { appliedTheme: theme } = useThemeStore();
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  // Spinner reflects an explicit Reheat — the engine sim is always
  // running (GPU/CPU), so a "settled" state isn't a real signal. Default
  // off; Reheat flips it on for a short window.
  const [physicsActive, setPhysicsActive] = useState(false);

  // Engine-style info cards: one per pinned concept, rendered in-scene
  // via the same `NodeInfoOverlay` Force Graph uses. Documents bypass
  // this — clicking a document opens the viewer instead.
  const [activeNodeInfos, setActiveNodeInfos] = useState<NodeInfoData[]>([]);

  // Sim handle bridges the inside-Canvas hook to the Reheat button outside
  // the Canvas tree.
  const simHandleRef = useRef<ForceSimHandle | null>(null);

  // ---------------------------------------------------------------------------
  // Engine data — transform DocumentExplorer shape → EngineNode[]/EngineEdge[]
  // ---------------------------------------------------------------------------

  const engineData = useMemo(() => {
    if (!data) return { nodes: [] as EngineNode[], edges: [] as EngineEdge[], edgeVisible: [] as boolean[] };

    // Pre-compute degree from visible edges so concept nodes scale subtly
    // by connectivity. Document nodes use a constant scale set below.
    const degree = new Map<string, number>();
    for (const link of data.links) {
      if (!link.visible) continue;
      degree.set(link.source, (degree.get(link.source) ?? 0) + 1);
      degree.set(link.target, (degree.get(link.target) ?? 0) + 1);
    }

    const nodes: EngineNode[] = data.nodes.map((n) => ({
      id: n.id,
      label: n.label,
      category: n.type,
      degree: degree.get(n.id) ?? 0,
    }));

    const nodeIds = new Set(nodes.map((n) => n.id));
    // All links land in the engine — both visible relationship edges
    // (concept↔concept) and invisible clustering hints (document→concept).
    // The engine sim uses the full set for force computation; rendering
    // checks `edgeVisible` and collapses invisible edges to a point.
    // Without this, concept dots drift away from their parent documents
    // (concepts of one doc rarely link directly to each other in data).
    const edges: EngineEdge[] = [];
    const edgeVisible: boolean[] = [];
    for (const l of data.links) {
      if (!nodeIds.has(l.source) || !nodeIds.has(l.target)) continue;
      edges.push({ from: l.source, to: l.target, type: l.type });
      edgeVisible.push(l.visible);
    }

    return { nodes, edges, edgeVisible };
  }, [data]);

  // Index nodes by id for fast lookups during click / NodeInfoBox prep.
  const nodesById = useMemo(() => {
    const map = new Map<string, EngineNode>();
    for (const n of engineData.nodes) map.set(n.id, n);
    return map;
  }, [engineData]);

  // Map id → DocGraphNode (the source row carries `type` and `documentIds`).
  const sourceById = useMemo(() => {
    const map = new Map<string, DocumentExplorerData['nodes'][number]>();
    for (const n of data?.nodes ?? []) map.set(n.id, n);
    return map;
  }, [data]);

  const nodeType = useCallback(
    (id: string): DocNodeType | null => sourceById.get(id)?.type ?? null,
    [sourceById],
  );

  // ---------------------------------------------------------------------------
  // Per-node visuals: colors, geometry classes, scales
  // ---------------------------------------------------------------------------

  const nodeClasses = useMemo(() => {
    return engineData.nodes.map((n) => {
      const type = nodeType(n.id) ?? 'extended-concept';
      return TYPE_SHAPE[type];
    });
  }, [engineData, nodeType]);

  // Platonic-solid glyph per node type (the shared engine partitions one
  // InstancedMesh per class). Documents → dodecahedron, query-concepts →
  // octahedron, extended-concepts → tetrahedron: shape now carries the
  // node-type axis, with the faceted/lit material doing the rest. Size
  // (documentSize) is still handled per-instance via nodeScales.
  const geometryByClass = useMemo(() => shapeGeometryByClass(), []);

  // ---------------------------------------------------------------------------
  // Dim state — hover and focus drive the same engine `activeIds` /
  // `dimAlpha` machinery the Force Graph uses. Focus is persistent
  // (right-click → "Focus on document") and dims more aggressively;
  // hover is transient and dims subtly. When both are active, focus
  // wins — same convention as Force Graph.
  // ---------------------------------------------------------------------------

  // Document Explorer overlays two graphs: concept↔concept relationship
  // edges (visible) and document↔concept membership (the invisible
  // clustering scaffold). A node's meaningful neighborhood reads BOTH,
  // via the typed structural fields rather than the edge list — the
  // visibility flag is a render concern and muddles membership. Edge-
  // list traversal alone fails at the extremes: a document's edges are
  // all invisible (visible-only → zero neighbors → whole graph dims),
  // and concept↔concept links are sparse by design.
  //
  // Asymmetric by type:
  //   - document → the document and all its concepts (a document *is*
  //     its concepts; this is the visual cluster made literal)
  //   - concept  → the concept, the documents it belongs to (one hop up
  //     the scaffold via `documentIds`), and any visible concept
  //     relationship neighbors
  //
  // Focus and hover light the SAME neighborhood; only the dim strength
  // differs (focus aggressive, hover subtle) — same convention as
  // Force Graph, where focus and hover also share the 1-hop set.
  const neighborhoodOf = useCallback((id: string): Set<string> => {
    const set = new Set<string>([id]);
    if (!data) return set;
    if (nodeType(id) === 'document') {
      const doc = data.documents.find((d) => d.id === id);
      if (doc) for (const cid of doc.conceptIds) set.add(cid);
      return set;
    }
    const src = sourceById.get(id);
    if (src) for (const did of src.documentIds) set.add(did);
    const { edges, edgeVisible } = engineData;
    for (let i = 0; i < edges.length; i++) {
      if (!edgeVisible[i]) continue;
      const e = edges[i];
      if (e.from === id) set.add(e.to);
      else if (e.to === id) set.add(e.from);
    }
    return set;
  }, [data, nodeType, sourceById, engineData]);

  // Only documents can be focused (via right-click → "Focus on
  // document"); concepts use hover for inspection.
  const focusActiveIds = useMemo<Set<string> | null>(() => {
    if (!focusedDocumentId || !data) return null;
    return neighborhoodOf(focusedDocumentId);
  }, [focusedDocumentId, data, neighborhoodOf]);

  const hoverActiveIds = useMemo<Set<string> | null>(() => {
    if (!hoveredId) return null;
    return neighborhoodOf(hoveredId);
  }, [hoveredId, neighborhoodOf]);

  const dimState = useMemo<{ activeIds: Set<string>; alpha: number } | undefined>(() => {
    if (focusActiveIds) return { activeIds: focusActiveIds, alpha: DIM_MODEL.focus };
    if (hoverActiveIds) return { activeIds: hoverActiveIds, alpha: DIM_MODEL.hover };
    return undefined;
  }, [focusActiveIds, hoverActiveIds]);

  // Engine `<Nodes>` doesn't read activeIds/dimAlpha directly (only
  // Edges/Labels do), so bake the dim into the per-node color array —
  // the document and concept meshes themselves recede along with the
  // edges. Same pattern Force Graph uses.
  //
  // Dim = fade toward THIS scene's background (see the dim note in
  // ForceGraph). The Doc Explorer Canvas is transparent over the
  // wrapper's bg-gray-900/50, so that wrapper colour IS the scene
  // background — fade toward it, not toward black. This is what makes
  // the indigo/amber palette recede by the same *perceived* amount as
  // Force Graph's lime palette under the shared DIM_MODEL value.
  const nodeColors = useMemo(() => {
    const tmp = new THREE.Color();
    const bg = new THREE.Color(theme === 'dark' ? '#111827' : '#f9fafb');
    return engineData.nodes.map((n) => {
      const type = nodeType(n.id) ?? 'extended-concept';
      const base = COLORS[type];
      if (!dimState || dimState.activeIds.has(n.id)) return base;
      tmp.set(base).lerp(bg, 1 - dimState.alpha);
      return `rgb(${Math.round(tmp.r * 255)},${Math.round(tmp.g * 255)},${Math.round(tmp.b * 255)})`;
    });
  }, [engineData, nodeType, dimState, theme]);

  // Labels render in a colour distinct from the node mesh so text isn't
  // masked by the disc next to it. White-ish reads against any node
  // colour (the engine paints a dark stroke under the text). Dim is
  // intentionally NOT baked here — the engine dims out-of-set labels via
  // opacity on its single activeIds path (same as Force Graph). Baking
  // the alpha in too would double-dim and is what made Document Explorer
  // read harsher than Force Graph on hover.
  const LABEL_COLOR = '#e5e7eb';
  const labelColors = useMemo(
    () => engineData.nodes.map(() => LABEL_COLOR),
    [engineData],
  );

  // Per-node base scale. Documents use a large constant (documentSize
  // setting is in pixel-space in the original; here it controls relative
  // scale — documents land at ~6-12x a concept dot). Concept scales follow
  // the engine's degree-based default; we replicate it explicitly so
  // documents/concepts use one consistent formula.
  const nodeScales = useMemo(() => {
    const out = new Float32Array(engineData.nodes.length);
    const docScale = (settings?.layout?.documentSize ?? 24) / 4; // pixel → world unit
    for (let i = 0; i < engineData.nodes.length; i++) {
      const n = engineData.nodes[i];
      const type = nodeType(n.id) ?? 'extended-concept';
      if (type === 'document') {
        out[i] = docScale;
      } else {
        // Concept dots — mirror the engine default so concepts read at
        // their natural size regardless of how documentSize is set.
        out[i] = 0.8 + Math.sqrt(n.degree || 1) * 0.3;
      }
    }
    return out;
  }, [engineData, settings?.layout?.documentSize, nodeType]);

  // ---------------------------------------------------------------------------
  // Interaction handlers — left-click is pure inspection (no graph
  // mutation, no focus toggle); right-click drives the context menu
  // where focus and graph-mutating actions live. Mirrors Force Graph.
  //
  // - Click on a document: opens the document viewer.
  // - Click on a concept: toggles its in-scene `NodeInfoOverlay`.
  // - Hover: dims non-neighbours (subtle, transient).
  // - Right-click: opens the context menu. Document menu offers
  //   View / Focus / Unfocus; concept menu offers Unfocus (when a
  //   document is focused) — graph mutations don't fit this explorer
  //   since the dataset is built from a saved query plus document
  //   hydration, not a generic exploration.
  // ---------------------------------------------------------------------------

  const handleSelect = useCallback((id: string | null) => {
    if (!id) return;
    const type = nodeType(id);
    if (type === 'document') {
      onViewDocument?.(id);
      return;
    }
    // Concept — toggle the in-scene info overlay.
    const node = nodesById.get(id);
    if (!node) return;
    setActiveNodeInfos((prev) => {
      if (prev.some((i) => i.nodeId === id)) {
        return prev.filter((i) => i.nodeId !== id);
      }
      return [
        ...prev,
        { nodeId: id, label: node.label, group: type ?? undefined, degree: node.degree },
      ];
    });
  }, [nodeType, nodesById, onViewDocument]);

  const handleDismissNodeInfo = useCallback(
    (nodeId: string) => setActiveNodeInfos((prev) => prev.filter((i) => i.nodeId !== nodeId)),
    [],
  );

  const handleHover = useCallback((id: string | null) => {
    if (settings?.interaction?.highlightOnHover === false) {
      setHoveredId(null);
      return;
    }
    setHoveredId(id);
  }, [settings?.interaction?.highlightOnHover]);

  // ---------------------------------------------------------------------------
  // Right-click context menu
  // ---------------------------------------------------------------------------

  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    nodeId: string | null;
    nodeLabel: string | null;
  } | null>(null);

  // Set when a node-mesh right-click consumes the event so the
  // background div's onContextMenu doesn't ALSO open a menu (mirrors
  // Force Graph's pattern).
  const nodeContextConsumedRef = useRef(false);

  const handleNodeContextMenu = useCallback(
    (id: string, event: PointerEvent) => {
      nodeContextConsumedRef.current = true;
      const label = nodesById.get(id)?.label ?? id;
      setContextMenu({ x: event.clientX, y: event.clientY, nodeId: id, nodeLabel: label });
    },
    [nodesById],
  );

  const handleBackgroundContextMenu = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      event.preventDefault();
      if (nodeContextConsumedRef.current) {
        nodeContextConsumedRef.current = false;
        return;
      }
      // Background menu — only useful when something is focused, to
      // offer Unfocus. Otherwise dismiss silently so right-click on
      // empty canvas doesn't surprise the user.
      if (!focusedDocumentId) return;
      setContextMenu({ x: event.clientX, y: event.clientY, nodeId: null, nodeLabel: null });
    },
    [focusedDocumentId],
  );

  const contextMenuItems = useMemo<ContextMenuItem[]>(() => {
    if (!contextMenu) return [];
    const items: ContextMenuItem[] = [];
    const type = contextMenu.nodeId ? nodeType(contextMenu.nodeId) : null;
    if (type === 'document') {
      items.push({
        label: 'View document',
        icon: FileText,
        onClick: () => onViewDocument?.(contextMenu.nodeId!),
      });
      if (focusedDocumentId === contextMenu.nodeId) {
        items.push({
          label: 'Unfocus',
          icon: EyeOff,
          onClick: () => onFocusChange?.(null),
        });
      } else {
        items.push({
          label: 'Focus on document',
          icon: Crosshair,
          onClick: () => onFocusChange?.(contextMenu.nodeId!),
        });
      }
    } else if (type === 'query-concept' || type === 'extended-concept') {
      // Concepts — the only menu entry that makes sense right now is
      // unfocus when something is focused. A "Focus on concept" item
      // would need a concept-level dim model we don't have yet.
      if (focusedDocumentId) {
        items.push({
          label: 'Unfocus',
          icon: EyeOff,
          onClick: () => onFocusChange?.(null),
        });
      }
    } else {
      // Background — only opens when something is focused (see
      // handleBackgroundContextMenu).
      items.push({
        label: 'Unfocus',
        icon: Eye,
        onClick: () => onFocusChange?.(null),
      });
    }
    return items;
  }, [contextMenu, nodeType, focusedDocumentId, onFocusChange, onViewDocument]);

  const handleReheat = useCallback(() => {
    simHandleRef.current?.reheat();
    // The engine doesn't yet expose a settle-end callback, so the spinner
    // is a fixed-duration visual hint rather than a real signal that the
    // layout has actually quieted. ~2.5s matches typical convergence in
    // practice on the engine's GPU sim; the rendering is correct
    // regardless of whether the spinner is on or off.
    setPhysicsActive(true);
    window.setTimeout(() => setPhysicsActive(false), 2500);
  }, []);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  const projection = settings?.projection ?? '3D';
  const bgClass = theme === 'dark' ? 'bg-gray-900' : 'bg-gray-50';

  return (
    <div
      className={`relative w-full h-full overflow-hidden ${bgClass} ${className || ''}`}
      onContextMenu={handleBackgroundContextMenu}
    >
      {/* Canvas keys on projection so the camera dispatch in Scene gets a
          fresh r3f tree (perspective vs orthographic can't be swapped
          mid-mount without state confusion). */}
      <Canvas
        key={projection}
        camera={
          projection === '2D'
            ? { position: [0, 0, 400], up: [0, 1, 0], near: 0.1, far: 5000 }
            : { position: [0, 0, 400], up: [0, 1, 0], near: 0.1, far: 5000, fov: 50 }
        }
        orthographic={projection === '2D'}
        frameloop="demand"
      >
        <Scene
          nodes={engineData.nodes}
          edges={engineData.edges}
          edgeVisible={engineData.edgeVisible}
          colors={nodeColors}
          labelColors={labelColors}
          nodeLabelOffsetY={-2.2}
          nodeClasses={nodeClasses}
          geometryByClass={geometryByClass}
          nodeScales={nodeScales}
          activeIds={dimState?.activeIds}
          dimAlpha={dimState?.alpha ?? 1}
          dimLabelOpacity={dimState?.alpha ?? 1}
          showArrows={false}
          showEdgeLabels={false}
          showNodeLabels={settings?.visual?.showNodeLabels !== false}
          edgeOpacity={settings?.visual?.showEdges === false ? 0 : 0.45}
          linkWidth={1}
          nodeSize={settings?.visual?.nodeSize ?? 1}
          lit={
            (settings?.visual?.lightingFollowsProjection ?? false)
              ? (settings?.projection ?? '3D') === '3D'
              : (settings?.visual?.lighting ?? 'flat') === 'lit'
          }
          orientPullback={0.45}
          enableDrag
          enableZoom={settings?.interaction?.enableZoom !== false}
          enablePan={settings?.interaction?.enablePan !== false}
          hoveredId={hoveredId}
          onSelect={handleSelect}
          onHover={handleHover}
          onContextMenu={handleNodeContextMenu}
          activeNodeInfos={activeNodeInfos}
          onDismissNodeInfo={handleDismissNodeInfo}
          simHandleRef={simHandleRef}
          projection={projection}
        />
      </Canvas>

      {/* Stats — top right */}
      <PanelStack side="right">
        <StatsPanel nodeCount={engineData.nodes.length} edgeCount={engineData.edges.length} />
      </PanelStack>

      {/* Reheat — top left */}
      <div className="absolute top-4 left-4">
        <button
          onClick={handleReheat}
          disabled={physicsActive}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium border transition-colors ${
            physicsActive
              ? 'bg-amber-500/15 border-amber-500/30 text-amber-500 cursor-default'
              : 'bg-card/90 border-border text-muted-foreground hover:text-foreground hover:bg-accent'
          }`}
          title={physicsActive ? 'Simulation running...' : 'Reheat layout'}
        >
          <RotateCcw className={`h-3.5 w-3.5 ${physicsActive ? 'animate-spin' : ''}`} />
          {physicsActive ? 'Settling...' : 'Reheat'}
        </button>
      </div>

      {/* Legend — bottom left */}
      <div className="absolute bottom-4 left-4 bg-card/90 backdrop-blur-sm border border-border rounded-lg p-3 text-xs space-y-1.5">
        <div className="flex items-center gap-2">
          <span className="inline-block w-3 h-3 rounded-full" style={{ background: COLORS.document }} />
          <span>Document</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: COLORS['query-concept'] }} />
          <span>Query concept</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-block w-2 h-2 rounded-full" style={{ background: COLORS['extended-concept'] }} />
          <span>Extended concept</span>
        </div>
      </div>

      {/* Right-click context menu */}
      {contextMenu && contextMenuItems.length > 0 && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          items={contextMenuItems}
          onClose={() => setContextMenu(null)}
        />
      )}
    </div>
  );
};
