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
import type { EngineNode, EngineEdge } from '../ForceGraph/types';
import type { ForceSimHandle } from '../ForceGraph/scene/useForceSim';
import type { NodeInfoData } from '../ForceGraph/scene/NodeInfoOverlay';

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

const NODE_CLASS_BY_TYPE: Record<DocNodeType, 'document' | 'concept'> = {
  'document':         'document',
  'query-concept':    'concept',
  'extended-concept': 'concept',
};

const DOUBLE_CLICK_MS = 300;

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
    if (!data) return { nodes: [] as EngineNode[], edges: [] as EngineEdge[] };

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
      return NODE_CLASS_BY_TYPE[type];
    });
  }, [engineData, nodeType]);

  // Both documents and concepts render as the same icosahedron geometry —
  // the d3 implementation drew documents as larger circles too (with a
  // small white file-glyph overlay; that overlay is the only detail
  // dropped on the engine port). Size + color do the visual distinction.
  // `geometryByClass` is wired so this stays single-source if we want to
  // re-add a glyph (textured plane / instanced sprite) on documents later.
  const geometryByClass = useMemo(() => ({
    document: <icosahedronGeometry args={[1, 2]} />,
    concept: <icosahedronGeometry args={[1, 1]} />,
  }), []);

  // ---------------------------------------------------------------------------
  // Focus mode → activeIds (drives the engine's dim and the per-node
  // color dim baked below)
  // ---------------------------------------------------------------------------

  const focusedConceptSet = useMemo(() => {
    if (!focusedDocumentId || !data) return null;
    const doc = data.documents.find((d) => d.id === focusedDocumentId);
    if (!doc) return null;
    return new Set(doc.conceptIds);
  }, [focusedDocumentId, data]);

  // When set, items not in this set render at FOCUS_DIM_ALPHA on the
  // engine's edges/labels and via the baked color dim on the nodes.
  // Nothing focused → undefined, full opacity for everything.
  const activeIds = useMemo(() => {
    if (!focusedDocumentId || !focusedConceptSet) return undefined;
    const set = new Set<string>(focusedConceptSet);
    set.add(focusedDocumentId);
    return set;
  }, [focusedDocumentId, focusedConceptSet]);

  // Engine `<Nodes>` doesn't read activeIds/dimAlpha (only Edges/Labels
  // do), so bake the dim into the color array — that's how the document
  // and concept meshes themselves visually recede when a different doc
  // is focused.
  const FOCUS_DIM_ALPHA = 0.08;
  const nodeColors = useMemo(() => {
    const tmp = new THREE.Color();
    const hasFocus = !!activeIds && activeIds.size > 0;
    return engineData.nodes.map((n) => {
      const type = nodeType(n.id) ?? 'extended-concept';
      const base = COLORS[type];
      if (!hasFocus || activeIds!.has(n.id)) return base;
      tmp.set(base).multiplyScalar(FOCUS_DIM_ALPHA);
      return `rgb(${Math.round(tmp.r * 255)},${Math.round(tmp.g * 255)},${Math.round(tmp.b * 255)})`;
    });
  }, [engineData, nodeType, activeIds]);

  // Labels render in a colour distinct from the node mesh so text isn't
  // masked by the disc it sits next to. White-ish reads against any node
  // colour (the engine's label canvas paints a dark stroke underneath
  // for legibility on light themes). Focus dim is baked in here too.
  const LABEL_COLOR = '#e5e7eb';
  const labelColors = useMemo(() => {
    const tmp = new THREE.Color();
    const hasFocus = !!activeIds && activeIds.size > 0;
    return engineData.nodes.map((n) => {
      if (!hasFocus || activeIds!.has(n.id)) return LABEL_COLOR;
      tmp.set(LABEL_COLOR).multiplyScalar(FOCUS_DIM_ALPHA);
      return `rgb(${Math.round(tmp.r * 255)},${Math.round(tmp.g * 255)},${Math.round(tmp.b * 255)})`;
    });
  }, [engineData, activeIds]);

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
  // Interaction handlers — bridge engine onSelect to DocumentExplorer's
  // focus / view-document model.
  //
  // - Click on a document: opens the document viewer AND focuses (dims
  //   non-focused). Clicking the focused document again clears focus and
  //   the open viewer is left in place — closing the viewer is its own
  //   dismiss control.
  // - Click on a concept: pins an in-scene `NodeInfoOverlay` (the same
  //   info card Force Graph uses). Click the same concept again to
  //   dismiss it.
  // ---------------------------------------------------------------------------

  const handleSelect = useCallback((id: string | null) => {
    if (!id) return;
    const type = nodeType(id);
    if (type === 'document') {
      onViewDocument?.(id);
      onFocusChange?.(focusedDocumentId === id ? null : id);
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
  }, [focusedDocumentId, nodeType, nodesById, onFocusChange, onViewDocument]);

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
          activeIds={activeIds}
          dimAlpha={FOCUS_DIM_ALPHA}
          showArrows={false}
          showEdgeLabels={false}
          showNodeLabels={settings?.visual?.showLabels !== false}
          edgeOpacity={settings?.visual?.showEdges === false ? 0 : 0.45}
          linkWidth={1}
          nodeSize={settings?.visual?.nodeSize ?? 1}
          enableDrag
          enableZoom={settings?.interaction?.enableZoom !== false}
          enablePan={settings?.interaction?.enablePan !== false}
          hoveredId={hoveredId}
          onSelect={handleSelect}
          onHover={handleHover}
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

    </div>
  );
};
