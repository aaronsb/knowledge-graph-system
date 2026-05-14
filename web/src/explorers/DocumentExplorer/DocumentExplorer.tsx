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
import { RotateCcw } from 'lucide-react';
import type { ExplorerProps } from '../../types/explorer';
import type {
  DocumentExplorerSettings,
  DocumentExplorerData,
  DocNodeType,
  PassageQuery,
} from './types';
import { useThemeStore } from '../../store/themeStore';
import { NodeInfoBox, StatsPanel, PanelStack } from '../common';
import { Scene } from '../ForceGraph/scene/Scene';
import type { EngineNode, EngineEdge } from '../ForceGraph/types';
import type { ForceSimHandle } from '../ForceGraph/scene/useForceSim';

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
  const [selectedConceptId, setSelectedConceptId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [physicsActive, setPhysicsActive] = useState(true);

  // Sim handle bridges the inside-Canvas hook to the Reheat button outside
  // the Canvas tree.
  const simHandleRef = useRef<ForceSimHandle | null>(null);

  // Last-click bookkeeping for manual dblclick detection. The engine's
  // pointer handler fires once per pointer-up; double-click semantics are
  // local concern (we use it to open the document viewer on documents).
  const lastClickRef = useRef<{ id: string; at: number } | null>(null);

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
    // Only visible edges land in the engine. Document→concept clustering
    // hints from the d3 implementation are dropped on first cut — the
    // engine's center gravity + concept-to-concept links produce a
    // workable layout. If clustering proves loose in practice, the engine
    // can grow per-edge visibility (render-skip while sim still uses them).
    const edges: EngineEdge[] = data.links
      .filter((l) => l.visible && nodeIds.has(l.source) && nodeIds.has(l.target))
      .map((l) => ({
        from: l.source,
        to: l.target,
        type: l.type,
      }));

    return { nodes, edges };
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

  const geometryByClass = useMemo(() => ({
    document: <boxGeometry args={[1, 1, 1]} />,
    concept: <icosahedronGeometry args={[1, 1]} />,
  }), []);

  const nodeColors = useMemo(() => {
    return engineData.nodes.map((n) => {
      const type = nodeType(n.id) ?? 'extended-concept';
      return COLORS[type];
    });
  }, [engineData, nodeType]);

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
  // Focus mode → engine highlight + dim
  // ---------------------------------------------------------------------------

  const focusedConceptSet = useMemo(() => {
    if (!focusedDocumentId || !data) return null;
    const doc = data.documents.find((d) => d.id === focusedDocumentId);
    if (!doc) return null;
    return new Set(doc.conceptIds);
  }, [focusedDocumentId, data]);

  // activeIds drives the engine's dim — when set, items not in the set
  // render at `dimAlpha`. Focus on a document narrows to the document
  // plus its concept set; nothing focused leaves the whole graph active.
  const activeIds = useMemo(() => {
    if (!focusedDocumentId || !focusedConceptSet) return undefined;
    const set = new Set<string>(focusedConceptSet);
    set.add(focusedDocumentId);
    return set;
  }, [focusedDocumentId, focusedConceptSet]);

  // ---------------------------------------------------------------------------
  // Interaction handlers — bridge engine onSelect to DocumentExplorer's
  // focus / view-document model. Single-click on a document focuses it;
  // double-click opens the viewer. Single-click on a concept shows the
  // NodeInfoBox; clicking the same concept again dismisses it (engine's
  // toggle behavior is preserved).
  // ---------------------------------------------------------------------------

  const handleSelect = useCallback((id: string | null) => {
    if (!id) {
      setSelectedConceptId(null);
      return;
    }
    const type = nodeType(id);

    // Manual dblclick detection — engine fires onSelect once per click.
    const now = performance.now();
    const isDouble = lastClickRef.current?.id === id
      && (now - lastClickRef.current.at) < DOUBLE_CLICK_MS;
    lastClickRef.current = { id, at: now };

    if (type === 'document') {
      if (isDouble) {
        onViewDocument?.(id);
        return;
      }
      // Single-click on a document toggles focus.
      if (focusedDocumentId === id) {
        onFocusChange?.(null);
      } else {
        onFocusChange?.(id);
      }
      setSelectedConceptId(null);
      return;
    }

    // Concept click — toggle the NodeInfoBox selection.
    setSelectedConceptId((prev) => (prev === id ? null : id));
  }, [focusedDocumentId, nodeType, onFocusChange, onViewDocument]);

  const handleHover = useCallback((id: string | null) => {
    if (settings?.interaction?.highlightOnHover === false) {
      setHoveredId(null);
      return;
    }
    setHoveredId(id);
  }, [settings?.interaction?.highlightOnHover]);

  const handleReheat = useCallback(() => {
    simHandleRef.current?.reheat();
    setPhysicsActive(true);
    // Engine's reheat doesn't drive a settled callback yet; reflect the
    // active state for a short window so the spinner UX matches the d3
    // version. The engine settles much faster than the old d3 sim so a
    // brief indicator is more honest than waiting for a real-end event.
    window.setTimeout(() => setPhysicsActive(false), 2500);
  }, []);

  // ---------------------------------------------------------------------------
  // Selected concept → NodeInfoBox data
  // ---------------------------------------------------------------------------

  const selectedNodeData = useMemo(() => {
    if (!selectedConceptId) return null;
    const src = sourceById.get(selectedConceptId);
    const eng = nodesById.get(selectedConceptId);
    if (!src || !eng) return null;
    const degree = engineData.edges.filter(
      (e) => e.from === selectedConceptId || e.to === selectedConceptId,
    ).length;
    return {
      id: selectedConceptId,
      label: src.label || 'Unknown',
      type: src.type,
      degree,
    };
  }, [selectedConceptId, sourceById, nodesById, engineData]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  const projection = settings?.projection ?? '3D';
  const bgClass = theme === 'dark' ? 'bg-gray-900' : 'bg-gray-50';

  return (
    <div
      className={`relative w-full h-full overflow-hidden ${bgClass} ${className || ''}`}
      onContextMenu={(e) => e.preventDefault()}
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
          colors={nodeColors}
          nodeClasses={nodeClasses}
          geometryByClass={geometryByClass}
          nodeScales={nodeScales}
          activeIds={activeIds}
          dimAlpha={0.08}
          showArrows={false}
          showEdgeLabels={false}
          showNodeLabels={settings?.visual?.showLabels !== false}
          edgeOpacity={settings?.visual?.showEdges === false ? 0 : 0.45}
          linkWidth={1}
          nodeSize={settings?.visual?.nodeSize ?? 1}
          enableDrag
          enableZoom={settings?.interaction?.enableZoom !== false}
          enablePan={settings?.interaction?.enablePan !== false}
          selectedId={selectedConceptId}
          hoveredId={hoveredId}
          onSelect={handleSelect}
          onHover={handleHover}
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
          <span className="inline-block w-3 h-3 rounded-sm" style={{ background: COLORS.document }} />
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

      {/* NodeInfoBox for selected concept */}
      {selectedNodeData && selectedNodeData.type !== 'document' && (
        <NodeInfoBox
          info={{
            nodeId: selectedNodeData.id,
            label: selectedNodeData.label,
            group: selectedNodeData.type === 'query-concept' ? 'query match' : 'document extended',
            degree: selectedNodeData.degree,
            x: 16,
            y: 16,
          }}
          onDismiss={() => setSelectedConceptId(null)}
        />
      )}
    </div>
  );
};
