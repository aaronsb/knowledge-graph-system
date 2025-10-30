/**
 * Force-Directed 3D Graph Explorer - Main Component
 *
 * Interactive 3D force-directed graph visualization using react-force-graph-3d.
 * Follows ADR-034 Explorer Plugin Interface.
 */

import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import ForceGraph3DLib from 'react-force-graph-3d';
import * as THREE from 'three';
import SpriteText from 'three-spritetext';
import { Line2 } from 'three/examples/jsm/lines/Line2.js';
import { LineMaterial } from 'three/examples/jsm/lines/LineMaterial.js';
import { LineGeometry } from 'three/examples/jsm/lines/LineGeometry.js';
import type { ExplorerProps } from '../../types/explorer';
import type { ForceGraph3DSettings, ForceGraph3DData } from './types';
import { getNeighbors, transformForD3 } from '../../utils/graphTransform';
import { useGraphStore } from '../../store/graphStore';
import { useVocabularyStore } from '../../store/vocabularyStore';
import { getCategoryColor } from '../../config/categoryColors';
import { ContextMenu, type ContextMenuItem } from '../../components/shared/ContextMenu';
import {
  NodeInfoBox,
  EdgeInfoBox,
  StatsPanel,
  Settings3DPanel,
  GraphSettingsPanel,
  Legend,
  PanelStack,
  useGraphNavigation,
  buildContextMenuItems,
  LABEL_FONTS,
  LABEL_RENDERING,
  LABEL_STYLE_3D,
  ColorTransform,
  createTextCanvas,
} from '../common';
import { SLIDER_RANGES } from './types';

export const ForceGraph3D: React.FC<
  ExplorerProps<ForceGraph3DData, ForceGraph3DSettings>
