/**
 * Force-Directed 3D Graph Explorer - Main Component
 *
 * Interactive 3D force-directed graph visualization using react-force-graph-3d.
 * Follows ADR-034 Explorer Plugin Interface.
 */

import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import ForceGraph3DLib from 'react-force-graph-3d';
import * as THREE from 'three';
import { ArrowRight, Plus } from 'lucide-react';
import type { ExplorerProps } from '../../types/explorer';
import type { ForceGraph3DSettings, ForceGraph3DData } from './types';
import { getNeighbors } from '../../utils/graphTransform';
import { useGraphStore } from '../../store/graphStore';
import { useVocabularyStore } from '../../store/vocabularyStore';
import { getCategoryColor } from '../../config/categoryColors';
import { ContextMenu, type ContextMenuItem } from '../../components/shared/ContextMenu';
import { Legend } from './Legend';
import { CanvasSettingsPanel } from './CanvasSettingsPanel';
import { NodeInfoBox, EdgeInfoBox, StatsPanel } from '../common';

export const ForceGraph3D: React.FC<
  ExplorerProps<ForceGraph3DData, ForceGraph3DSettings>
> = ({ data, settings, onSettingsChange, onNodeClick, className }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<any>();
  const [dimensions, setDimensions] = useState({ width: 1200, height: 800 });
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  // Context menu state
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    nodeId: string;
    nodeLabel: string;
  } | null>(null);

  // Track active node info boxes
  interface NodeInfo {
    nodeId: string;
    label: string;
    group: string;
    degree: number;
    x: number;
    y: number;
  }
  const [activeNodeInfos, setActiveNodeInfos] = useState<NodeInfo[]>([]);

  // Track active edge info boxes
  interface EdgeInfo {
    linkKey: string;
    sourceId: string;
    targetId: string;
    type: string;
    confidence: number;
    category?: string;
    x: number;
    y: number;
  }
  const [activeEdgeInfos, setActiveEdgeInfos] = useState<EdgeInfo[]>([]);

  // Get navigation state from store
  const { originNodeId, setOriginNodeId, setFocusedNodeId, setGraphData, graphData } = useGraphStore();

  // Calculate node colors (match 2D implementation)
  const nodeColors = useMemo(() => {
    const colors = new Map<string, string>();

    if (settings.visual.nodeColorBy === 'ontology') {
      // Use pre-computed colors from transformForD3
      data.nodes.forEach(node => {
        colors.set(node.id, node.color);
      });
    } else if (settings.visual.nodeColorBy === 'degree') {
      // Color by degree (number of connections)
      const degrees = new Map<string, number>();
      data.links.forEach(link => {
        const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
        const targetId = typeof link.target === 'string' ? link.target : link.target.id;
        degrees.set(sourceId, (degrees.get(sourceId) || 0) + 1);
        degrees.set(targetId, (degrees.get(targetId) || 0) + 1);
      });

      const maxDegree = Math.max(...Array.from(degrees.values()), 1);
      data.nodes.forEach(node => {
        const degree = degrees.get(node.id) || 0;
        const normalized = degree / maxDegree;
        const hue = 220 + normalized * 120; // Blue to green
        colors.set(node.id, `hsl(${hue}, 70%, 50%)`);
      });
    } else if (settings.visual.nodeColorBy === 'centrality') {
      // Color by centrality
      data.nodes.forEach(node => {
        const centrality = node.centrality || 0;
        const hue = centrality * 180;
        colors.set(node.id, `hsl(${hue}, 70%, 50%)`);
      });
    }

    return colors;
  }, [data.nodes, data.links, settings.visual.nodeColorBy]);

  // Calculate link colors
  const linkColors = useMemo(() => {
    const colors = new Map<string, string>();

    data.links.forEach((link) => {
      const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
      const targetId = typeof link.target === 'string' ? link.target : link.target.id;
      const linkKey = `${sourceId}->${targetId}-${link.type}`;

      let color = '#999';

      switch (settings.visual.edgeColorBy) {
        case 'category':
          const vocabStore = useVocabularyStore.getState();
          const category = vocabStore.getCategory(link.type) || 'default';
          color = getCategoryColor(category);
          break;
        case 'confidence':
          const confidence = link.confidence || 0.5;
          color = `hsl(${confidence * 120}, 70%, 50%)`;
          break;
        case 'uniform':
          color = '#666';
          break;
      }

      colors.set(linkKey, color);
    });

    return colors;
  }, [data.links, settings.visual.edgeColorBy]);

  // Calculate neighbors for highlighting
  const neighbors = useMemo(() => {
    if (!hoveredNode || !settings.interaction.highlightNeighbors) return new Set<string>();
    return getNeighbors(hoveredNode, data.links);
  }, [hoveredNode, data.links, settings.interaction.highlightNeighbors]);

  // Handle window resize
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    };

    // Initial size
    updateDimensions();

    // Update on resize
    window.addEventListener('resize', updateDimensions);

    // Also update after a short delay to ensure container is rendered
    const timer = setTimeout(updateDimensions, 100);

    return () => {
      window.removeEventListener('resize', updateDimensions);
      clearTimeout(timer);
    };
  }, []);

  // Configure D3 forces when settings change
  useEffect(() => {
    if (!fgRef.current) return;

    const fg = fgRef.current;

    // Immediate force update (no delay on subsequent changes)
    try {
      const chargeForce = fg.d3Force('charge');
      const linkForce = fg.d3Force('link');
      const centerForce = fg.d3Force('center');

      // Configure forces if they exist
      if (chargeForce) {
        chargeForce.strength(settings.physics?.charge ?? -300);
      }
      if (linkForce) {
        linkForce.distance(settings.physics?.linkDistance ?? 80);
      }
      if (centerForce) {
        centerForce.strength(settings.physics?.gravity ?? 0.1);
      }

      // Reheat simulation to keep it active while adjusting sliders
      // This mimics the behavior of clicking and dragging a node
      if (fg.d3ReheatSimulation) {
        fg.d3ReheatSimulation();
      }
    } catch (e) {
      // Silently ignore - simulation might not be ready yet on first render
    }
  }, [settings.physics?.charge, settings.physics?.linkDistance, settings.physics?.gravity]);

  // Add grid helper when enabled
  useEffect(() => {
    if (!fgRef.current || !settings.visual.showGrid) return;

    const scene = fgRef.current.scene();

    // Create grid helper - pure geometry
    const grid = new THREE.GridHelper(
      2000,      // Size
      100,       // Divisions
      0x444444,  // Center line color
      0x222222   // Grid line color
    );

    grid.position.y = -200;  // Position below graph
    grid.name = 'ground-grid';
    scene.add(grid);

    return () => {
      const existingGrid = scene.getObjectByName('ground-grid');
      if (existingGrid) scene.remove(existingGrid);
    };
  }, [settings.visual.showGrid]);

  // Project 3D world coordinates to 2D screen coordinates
  const projectToScreen = useCallback((x: number, y: number, z: number): { x: number; y: number } | null => {
    if (!fgRef.current) return null;

    const camera = fgRef.current.camera();
    const renderer = fgRef.current.renderer();

    if (!camera || !renderer) return null;

    // Create a 3D vector at the node's position
    const vec = new THREE.Vector3(x, y, z);

    // Project to screen space
    vec.project(camera);

    // Convert normalized device coordinates (-1 to +1) to screen pixels
    const canvas = renderer.domElement;
    const screenX = (vec.x * 0.5 + 0.5) * canvas.width;
    const screenY = (-(vec.y * 0.5) + 0.5) * canvas.height;

    return { x: screenX, y: screenY };
  }, []);

  // Update info box positions when camera moves or simulation updates
  useEffect(() => {
    if (!fgRef.current) return;

    const updateInfoBoxPositions = () => {
      // Update node info boxes
      setActiveNodeInfos(prevInfos =>
        prevInfos.map(info => {
          const node = data.nodes.find(n => n.id === info.nodeId);
          if (!node || node.x === undefined || node.y === undefined || node.z === undefined) {
            return info;
          }

          const screenPos = projectToScreen(node.x, node.y, node.z);
          if (!screenPos) return info;

          return { ...info, x: screenPos.x, y: screenPos.y };
        })
      );

      // Update edge info boxes
      setActiveEdgeInfos(prevInfos =>
        prevInfos.map(info => {
          const link = data.links.find(l => {
            const sourceId = typeof l.source === 'string' ? l.source : l.source.id;
            const targetId = typeof l.target === 'string' ? l.target : l.target.id;
            return `${sourceId}->${targetId}-${l.type}` === info.linkKey;
          });

          if (!link) return info;

          // Get source and target positions
          const sourceNode = typeof link.source === 'object' ? link.source : data.nodes.find(n => n.id === link.source);
          const targetNode = typeof link.target === 'object' ? link.target : data.nodes.find(n => n.id === link.target);

          if (!sourceNode || !targetNode ||
              sourceNode.x === undefined || sourceNode.y === undefined || sourceNode.z === undefined ||
              targetNode.x === undefined || targetNode.y === undefined || targetNode.z === undefined) {
            return info;
          }

          // Calculate midpoint in 3D space
          const midX = (sourceNode.x + targetNode.x) / 2;
          const midY = (sourceNode.y + targetNode.y) / 2;
          const midZ = (sourceNode.z + targetNode.z) / 2;

          const screenPos = projectToScreen(midX, midY, midZ);
          if (!screenPos) return info;

          return { ...info, x: screenPos.x, y: screenPos.y };
        })
      );
    };

    // Update positions on animation frame
    const intervalId = setInterval(updateInfoBoxPositions, 100); // Update every 100ms

    return () => clearInterval(intervalId);
  }, [data.nodes, data.links, projectToScreen, activeNodeInfos.length, activeEdgeInfos.length]);

  // Dismiss node info box
  const handleDismissNodeInfo = useCallback((nodeId: string) => {
    setActiveNodeInfos(prev => prev.filter(info => info.nodeId !== nodeId));
  }, []);

  // Dismiss edge info box
  const handleDismissEdgeInfo = useCallback((linkKey: string) => {
    setActiveEdgeInfos(prev => prev.filter(info => info.linkKey !== linkKey));
  }, []);

  // Context menu items
  const contextMenuItems: ContextMenuItem[] = contextMenu
    ? [
        {
          label: `Follow "${contextMenu.nodeLabel}"`,
          icon: ArrowRight,
          onClick: () => {
            setFocusedNodeId(contextMenu.nodeId);
            setContextMenu(null);
          },
        },
        {
          label: `Add "${contextMenu.nodeLabel}" to Graph`,
          icon: Plus,
          onClick: () => {
            // Add concept to graph
            setContextMenu(null);
          },
        },
      ]
    : [];

  return (
    <div ref={containerRef} className={`relative w-full h-full ${className || ''}`}>
      {/* Force Graph 3D */}
      <ForceGraph3DLib
        ref={fgRef}
        width={dimensions.width}
        height={dimensions.height}
        graphData={data}
        backgroundColor="#1a1a2e"

        // Node appearance
        nodeLabel={(node: any) => node.label}
        nodeColor={(node: any) => nodeColors.get(node.id) || '#888'}
        nodeVal={(node: any) => {
          // Direct scaling to match 2D visual appearance
          // node.size ranges from 5-30 (already log-scaled in graphTransform.ts)
          const baseSize = node.size || 10;
          const sizeMultiplier = settings.visual?.nodeSize ?? 1;
          const result = baseSize * sizeMultiplier;
          // Safety check to prevent NaN from breaking THREE.js geometry
          return isNaN(result) ? 10 : result;
        }}
        nodeOpacity={0.9}
        nodeResolution={16}  // Sphere detail

        // Link appearance - using THREE.Line (pure geometry, no cylinders)
        linkLabel={(link: any) => link.type}
        linkColor={(link: any) => {
          const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
          const targetId = typeof link.target === 'string' ? link.target : link.target.id;
          const linkKey = `${sourceId}->${targetId}-${link.type}`;
          return linkColors.get(linkKey) || '#999';
        }}
        linkWidth={0}  // 0 = use lines, >0 = use cylinder geometry
        linkOpacity={0.6}

        // Billboard arrow sprites (2D textures facing camera)
        linkDirectionalArrowLength={0}  // Disable 3D cone arrows
        linkDirectionalParticles={settings.visual.showArrows ? 1 : 0}
        linkDirectionalParticleSpeed={0}  // Static, not moving
        linkDirectionalParticleWidth={4}
        linkDirectionalParticleResolution={8}
        linkDirectionalParticleColor={(link: any) => {
          const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
          const targetId = typeof link.target === 'string' ? link.target : link.target.id;
          const linkKey = `${sourceId}->${targetId}-${link.type}`;
          return linkColors.get(linkKey) || '#999';
        }}

        // Interaction
        enableNodeDrag={settings.interaction.enableDrag}
        enableNavigationControls={settings.interaction.enableZoom && settings.interaction.enablePan}
        showNavInfo={false}

        // Events
        onNodeClick={(node: any, event: MouseEvent) => {
          if (event.button === 0) {
            // Left click - show info box
            setContextMenu(null); // Close any open context menu

            // Use functional setState to ensure we have the latest state
            setActiveNodeInfos(prev => {
              const exists = prev.some(info => info.nodeId === node.id);
              if (exists) return prev; // Don't create duplicate

              // Calculate degree (number of connections)
              const degree = data.links.filter(link => {
                const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
                const targetId = typeof link.target === 'string' ? link.target : link.target.id;
                return sourceId === node.id || targetId === node.id;
              }).length;

              // Project to screen coordinates
              const screenPos = projectToScreen(node.x || 0, node.y || 0, node.z || 0);
              if (!screenPos) return prev;

              // Create new node info
              const newInfo: NodeInfo = {
                nodeId: node.id,
                label: node.label,
                group: node.group || 'Unknown',
                degree,
                x: screenPos.x,
                y: screenPos.y,
              };

              return [...prev, newInfo];
            });
          }
        }}
        onNodeRightClick={(node: any, event: MouseEvent) => {
          event.preventDefault();
          setContextMenu({
            x: event.clientX,
            y: event.clientY,
            nodeId: node.id,
            nodeLabel: node.label,
          });
        }}
        onNodeHover={(node: any) => {
          setHoveredNode(node ? node.id : null);
        }}
        onLinkClick={(link: any, event: MouseEvent) => {
          if (event.button === 0) {
            // Left click - show edge info box
            const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
            const targetId = typeof link.target === 'string' ? link.target : link.target.id;
            const linkKey = `${sourceId}->${targetId}-${link.type}`;

            setActiveEdgeInfos(prev => {
              const exists = prev.some(info => info.linkKey === linkKey);
              if (exists) return prev; // Don't create duplicate

              // Get source and target positions for midpoint calculation
              const sourceNode = typeof link.source === 'object' ? link.source : data.nodes.find(n => n.id === link.source);
              const targetNode = typeof link.target === 'object' ? link.target : data.nodes.find(n => n.id === link.target);

              if (!sourceNode || !targetNode ||
                  sourceNode.x === undefined || sourceNode.y === undefined || sourceNode.z === undefined ||
                  targetNode.x === undefined || targetNode.y === undefined || targetNode.z === undefined) {
                return prev;
              }

              // Calculate midpoint in 3D space
              const midX = (sourceNode.x + targetNode.x) / 2;
              const midY = (sourceNode.y + targetNode.y) / 2;
              const midZ = (sourceNode.z + targetNode.z) / 2;

              // Project to screen coordinates
              const screenPos = projectToScreen(midX, midY, midZ);
              if (!screenPos) return prev;

              // Get category from vocabulary
              const vocabStore = useVocabularyStore.getState();
              const category = vocabStore.getCategory(link.type);

              // Create new edge info
              const newInfo: EdgeInfo = {
                linkKey,
                sourceId,
                targetId,
                type: link.type,
                confidence: link.value || 1.0,
                category,
                x: screenPos.x,
                y: screenPos.y,
              };

              return [...prev, newInfo];
            });
          }
        }}
        onBackgroundClick={() => {
          setContextMenu(null);
        }}
      />

      {/* Stats Panel */}
      <StatsPanel nodeCount={data.nodes.length} edgeCount={data.links.length} />

      {/* Legend */}
      <Legend data={data} nodeColorMode={settings.visual.nodeColorBy} />

      {/* Canvas Settings Panel */}
      {onSettingsChange && (
        <CanvasSettingsPanel
          settings={settings}
          onChange={onSettingsChange}
        />
      )}

      {/* Context Menu */}
      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          items={contextMenuItems}
          onClose={() => setContextMenu(null)}
        />
      )}

      {/* Node Info Boxes */}
      <div className="absolute inset-0 pointer-events-none" style={{ zIndex: 10000 }}>
        {activeNodeInfos.map(info => (
          <NodeInfoBox
            key={info.nodeId}
            info={info}
            onDismiss={() => handleDismissNodeInfo(info.nodeId)}
          />
        ))}
      </div>

      {/* Edge Info Boxes */}
      <div className="absolute inset-0 pointer-events-none" style={{ zIndex: 10000 }}>
        {activeEdgeInfos.map(info => (
          <EdgeInfoBox
            key={info.linkKey}
            info={info}
            onDismiss={() => handleDismissEdgeInfo(info.linkKey)}
          />
        ))}
      </div>
    </div>
  );
};
