/**
 * ForceGraph3D — Main Component
 *
 * Mounts the r3f Canvas and the scene composition (instanced nodes +
 * indexed edges, GPU force sim). Consumes the ExplorerPlugin contract
 * from ADR-034; engine primitives come from the scene/ subdirectory
 * per ADR-702.
 *
 * Node palette: built per-dataset from the ontologies present
 * (createOntologyColorScale). Default edge coloring is by relationship
 * type; falls back to endpoint-gradient when the edge-type palette is
 * disabled.
 */

import React, { useCallback, useMemo, useRef, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import * as THREE from 'three';
import { Flame } from 'lucide-react';
import type { ExplorerProps } from '../../types/explorer';
import type { ForceGraph3DData, ForceGraph3DSettings } from './types';
import { Scene } from './scene/Scene';
import type { NodeInfoData } from './scene/NodeInfoOverlay';
import { simBackend } from './scene/useSim';
import type { ForceSimHandle } from './scene/useForceSim';
import { createOntologyColorScale } from '../../utils/colorScale';
import { useVocabularyStore } from '../../store/vocabularyStore';
import { useGraphStore } from '../../store/graphStore';
import { getCategoryColor } from '../../config/categoryColors';
import { ContextMenu, type ContextMenuItem } from '../../components/shared/ContextMenu';
import { buildContextMenuItems, useGraphNavigation, Legend, StatsPanel, PanelStack, explorerTheme, computeNodeColors } from '../common';
import { FileSpreadsheet } from 'lucide-react';
import type { GraphData } from '../../types/graph';
import { useThemeStore } from '../../store/themeStore';


/** ForceGraph3D — r3f Canvas + scene composition.  @verified c17bbeb9 */
export const ForceGraph3D: React.FC<
  ExplorerProps<ForceGraph3DData, ForceGraph3DSettings>
> = ({ data, settings, onSettingsChange, onNodeClick, onSendToReports, className }) => {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [hiddenIds] = useState<Set<string>>(() => new Set());
  const [pinnedIds, setPinnedIds] = useState<Set<string>>(() => new Set());
  // Sim handle bridges the inside-Canvas hook to the Reheat button outside
  // the Canvas tree. Simmer/Freeze were dropped — Reheat covers the common
  // case (kick the layout when the graph drifts off-screen).
  const simHandleRef = useRef<ForceSimHandle | null>(null);
  const handleReheat = useCallback(() => {
    simHandleRef.current?.reheat();
  }, []);

  // Background right-click dispatch: r3f mesh handlers fire first on the
  // bubble path, then the native contextmenu event reaches the wrapping
  // div. We need the wrapper to open a node-less menu only when the click
  // missed all nodes. The flag is set by the node handler and consumed by
  // the wrapper handler — guaranteed same-tick because both attach to the
  // one underlying DOM contextmenu event.
  const nodeContextMenuConsumedRef = useRef(false);

  // Context menu + origin/destination / focus markers feed the shared
  // buildContextMenuItems helper.
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    nodeId: string | null;
    nodeLabel: string | null;
  } | null>(null);
  const [originNodeId, setOriginNodeId] = useState<string | null>(null);
  const [destinationNodeId, setDestinationNodeId] = useState<string | null>(null);
  const [focusedNode, setFocusedNode] = useState<string | null>(null);
  // Open node info panels — one per selected node, dismissable.
  const [activeNodeInfos, setActiveNodeInfos] = useState<NodeInfoData[]>([]);

  const mergeRawGraphData = useGraphStore((s) => s.mergeRawGraphData);
  const visibleEdgeCategories = useGraphStore((s) => s.filters.visibleEdgeCategories);
  // Universal filters live in the store so every explorer sees the same
  // filtered data. Reading them via individual selectors keeps zustand's
  // shallow equality from re-rendering on unrelated store updates.
  const minConfidence = useGraphStore((s) => s.filters.minConfidence);
  const appliedTheme = useThemeStore((s) => s.appliedTheme);
  const canvasBg = explorerTheme.canvas3D[appliedTheme];
  const {
    handleFollowConcept,
    handleAddToGraph,
    handleRemoveFromGraph,
    handleTravelPath,
    handleSendToPolarity,
    handleSendPathToReports,
  } = useGraphNavigation();

  // Left-click selects the node and opens its info panel — pure inspection,
  // no graph mutation. Graph-mutating actions (Follow / Add Adjacent /
  // Remove) live on the right-click context menu so they're invoked
  // deliberately rather than every time the user inspects a node.
  const handleSelect = useCallback(
    (id: string | null) => {
      setSelectedId(id);
      if (id) {
        const node = data?.nodes?.find((n) => n.id === id);
        if (node) {
          setActiveNodeInfos((prev) => {
            if (prev.some((i) => i.nodeId === id)) return prev;
            return [
              ...prev,
              { nodeId: id, label: node.label, group: node.category, degree: node.degree },
            ];
          });
        }
      }
    },
    [data]
  );
  const handleDismissNodeInfo = useCallback(
    (nodeId: string) =>
      setActiveNodeInfos((prev) => prev.filter((i) => i.nodeId !== nodeId)),
    []
  );
  const handleHover = useCallback((id: string | null) => {
    setHoveredId(id);
  }, []);
  const handleContextMenu = useCallback(
    (id: string, event: PointerEvent) => {
      const node = data?.nodes?.find((n) => n.id === id);
      nodeContextMenuConsumedRef.current = true;
      setContextMenu({
        x: event.clientX,
        y: event.clientY,
        nodeId: id,
        nodeLabel: node?.label ?? id,
      });
    },
    [data]
  );
  // Background right-click: fired by the wrapper div after the mesh handler
  // has had a chance to consume the event. Opens the context menu with a
  // null node so the shared builder renders the background-only items
  // (Unpin All, etc.).
  const handleBackgroundContextMenu = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      event.preventDefault();
      if (nodeContextMenuConsumedRef.current) {
        nodeContextMenuConsumedRef.current = false;
        return;
      }
      setContextMenu({
        x: event.clientX,
        y: event.clientY,
        nodeId: null,
        nodeLabel: null,
      });
    },
    []
  );

  // Pin helpers wired through the shared context menu. Drag-to-pin already
  // mutates pinnedIds via useDragHandler, so these stay aligned with drag.
  const isPinned = useCallback((nodeId: string) => pinnedIds.has(nodeId), [pinnedIds]);
  const togglePinNode = useCallback(
    (nodeId: string) =>
      setPinnedIds((prev) => {
        const next = new Set(prev);
        if (next.has(nodeId)) next.delete(nodeId);
        else next.add(nodeId);
        return next;
      }),
    []
  );
  const unpinAllNodes = useCallback(() => setPinnedIds(new Set()), []);
  const palette = useMemo(() => {
    const ontologies = [...new Set(data?.nodes?.map((n) => n.category) ?? [])].sort();
    return createOntologyColorScale(ontologies);
  }, [data?.nodes]);
  const nodeColorBy = settings?.visual?.nodeColorBy ?? 'ontology';

  const vocabStore = useVocabularyStore();

  // Resolve an edge's category with a 3-level fallback (matches the chain
  // used by the 2D explorer's transformForD3): vocabulary lookup →
  // API-provided category → fallback. Keeping the chain in sync means the
  // shared visibleEdgeCategories store stays consistent across explorers.
  const edgeCategory = useCallback(
    (e: ForceGraph3DData['edges'][number]): string => {
      let cat = vocabStore.getCategory(e.type);
      if (!cat) cat = e.source?.category;
      if (!cat || cat === 'default') cat = 'Uncategorized';
      return cat;
    },
    [vocabStore]
  );

  // Apply shared-store filters. Both are universal — every explorer
  // reads from the same store fields, so a filter set in one place
  // applies everywhere. Empty / zero means "show all".
  const filteredData = useMemo(() => {
    if (!data) return data;
    const hasCatFilter = visibleEdgeCategories.size > 0;
    const hasConfFilter = minConfidence > 0;
    if (!hasCatFilter && !hasConfFilter) return data;
    const edges = data.edges.filter((e) => {
      if (hasCatFilter && !visibleEdgeCategories.has(edgeCategory(e))) return false;
      if (hasConfFilter && (e.weight ?? 1) < minConfidence) return false;
      return true;
    });
    return { ...data, edges };
  }, [data, visibleEdgeCategories, minConfidence, edgeCategory]);

  // Per-edge colors driven by edgeColorBy. Parallel to filteredData.edges
  // by index. Undefined means "use endpoint gradient" — the engine's
  // default. Centralising the mode dispatch here keeps Edges, Arrows, and
  // EdgeLabels uniform: they consume a string[] regardless of mode.
  const edgeColorBy = settings?.visual?.edgeColorBy ?? 'type';
  const edgeColors = useMemo<string[] | undefined>(() => {
    const es = filteredData?.edges;
    if (!es) return undefined;
    if (edgeColorBy === 'endpoint') return undefined;
    if (edgeColorBy === 'uniform') return es.map(() => '#888888');
    if (edgeColorBy === 'confidence') {
      return es.map((e) => {
        // weight ∈ [0,1] (set from API confidence). Hue 0=red, 120=green
        // matches the d3 2D explorer's scale so cross-view comparison reads.
        const w = typeof e.weight === 'number' ? e.weight : 0.5;
        const hue = Math.max(0, Math.min(1, w)) * 120;
        return `hsl(${hue}, 70%, 50%)`;
      });
    }
    // 'type' — relationship → vocabulary category → category color.
    return es.map((e) => {
      const category = vocabStore.getCategory(e.type);
      return getCategoryColor(category || undefined);
    });
  }, [filteredData, edgeColorBy, vocabStore]);

  const counts = useMemo(
    () => ({
      nodes: filteredData?.nodes?.length ?? 0,
      edges: filteredData?.edges?.length ?? 0,
    }),
    [filteredData]
  );

  // Per-node colors. Engine consumes this as a string[] indexed by node
  // position; Legend consumes the same map shape via legendData below.
  // Computed against the filtered set so degree/centrality reflect what's
  // currently visible — matches 2D's behavior except for centrality, which
  // 2D computes against the unfiltered graph (deferred convergence).
  const nodeColorMap = useMemo(() => {
    const ns = filteredData?.nodes ?? [];
    const es = filteredData?.edges ?? [];
    return computeNodeColors(
      ns.map((n) => ({ id: n.id, fallbackColor: palette(n.category) })),
      es.map((e) => ({ sourceId: e.from, targetId: e.to })),
      nodeColorBy,
    );
  }, [filteredData, palette, nodeColorBy]);

  const baseNodeColors = useMemo(() => {
    const ns = filteredData?.nodes ?? [];
    return ns.map((n) => nodeColorMap.get(n.id) ?? palette(n.category));
  }, [filteredData, nodeColorMap, palette]);

  // Direct neighbors of the currently-selected node, used for size-boosting
  // adjacent nodes when settings.interaction.highlightNeighbors is on.
  // Empty Set when disabled or nothing selected — Nodes.tsx skips the
  // boost when the set is empty so this is the cheapest no-op shape.
  const highlightedIds = useMemo(() => {
    if (!selectedId || !(settings?.interaction?.highlightNeighbors ?? true)) {
      return new Set<string>();
    }
    const neighbors = new Set<string>();
    for (const e of filteredData?.edges ?? []) {
      if (e.from === selectedId) neighbors.add(e.to);
      else if (e.to === selectedId) neighbors.add(e.from);
    }
    return neighbors;
  }, [selectedId, filteredData, settings?.interaction?.highlightNeighbors]);

  // Active set + dim alpha for hover/focus dimming. Focus (right-click
  // "Focus on node") wins over hover and dims more aggressively (0.05 vs.
  // 0.2). When neither is active the set is undefined and the engine
  // renders at full opacity for everything.
  const dimState = useMemo<{ activeIds: Set<string>; dimAlpha: number } | undefined>(() => {
    const driverId = focusedNode ?? hoveredId;
    if (!driverId) return undefined;
    const active = new Set<string>([driverId]);
    for (const e of filteredData?.edges ?? []) {
      if (e.from === driverId) active.add(e.to);
      else if (e.to === driverId) active.add(e.from);
    }
    return { activeIds: active, dimAlpha: focusedNode ? 0.05 : 0.2 };
  }, [focusedNode, hoveredId, filteredData]);

  // Bake the dim into the per-node color array so Nodes (and endpoint-
  // gradient Edges) automatically dim without engine-level changes. Edges/
  // Arrows in edge-type mode and the labels handle their own dimming via
  // the activeIds prop.
  const nodeColors = useMemo(() => {
    if (!dimState) return baseNodeColors;
    const tmp = new THREE.Color();
    return baseNodeColors.map((c, i) => {
      const id = filteredData?.nodes?.[i]?.id;
      if (id && dimState.activeIds.has(id)) return c;
      tmp.set(c).multiplyScalar(dimState.dimAlpha);
      return `#${tmp.getHexString()}`;
    });
  }, [baseNodeColors, dimState, filteredData]);

  // Synthesize the GraphData shape the shared Legend component expects.
  // Legend reads `nodes[*].{group,color}` and `links[*].{category,color}`;
  // EngineNode/EngineEdge don't carry computed colors (they're applied
  // in-shader), so we derive them here using the same palette functions
  // the scene uses. Cast is safe — Legend only touches these fields.
  const legendData = useMemo<GraphData>(() => {
    const engineNodes = filteredData?.nodes ?? [];
    const engineEdges = filteredData?.edges ?? [];
    const ns = engineNodes.map((n) => ({
      id: n.id,
      concept_id: n.id,
      label: n.label,
      ontology: n.category,
      group: n.category,
      color: palette(n.category),
      size: 10,
      search_terms: [],
    }));
    const ls = engineEdges.map((e, i) => {
      const category = edgeCategory(e);
      return {
        from_id: e.from,
        to_id: e.to,
        source: e.from,
        target: e.to,
        type: e.type,
        relationship_type: e.type,
        category,
        // Legend swatch follows the rendered edge colour when one is
        // computed, falling back to the category palette so endpoint
        // mode still produces a meaningful swatch.
        color: edgeColors?.[i] ?? getCategoryColor(category),
        value: 1,
      };
    });
    return { nodes: ns, links: ls } as unknown as GraphData;
  }, [filteredData, palette, edgeColors, edgeCategory]);

  // Build the context-menu item list using the shared helper — produces
  // the same Follow / Add / Remove / Pin / Focus / Origin / Destination /
  // Report menu the other explorers use.
  const contextMenuItems: ContextMenuItem[] = contextMenu
    ? buildContextMenuItems(
        contextMenu.nodeId && contextMenu.nodeLabel
          ? { nodeId: contextMenu.nodeId, nodeLabel: contextMenu.nodeLabel }
          : null,
        {
          handleFollowConcept,
          handleAddToGraph,
          handleRemoveFromGraph,
          setOriginNode: setOriginNodeId,
          setDestinationNode: setDestinationNodeId,
          setFocusedNode,
          focusedNodeId: focusedNode,
          isPinned,
          togglePinNode,
          unpinAllNodes,
          // Camera travel and origin/destination ring markers are tracked
          // as follow-up work — they need an r3f camera-tween hook and a
          // marker overlay primitive.
        },
        { onClose: () => setContextMenu(null) },
        originNodeId,
        destinationNodeId,
        {
          handleTravelPath,
          handleSendToPolarity,
          handleSendPathToReports,
          handleSendConceptToReports: onSendToReports,
        }
      )
    : [];

  // Diagnostic: the engine expects {nodes, edges}. If `data.links` shows
  // up the dataTransformer wasn't run and a foreign shape leaked through
  // — surfacing the mismatch on-canvas catches transformer-routing bugs
  // immediately rather than as silent zero-count renders.
  const shapeTag = useMemo(() => {
    if (!data) return 'null';
    const d = data as unknown as { edges?: unknown[]; links?: unknown[] };
    if (Array.isArray(d.edges)) return 'engine (edges)';
    if (Array.isArray(d.links)) return 'foreign-shape (links)';
    return 'unknown';
  }, [data]);

  // Raw counts from the store — non-zero raw counts with zero filtered
  // counts means the transformer isn't running or is producing the wrong
  // shape. Select primitives individually (not a freshly-constructed
  // object) so zustand's shallow equality sees stable values.
  const rawNodeCount = useGraphStore((s) => s.rawGraphData?.nodes?.length ?? 0);
  const rawLinkCount = useGraphStore((s) => s.rawGraphData?.links?.length ?? 0);

  return (
    <div
      className={`relative w-full h-full ${className || ''}`}
      style={{ background: canvasBg }}
      onContextMenu={handleBackgroundContextMenu}
    >
      <Canvas
        // Projection dispatch picks the camera flavor: perspective for 3D
        // (looking down -Z from z=400) and orthographic for 2D (frustum
        // computed from canvas aspect, zoom drives world-units-per-pixel).
        // `key` forces a Canvas remount on projection change so r3f
        // instantiates the right camera class — the `orthographic` prop
        // is read once at mount.
        key={settings?.projection ?? '3D'}
        camera={
          (settings?.projection ?? '3D') === '2D'
            ? { position: [0, 0, 400], near: 0.1, far: 5000, zoom: 2.5 }
            : { position: [0, 0, 400], fov: 60, near: 0.1, far: 5000 }
        }
        orthographic={(settings?.projection ?? '3D') === '2D'}
        gl={{ antialias: true }}
        frameloop="demand"
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
      >
        <color attach="background" args={[canvasBg]} />
        <Scene
          nodes={filteredData?.nodes ?? []}
          edges={filteredData?.edges ?? []}
          colors={nodeColors}
          edgeColors={edgeColors}
          physics={{
            enabled: settings?.physics?.enabled ?? true,
            repulsion: settings?.physics?.repulsion,
            attraction: settings?.physics?.attraction,
            centerGravity: settings?.physics?.centerGravity,
            damping: settings?.physics?.damping,
          }}
          projection={settings?.projection ?? '3D'}
          nodeSize={settings?.visual?.nodeSize ?? 1}
          edgeOpacity={0.7}
          linkWidth={settings?.visual?.linkWidth ?? 1}
          nodeLabelSize={settings?.visual?.nodeLabelSize ?? 1}
          edgeLabelSize={settings?.visual?.edgeLabelSize ?? 1}
          showArrows={settings?.visual?.showArrows ?? true}
          showEdgeLabels={settings?.visual?.showLabels ?? true}
          showNodeLabels={settings?.visual?.showNodeLabels ?? true}
          labelVisibilityRadius={settings?.visual?.labelVisibilityRadius ?? 250}
          selectedId={selectedId}
          hoveredId={hoveredId}
          hiddenIds={hiddenIds}
          pinnedIds={pinnedIds}
          highlightedIds={highlightedIds}
          activeIds={dimState?.activeIds}
          dimAlpha={dimState?.dimAlpha ?? 1}
          enableDrag={settings?.interaction?.enableDrag ?? true}
          enableZoom={settings?.interaction?.enableZoom ?? true}
          enablePan={settings?.interaction?.enablePan ?? true}
          onPinnedIdsChange={setPinnedIds}
          onSelect={handleSelect}
          onHover={handleHover}
          onContextMenu={handleContextMenu}
          activeNodeInfos={activeNodeInfos}
          onDismissNodeInfo={handleDismissNodeInfo}
          simHandleRef={simHandleRef}
        />
      </Canvas>

      <PanelStack side="left" gap={16} initialTop={16}>
        <div
          className="bg-card/95 border border-border rounded-lg shadow-xl p-3 text-xs text-card-foreground"
          style={{ width: '240px' }}
        >
          <div className="flex items-center gap-2 mb-2">
            <span className="font-medium text-sm text-foreground">ForceGraph3D</span>
            <span
              className={`text-[10px] uppercase font-mono px-1.5 py-0.5 rounded ${
                simBackend === 'gpu'
                  ? 'bg-emerald-900/40 text-emerald-300'
                  : 'bg-amber-900/40 text-amber-300'
              }`}
            >
              {simBackend}
            </span>
          </div>
          <div className="font-mono tabular-nums">
            {counts.nodes} nodes · {counts.edges} edges
          </div>
          <div className="text-[10px] text-muted-foreground font-mono mt-0.5">
            store raw: {rawNodeCount} nodes · {rawLinkCount} links
          </div>
          <div className="text-[10px] text-muted-foreground font-mono">
            shape: {shapeTag}
          </div>
          {(selectedId || hoveredId) && (
            <div className="text-[11px] text-muted-foreground mt-1 truncate">
              {selectedId ? 'selected: ' : 'hover: '}
              {data?.nodes?.find((n) => n.id === (selectedId || hoveredId))?.label ?? (selectedId || hoveredId)}
            </div>
          )}
          <button
            type="button"
            onClick={handleReheat}
            title="Reheat — restart the layout sim from full energy"
            className="mt-3 inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-border bg-muted/50 text-card-foreground text-xs hover:bg-muted hover:text-foreground transition-colors"
          >
            <Flame size={12} />
            <span>Reheat</span>
          </button>
        </div>
        <Legend
          data={legendData}
          nodeColorMode={nodeColorBy}
          visibilityControls={{
            showArrows: settings?.visual?.showArrows ?? true,
            showEdgeLabels: settings?.visual?.showLabels ?? true,
            showNodeLabels: settings?.visual?.showNodeLabels ?? true,
            onToggleArrows: (v) =>
              settings && onSettingsChange?.({ ...settings, visual: { ...settings.visual, showArrows: v } }),
            onToggleEdgeLabels: (v) =>
              settings && onSettingsChange?.({ ...settings, visual: { ...settings.visual, showLabels: v } }),
            onToggleNodeLabels: (v) =>
              settings && onSettingsChange?.({ ...settings, visual: { ...settings.visual, showNodeLabels: v } }),
          }}
        />
      </PanelStack>

      <PanelStack side="right" gap={16} initialTop={16}>
        <div className="flex items-center gap-2">
          <StatsPanel nodeCount={counts.nodes} edgeCount={counts.edges} />
          {onSendToReports && (
            <button
              onClick={onSendToReports}
              className="flex items-center gap-1.5 px-3 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 shadow-lg transition-colors text-sm font-medium"
              title="Send to Reports"
            >
              <FileSpreadsheet className="w-4 h-4" />
              <span>Reports</span>
            </button>
          )}
        </div>
      </PanelStack>

      {contextMenu && (
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
