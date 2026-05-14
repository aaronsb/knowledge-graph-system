/**
 * Graph Context Menu Hook
 *
 * Provides common context menu functionality for both 2D and 3D explorers:
 * - Node context menu actions (follow, add, mark location)
 * - Canvas context menu actions (travel path, send to polarity)
 * - Generic navigation and graph manipulation
 *
 * Explorer-specific actions (pin/unpin for 2D vs 3D) are passed as callbacks.
 */

import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { extractGraphFromPath } from '../../utils/cypherResultMapper';
import type { RawGraphNode, PathResult } from '../../utils/cypherResultMapper';
import { useGraphStore } from '../../store/graphStore';
import { useReportStore, type TraversalReportData } from '../../store/reportStore';
import { useExplorationActions } from '../../hooks/useExplorationActions';
import type { ContextMenuItem } from '../../components/shared/ContextMenu';
import {
  ArrowRight,
  Plus,
  Minus,
  MapPin,
  MapPinOff,
  Pin,
  PinOff,
  Circle,
  Eye,
  EyeOff,
  Navigation,
  Target,
  Flag,
  FlagOff,
  GitBranch,
  Route,
  FileSpreadsheet,
} from 'lucide-react';

/** Identifies the node a context menu was opened on.  @verified 7b5be48d */
export interface NodeContextMenuParams {
  nodeId: string;
  nodeLabel: string;
}

/** Callbacks wired into the context menu — generic actions plus explorer-specific ones.  @verified 7b5be48d */
export interface GraphContextMenuHandlers {
  // Generic handlers (provided by hook)
  handleFollowConcept: (nodeId: string) => Promise<void>;
  /**
   * Merge the node's neighborhood into the graph at the given depth.
   * Depth selector (1/2/3) is exposed as a submenu in the context menu;
   * omitting the argument falls back to the hub's default depth.
   */
  handleAddToGraph: (nodeId: string, depth?: 1 | 2 | 3) => Promise<void>;
  handleRemoveFromGraph: (nodeId: string) => void;
  setOriginNode: (nodeId: string | null) => void;
  setDestinationNode: (nodeId: string | null) => void;
  travelToOrigin?: () => void;
  travelToDestination?: () => void;

  // Path travel — explorer-provided camera animation through ordered node list
  travelAlongPath?: (nodeIds: string[], reverse?: boolean) => void;

  // Focus handlers
  setFocusedNode: (nodeId: string | null) => void;
  focusedNodeId: string | null;

  // Explorer-specific handlers (must be provided by explorer)
  isPinned: (nodeId: string) => boolean;
  togglePinNode: (nodeId: string) => void;
  unpinAllNodes: () => void;
  applyOriginMarker?: (nodeId: string) => void;
  applyDestinationMarker?: (nodeId: string) => void;
}

/** Lifecycle callbacks from the context menu overlay back to the explorer.  @verified 7b5be48d */
export interface GraphContextMenuCallbacks {
  onClose: () => void;
  onSettingsChange?: (settings: any) => void;
}

/**
 * Hook providing generic graph navigation actions.
 *
 * Follow / add-adjacent / remove / travel-path delegate to
 * `useExplorationActions` — the single writer for graph-mutating
 * operations. The wrappers here add UX concerns layered on top (an
 * `alert` dialog on failure) and preserve the historic return shape so
 * existing call sites in 2D / 3D-V1 / 3D-V2 don't need to change.
 *
 * Send-to-polarity and send-path-to-reports stay here because they're
 * pure navigation / report creation, not graph-mutating.
 *
 * @verified 80d68539
 */