> = ({ data, settings, onSettingsChange, onNodeClick, className }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<any>();
  const [dimensions, setDimensions] = useState({ width: 1200, height: 800 });
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  // Texture cache for edge labels - reuse textures across sprites for memory efficiency
  const edgeLabelTextureCache = useRef<Map<string, THREE.CanvasTexture>>(new Map());

  // Store camera-facing rotation angles for each edge (rotation around edge axis)
  // Key: linkKey (sourceId->targetId-type), Value: angle in radians
  const labelCameraAngles = useRef<Map<string, number>>(new Map());

  // Unified context menu state (handles both node and background clicks)
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    nodeId: string | null;  // null for background clicks
    nodeLabel: string | null;  // null for background clicks
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
  const { originNodeId, setOriginNodeId, destinationNodeId, setDestinationNodeId, setFocusedNodeId, setGraphData, graphData } = useGraphStore();

  // Helper function to create or retrieve edge label texture
  // NOTE: Font size is NOT a react-force-graph-3d prop because we manually render text
  // to canvas textures and apply them to 3D plane geometry. This gives us full control
  // over appearance (font size, stroke, colors) and ensures proper Z-buffering.
  //
  // Strategy: Always render to FIXED canvas size (based on max fontSize=20px) and center
  // smaller text within it. This provides:
  // 1. Consistent texture resolution (no blur when shrinking)
  // 2. Fixed geometry size (no need to recreate geometry)
  // 3. Stable memory allocation (no texture size churn)
  // 4. Real-time updates to existing geometry references
  const getEdgeLabelTexture = useCallback((text: string, color: string, fontSize: number): THREE.CanvasTexture => {
    // Create cache key from text, color, and font size
    const cacheKey = `${text}:${color}:${fontSize}`;

    // Return cached texture if available
    if (edgeLabelTextureCache.current.has(cacheKey)) {
      return edgeLabelTextureCache.current.get(cacheKey)!;
    }

    // Get unified label colors
    const colors = ColorTransform.getLabelColors(color, 'edge');
    const scale = LABEL_RENDERING.canvasScale;
    const padding = LABEL_RENDERING.padding;

    // Create new texture by rendering text to a canvas
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d')!;

    // Measure text at ACTUAL fontSize to determine canvas dimensions (not max size)
    // This ensures texture tightly fits the rendered text with no wasted space
    ctx.font = `${LABEL_STYLE_3D.edge.fontWeight} ${fontSize * scale}px ${LABEL_FONTS.family}`;
    const metrics = ctx.measureText(text);
    const textWidth = metrics.width;
    const textHeight = fontSize * scale;  // Approximate height from font size

    // Set canvas size at 4x resolution based on actual text dimensions
    canvas.width = Math.ceil(textWidth + padding * 2 * scale);
    canvas.height = Math.ceil(textHeight + padding * 2 * scale);

    // Re-set font after canvas resize (resize clears state)
    ctx.font = `${LABEL_STYLE_3D.edge.fontWeight} ${fontSize * scale}px ${LABEL_FONTS.family}`;
    ctx.textAlign = LABEL_RENDERING.textAlign;
    ctx.textBaseline = LABEL_RENDERING.textBaseline;

    // Apply unified color transformation
    ctx.fillStyle = colors.fill;
    ctx.strokeStyle = colors.stroke;
    ctx.lineWidth = LABEL_STYLE_3D.edge.strokeWidth * scale;

    // Position text: centered in canvas for maximum geometry utilization
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

  // Track floor position with hysteresis to prevent jitter
  const floorPosition = useRef<number>(200);  // Initial position

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

    grid.position.y = floorPosition.current;  // Use tracked position
    grid.name = 'ground-grid';
    scene.add(grid);

    return () => {
      const existingGrid = scene.getObjectByName('ground-grid');
      if (existingGrid) scene.remove(existingGrid);
    };
  }, [settings.visual.showGrid]);

  // Dynamically position floor below lowest node with hysteresis
  useEffect(() => {
    if (!fgRef.current || !settings.visual.showGrid) return;

    const scene = fgRef.current.scene();
    const grid = scene.getObjectByName('ground-grid');
    if (!grid) return;

    // Update floor position on each animation frame
    let animationFrameId: number;

    const updateFloorPosition = () => {
      // Find the lowest Y position in the graph (highest value since Y+ is down)
      let lowestY = -100;  // Default starting point above graph center

      data.nodes.forEach(node => {
        if (node.y !== undefined && node.y > lowestY) {
          lowestY = node.y;
        }
      });

      // Calculate target floor position: lowest node + offset
      const floorOffset = 100;  // Distance below lowest node
      const targetFloorY = lowestY + floorOffset;

      // Hysteresis: only update if difference exceeds threshold
      const hysteresisThreshold = 30;  // Only move floor if > 30 units different
      const currentFloorY = floorPosition.current;

      if (Math.abs(targetFloorY - currentFloorY) > hysteresisThreshold) {
        // Smooth interpolation instead of instant jump
        const lerpFactor = 0.05;  // 5% interpolation per frame
        const newFloorY = currentFloorY + (targetFloorY - currentFloorY) * lerpFactor;

        floorPosition.current = newFloorY;
        grid.position.y = newFloorY;
      }

      animationFrameId = requestAnimationFrame(updateFloorPosition);
    };

    updateFloorPosition();

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [data.nodes, settings.visual.showGrid]);

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

  // Apply camera FOV setting
  useEffect(() => {
    if (!fgRef.current) return;

    const camera = fgRef.current.camera();
    if (!camera || !(camera instanceof THREE.PerspectiveCamera)) return;

    // Update field of view
    camera.fov = settings.camera?.fov ?? 75;
    camera.updateProjectionMatrix();
  }, [settings.camera?.fov]);


  // Clamp camera to prevent going below floor
  useEffect(() => {
    if (!fgRef.current || !settings.camera?.clampToFloor) return;

    const controls = fgRef.current.controls();
    const camera = fgRef.current.camera();
    if (!controls || !camera) return;

    // Grid is at y=200 (positive Y is down in our coordinate system)
    // Prevent camera from going below the floor
    const floorY = 200;
    const minDistanceAboveFloor = 10; // Keep camera at least 10 units above floor

    const clampCameraPosition = () => {
      if (!camera) return;

      // If camera goes below floor (y > floorY), clamp it
      if (camera.position.y > floorY - minDistanceAboveFloor) {
        camera.position.y = floorY - minDistanceAboveFloor;
      }
    };

    // Clamp on every camera movement
    controls.addEventListener('change', clampCameraPosition);

    return () => {
      controls.removeEventListener('change', clampCameraPosition);
    };
  }, [settings.camera?.clampToFloor]);

  // Helper function to calculate target camera-facing rotation for edge labels
  // Returns a map of linkKey -> rotation angle around edge axis
  const calculateTargetCameraRotations = useCallback((camera: THREE.Camera) => {
    const targets = new Map<string, number>();

    data.links.forEach((link) => {
      // Get source and target positions
      const sourceNode = typeof link.source === 'object' ? link.source : data.nodes.find((n: any) => n.id === link.source);
      const targetNode = typeof link.target === 'object' ? link.target : data.nodes.find((n: any) => n.id === link.target);

      if (!sourceNode || !targetNode) return;

      const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
      const targetId = typeof link.target === 'string' ? link.target : link.target.id;
      const linkKey = `${sourceId}->${targetId}-${link.type}`;

      // Get node positions (use current positions from force simulation)
      const start = new THREE.Vector3(sourceNode.x || 0, sourceNode.y || 0, sourceNode.z || 0);
      const end = new THREE.Vector3(targetNode.x || 0, targetNode.y || 0, targetNode.z || 0);

      // Calculate edge tangent (this is the axis we rotate around)
      const tangent = new THREE.Vector3().subVectors(end, start).normalize();

      // Calculate label position (midpoint)
      const labelPos = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5);

      // Calculate direction from label to camera
      const toCamera = new THREE.Vector3().subVectors(camera.position, labelPos).normalize();

      // Project toCamera onto plane perpendicular to tangent (edge axis)
      const projection = toCamera.clone().sub(
        tangent.clone().multiplyScalar(toCamera.dot(tangent))
      );

      // If projection is too small, viewing along edge axis - skip
      if (projection.lengthSq() < 0.01) return;

      projection.normalize();

      // Calculate current "normal" direction for label (sticks out of plane face)
      // This is what we want to point toward the camera
      const worldUp = new THREE.Vector3(0, 0, 1);
      const currentNormal = new THREE.Vector3().crossVectors(tangent, worldUp).normalize();

      // Handle edge case where tangent is parallel to world up
      if (currentNormal.length() < 0.001) {
        worldUp.set(0, 1, 0);
        currentNormal.crossVectors(tangent, worldUp).normalize();
      }

      // Calculate rotation angle around edge axis to align currentNormal with projection
      // We want the normal (Z-axis, face of plane) to point toward camera
      const angle = Math.atan2(
        tangent.dot(new THREE.Vector3().crossVectors(currentNormal, projection)),
        currentNormal.dot(projection)
      );

      // Store angle if significant (> 0.5 degrees)
      if (Math.abs(angle) > 0.009) {
        targets.set(linkKey, angle);
      }
    });

    return targets;
  }, [data.links, data.nodes]);


  // Clear camera angles when orient labels is disabled
  useEffect(() => {
    if (!settings.camera?.orientLabels) {
      labelCameraAngles.current.clear();
    }
  }, [settings.camera?.orientLabels]);



  // Auto-level camera and orient labels when user releases mouse
  useEffect(() => {
    if (!fgRef.current) return;
    // Run if either autoLevel or orientLabels is enabled
    if (!settings.camera?.autoLevel && !settings.camera?.orientLabels) return;

    const controls = fgRef.current.controls();
    const camera = fgRef.current.camera();
    if (!controls || !camera) return;

    let animationFrame: number | null = null;
    let isAnimating = false;
    let startTime = 0;
    const animationDuration = 800; // 800ms smooth animation

    // Store animation state
    let cameraStartUp: THREE.Vector3 | null = null;
    let labelTargetAngles = new Map<string, number>(); // Target rotation angles by linkKey (edges)

    // In our coordinate system, positive Y points DOWN, so up is -Y
    const targetUp = new THREE.Vector3(0, -1, 0);

    const smoothAnimation = (timestamp: number) => {
      if (!camera) return;

      if (!startTime) startTime = timestamp;
      const elapsed = timestamp - startTime;
      const progress = Math.min(elapsed / animationDuration, 1);

      // Ease-in-out curve for smooth acceleration/deceleration
      const eased = progress < 0.5
        ? 2 * progress * progress
        : 1 - Math.pow(-2 * progress + 2, 2) / 2;

      // Auto-level: Interpolate camera up vector toward target
      if (settings.camera?.autoLevel && cameraStartUp) {
        const newUp = new THREE.Vector3().lerpVectors(cameraStartUp, targetUp, eased);
        camera.up.copy(newUp);
      }

      // Orient edge labels: Interpolate rotation angles and store in ref
      if (settings.camera?.orientLabels) {
        labelTargetAngles.forEach((targetAngle, linkKey) => {
          // Interpolate from 0 to target angle
          const currentAngle = targetAngle * eased;
          // Store in ref for use in linkPositionUpdate
          labelCameraAngles.current.set(linkKey, currentAngle);
        });
      }

      if (progress < 1) {
        animationFrame = requestAnimationFrame(smoothAnimation);
      } else {
        isAnimating = false;
        animationFrame = null;
        // Keep final angles in ref (don't clear)
        labelTargetAngles.clear();
        cameraStartUp = null;
      }
    };

    const startAnimation = () => {
      if (isAnimating) return; // Already animating

      // Check if camera needs leveling (up vector not aligned with -Y)
      const shouldLevel = settings.camera?.autoLevel &&
        camera.up.clone().normalize().dot(targetUp) < 0.999; // More than ~2.5 degree off

      // Calculate label target angles if orient labels is enabled
      let shouldOrient = false;
      if (settings.camera?.orientLabels) {
        // Edge labels: calculate target rotation angles
        labelTargetAngles = calculateTargetCameraRotations(camera);
        shouldOrient = labelTargetAngles.size > 0;
      }

      if (shouldLevel || shouldOrient) {
        // Store camera starting orientation
        if (shouldLevel) {
          cameraStartUp = camera.up.clone();
        }

        isAnimating = true;
        startTime = 0;
        animationFrame = requestAnimationFrame(smoothAnimation);
      }
    };

    // Listen for end of interaction (mouse release)
    controls.addEventListener('end', startAnimation);

    return () => {
      controls.removeEventListener('end', startAnimation);
      if (animationFrame !== null) {
        cancelAnimationFrame(animationFrame);
      }
    };
  }, [settings.camera?.autoLevel, settings.camera?.orientLabels, calculateTargetCameraRotations]);

  // Helper: Merge new graph data with existing (deduplicate nodes/links)
  const mergeGraphData = useCallback((newData: any) => {
    if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {
      return newData;
    }

    const existingNodesMap = new Map(
      graphData.nodes.map((n: any) => [n.id, n])
    );

    const mergedNodes: any[] = [...graphData.nodes];

    // Add new nodes near center of existing graph
    newData.nodes.forEach((node: any) => {
      if (!existingNodesMap.has(node.id)) {
        const existingPositions = graphData.nodes
          .filter((n: any) => n.x !== undefined && n.y !== undefined && n.z !== undefined)
          .map((n: any) => ({ x: n.x, y: n.y, z: n.z }));

        if (existingPositions.length > 0) {
          const centerX = existingPositions.reduce((sum, p) => sum + p.x, 0) / existingPositions.length;
          const centerY = existingPositions.reduce((sum, p) => sum + p.y, 0) / existingPositions.length;
          const centerZ = existingPositions.reduce((sum, p) => sum + p.z, 0) / existingPositions.length;

          node.x = centerX + (Math.random() - 0.5) * 50;
          node.y = centerY + (Math.random() - 0.5) * 50;
          node.z = centerZ + (Math.random() - 0.5) * 50;
        }

        mergedNodes.push(node);
      }
    });

    // Merge links (deduplicate)
    const existingLinks = graphData.links || [];
    const existingLinkKeys = new Set(
      existingLinks.map((l: any) => {
        const sourceId = typeof l.source === 'string' ? l.source : l.source.id;
        const targetId = typeof l.target === 'string' ? l.target : l.target.id;
        return `${sourceId}->${targetId}:${l.type}`;
      })
    );
    const mergedLinks = [...existingLinks];

    newData.links.forEach((link: any) => {
      const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
      const targetId = typeof link.target === 'string' ? link.target : link.target.id;
      const key = `${sourceId}->${targetId}:${link.type}`;
      if (!existingLinkKeys.has(key)) {
        mergedLinks.push(link);
      }
    });

    return { nodes: mergedNodes, links: mergedLinks };
  }, [graphData]);

  // Use common graph navigation hook
  const { handleFollowConcept, handleAddToGraph } = useGraphNavigation(mergeGraphData);

  // Pin/Unpin node functionality for 3D
  const isPinned = useCallback((nodeId: string): boolean => {
    const node = data.nodes.find(n => n.id === nodeId);
    return node?.fx !== undefined && node?.fx !== null;
  }, [data.nodes]);

  const togglePinNode = useCallback((nodeId: string) => {
    if (!fgRef.current) return;

    const node = data.nodes.find(n => n.id === nodeId);
    if (!node) return;

    if (node.fx !== undefined && node.fx !== null) {
      // Unpin: remove fixed position
      node.fx = undefined;
      node.fy = undefined;
      node.fz = undefined;
    } else {
      // Pin: set fixed position to current position
      node.fx = node.x;
      node.fy = node.y;
      node.fz = node.z;
    }

    // Refresh graph to apply changes
    fgRef.current.refresh();
  }, [data.nodes]);

  const unpinAllNodes = useCallback(() => {
    if (!fgRef.current) return;

    data.nodes.forEach(node => {
      node.fx = undefined;
      node.fy = undefined;
      node.fz = undefined;
    });

    // Refresh graph to apply changes
    fgRef.current.refresh();
  }, [data.nodes]);

  // Origin node marker with ring sprite
  const applyOriginRing = useCallback((nodeId: string) => {
    if (!fgRef.current || !settings.interaction.showOriginNode) return;

    const scene = fgRef.current.scene();

    // Remove existing ring
    const existingRing = scene.getObjectByName('origin-ring');
    if (existingRing) scene.remove(existingRing);

    // Find the target node
    const targetNode = data.nodes.find(n => n.id === nodeId);
    if (!targetNode) return;

    // Create ring texture with transparency
    const canvas = document.createElement('canvas');
    canvas.width = 128;
    canvas.height = 128;
    const ctx = canvas.getContext('2d')!;

    // Draw gold ring
    ctx.strokeStyle = '#FFD700';  // Gold color
    ctx.lineWidth = 8;
    ctx.globalAlpha = 0.8;
    ctx.beginPath();
    ctx.arc(64, 64, 50, 0, Math.PI * 2);
    ctx.stroke();

    // Inner glow
    ctx.strokeStyle = '#FFF8DC';
    ctx.lineWidth = 4;
    ctx.globalAlpha = 0.4;
    ctx.beginPath();
    ctx.arc(64, 64, 46, 0, Math.PI * 2);
    ctx.stroke();

    const texture = new THREE.CanvasTexture(canvas);
    const spriteMaterial = new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      opacity: 1,
      depthTest: false,  // Always visible
    });

    const sprite = new THREE.Sprite(spriteMaterial);
    sprite.name = 'origin-ring';

    // Calculate node radius
    const calcRadius = (node: any) => {
      const baseSize = node.size || 10;
      const sizeMultiplier = settings.visual?.nodeSize ?? 1;
      const radius = baseSize * sizeMultiplier;
      const volume = Math.pow(radius, 3);
      return Math.cbrt(volume);
    };

    const nodeRadius = calcRadius(targetNode);
    sprite.scale.set(nodeRadius * 3, nodeRadius * 3, 1);  // 3x node size
    sprite.position.set(targetNode.x || 0, targetNode.y || 0, targetNode.z || 0);

    scene.add(sprite);

    // Animate pulsing effect
    let frame = 0;
    const animate = () => {
      if (!sprite.parent) return;  // Stop if removed from scene

      frame++;
      const scale = nodeRadius * 3 + Math.sin(frame * 0.15) * nodeRadius * 0.3;
      sprite.scale.set(scale, scale, 1);
      sprite.material.opacity = 0.7 + Math.sin(frame * 0.15) * 0.3;

      // Update position to follow node
      const node = data.nodes.find(n => n.id === nodeId);
      if (node) {
        sprite.position.set(node.x || 0, node.y || 0, node.z || 0);
      }

      requestAnimationFrame(animate);
    };
    animate();
  }, [data.nodes, settings.visual?.nodeSize, settings.interaction.showOriginNode]);

  // Destination node marker with ring sprite (blue)
  const applyDestinationRing = useCallback((nodeId: string) => {
    if (!fgRef.current || !settings.interaction.showOriginNode) return;

    const scene = fgRef.current.scene();

    // Remove existing ring
    const existingRing = scene.getObjectByName('destination-ring');
    if (existingRing) scene.remove(existingRing);

    // Find the target node
    const targetNode = data.nodes.find(n => n.id === nodeId);
    if (!targetNode) return;

    // Create ring texture with transparency
    const canvas = document.createElement('canvas');
    canvas.width = 128;
    canvas.height = 128;
    const ctx = canvas.getContext('2d')!;

    // Draw royal blue ring
    ctx.strokeStyle = '#4169E1';  // Royal Blue color
    ctx.lineWidth = 8;
    ctx.globalAlpha = 0.8;
    ctx.beginPath();
    ctx.arc(64, 64, 50, 0, Math.PI * 2);
    ctx.stroke();

    // Inner glow
    ctx.strokeStyle = '#6495ED';  // Cornflower Blue for glow
    ctx.lineWidth = 4;
    ctx.globalAlpha = 0.4;
    ctx.beginPath();
    ctx.arc(64, 64, 46, 0, Math.PI * 2);
    ctx.stroke();

    const texture = new THREE.CanvasTexture(canvas);
    const spriteMaterial = new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      opacity: 1,
      depthTest: false,  // Always visible
    });

    const sprite = new THREE.Sprite(spriteMaterial);
    sprite.name = 'destination-ring';

    // Calculate node radius
    const calcRadius = (node: any) => {
      const baseSize = node.size || 10;
      const sizeMultiplier = settings.visual?.nodeSize ?? 1;
      const radius = baseSize * sizeMultiplier;
      const volume = Math.pow(radius, 3);
      return Math.cbrt(volume);
    };

    const nodeRadius = calcRadius(targetNode);
    sprite.scale.set(nodeRadius * 3, nodeRadius * 3, 1);  // 3x node size
    sprite.position.set(targetNode.x || 0, targetNode.y || 0, targetNode.z || 0);

    scene.add(sprite);

    // Animate pulsing effect
    let frame = 0;
    const animate = () => {
      if (!sprite.parent) return;  // Stop if removed from scene

      frame++;
      const scale = nodeRadius * 3 + Math.sin(frame * 0.15) * nodeRadius * 0.3;
      sprite.scale.set(scale, scale, 1);
      sprite.material.opacity = 0.7 + Math.sin(frame * 0.15) * 0.3;

      // Update position to follow node
      const node = data.nodes.find(n => n.id === nodeId);
      if (node) {
        sprite.position.set(node.x || 0, node.y || 0, node.z || 0);
      }

      requestAnimationFrame(animate);
    };
    animate();
  }, [data.nodes, settings.visual?.nodeSize, settings.interaction.showOriginNode]);

  // Apply origin ring when originNodeId changes
  useEffect(() => {
    if (!fgRef.current) return;

    const scene = fgRef.current.scene();

    if (originNodeId && settings.interaction.showOriginNode) {
      // Apply ring to new origin node
      applyOriginRing(originNodeId);
    } else {
      // Remove ring if no origin node
      const existingRing = scene.getObjectByName('origin-ring');
      if (existingRing) scene.remove(existingRing);
    }
  }, [originNodeId, settings.interaction.showOriginNode, applyOriginRing]);

  // Apply destination ring when destinationNodeId changes
  useEffect(() => {
    if (!fgRef.current) return;

    const scene = fgRef.current.scene();

    if (destinationNodeId && settings.interaction.showOriginNode) {
      // Apply ring to new destination node
      applyDestinationRing(destinationNodeId);
    } else {
      // Remove ring if no destination node
      const existingRing = scene.getObjectByName('destination-ring');
      if (existingRing) scene.remove(existingRing);
    }
  }, [destinationNodeId, settings.interaction.showOriginNode, applyDestinationRing]);

  // Travel to origin node (animate camera with smooth easing)
  const travelToOrigin = useCallback(() => {
    if (!originNodeId || !fgRef.current) return;

    const originNode = data.nodes.find(n => n.id === originNodeId);
    if (!originNode || originNode.x === undefined || originNode.y === undefined || originNode.z === undefined) return;

    // Get current camera state
    const camera = fgRef.current.camera();
    const startPos = { x: camera.position.x, y: camera.position.y, z: camera.position.z };

    // Calculate target camera position (maintain reasonable distance and viewing angle)
    const distance = 200;
    const angle = Math.atan2(startPos.z - originNode.z, startPos.x - originNode.x);
    const targetPos = {
      x: originNode.x + Math.cos(angle) * distance,
      y: originNode.y + 50,  // Slight elevation for better viewing
      z: originNode.z + Math.sin(angle) * distance,
    };

    // Cubic ease in/out function for smooth acceleration/deceleration
    const easeInOutCubic = (t: number): number => {
      return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    };

    // Animate camera with easing (750ms duration)
    const duration = 750;
    const startTime = Date.now();

    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = easeInOutCubic(progress);

      // Interpolate camera position with easing
      const currentPos = {
        x: startPos.x + (targetPos.x - startPos.x) * eased,
        y: startPos.y + (targetPos.y - startPos.y) * eased,
        z: startPos.z + (targetPos.z - startPos.z) * eased,
      };

      // Update camera position (looking at the node)
      fgRef.current?.cameraPosition(
        currentPos,
        { x: originNode.x, y: originNode.y, z: originNode.z },
        0  // No built-in transition, we're handling it manually
      );

      // Continue animation until complete
      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };

    animate();
  }, [originNodeId, data.nodes]);

  // Travel to destination node (animate camera with smooth easing)
  const travelToDestination = useCallback(() => {
    if (!destinationNodeId || !fgRef.current) return;

    const destinationNode = data.nodes.find(n => n.id === destinationNodeId);
    if (!destinationNode || destinationNode.x === undefined || destinationNode.y === undefined || destinationNode.z === undefined) return;

    // Get current camera state
    const camera = fgRef.current.camera();
    const startPos = { x: camera.position.x, y: camera.position.y, z: camera.position.z };

    // Calculate target camera position (maintain reasonable distance and viewing angle)
    const distance = 200;
    const angle = Math.atan2(startPos.z - destinationNode.z, startPos.x - destinationNode.x);
    const targetPos = {
      x: destinationNode.x + Math.cos(angle) * distance,
      y: destinationNode.y + 50,  // Slight elevation for better viewing
      z: destinationNode.z + Math.sin(angle) * distance,
    };

    // Cubic ease in/out function for smooth acceleration/deceleration
    const easeInOutCubic = (t: number): number => {
      return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    };

    // Animate camera with easing (750ms duration)
    const duration = 750;
    const startTime = Date.now();

    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = easeInOutCubic(progress);

      // Interpolate camera position with easing
      const currentPos = {
        x: startPos.x + (targetPos.x - startPos.x) * eased,
        y: startPos.y + (targetPos.y - startPos.y) * eased,
        z: startPos.z + (targetPos.z - startPos.z) * eased,
      };

      // Update camera position (looking at the node)
      fgRef.current?.cameraPosition(
        currentPos,
        { x: destinationNode.x, y: destinationNode.y, z: destinationNode.z },
        0  // No built-in transition, we're handling it manually
      );

      // Continue animation until complete
      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };

    animate();
  }, [destinationNodeId, data.nodes]);

  // Dismiss node info box
  const handleDismissNodeInfo = useCallback((nodeId: string) => {
    setActiveNodeInfos(prev => prev.filter(info => info.nodeId !== nodeId));
  }, []);

  // Dismiss edge info box
  const handleDismissEdgeInfo = useCallback((linkKey: string) => {
    setActiveEdgeInfos(prev => prev.filter(info => info.linkKey !== linkKey));
  }, []);

  // Build unified context menu items (context-aware for node vs background)
  const contextMenuItems: ContextMenuItem[] = contextMenu
    ? buildContextMenuItems(
        // Pass node context (null for background clicks)
        contextMenu.nodeId && contextMenu.nodeLabel
          ? { nodeId: contextMenu.nodeId, nodeLabel: contextMenu.nodeLabel }
          : null,
        {
          handleFollowConcept,
          handleAddToGraph,
          setOriginNode: setOriginNodeId,
          setDestinationNode: setDestinationNodeId,
          travelToOrigin,
          travelToDestination,
          isPinned,
          togglePinNode,
          unpinAllNodes,
          applyOriginMarker: applyOriginRing,
          applyDestinationMarker: applyDestinationRing,
        },
        { onClose: () => setContextMenu(null) },
        originNodeId,
        destinationNodeId
      )
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
        // NOTE: nodeLabel shows HTML tooltips, not 3D geometry, so nodeLabelSize setting
        // doesn't apply here (unlike edge labels which are custom 3D geometry with textures).
        // To make nodeLabelSize work, we'd need to implement custom 3D text geometry for nodes.
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

        // Node representation - create group with sphere + label (transform together)
        nodeThreeObjectExtend={false}  // Replace default node entirely
        nodeThreeObject={(node: any) => {
          if (!settings.visual?.showLabels) {
            // No labels - just return undefined to use default sphere rendering
            return undefined;
          }

          // Calculate node radius
          const baseSize = node.size || 10;
          const sizeMultiplier = settings.visual?.nodeSize ?? 1;
          const radius = baseSize * sizeMultiplier;
          const nodeRadius = Math.cbrt(Math.pow(radius, 3));

          // Get node color
          const nodeColor = nodeColors.get(node.id) || '#888';

          // Create group to hold sphere and text sprite
          const group = new THREE.Group();

          // Create node sphere
          const sphereGeometry = new THREE.SphereGeometry(nodeRadius, 16, 16);
          const sphereMaterial = new THREE.MeshLambertMaterial({
            color: nodeColor,
            transparent: true,
            opacity: 0.9,
          });
          const sphere = new THREE.Mesh(sphereGeometry, sphereMaterial);
          group.add(sphere);

          // Create text sprite (automatically faces camera)
          const sprite = new SpriteText(node.label);

          // Apply unified label styling
          const colors = ColorTransform.getLabelColors(nodeColor, 'node');
          sprite.color = colors.fill;
          sprite.fontFace = LABEL_FONTS.family;
          sprite.fontWeight = String(LABEL_FONTS.weights.node3D);
          sprite.strokeColor = colors.stroke;
          sprite.strokeWidth = 0.3;  // Relative to font size (similar to 2D: 0.3)
          sprite.textHeight = settings.visual?.nodeLabelSize ?? 10;
          sprite.position.set(0, nodeRadius + sprite.textHeight / 2, 0);
          group.add(sprite);

          return group;
        }}

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
          // Font size from settings controls canvas text rendering, not a library prop.
          // We render text to canvas → convert to texture → apply to PlaneGeometry.
          const labelTexture = getEdgeLabelTexture(link.type, edgeColor, settings.visual?.edgeLabelSize ?? 9);

          // Create rectangular plane geometry sized to match texture aspect ratio
          // Geometry is 20% larger than texture to prevent edge clipping
          const aspectRatio = labelTexture.image.width / labelTexture.image.height;
          const labelHeight = 12;  // Increased from 10 to 12 (20% larger)
          const labelWidth = aspectRatio * labelHeight;
          const planeGeometry = new THREE.PlaneGeometry(labelWidth, labelHeight);

          const labelMaterial = new THREE.MeshBasicMaterial({
            map: labelTexture,
            transparent: true,
            opacity: 1,
            side: THREE.DoubleSide,  // Visible from both sides
            depthTest: true,  // Participate in Z-buffering (occluded by nodes)
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
            // Calculate linkKey for this edge (needed for camera-facing rotation lookup)
            const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
            const targetId = typeof link.target === 'string' ? link.target : link.target.id;
            const linkKey = `${sourceId}->${targetId}-${link.type}`;

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

            // If "Orient Labels to Camera" is enabled, apply camera-facing rotation
            if (settings.camera?.orientLabels) {
              const cameraAngle = labelCameraAngles.current.get(linkKey);
              if (cameraAngle !== undefined) {
                // Apply rotation around edge tangent (axis of rotation)
                const edgeAxis = tangent.clone().normalize();
                const cameraRotation = new THREE.Quaternion().setFromAxisAngle(edgeAxis, cameraAngle);
                labelMesh.quaternion.premultiply(cameraRotation);
              }
            }

            // Position label: First place center on edge, then offset along rotated local Y-axis
            // This ensures rotation pivot is ON the edge, not offset in space
            const labelHeight = 12;  // Match increased geometry size (20% larger)
            labelMesh.position.copy(midPoint);

            // Offset along the mesh's LOCAL Y-axis (after all rotations applied)
            const localUp = new THREE.Vector3(0, 1, 0);
            const rotatedUp = localUp.applyQuaternion(labelMesh.quaternion);
            const offset = rotatedUp.multiplyScalar(labelHeight / 2);
            labelMesh.position.add(offset);

            // Update texture if edge color mode changed
            const currentEdgeColor = linkColors.get(linkKey) || '#999';
            const newTexture = getEdgeLabelTexture(link.type, currentEdgeColor, settings.visual?.edgeLabelSize ?? 9);

            if (labelMesh.material.map !== newTexture) {
              labelMesh.material.map = newTexture;
              labelMesh.material.needsUpdate = true;

              // Update geometry scale based on new texture aspect ratio
              // Geometry is 20% larger than base size to prevent edge clipping
              const aspectRatio = newTexture.image.width / newTexture.image.height;
              const labelHeight = 12;  // Increased from 10 to 12 (20% larger)
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
        onBackgroundRightClick={(event: MouseEvent) => {
          event.preventDefault();
          // Show unified context menu with null node context (background click)
          setContextMenu({
            x: event.clientX,
            y: event.clientY,
            nodeId: null,
            nodeLabel: null,
          });
        }}
      />

      {/* Left-side panel stack */}
      <PanelStack side="left" gap={16} initialTop={16}>
        <Legend data={data} nodeColorMode={settings.visual.nodeColorBy} />
      </PanelStack>

      {/* Right-side panel stack */}
      <PanelStack side="right" gap={16} initialTop={16}>
        <StatsPanel nodeCount={data.nodes.length} edgeCount={data.links.length} />

        {onSettingsChange && (
          <GraphSettingsPanel
            settings={settings}
            onChange={onSettingsChange}
            sliderRanges={SLIDER_RANGES}
          />
        )}

        {onSettingsChange && (
          <Settings3DPanel
            camera={settings.camera}
            onCameraChange={(camera) => onSettingsChange({ ...settings, camera })}
          />
        )}
      </PanelStack>

      {/* Unified Context Menu (context-aware for node vs background) */}
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
