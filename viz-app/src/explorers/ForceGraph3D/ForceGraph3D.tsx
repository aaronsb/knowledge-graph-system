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
import { apiClient } from '../../api/client';
import { Legend } from './Legend';
import { CanvasSettingsPanel } from './CanvasSettingsPanel';

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

  // Get navigation state from store
  const { originNodeId, setOriginNodeId, setFocusedNodeId, setGraphData, graphData } = useGraphStore();

  // Calculate node colors
  const nodeColors = useMemo(() => {
    const colors = new Map<string, string>();
    data.nodes.forEach((node) => {
      let color = '#888';

      switch (settings.visual.nodeColorBy) {
        case 'ontology':
          // Use d3-scale-chromatic colors based on ontology hash
          const ontologyHash = node.group?.split('').reduce((acc, char) =>
            char.charCodeAt(0) + ((acc << 5) - acc), 0) || 0;
          const hue = Math.abs(ontologyHash % 360);
          color = `hsl(${hue}, 70%, 50%)`;
          break;
        case 'degree':
          const degree = node.degree || 1;
          const degreeNormalized = Math.min(degree / 20, 1);
          color = `hsl(${220 + degreeNormalized * 120}, 70%, 50%)`;
          break;
        case 'centrality':
          color = `hsl(${(node.centrality || 0) * 180}, 70%, 50%)`;
          break;
      }

      colors.set(node.id, color);
    });
    return colors;
  }, [data.nodes, settings.visual.nodeColorBy]);

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
        nodeVal={(node: any) => (node.size || 10) * settings.visual.nodeSize}
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

        // Physics
        d3AlphaDecay={settings.physics.enabled ? 0.0228 : 1}
        d3VelocityDecay={settings.physics.friction}
        warmupTicks={settings.physics.enabled ? 100 : 0}
        cooldownTicks={settings.physics.enabled ? Infinity : 0}

        // Interaction
        enableNodeDrag={settings.interaction.enableDrag}
        enableNavigationControls={settings.interaction.enableZoom && settings.interaction.enablePan}
        showNavInfo={false}

        // Events
        onNodeClick={(node: any, event: MouseEvent) => {
          if (event.button === 0) {
            // Left click
            setOriginNodeId(node.id);
            onNodeClick?.(node.id);
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
        onBackgroundClick={() => {
          setContextMenu(null);
        }}
      />

      {/* Stats Panel */}
      <div className="absolute top-4 right-4 bg-gray-800/95 border border-gray-600 rounded-lg shadow-xl px-3 py-2 text-sm z-10">
        <div className="text-gray-200">
          {data.nodes.length} nodes • {data.links.length} edges
        </div>
      </div>

      {/* Legend */}
      <Legend
        nodeColors={nodeColors}
        linkColors={linkColors}
        data={data}
        settings={settings}
      />

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
    </div>
  );
};
