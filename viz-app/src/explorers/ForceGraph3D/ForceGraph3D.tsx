/**
 * Force-Directed 3D Graph Explorer - Main Component
 *
 * Interactive 3D force-directed graph visualization using react-force-graph-3d.
 * Follows ADR-034 Explorer Plugin Interface.
 */

import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import ForceGraph3DLib from 'react-force-graph-3d';
import * as THREE from 'three';
import { Line2 } from 'three/examples/jsm/lines/Line2.js';
import { LineMaterial } from 'three/examples/jsm/lines/LineMaterial.js';
import { LineGeometry } from 'three/examples/jsm/lines/LineGeometry.js';
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

  // Texture cache for edge labels - reuse textures across sprites for memory efficiency
  const edgeLabelTextureCache = useRef<Map<string, THREE.CanvasTexture>>(new Map());

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

  // Helper function to create or retrieve edge label texture
  const getEdgeLabelTexture = useCallback((text: string, color: string): THREE.CanvasTexture => {
    // Create cache key from text and color
    const cacheKey = `${text}:${color}`;

    // Return cached texture if available
    if (edgeLabelTextureCache.current.has(cacheKey)) {
      return edgeLabelTextureCache.current.get(cacheKey)!;
    }

    // Create new texture
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d')!;

    // Render at 4x resolution for crisp text
    const scale = 4;
    const fontSize = 9;  // Base font size (match 2D graph)
    const padding = 4;   // Base padding

    // Measure text at base size first
    ctx.font = `400 ${fontSize}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
    const metrics = ctx.measureText(text);
    const textWidth = metrics.width;

    // Set canvas size at 4x resolution
    canvas.width = Math.ceil((textWidth + padding * 2) * scale);
    canvas.height = (fontSize + padding * 2) * scale;

    // Re-set font after canvas resize (resize clears state) at 4x size
    ctx.font = `400 ${fontSize * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    // Brighten color by 40% (match 2D implementation)
    const threeColor = new THREE.Color(color);
    const brightened = threeColor.clone().multiplyScalar(1.4);
    // Manually clamp RGB components to [0, 1]
    brightened.r = Math.min(1, brightened.r);
    brightened.g = Math.min(1, brightened.g);
    brightened.b = Math.min(1, brightened.b);

    // Draw text with stroke outline (paint-order: stroke) at 4x scale
    ctx.strokeStyle = '#1a1a2e';  // Dark background color
    ctx.lineWidth = 1 * scale;  // Scale stroke width
    ctx.fillStyle = `rgb(${Math.floor(brightened.r * 255)}, ${Math.floor(brightened.g * 255)}, ${Math.floor(brightened.b * 255)})`;

    const x = canvas.width / 2;
    const y = canvas.height / 2;

    ctx.strokeText(text, x, y);
    ctx.fillText(text, x, y);

    // Create texture
    const texture = new THREE.CanvasTexture(canvas);
    texture.needsUpdate = true;

    // Cache it
    edgeLabelTextureCache.current.set(cacheKey, texture);

    return texture;
  }, []);

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

  // Calculate curve offsets for multiple edges between same nodes (collision avoidance)
  const linkCurveOffsets = useMemo(() => {
    const offsets = new Map<string, number>();

    // Group links by node pair (undirected - sorted to treat A→B and B→A as same pair)
    const linkGroups = new Map<string, any[]>();

    data.links.forEach(link => {
      const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
      const targetId = typeof link.target === 'string' ? link.target : link.target.id;

      // Create a consistent key for the node pair (sorted)
      const pairKey = [sourceId, targetId].sort().join('->');

      if (!linkGroups.has(pairKey)) {
        linkGroups.set(pairKey, []);
      }
      linkGroups.get(pairKey)!.push(link);
    });

    // Assign curve offsets to links in groups with multiple edges
    linkGroups.forEach(links => {
      if (links.length > 1) {
        // Multiple edges between same nodes - distribute them with curves
        links.forEach((link, index) => {
          const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
          const targetId = typeof link.target === 'string' ? link.target : link.target.id;
          const linkKey = `${sourceId}->${targetId}-${link.type}`;

          // Calculate offset: center around 0 and spread evenly
          const totalLinks = links.length;
          const offsetMultiplier = index - (totalLinks - 1) / 2;
          const curveStrength = 30; // Base curve distance (same as 2D)

          offsets.set(linkKey, offsetMultiplier * curveStrength);
        });
      } else {
        // Single edge - no curve needed (offset = 0, straight line)
        const link = links[0];
        const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
        const targetId = typeof link.target === 'string' ? link.target : link.target.id;
        const linkKey = `${sourceId}->${targetId}-${link.type}`;
        offsets.set(linkKey, 0);
      }
    });

    return offsets;
  }, [data.links]);

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
        const newDimensions = {
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        };
        setDimensions(newDimensions);

        // Update Line2 material resolution when window resizes
        if (fgRef.current) {
          const scene = fgRef.current.scene();
          scene.traverse((obj: any) => {
            if (obj instanceof Line2 && obj.material instanceof LineMaterial) {
              obj.material.resolution.set(newDimensions.width, newDimensions.height);
            }
          });
        }
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
    if (!fgRef.current || !settings.physics?.enabled) return;

    const fg = fgRef.current;

    // Delay force configuration to ensure simulation is initialized
    const timer = setTimeout(() => {
      try {
        const chargeForce = fg.d3Force?.('charge');
        const linkForce = fg.d3Force?.('link');
        const centerForce = fg.d3Force?.('center');

        // Configure forces if they exist
        if (chargeForce && typeof chargeForce.strength === 'function') {
          chargeForce.strength(settings.physics?.charge ?? -300);
        }
        if (linkForce && typeof linkForce.distance === 'function') {
          linkForce.distance(settings.physics?.linkDistance ?? 80);
        }
        if (centerForce && typeof centerForce.strength === 'function') {
          centerForce.strength(settings.physics?.gravity ?? 0.1);
        }

        // Reheat simulation to keep it active while adjusting sliders
        // This mimics the behavior of clicking and dragging a node
        if (fg.d3ReheatSimulation && typeof fg.d3ReheatSimulation === 'function') {
          fg.d3ReheatSimulation();
        }
      } catch (e) {
        // Silently ignore - simulation might not be ready yet on first render
        console.warn('Error configuring D3 forces:', e);
      }
    }, 100);

    return () => clearTimeout(timer);
  }, [settings.physics?.charge, settings.physics?.linkDistance, settings.physics?.gravity, settings.physics?.enabled]);

  // Update line widths when linkWidth slider changes
  useEffect(() => {
    if (!fgRef.current) return;

    const scene = fgRef.current.scene();
    const lineWidth = settings.visual?.linkWidth ?? 1;

    scene.traverse((obj: any) => {
      if (obj instanceof Line2 && obj.material instanceof LineMaterial) {
        obj.material.linewidth = lineWidth * 2;  // Match scale in linkThreeObject
      }
    });
  }, [settings.visual?.linkWidth]);

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
          // nodeVal represents sphere VOLUME, library calculates radius as ∛(volume)
          // To match 2D visual radius, we need to pass radius³ as volume
          // node.size ranges from 5-30 (already log-scaled in graphTransform.ts)
          const baseSize = node.size || 10;
          const sizeMultiplier = settings.visual?.nodeSize ?? 1;
          const radius = baseSize * sizeMultiplier;
          // Cube the radius to get volume: V = r³ (ignoring the 4/3π constant)
          const volume = Math.pow(radius, 3);
          // Safety check to prevent NaN from breaking THREE.js geometry
          return isNaN(volume) ? 1000 : volume;
        }}
        nodeOpacity={0.9}
        nodeResolution={16}  // Sphere detail

        // Link appearance - custom curved gradient lines (not cylinders)
        linkLabel={(link: any) => link.type}
        linkWidth={0}  // Disable default cylinders, use custom linkThreeObject
        linkThreeObject={(link: any) => {
          // Get edge color based on settings (category, confidence, or uniform)
          const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
          const targetId = typeof link.target === 'string' ? link.target : link.target.id;
          const linkKey = `${sourceId}->${targetId}-${link.type}`;
          const edgeColor = linkColors.get(linkKey) || '#999';

          // Use edge color for both source and target (uniform gradient)
          const sourceColor = new THREE.Color(edgeColor);
          const targetColor = new THREE.Color(edgeColor);

          // Create group to hold line + arrow sprite
          const group = new THREE.Group();

          // We'll set positions in linkPositionUpdate
          // Create placeholder points for now
          const numPoints = 20;
          const positions: number[] = [];
          const colors: number[] = [];

          for (let i = 0; i <= numPoints; i++) {
            // Placeholder positions (will be updated in linkPositionUpdate)
            positions.push(0, i, 0);

            // Create gradient colors from source to target
            const t = i / numPoints;
            const gradientColor = sourceColor.clone().lerp(targetColor, t);
            colors.push(gradientColor.r, gradientColor.g, gradientColor.b);
          }

          // Create LineGeometry with positions and colors
          const geometry = new LineGeometry();
          geometry.setPositions(positions);
          geometry.setColors(colors);

          const linkOpacity = 0.6;
          const lineWidth = settings.visual?.linkWidth ?? 1;

          // LineMaterial for shader-based thick lines
          const material = new LineMaterial({
            vertexColors: true,
            transparent: true,
            opacity: linkOpacity,
            linewidth: lineWidth * 2,  // LineMaterial uses pixels, scale up for visibility
            resolution: new THREE.Vector2(dimensions.width, dimensions.height),
          });

          const line = new Line2(geometry, material);
          line.computeLineDistances();  // Required for dashed lines and proper rendering
          group.add(line);

          // Add 2D arrow sprite at endpoint (if enabled)
          if (settings.visual.showArrows) {
            // Create arrow sprite texture using edge color
            const canvas = document.createElement('canvas');
            canvas.width = 64;
            canvas.height = 64;
            const ctx = canvas.getContext('2d')!;

            // Draw arrow pointing right with edge color
            ctx.fillStyle = `rgb(${Math.floor(sourceColor.r * 255)}, ${Math.floor(sourceColor.g * 255)}, ${Math.floor(sourceColor.b * 255)})`;
            ctx.globalAlpha = linkOpacity;
            ctx.beginPath();
            ctx.moveTo(10, 32);
            ctx.lineTo(54, 32);
            ctx.lineTo(54, 20);
            ctx.lineTo(64, 32);
            ctx.lineTo(54, 44);
            ctx.lineTo(54, 32);
            ctx.fill();

            const texture = new THREE.CanvasTexture(canvas);
            const spriteMaterial = new THREE.SpriteMaterial({
              map: texture,
              transparent: true,
              opacity: linkOpacity,
            });

            const sprite = new THREE.Sprite(spriteMaterial);
            sprite.scale.set(8, 8, 1);
            sprite.name = 'arrow-sprite';
            group.add(sprite);
          }

          // Add edge label as 3D geometry (participates in Z-buffering)
          const labelTexture = getEdgeLabelTexture(link.type, edgeColor);

          // Create rectangular plane geometry
          const aspectRatio = labelTexture.image.width / labelTexture.image.height;
          const labelHeight = 10;
          const labelWidth = aspectRatio * labelHeight;
          const planeGeometry = new THREE.PlaneGeometry(labelWidth, labelHeight);

          const labelMaterial = new THREE.MeshBasicMaterial({
            map: labelTexture,
            transparent: true,
            opacity: 1,
            side: THREE.DoubleSide,  // Visible from both sides
            depthTest: true,  // Participate in Z-buffering
            depthWrite: false,  // Don't write to depth buffer (transparency)
          });

          const labelMesh = new THREE.Mesh(planeGeometry, labelMaterial);
          labelMesh.name = 'edge-label-mesh';
          group.add(labelMesh);

          return group;
        }}
        linkPositionUpdate={(obj: any, { start, end }: any, link: any) => {
          // Update curved line geometry when nodes move
          if (!start || !end || !link || !link.type) return;

          // Defensive: wrap in try-catch to prevent simulation crashes
          try {

          // Get node radii for surface offset calculation
          const sourceNode = typeof link.source === 'object' ? link.source : data.nodes.find((n: any) => n.id === link.source);
          const targetNode = typeof link.target === 'object' ? link.target : data.nodes.find((n: any) => n.id === link.target);

          if (!sourceNode || !targetNode) return;

          // Calculate node radii (match nodeVal calculation)
          const calcRadius = (node: any) => {
            const baseSize = node.size || 10;
            const sizeMultiplier = settings.visual?.nodeSize ?? 1;
            const radius = baseSize * sizeMultiplier;
            const volume = Math.pow(radius, 3);
            // Reverse: radius = ∛(volume)
            return Math.cbrt(isNaN(volume) ? 1000 : volume);
          };

          const sourceRadius = calcRadius(sourceNode);
          const targetRadius = calcRadius(targetNode);

          // Create vectors for start and end positions
          const startPos = new THREE.Vector3(start.x, start.y, start.z);
          const endPos = new THREE.Vector3(end.x, end.y, end.z);

          // Calculate direction vector from source to target
          const direction = new THREE.Vector3().subVectors(endPos, startPos);
          const distance = direction.length();
          direction.normalize();

          // Offset start and end points to sphere surfaces
          const surfaceStart = startPos.clone().add(direction.clone().multiplyScalar(sourceRadius));
          const surfaceEnd = endPos.clone().sub(direction.clone().multiplyScalar(targetRadius));

          // Get curve offset for collision avoidance
          const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
          const targetId = typeof link.target === 'string' ? link.target : link.target.id;
          const linkKey = `${sourceId}->${targetId}-${link.type}`;
          const curveOffset = linkCurveOffsets?.get(linkKey) ?? 0;

          // Calculate control point for curved arc (perpendicular offset)
          const midPoint = new THREE.Vector3().addVectors(surfaceStart, surfaceEnd).multiplyScalar(0.5);
          const perpendicular = new THREE.Vector3(-direction.y, direction.x, 0).normalize();

          // If no offset (single edge), use straight line (no curvature)
          // If offset exists (multiple edges), apply offset + base curvature for smooth arc
          let controlPoint: THREE.Vector3;
          if (curveOffset === 0) {
            // Straight line - control point at midpoint
            controlPoint = midPoint.clone();
          } else {
            // Curved line - apply offset for collision avoidance
            const baseCurvature = distance * 0.15; // 15% arc height for smooth curves
            controlPoint = midPoint.clone().add(perpendicular.multiplyScalar(curveOffset + baseCurvature));
          }

          // Create curved line
          const curve = new THREE.QuadraticBezierCurve3(surfaceStart, controlPoint, surfaceEnd);
          const points = curve.getPoints(20);

          // Update Line2 geometry with new positions
          const line = obj.children.find((child: any) => child instanceof Line2);
          if (line && line.geometry) {
            // Convert Vector3 points to flat array for LineGeometry
            const positions: number[] = [];
            points.forEach(p => {
              positions.push(p.x, p.y, p.z);
            });

            line.geometry.setPositions(positions);
            line.computeLineDistances();  // Recompute after position update

            // Update gradient colors based on edge color settings
            const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
            const targetId = typeof link.target === 'string' ? link.target : link.target.id;
            const linkKey = `${sourceId}->${targetId}-${link.type}`;
            const edgeColor = linkColors.get(linkKey) || '#999';

            // Use edge color for uniform gradient
            const color = new THREE.Color(edgeColor);

            const colors: number[] = [];
            for (let i = 0; i <= 20; i++) {
              // Uniform color along the curve (no gradient)
              colors.push(color.r, color.g, color.b);
            }

            line.geometry.setColors(colors);
          }

          // Update arrow sprite position at endpoint
          const arrowSprite = obj.getObjectByName('arrow-sprite');
          if (arrowSprite) {
            arrowSprite.position.copy(surfaceEnd);

            // Orient sprite to face direction of link
            const angle = Math.atan2(direction.y, direction.x);
            arrowSprite.rotation.z = angle;
          }

          // Update edge label mesh position and orientation
          const labelMesh = obj.getObjectByName('edge-label-mesh');
          if (labelMesh) {
            // Get midpoint of curve (t=0.5)
            const midPoint = curve.getPoint(0.5);

            // Get tangent direction at midpoint - this is the edge arrow direction
            const tangent = curve.getTangent(0.5);

            // Orient text to read along the edge direction (following the arrow)
            // Create a coordinate system where:
            // - X-axis points along the curve tangent (text reads in arrow direction)
            // - Y-axis points "up" (perpendicular to tangent)
            // - Z-axis is the plane normal (perpendicular to label, facing outward)

            const worldUp = new THREE.Vector3(0, 0, 1);  // World up
            const normal = new THREE.Vector3().crossVectors(tangent, worldUp).normalize();

            // If tangent is parallel to world up, use different reference
            if (normal.length() < 0.001) {
              worldUp.set(0, 1, 0);
              normal.crossVectors(tangent, worldUp).normalize();
            }

            const up = new THREE.Vector3().crossVectors(normal, tangent).normalize();

            // Create rotation matrix: X=tangent (reading direction), Y=up, Z=normal
            const matrix = new THREE.Matrix4();
            matrix.makeBasis(tangent, up, normal);

            // Apply rotation - text reads along edge direction
            labelMesh.setRotationFromMatrix(matrix);

            // Offset position so bottom edge of label touches curve (not center)
            // Shift along the UP direction (Y-axis in label space) by half label height
            const labelHeight = 10;
            const offset = up.clone().multiplyScalar(labelHeight / 2);
            labelMesh.position.copy(midPoint.clone().add(offset));

            // Update texture if edge color mode changed
            const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
            const targetId = typeof link.target === 'string' ? link.target : link.target.id;
            const linkKey = `${sourceId}->${targetId}-${link.type}`;
            const currentEdgeColor = linkColors.get(linkKey) || '#999';
            const newTexture = getEdgeLabelTexture(link.type, currentEdgeColor);

            if (labelMesh.material.map !== newTexture) {
              labelMesh.material.map = newTexture;
              labelMesh.material.needsUpdate = true;

              // Update geometry scale based on new texture aspect ratio
              const aspectRatio = newTexture.image.width / newTexture.image.height;
              const labelHeight = 10;
              const labelWidth = aspectRatio * labelHeight;

              labelMesh.geometry.dispose();  // Clean up old geometry
              labelMesh.geometry = new THREE.PlaneGeometry(labelWidth, labelHeight);
            }
          }
          } catch (error) {
            // Silently ignore errors during position update to prevent simulation crashes
            console.warn('Error in linkPositionUpdate:', error);
          }
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
