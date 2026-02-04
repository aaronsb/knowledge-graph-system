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
import { stepToCypher } from '../../utils/cypherGenerator';
import { extractGraphFromPath } from '../../utils/cypherResultMapper';
import type { RawGraphNode, RawGraphData, PathResult } from '../../utils/cypherResultMapper';
import { useGraphStore } from '../../store/graphStore';
import { useReportStore, type TraversalReportData } from '../../store/reportStore';
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

export interface NodeContextMenuParams {
  nodeId: string;
  nodeLabel: string;
}

export interface GraphContextMenuHandlers {
  // Generic handlers (provided by hook)
  handleFollowConcept: (nodeId: string) => Promise<void>;
  handleAddToGraph: (nodeId: string) => Promise<void>;
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

export interface GraphContextMenuCallbacks {
  onClose: () => void;
  onSettingsChange?: (settings: any) => void;
}

/**
 * Hook providing generic graph navigation actions
 */
export function useGraphNavigation(mergeGraphData: (newData: RawGraphData) => void) {
  const { setGraphData, setRawGraphData, mergeRawGraphData, setFocusedNodeId } = useGraphStore();
  const navigate = useNavigate();

  /** Follow concept — replace graph with this node's neighborhood and record the step */
  const handleFollowConcept = useCallback(async (nodeId: string) => {
    try {
      const store = useGraphStore.getState();
      const nodeLabel = store.rawGraphData?.nodes?.find(
        (n: RawGraphNode) => n.concept_id === nodeId
      )?.label || nodeId;

      const response = await apiClient.getSubgraph({
        center_concept_id: nodeId,
        depth: 1,
      });

      store.addExplorationStep({
        action: 'follow',
        op: '+',
        cypher: stepToCypher({ action: 'follow', conceptLabel: nodeLabel, depth: 1 }),
        conceptId: nodeId,
        conceptLabel: nodeLabel,
        depth: 1,
      });

      setGraphData(null);
      setRawGraphData({ nodes: response.nodes, links: response.links });
      setFocusedNodeId(nodeId);
    } catch (error: unknown) {
      console.error('Failed to follow concept:', error);
      alert(`Failed to follow concept: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }, [setGraphData, setRawGraphData, setFocusedNodeId]);

  /** Add adjacent nodes — merge this node's neighbors into the graph and record the step */
  const handleAddToGraph = useCallback(async (nodeId: string) => {
    try {
      const store = useGraphStore.getState();
      const nodeLabel = store.rawGraphData?.nodes?.find(
        (n: RawGraphNode) => n.concept_id === nodeId
      )?.label || nodeId;

      const response = await apiClient.getSubgraph({
        center_concept_id: nodeId,
        depth: 1,
      });

      store.addExplorationStep({
        action: 'add-adjacent',
        op: '+',
        cypher: stepToCypher({ action: 'add-adjacent', conceptLabel: nodeLabel, depth: 1 }),
        conceptId: nodeId,
        conceptLabel: nodeLabel,
        depth: 1,
      });

      mergeRawGraphData({ nodes: response.nodes, links: response.links });
      setFocusedNodeId(nodeId);
    } catch (error: unknown) {
      console.error('Failed to add adjacent nodes:', error);
      alert(`Failed to add adjacent nodes: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }, [mergeRawGraphData, setFocusedNodeId]);

  /** Remove node and its connections from the graph, recording a subtractive step */
  const handleRemoveFromGraph = useCallback((nodeId: string) => {
    const store = useGraphStore.getState();
    const node = store.rawGraphData?.nodes?.find(
      (n: RawGraphNode) => n.concept_id === nodeId
    );
    const nodeLabel = node?.label || nodeId;

    store.addExplorationStep({
      action: 'cypher',
      op: '-',
      cypher: `MATCH (c:Concept)-[r]-(n:Concept)\nWHERE c.label = '${nodeLabel}'\nRETURN c, r, n`,
      conceptId: nodeId,
      conceptLabel: nodeLabel,
      depth: 1,
    });

    store.subtractRawGraphData({
      nodes: [{ id: nodeId, concept_id: nodeId }],
      links: [],
    });
  }, []);

  /** Find path between origin/destination, merge into graph, then animate camera */
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

      const { nodes, links, conceptNodeIds } = extractGraphFromPath(result.paths[0]);

      // Record exploration step
      store.addExplorationStep({
        action: 'load-path',
        op: '+',
        cypher: stepToCypher({
          action: 'load-path',
          conceptLabel: originLabel,
          depth: 1,
          destinationConceptLabel: destLabel,
          maxHops: 5,
        }),
        conceptId: originId,
        conceptLabel: originLabel,
        depth: 1,
        destinationConceptId: destinationId,
        destinationConceptLabel: destLabel,
        maxHops: 5,
      });

      // Merge path into graph
      mergeRawGraphData({ nodes, links });

      // Wait for graph to re-render with new nodes, then animate
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          travelAlongPath(conceptNodeIds, reverse);
        });
      });
    } catch (error: unknown) {
      console.error('Failed to travel path:', error);
    }
  }, [mergeRawGraphData]);

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

  // Send to Polarity Explorer — use origin/destination as poles
  if (originNodeId && destinationNodeId && extraHandlers?.handleSendToPolarity) {
    const { handleSendToPolarity } = extraHandlers;
    items.push({
      label: 'Send to Polarity Explorer',
      icon: GitBranch,
      onClick: () => {
        onClose();
        handleSendToPolarity(originNodeId, destinationNodeId);
      },
    });
  }

  // Send Path to Reports — create traversal report from origin/destination
  if (originNodeId && destinationNodeId && extraHandlers?.handleSendPathToReports) {
    const { handleSendPathToReports } = extraHandlers;
    items.push({
      label: 'Send Path to Reports',
      icon: FileSpreadsheet,
      onClick: () => {
        onClose();
        handleSendPathToReports(originNodeId, destinationNodeId);
      },
    });
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

    items.push({
      label: `Add Adjacent Nodes`,
      icon: Plus,
      onClick: () => {
        handleAddToGraph(nodeId);
        onClose();
      },
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
