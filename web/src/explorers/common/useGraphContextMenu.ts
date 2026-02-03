/**
 * Graph Context Menu Hook
 *
 * Provides common context menu functionality for both 2D and 3D explorers:
 * - Node context menu actions (follow, add, mark location)
 * - Canvas context menu actions (show/hide grid)
 * - Generic navigation and graph manipulation
 *
 * Explorer-specific actions (pin/unpin for 2D vs 3D) are passed as callbacks.
 */

import { useCallback } from 'react';
import { apiClient } from '../../api/client';
import { transformForD3 } from '../../utils/graphTransform';
import { stepToCypher } from '../../utils/cypherGenerator';
import { useGraphStore } from '../../store/graphStore';
import type { ContextMenuItem } from '../../components/shared/ContextMenu';
import {
  ArrowRight,
  Plus,
  MapPin,
  MapPinOff,
  Pin,
  PinOff,
  Circle,
  Grid3x3,
  Eye,
  EyeOff,
  Navigation,
  Target,
  Flag,
  FlagOff,
} from 'lucide-react';

export interface NodeContextMenuParams {
  nodeId: string;
  nodeLabel: string;
}

export interface GraphContextMenuHandlers {
  // Generic handlers (provided by hook)
  handleFollowConcept: (nodeId: string) => Promise<void>;
  handleAddToGraph: (nodeId: string) => Promise<void>;
  setOriginNode: (nodeId: string | null) => void;
  setDestinationNode: (nodeId: string | null) => void;
  travelToOrigin?: () => void;  // Optional navigation to origin node
  travelToDestination?: () => void;  // Optional navigation to destination node

  // Focus handlers
  setFocusedNode: (nodeId: string | null) => void;
  focusedNodeId: string | null;

  // Explorer-specific handlers (must be provided by explorer)
  isPinned: (nodeId: string) => boolean;
  togglePinNode: (nodeId: string) => void;
  unpinAllNodes: () => void;
  applyOriginMarker?: (nodeId: string) => void;  // Optional visual marker (e.g., gold ring)
  applyDestinationMarker?: (nodeId: string) => void;  // Optional visual marker (e.g., blue flag)
}

export interface GraphContextMenuCallbacks {
  onClose: () => void;
  onSettingsChange?: (settings: any) => void;
}

/**
 * Hook providing generic graph navigation actions
 */
export function useGraphNavigation(mergeGraphData: (newData: any) => any) {
  const { setGraphData, setRawGraphData, mergeRawGraphData, setFocusedNodeId } = useGraphStore();

  /** Follow concept — replace graph with this node's neighborhood and record the step */
  const handleFollowConcept = useCallback(async (nodeId: string) => {
    try {
      const store = useGraphStore.getState();
      const nodeLabel = store.rawGraphData?.nodes?.find(
        (n: any) => (n.concept_id || n.id) === nodeId
      )?.label || nodeId;

      store.addExplorationStep({
        action: 'follow',
        op: '+',
        cypher: stepToCypher({ action: 'follow', conceptLabel: nodeLabel, depth: 1 }),
        conceptId: nodeId,
        conceptLabel: nodeLabel,
        depth: 1,
      });

      const response = await apiClient.getSubgraph({
        center_concept_id: nodeId,
        depth: 1,
      });

      setGraphData(null);
      setRawGraphData({ nodes: response.nodes, links: response.links });
      setFocusedNodeId(nodeId);
    } catch (error: any) {
      console.error('Failed to follow concept:', error);
      alert(`Failed to follow concept: ${error.message || 'Unknown error'}`);
    }
  }, [setGraphData, setRawGraphData, setFocusedNodeId]);

  /** Add adjacent nodes — merge this node's neighbors into the graph and record the step */
  const handleAddToGraph = useCallback(async (nodeId: string) => {
    try {
      const store = useGraphStore.getState();
      const nodeLabel = store.rawGraphData?.nodes?.find(
        (n: any) => (n.concept_id || n.id) === nodeId
      )?.label || nodeId;

      store.addExplorationStep({
        action: 'add-adjacent',
        op: '+',
        cypher: stepToCypher({ action: 'add-adjacent', conceptLabel: nodeLabel, depth: 1 }),
        conceptId: nodeId,
        conceptLabel: nodeLabel,
        depth: 1,
      });

      const response = await apiClient.getSubgraph({
        center_concept_id: nodeId,
        depth: 1,
      });

      mergeRawGraphData({ nodes: response.nodes, links: response.links });
      setFocusedNodeId(nodeId);
    } catch (error: any) {
      console.error('Failed to add adjacent nodes:', error);
      alert(`Failed to add adjacent nodes: ${error.message || 'Unknown error'}`);
    }
  }, [mergeRawGraphData, setFocusedNodeId]);

  return { handleFollowConcept, handleAddToGraph };
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
  destinationNodeId: string | null
): ContextMenuItem[] {
  const {
    isPinned,
    togglePinNode,
    unpinAllNodes,
    applyOriginMarker,
    applyDestinationMarker,
    handleFollowConcept,
    handleAddToGraph,
    setOriginNode,
    setDestinationNode,
    travelToOrigin,
    travelToDestination,
    setFocusedNode,
    focusedNodeId,
  } = handlers;
  const { onClose } = callbacks;

  const items: ContextMenuItem[] = [];

  // Build Origin submenu - context-aware
  const originSubmenu: ContextMenuItem[] = [];

  if (nodeContext) {
    // Right-clicked on a node
    const { nodeId } = nodeContext;

    if (originNodeId === nodeId) {
      // This node IS the origin - show Clear
      originSubmenu.push({
        label: 'Clear Origin',
        icon: MapPinOff,
        onClick: () => {
          setOriginNode(null);
          onClose();
        },
      });
    } else {
      // This node is NOT the origin - show Set
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

      // Travel to origin if origin exists
      if (originNodeId && travelToOrigin) {
        originSubmenu.push({
          label: 'Travel to Origin',
          icon: Navigation,
          onClick: () => {
            travelToOrigin();
            onClose();
          },
        });
      }
    }
  } else {
    // Right-clicked on background
    if (originNodeId) {
      // Origin is set - show Clear and Travel
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
          label: 'Travel to Origin',
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
    // Right-clicked on a node
    const { nodeId } = nodeContext;

    if (destinationNodeId === nodeId) {
      // This node IS the destination - show Clear
      destinationSubmenu.push({
        label: 'Clear Destination',
        icon: FlagOff,
        onClick: () => {
          setDestinationNode(null);
          onClose();
        },
      });
    } else {
      // This node is NOT the destination - show Set
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

      // Travel to destination if destination exists
      if (destinationNodeId && travelToDestination) {
        destinationSubmenu.push({
          label: 'Travel to Destination',
          icon: Navigation,
          onClick: () => {
            travelToDestination();
            onClose();
          },
        });
      }
    }
  } else {
    // Right-clicked on background
    if (destinationNodeId) {
      // Destination is set - show Clear and Travel
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
          label: 'Travel to Destination',
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

  // Node-specific actions (only when right-clicking on a node)
  if (nodeContext) {
    const { nodeId, nodeLabel } = nodeContext;

    // Node submenu with pin operations
    items.push({
      label: 'Node',
      icon: Circle,
      submenu: [
        // Contextual pin/unpin node
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
