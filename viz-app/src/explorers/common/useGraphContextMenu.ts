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
  EyeOff,
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

  // Explorer-specific handlers (must be provided by explorer)
  isPinned: (nodeId: string) => boolean;
  togglePinNode: (nodeId: string) => void;
  unpinAllNodes: () => void;
  applyOriginMarker?: (nodeId: string) => void;  // Optional visual marker (e.g., gold ring)
}

export interface GraphContextMenuCallbacks {
  onClose: () => void;
  onSettingsChange?: (settings: any) => void;
}

/**
 * Hook providing generic graph navigation actions
 */
export function useGraphNavigation(mergeGraphData: (newData: any) => any) {
  const { setGraphData, setFocusedNodeId } = useGraphStore();

  // Handler: Follow concept (replace graph)
  const handleFollowConcept = useCallback(async (nodeId: string) => {
    try {
      const response = await apiClient.getSubgraph({
        center_concept_id: nodeId,
        depth: 1, // Load immediate neighbors
      });

      const transformedData = transformForD3(response.nodes, response.links);
      setGraphData(transformedData);
      setFocusedNodeId(nodeId);
    } catch (error: any) {
      console.error('Failed to follow concept:', error);
      alert(`Failed to follow concept: ${error.message || 'Unknown error'}`);
    }
  }, [setGraphData, setFocusedNodeId]);

  // Handler: Add concept to graph (merge)
  const handleAddToGraph = useCallback(async (nodeId: string) => {
    try {
      const response = await apiClient.getSubgraph({
        center_concept_id: nodeId,
        depth: 1, // Load immediate neighbors
      });

      const transformedData = transformForD3(response.nodes, response.links);
      setGraphData(mergeGraphData(transformedData));
      setFocusedNodeId(nodeId);
    } catch (error: any) {
      console.error('Failed to add concept to graph:', error);
      alert(`Failed to add concept to graph: ${error.message || 'Unknown error'}`);
    }
  }, [mergeGraphData, setGraphData, setFocusedNodeId]);

  return { handleFollowConcept, handleAddToGraph };
}

/**
 * Build node context menu items
 */
export function buildNodeContextMenuItems(
  nodeContext: NodeContextMenuParams,
  handlers: GraphContextMenuHandlers,
  callbacks: GraphContextMenuCallbacks,
  originNodeId: string | null
): ContextMenuItem[] {
  const { nodeId, nodeLabel } = nodeContext;
  const { isPinned, togglePinNode, unpinAllNodes, applyOriginMarker, handleFollowConcept, handleAddToGraph, setOriginNode } = handlers;
  const { onClose } = callbacks;

  return [
    // Contextual mark/unmark location
    originNodeId === nodeId
      ? {
          label: 'Unmark Location',
          icon: MapPinOff,
          onClick: () => {
            setOriginNode(null);
            onClose();
          },
        }
      : {
          label: 'Mark Location',
          icon: MapPin,
          onClick: () => {
            setOriginNode(nodeId);
            if (applyOriginMarker) {
              applyOriginMarker(nodeId);
            }
            onClose();
          },
        },
    // Node submenu with pin operations
    {
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
    },
    {
      label: `Follow "${nodeLabel}"`,
      icon: ArrowRight,
      onClick: () => {
        handleFollowConcept(nodeId);
        onClose();
      },
    },
    {
      label: `Add "${nodeLabel}" to Graph`,
      icon: Plus,
      onClick: () => {
        handleAddToGraph(nodeId);
        onClose();
      },
    },
  ];
}

/**
 * Build canvas context menu items
 */
export function buildCanvasContextMenuItems(
  settings: { visual: { showGrid: boolean } },
  callbacks: GraphContextMenuCallbacks
): ContextMenuItem[] {
  const { onClose, onSettingsChange } = callbacks;

  if (!onSettingsChange) return [];

  return [
    settings.visual.showGrid
      ? {
          label: 'Hide Grid',
          icon: EyeOff,
          onClick: () => {
            onSettingsChange({
              ...settings,
              visual: { ...settings.visual, showGrid: false },
            });
            onClose();
          },
        }
      : {
          label: 'Show Grid',
          icon: Grid3x3,
          onClick: () => {
            onSettingsChange({
              ...settings,
              visual: { ...settings.visual, showGrid: true },
            });
            onClose();
          },
        },
  ];
}