export function useGraphNavigation() {
  const navigate = useNavigate();
  const actions = useExplorationActions();

  /** Follow concept — delegates to the action hub, with an alert on failure. */
  const handleFollowConcept = useCallback(
    async (nodeId: string) => {
      try {
        await actions.followConcept(nodeId);
      } catch (error: unknown) {
        alert(`Failed to follow concept: ${error instanceof Error ? error.message : 'Unknown error'}`);
      }
    },
    [actions]
  );

  /** Add adjacent — delegates to the action hub, with an alert on failure.
   *  Optional `depth` (1/2/3) drives the depth selector exposed by the
   *  shared context menu; undefined uses the hub's default depth. */
  const handleAddToGraph = useCallback(
    async (nodeId: string, depth?: 1 | 2 | 3) => {
      try {
        await actions.addAdjacent(nodeId, depth ? { depth } : undefined);
      } catch (error: unknown) {
        alert(`Failed to add adjacent nodes: ${error instanceof Error ? error.message : 'Unknown error'}`);
      }
    },
    [actions]
  );

  /** Remove node — delegates to the action hub. */
  const handleRemoveFromGraph = useCallback(
    (nodeId: string) => {
      actions.removeNode(nodeId);
    },
    [actions]
  );

  /**
   * Find path between origin/destination, route the graph mutation +
   * step recording through the hub, then animate the camera through
   * the path nodes.
   *
   * The path fetch lives here (not in the hub) because the camera
   * animation needs the path object. Once we have it, the actual graph
   * write goes through `actions.loadPath` so the single-writer invariant
   * holds and replay through the autosave reproduces the same state.
   * Enrichment is disabled — travel is a "show me this path" action,
   * not "explore around the path".
   */
  const handleTravelPath = useCallback(async (
    originId: string,
    destinationId: string,
    travelAlongPath: (nodeIds: string[], reverse?: boolean) => void,
    reverse: boolean
  ) => {
    try {
      const store = useGraphStore.getState();
      const rawNodes = store.rawGraphData?.nodes || [];
      const originLabel = rawNodes.find(
        (n: RawGraphNode) => n.concept_id === originId
      )?.label || originId;
      const destLabel = rawNodes.find(
        (n: RawGraphNode) => n.concept_id === destinationId
      )?.label || destinationId;

      const result = await apiClient.findConnection({
        from_id: originId,
        to_id: destinationId,
        max_hops: 5,
      });

      if (!result.paths?.length) {
        console.warn('No path found between origin and destination');
        return;
      }
      const path = result.paths[0];

      await actions.loadPath({
        fromId: originId,
        fromLabel: originLabel,
        toId: destinationId,
        toLabel: destLabel,
        path,
        depth: 1,
        maxHops: 5,
        loadMode: 'add',
        enrich: false,
      });

      // Camera animation runs after the graph re-renders with the new
      // path nodes — two RAFs match the previous behavior's timing.
      const { conceptNodeIds } = extractGraphFromPath(path);
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          travelAlongPath(conceptNodeIds, reverse);
        });
      });
    } catch (error: unknown) {
      console.error('Failed to travel path:', error);
    }
  }, [actions]);

  /** Set polarity poles from origin/destination and navigate to polarity explorer */
  const handleSendToPolarity = useCallback((originId: string, destinationId: string) => {
    const store = useGraphStore.getState();
    const rawNodes = store.rawGraphData?.nodes || [];

    const originNode = rawNodes.find((n: RawGraphNode) => n.concept_id === originId);
    const destNode = rawNodes.find((n: RawGraphNode) => n.concept_id === destinationId);

    if (!originNode || !destNode) return;

    store.setPolarityState({
      selectedPositivePole: {
        concept_id: originId,
        label: originNode.label,
      },
      selectedNegativePole: {
        concept_id: destinationId,
        label: destNode.label,
      },
      pendingAnalysis: true,
    });

    navigate('/polarity');
  }, [navigate]);

  /** Find path between origin/destination and create a traversal report */
  const handleSendPathToReports = useCallback(async (originId: string, destinationId: string) => {
    try {
      const store = useGraphStore.getState();
      const rawNodes = store.rawGraphData?.nodes || [];

      const originNode = rawNodes.find((n: RawGraphNode) => n.concept_id === originId);
      const destNode = rawNodes.find((n: RawGraphNode) => n.concept_id === destinationId);

      if (!originNode || !destNode) return;

      const result = await apiClient.findConnection({
        from_id: originId,
        to_id: destinationId,
        max_hops: 5,
      });

      const reportData: TraversalReportData = {
        type: 'traversal',
        origin: { concept_id: originId, label: originNode.label },
        destination: { concept_id: destinationId, label: destNode.label },
        maxHops: 5,
        pathCount: result.count || result.paths?.length || 0,
        paths: (result.paths || []).map((p: PathResult) => {
          const nodes = (p.nodes || [])
            .filter((n) => n.id && n.id !== '')
            .map((n) => ({
              id: n.id,
              label: n.label,
              description: n.description,
              grounding_strength: n.grounding_strength,
              confidence_level: n.confidence_level,
              diversity_score: n.diversity_score,
            }));
          return {
            hops: p.hops || nodes.length - 1,
            nodes,
            relationships: p.relationships || [],
          };
        }),
      };

      const { addReport } = useReportStore.getState();
      await addReport({
        type: 'traversal',
        data: reportData,
        name: '',
        sourceExplorer: 'traversal',
      });

      navigate('/report');
    } catch (error: unknown) {
      console.error('Failed to create traversal report:', error);
    }
  }, [navigate]);

  return {
    handleFollowConcept,
    handleAddToGraph,
    handleRemoveFromGraph,
    handleTravelPath,
    handleSendToPolarity,
    handleSendPathToReports,
  };
}

