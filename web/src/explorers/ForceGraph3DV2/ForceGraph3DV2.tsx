/**
 * ForceGraph3D V2 — Main Component
 *
 * Mounts the r3f Canvas and the scene composition (M1: instanced nodes +
 * indexed edges with seeded sphere positions, no physics yet). Consumes
 * the ExplorerPlugin contract from ADR-034; engine primitives come from
 * the scene/ subdirectory per ADR-702.
 *
 * Node palette: built per-dataset from the ontologies present
 * (createOntologyColorScale). Edge coloring at M1 is endpoint-gradient
 * through the same palette; M3 task #12 adds edge-type coloring.
 */

import React, { useCallback, useMemo, useRef, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import * as THREE from 'three';
import { Flame } from 'lucide-react';
import type { ExplorerProps } from '../../types/explorer';
import type { ForceGraph3DV2Data, ForceGraph3DV2Settings } from './types';
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


/** ForceGraph3D V2 — r3f Canvas + scene composition.  @verified c17bbeb9 */
export const ForceGraph3DV2: React.FC<
  ExplorerProps<ForceGraph3DV2Data, ForceGraph3DV2Settings>
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

  // Context menu + origin/destination / focus markers are the state backing
  // the shared right-click menu. These mirror V1's ForceGraph3D bookkeeping
  // so the same buildContextMenuItems helper produces an identical menu.
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    nodeId: string | null;
    nodeLabel: string | null;
  } | null>(null);
  const [originNodeId, setOriginNodeId] = useState<string | null>(null);
  const [destinationNodeId, setDestinationNodeId] = useState<string | null>(null);
  const [focusedNode, setFocusedNode] = useState<string | null>(null);
  // Open node info panels — one per selected node, dismissable. V1 tracks
  // the same state; our version lives in a flat array for stable keying.
  const [activeNodeInfos, setActiveNodeInfos] = useState<NodeInfoData[]>([]);

  const mergeRawGraphData = useGraphStore((s) => s.mergeRawGraphData);
  const visibleEdgeCategories = useGraphStore((s) => s.filters.visibleEdgeCategories);
  const appliedTheme = useThemeStore((s) => s.appliedTheme);
  const canvasBg = explorerTheme.canvas3D[appliedTheme];
  const {
    handleFollowConcept,
    handleAddToGraph,
    handleRemoveFromGraph,
    handleTravelPath,
    handleSendToPolarity,
    handleSendPathToReports,
  } = useGraphNavigation(mergeRawGraphData);

  // Left-click: select + open info panel. Note we do NOT fire onNodeClick
  // here — at the parent level (ExplorerView) onNodeClick is wired to
  // "Follow Concept" which reloads the graph. That action stays on the
  // right-click context menu (handleFollowConcept) so users can invoke it
  // deliberately rather than every time they want to inspect a node.
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
      setContextMenu({
        x: event.clientX,
        y: event.clientY,
        nodeId: id,
        nodeLabel: node?.label ?? id,
      });
    },
    [data]
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

  // kg-specific edge palette: relationship_type → vocabulary category →
  // hex via categoryColors.ts. Mirrors V1's edge-coloring behavior but
  // as an opaque function the engine treats generically.
  const vocabStore = useVocabularyStore();
  const edgePalette = useMemo(() => {
    if ((settings?.visual?.edgeColorBy ?? 'type') !== 'type') return undefined;
    return (edgeType: string): string => {
      const category = vocabStore.getCategory(edgeType);
      return getCategoryColor(category || undefined);
    };
  }, [vocabStore, settings?.visual?.edgeColorBy]);

  // Resolve an edge's category with the same 3-level fallback V1 uses in
  // transformForD3: vocabulary lookup → API-provided category → fallback.
  // Matching the chain keeps V1 and V2 producing the same category set for
  // the same edges, so the shared visibleEdgeCategories (populated once by
  // Legend based on whichever explorer rendered first) lines up.
  const edgeCategory = useCallback(
    (e: ForceGraph3DV2Data['edges'][number]): string => {
      let cat = vocabStore.getCategory(e.type);
      if (!cat) cat = e.source?.category;
      if (!cat || cat === 'default') cat = 'Uncategorized';
      return cat;
    },
    [vocabStore]
  );

  // Apply the edge-category filter from the shared store. Empty set means
  // "show all" — keep data untouched to skip allocations on the common path.
  const filteredData = useMemo(() => {
    if (!data || visibleEdgeCategories.size === 0) return data;
    const edges = data.edges.filter((e) => visibleEdgeCategories.has(edgeCategory(e)));
    return { ...data, edges };
  }, [data, visibleEdgeCategories, edgeCategory]);

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
  // "Focus on node") wins over hover and dims more aggressively. Mirrors
  // V1 2D's pattern (focus 0.05, hover 0.2). When neither is active the
  // set is undefined and engine renders at full opacity for everything.
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

  // Synthesize a V1-shape GraphData object for the shared Legend component.
  // Legend reads `nodes[*].{group,color}` and `links[*].{category,color}`;
  // our EngineNode/EngineEdge don't carry computed colors (they're applied
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
    const ls = engineEdges.map((e) => {
      const category = edgeCategory(e);
      return {
        from_id: e.from,
        to_id: e.to,
        source: e.from,
        target: e.to,
        type: e.type,
        relationship_type: e.type,
        category,
        color: edgePalette ? edgePalette(e.type) : getCategoryColor(category),
        value: 1,
      };
    });
    return { nodes: ns, links: ls } as unknown as GraphData;
  }, [filteredData, palette, edgePalette, edgeCategory]);

  // Build the context-menu item list using the shared helper — identical
  // structure to V1 so users get the same Follow / Add / Remove / Pin /
  // Focus / Origin / Destination / Report menu layout.
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
          // Camera travel and origin/destination ring markers are V1-3D-
          // specific features; V2 can pick them up in a follow-up commit
          // once we have an r3f camera-tween and overlay renderer.
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

  // Detect V1-shape leaking into the V2 component: V1 data has `links`,
  // V2 has `edges`. If `data.links` exists we know the ExplorerView's
  // per-plugin transformer path skipped V2's transformer.
  const shapeTag = useMemo(() => {
    if (!data) return 'null';
    const d = data as unknown as { edges?: unknown[]; links?: unknown[] };
    if (Array.isArray(d.edges)) return 'v2 (edges)';
    if (Array.isArray(d.links)) return 'v1 leaked (links)';
    return 'unknown';
  }, [data]);

  // Raw counts from the store — when these are non-zero but `data` counts
  // are zero, the V2 dataTransformer isn't running or is producing the
  // wrong shape. Select primitives individually (not a freshly-constructed
  // object) so zustand's shallow equality sees stable values.
  const rawNodeCount = useGraphStore((s) => s.rawGraphData?.nodes?.length ?? 0);
  const rawLinkCount = useGraphStore((s) => s.rawGraphData?.links?.length ?? 0);

  return (
    <div
      className={`relative w-full h-full ${className || ''}`}
      style={{ background: canvasBg }}
    >
      <Canvas
        camera={{ position: [0, 0, 400], fov: 60, near: 0.1, far: 5000 }}
        gl={{ antialias: true }}
        frameloop="demand"
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
      >
        <color attach="background" args={[canvasBg]} />
        <Scene
          nodes={filteredData?.nodes ?? []}
          edges={filteredData?.edges ?? []}
          colors={nodeColors}
          edgePalette={edgePalette}
          physics={{
            enabled: settings?.physics?.enabled ?? true,
            repulsion: settings?.physics?.repulsion,
            attraction: settings?.physics?.attraction,
            centerGravity: settings?.physics?.centerGravity,
            damping: settings?.physics?.damping,
          }}
          nodeSize={settings?.visual?.nodeSize ?? 1}
          edgeOpacity={0.7}
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
            <span className="font-medium text-sm text-foreground">ForceGraph3D V2</span>
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
