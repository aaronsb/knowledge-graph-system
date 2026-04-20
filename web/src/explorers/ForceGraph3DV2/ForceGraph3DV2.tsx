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

import React, { useCallback, useMemo, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import type { ExplorerProps } from '../../types/explorer';
import type { ForceGraph3DV2Data, ForceGraph3DV2Settings } from './types';
import { Scene } from './scene/Scene';
import type { NodeInfoData } from './scene/NodeInfoOverlay';
import { simBackend } from './scene/useSim';
import { createOntologyColorScale } from '../../utils/colorScale';
import { useVocabularyStore } from '../../store/vocabularyStore';
import { useGraphStore } from '../../store/graphStore';
import { getCategoryColor } from '../../config/categoryColors';
import { ContextMenu, type ContextMenuItem } from '../../components/shared/ContextMenu';
import { buildContextMenuItems, useGraphNavigation, Legend, StatsPanel, PanelStack, explorerTheme } from '../common';
import { FileSpreadsheet } from 'lucide-react';
import type { GraphData } from '../../types/graph';
import { useThemeStore } from '../../store/themeStore';

/** ForceGraph3D V2 — r3f Canvas + scene composition.  @verified c17bbeb9 */
export const ForceGraph3DV2: React.FC<
  ExplorerProps<ForceGraph3DV2Data, ForceGraph3DV2Settings>
> = ({ data, settings, onNodeClick, onSendToReports, className }) => {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [hiddenIds] = useState<Set<string>>(() => new Set());
  const [pinnedIds, setPinnedIds] = useState<Set<string>>(() => new Set());

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

  const handleSelect = useCallback(
    (id: string | null) => {
      setSelectedId(id);
      if (id) {
        onNodeClick?.(id);
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
    [onNodeClick, data]
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
          palette={palette}
          edgePalette={edgePalette}
          physics={{
            repulsion: settings?.physics?.repulsion,
            attraction: settings?.physics?.attraction,
            centerGravity: settings?.physics?.centerGravity,
            damping: settings?.physics?.damping,
          }}
          nodeSize={settings?.visual?.nodeSize ?? 1}
          edgeOpacity={0.7}
          showArrows={settings?.visual?.showArrows ?? true}
          showEdgeLabels={settings?.visual?.showLabels ?? true}
          labelVisibilityRadius={settings?.visual?.labelVisibilityRadius ?? 250}
          selectedId={selectedId}
          hoveredId={hoveredId}
          hiddenIds={hiddenIds}
          pinnedIds={pinnedIds}
          onPinnedIdsChange={setPinnedIds}
          onSelect={handleSelect}
          onHover={handleHover}
          onContextMenu={handleContextMenu}
          activeNodeInfos={activeNodeInfos}
          onDismissNodeInfo={handleDismissNodeInfo}
        />
      </Canvas>

      <div
        style={{
          position: 'absolute',
          top: 12,
          left: 12,
          padding: '8px 12px',
          background: 'rgba(10, 10, 15, 0.85)',
          border: '1px solid #26263a',
          borderRadius: 4,
          color: '#d7d7e0',
          fontFamily: 'SF Mono, Menlo, monospace',
          fontSize: 12,
          pointerEvents: 'none',
        }}
      >
        <div style={{ fontWeight: 600, marginBottom: 4 }}>
          ForceGraph3D V2{' '}
          <span
            style={{
              fontSize: 10,
              fontWeight: 400,
              padding: '1px 6px',
              marginLeft: 4,
              borderRadius: 3,
              background: simBackend === 'gpu' ? '#2a4d3a' : '#4d3a2a',
              color: simBackend === 'gpu' ? '#7aff9a' : '#ffb37a',
              textTransform: 'uppercase',
            }}
          >
            {simBackend}
          </span>
        </div>
        <div>
          {counts.nodes} nodes · {counts.edges} edges
        </div>
        <div style={{ opacity: 0.5, fontSize: 10, marginTop: 2 }}>
          store raw: {rawNodeCount} nodes · {rawLinkCount} links
        </div>
        <div style={{ opacity: 0.5, fontSize: 10, marginTop: 1 }}>
          shape: {shapeTag}
        </div>
        {(selectedId || hoveredId) && (
          <div style={{ opacity: 0.6, marginTop: 4, maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {selectedId ? 'selected: ' : 'hover: '}
            {data?.nodes?.find((n) => n.id === (selectedId || hoveredId))?.label ?? (selectedId || hoveredId)}
          </div>
        )}
      </div>

      <PanelStack side="left" gap={16} initialTop={16}>
        <Legend data={legendData} nodeColorMode="ontology" />
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