/**
 * Build unified context menu items (handles both node clicks and background clicks)
 * @param nodeContext - Node data if right-clicked on a node, null if right-clicked on background
 */
export function buildContextMenuItems(
  nodeContext: NodeContextMenuParams | null,
  handlers: GraphContextMenuHandlers,
  callbacks: GraphContextMenuCallbacks,
  originNodeId: string | null,
  destinationNodeId: string | null,
  extraHandlers?: {
    handleTravelPath?: (
      originId: string,
      destinationId: string,
      travelAlongPath: (nodeIds: string[], reverse?: boolean) => void,
      reverse: boolean
    ) => Promise<void>;
    handleSendToPolarity?: (originId: string, destinationId: string) => void;
    handleSendPathToReports?: (originId: string, destinationId: string) => Promise<void>;
    handleSendConceptToReports?: () => void;
  }
): ContextMenuItem[] {
  const {
    isPinned,
    togglePinNode,
    unpinAllNodes,
    applyOriginMarker,
    applyDestinationMarker,
    handleFollowConcept,
    handleAddToGraph,
    handleRemoveFromGraph,
    setOriginNode,
    setDestinationNode,
    travelToOrigin,
    travelToDestination,
    travelAlongPath,
    setFocusedNode,
    focusedNodeId,
  } = handlers;
  const { onClose } = callbacks;

  const items: ContextMenuItem[] = [];

  // Build Origin submenu - context-aware
  const originSubmenu: ContextMenuItem[] = [];

  if (nodeContext) {
    const { nodeId } = nodeContext;

    if (originNodeId === nodeId) {
      originSubmenu.push({
        label: 'Clear Origin',
        icon: MapPinOff,
        onClick: () => {
          setOriginNode(null);
          onClose();
        },
      });
    } else {
      originSubmenu.push({
        label: 'Set Origin',
        icon: MapPin,
        onClick: () => {
          setOriginNode(nodeId);
          if (applyOriginMarker) {
            applyOriginMarker(nodeId);
          }
          onClose();
        },
      });

      if (originNodeId && travelToOrigin) {
        originSubmenu.push({
          label: 'Go to Origin',
          icon: Navigation,
          onClick: () => {
            travelToOrigin();
            onClose();
          },
        });
      }
    }
  } else {
    if (originNodeId) {
      originSubmenu.push({
        label: 'Clear Origin',
        icon: MapPinOff,
        onClick: () => {
          setOriginNode(null);
          onClose();
        },
      });

      if (travelToOrigin) {
        originSubmenu.push({
          label: 'Go to Origin',
          icon: Navigation,
          onClick: () => {
            travelToOrigin();
            onClose();
          },
        });
      }
    }
  }

  // Build Destination submenu - context-aware
  const destinationSubmenu: ContextMenuItem[] = [];

  if (nodeContext) {
    const { nodeId } = nodeContext;

    if (destinationNodeId === nodeId) {
      destinationSubmenu.push({
        label: 'Clear Destination',
        icon: FlagOff,
        onClick: () => {
          setDestinationNode(null);
          onClose();
        },
      });
    } else {
      destinationSubmenu.push({
        label: 'Set Destination',
        icon: Flag,
        onClick: () => {
          setDestinationNode(nodeId);
          if (applyDestinationMarker) {
            applyDestinationMarker(nodeId);
          }
          onClose();
        },
      });

      if (destinationNodeId && travelToDestination) {
        destinationSubmenu.push({
          label: 'Go to Destination',
          icon: Navigation,
          onClick: () => {
            travelToDestination();
            onClose();
          },
        });
      }
    }
  } else {
    if (destinationNodeId) {
      destinationSubmenu.push({
        label: 'Clear Destination',
        icon: FlagOff,
        onClick: () => {
          setDestinationNode(null);
          onClose();
        },
      });

      if (travelToDestination) {
        destinationSubmenu.push({
          label: 'Go to Destination',
          icon: Navigation,
          onClick: () => {
            travelToDestination();
            onClose();
          },
        });
      }
    }
  }

  // Add Origin submenu if it has items
  if (originSubmenu.length > 0) {
    items.push({
      label: 'Origin',
      icon: Target,
      submenu: originSubmenu,
    });
  }

  // Add Destination submenu if it has items
  if (destinationSubmenu.length > 0) {
    items.push({
      label: 'Destination',
      icon: Flag,
      submenu: destinationSubmenu,
    });
  }

  // Travel submenu — find path between origin and destination, animate camera through nodes
  if (originNodeId && destinationNodeId && travelAlongPath && extraHandlers?.handleTravelPath) {
    const { handleTravelPath } = extraHandlers;
    items.push({
      label: 'Travel',
      icon: Route,
      submenu: [
        {
          label: 'From Origin',
          icon: MapPin,
          onClick: () => {
            onClose();
            handleTravelPath(originNodeId, destinationNodeId, travelAlongPath, false);
          },
        },
        {
          label: 'From Destination',
          icon: Flag,
          onClick: () => {
            onClose();
            handleTravelPath(originNodeId, destinationNodeId, travelAlongPath, true);
          },
        },
      ],
    });
  }

  // Report submenu — groups all report/analysis export actions
  {
    const reportSubmenu: ContextMenuItem[] = [];

    // Polarity Explorer (requires origin + destination)
    if (originNodeId && destinationNodeId && extraHandlers?.handleSendToPolarity) {
      const { handleSendToPolarity } = extraHandlers;
      reportSubmenu.push({
        label: 'Polarity Axis',
        icon: GitBranch,
        onClick: () => {
          onClose();
          handleSendToPolarity(originNodeId, destinationNodeId);
        },
      });
    }

    // Path Report (requires origin + destination)
    if (originNodeId && destinationNodeId && extraHandlers?.handleSendPathToReports) {
      const { handleSendPathToReports } = extraHandlers;
      reportSubmenu.push({
        label: 'Path Report',
        icon: Route,
        onClick: () => {
          onClose();
          handleSendPathToReports(originNodeId, destinationNodeId);
        },
      });
    }

    // Concept Report (requires a node context — graph must have nodes)
    if (nodeContext && extraHandlers?.handleSendConceptToReports) {
      const { handleSendConceptToReports } = extraHandlers;
      reportSubmenu.push({
        label: 'Concept Report',
        icon: FileSpreadsheet,
        onClick: () => {
          onClose();
          handleSendConceptToReports();
        },
      });
    }

    if (reportSubmenu.length > 0) {
      items.push({
        label: 'Report',
        icon: FileSpreadsheet,
        submenu: reportSubmenu,
      });
    }
  }

  // Node-specific actions (only when right-clicking on a node)
  if (nodeContext) {
    const { nodeId, nodeLabel } = nodeContext;

    // Node submenu with pin operations
    items.push({
      label: 'Node',
      icon: Circle,
      submenu: [
        isPinned(nodeId)
          ? {
              label: 'Unpin Node',
              icon: PinOff,
              onClick: () => {
                togglePinNode(nodeId);
                onClose();
              },
            }
          : {
              label: 'Pin Node',
              icon: Pin,
              onClick: () => {
                togglePinNode(nodeId);
                onClose();
              },
            },
        {
          label: 'Unpin All',
          icon: PinOff,
          onClick: () => {
            unpinAllNodes();
            onClose();
          },
        },
      ],
    });

    // Follow and Add actions
    items.push({
      label: `Follow "${nodeLabel}"`,
      icon: ArrowRight,
      onClick: () => {
        handleFollowConcept(nodeId);
        onClose();
      },
    });

    // Add Adjacent — submenu with depth selector. Depth 1 is the
    // immediate neighborhood; 2 and 3 expand further at proportionally
    // higher fetch cost, capped at 3 (the API enforces this server-side
    // and the depth-2/3 fetches are noticeably slower on dense graphs).
    items.push({
      label: 'Add Adjacent Nodes',
      icon: Plus,
      submenu: ([1, 2, 3] as const).map((d) => ({
        label: `Depth ${d}${d === 1 ? ' (direct neighbors)' : ''}`,
        icon: Plus,
        onClick: () => {
          handleAddToGraph(nodeId, d);
          onClose();
        },
      })),
    });

    items.push({
      label: `Remove from Graph`,
      icon: Minus,
      onClick: () => {
        handleRemoveFromGraph(nodeId);
        onClose();
      },
    });

    // Focus on Node (only if not already focused)
    if (focusedNodeId !== nodeId) {
      items.push({
        label: 'Focus on Node',
        icon: Eye,
        onClick: () => {
          setFocusedNode(nodeId);
          onClose();
        },
      });
    }
  }

  // Defocus (global - works on any right-click if focus is active)
  if (focusedNodeId !== null) {
    items.push({
      label: 'Defocus',
      icon: EyeOff,
      onClick: () => {
        setFocusedNode(null);
        onClose();
      },
    });
  }

  return items;
}
