/**
 * 3D Scatter Plot for Embedding Landscape (ADR-078)
 *
 * Uses Three.js for WebGL rendering of concept embeddings in 3D space.
 * Supports multiple ontologies with different colors, hover labels, and camera controls.
 *
 * Sprites are rendered using SDF (Signed Distance Field) shaders for crisp,
 * pixel-perfect vector art style at any zoom level.
 */

import { useRef, useEffect, useCallback, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { EmbeddingPoint, ProjectionItemType } from './types';

// Shape type mapping: concept=0, source=1, vocabulary=2
const SHAPE_INDEX: Record<ProjectionItemType, number> = {
  concept: 0,    // Circle
  source: 1,     // Diamond
  vocabulary: 2, // Triangle
};

/**
 * SDF (Signed Distance Field) vertex shader.
 * Passes position, color, size, and shape type to fragment shader.
 */
const vertexShader = `
  attribute float size;
  attribute float shape;

  varying vec3 vColor;
  varying float vShape;

  void main() {
    vColor = color;
    vShape = shape;

    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = size * (300.0 / -mvPosition.z);
    gl_Position = projectionMatrix * mvPosition;
  }
`;

/**
 * SDF fragment shader for crisp vector-style shapes.
 *
 * Shapes:
 * - 0: Circle (concepts) - soft, continuous knowledge
 * - 1: Diamond (sources) - evidence chunks, documents
 * - 2: Triangle (vocabulary) - relationship types
 */
const fragmentShader = `
  varying vec3 vColor;
  varying float vShape;
  uniform float uOpacity;

  // SDF for circle
  float sdCircle(vec2 p, float r) {
    return length(p) - r;
  }

  // SDF for diamond (rotated square)
  float sdDiamond(vec2 p, float r) {
    vec2 q = abs(p);
    return (q.x + q.y - r) / 1.414;
  }

  // SDF for equilateral triangle (pointing up)
  float sdTriangle(vec2 p, float r) {
    const float k = 1.732050808; // sqrt(3)
    p.x = abs(p.x) - r;
    p.y = p.y + r / k;
    if (p.x + k * p.y > 0.0) {
      p = vec2(p.x - k * p.y, -k * p.x - p.y) / 2.0;
    }
    p.x -= clamp(p.x, -2.0 * r, 0.0);
    return -length(p) * sign(p.y);
  }

  void main() {
    // Map gl_PointCoord (0-1) to centered coordinates (-1 to 1)
    vec2 uv = gl_PointCoord * 2.0 - 1.0;

    // Calculate SDF based on shape type
    float d;
    int shapeType = int(vShape + 0.5);

    if (shapeType == 0) {
      // Circle for concepts
      d = sdCircle(uv, 0.8);
    } else if (shapeType == 1) {
      // Diamond for sources
      d = sdDiamond(uv, 0.7);
    } else {
      // Triangle for vocabulary
      d = sdTriangle(uv, 0.75);
    }

    // Anti-aliased edge (crisp but smooth)
    float alpha = 1.0 - smoothstep(-0.02, 0.02, d);

    if (alpha < 0.01) discard;

    // Add subtle edge highlight for depth
    float edge = smoothstep(-0.1, -0.02, d) - smoothstep(-0.02, 0.0, d);
    vec3 finalColor = vColor + edge * 0.2;

    gl_FragColor = vec4(finalColor, alpha * uOpacity);
  }
`;

interface Props {
  points: EmbeddingPoint[];
  onSelectPoint: (point: EmbeddingPoint | null, screenPos?: { x: number; y: number }) => void;
  onContextMenu?: (point: EmbeddingPoint, screenPos: { x: number; y: number }) => void;
  selectedPoint: EmbeddingPoint | null;
}

export function EmbeddingScatter3D({ points, onSelectPoint, onContextMenu, selectedPoint }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const pointsRef = useRef<THREE.Points | null>(null);
  const raycasterRef = useRef<THREE.Raycaster>(new THREE.Raycaster());
  const mouseRef = useRef<THREE.Vector2>(new THREE.Vector2());
  const hoveredIndexRef = useRef<number | null>(null);

  // Map from point index to EmbeddingPoint data
  const pointDataRef = useRef<EmbeddingPoint[]>([]);

  // Tooltip state
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    label: string;
    ontology: string;
  } | null>(null);

  // Initialize Three.js scene
  useEffect(() => {
    if (!containerRef.current) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight;

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a0f);
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 10000);
    camera.position.set(200, 200, 200);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.screenSpacePanning = false;
    controls.minDistance = 10;
    controls.maxDistance = 2000;
    controlsRef.current = controls;

    // Grid helper (subtle)
    const gridHelper = new THREE.GridHelper(400, 40, 0x333333, 0x222222);
    scene.add(gridHelper);

    // Axes helper (subtle)
    const axesHelper = new THREE.AxesHelper(100);
    axesHelper.setColors(
      new THREE.Color(0x663333), // X - red
      new THREE.Color(0x336633), // Y - green
      new THREE.Color(0x333366)  // Z - blue
    );
    scene.add(axesHelper);

    // Animation loop
    let animationId: number;
    const animate = () => {
      animationId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // Resize handler
    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    // Raycaster settings for point cloud
    raycasterRef.current.params.Points = { threshold: 5 };

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationId);
      controls.dispose();
      renderer.dispose();
      container.removeChild(renderer.domElement);
    };
  }, []);

  // Update points when data changes
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;

    // Remove old points
    if (pointsRef.current) {
      scene.remove(pointsRef.current);
      pointsRef.current.geometry.dispose();
      (pointsRef.current.material as THREE.ShaderMaterial).dispose();
    }

    if (points.length === 0) {
      pointDataRef.current = [];
      return;
    }

    pointDataRef.current = points;

    // Create geometry with attributes for SDF shader
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(points.length * 3);
    const colors = new Float32Array(points.length * 3);
    const sizes = new Float32Array(points.length);
    const shapes = new Float32Array(points.length);

    points.forEach((point, i) => {
      positions[i * 3] = point.x;
      positions[i * 3 + 1] = point.y;
      positions[i * 3 + 2] = point.z;

      const color = new THREE.Color(point.color);
      colors[i * 3] = color.r;
      colors[i * 3 + 1] = color.g;
      colors[i * 3 + 2] = color.b;

      // Size based on grounding if available
      sizes[i] = point.grounding !== null
        ? 8 + Math.abs(point.grounding) * 8
        : 12;

      // Shape based on item type
      shapes[i] = SHAPE_INDEX[point.itemType] ?? 0;
    });

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));
    geometry.setAttribute('shape', new THREE.BufferAttribute(shapes, 1));

    // Dynamic alpha based on point count
    // Higher base opacity for better color pop on dark backgrounds
    // Only reduce opacity for very large point clouds (>5000 points)
    const dynamicAlpha = Math.min(1 / Math.sqrt(points.length), 0.95);
    const effectiveAlpha = Math.max(0.75, dynamicAlpha); // Higher minimum for color vibrancy

    // Create custom SDF shader material for crisp vector shapes
    const material = new THREE.ShaderMaterial({
      uniforms: {
        uOpacity: { value: effectiveAlpha },
      },
      vertexShader,
      fragmentShader,
      vertexColors: true,
      transparent: true,
      depthWrite: false,
      blending: THREE.NormalBlending,
    });

    const pointCloud = new THREE.Points(geometry, material);
    scene.add(pointCloud);
    pointsRef.current = pointCloud;

    // Auto-fit camera to data
    if (cameraRef.current && controlsRef.current) {
      const bbox = new THREE.Box3().setFromBufferAttribute(
        geometry.getAttribute('position') as THREE.BufferAttribute
      );
      const center = bbox.getCenter(new THREE.Vector3());
      const size = bbox.getSize(new THREE.Vector3());
      const maxDim = Math.max(size.x, size.y, size.z);

      cameraRef.current.position.set(
        center.x + maxDim,
        center.y + maxDim * 0.8,
        center.z + maxDim
      );
      controlsRef.current.target.copy(center);
      controlsRef.current.update();
    }
  }, [points]);

  // Handle mouse move for hover detection
  const handleMouseMove = useCallback((event: React.MouseEvent) => {
    if (!containerRef.current || !pointsRef.current || !cameraRef.current) return;

    const rect = containerRef.current.getBoundingClientRect();
    mouseRef.current.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouseRef.current.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycasterRef.current.setFromCamera(mouseRef.current, cameraRef.current);
    const intersects = raycasterRef.current.intersectObject(pointsRef.current);

    if (intersects.length > 0) {
      const idx = intersects[0].index;
      if (idx !== undefined && idx !== hoveredIndexRef.current) {
        hoveredIndexRef.current = idx;
        const point = pointDataRef.current[idx];
        if (point) {
          setTooltip({
            x: event.clientX - rect.left,
            y: event.clientY - rect.top,
            label: point.label,
            ontology: point.ontology,
          });
        }
      }
    } else {
      if (hoveredIndexRef.current !== null) {
        hoveredIndexRef.current = null;
        setTooltip(null);
      }
    }
  }, []);

  // Handle click for selection
  const handleClick = useCallback((event: React.MouseEvent) => {
    if (!containerRef.current || !pointsRef.current || !cameraRef.current) return;

    const rect = containerRef.current.getBoundingClientRect();
    mouseRef.current.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouseRef.current.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycasterRef.current.setFromCamera(mouseRef.current, cameraRef.current);
    const intersects = raycasterRef.current.intersectObject(pointsRef.current);

    if (intersects.length > 0) {
      const idx = intersects[0].index;
      if (idx !== undefined) {
        const point = pointDataRef.current[idx];
        // Pass container-relative coordinates for info box positioning
        const screenPos = {
          x: event.clientX - rect.left,
          y: event.clientY - rect.top
        };
        onSelectPoint(point || null, screenPos);
      }
    } else {
      onSelectPoint(null);
    }
  }, [onSelectPoint]);

  // Handle right-click for context menu
  const handleRightClick = useCallback((event: React.MouseEvent) => {
    if (!containerRef.current || !pointsRef.current || !cameraRef.current) return;
    if (!onContextMenu) return;

    event.preventDefault();

    const rect = containerRef.current.getBoundingClientRect();
    mouseRef.current.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouseRef.current.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycasterRef.current.setFromCamera(mouseRef.current, cameraRef.current);
    const intersects = raycasterRef.current.intersectObject(pointsRef.current);

    if (intersects.length > 0) {
      const idx = intersects[0].index;
      if (idx !== undefined) {
        const point = pointDataRef.current[idx];
        if (point) {
          // Pass container-relative coordinates for menu positioning
          const screenPos = {
            x: event.clientX - rect.left,
            y: event.clientY - rect.top
          };
          onContextMenu(point, screenPos);
        }
      }
    }
  }, [onContextMenu]);

  return (
    <div
      ref={containerRef}
      className="w-full h-full relative"
      onMouseMove={handleMouseMove}
      onClick={handleClick}
      onContextMenu={handleRightClick}
    >
      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute pointer-events-none z-10 px-2 py-1 bg-card/95 border border-border rounded text-sm shadow-lg"
          style={{
            left: tooltip.x + 10,
            top: tooltip.y + 10,
          }}
        >
          <div className="text-foreground font-medium">{tooltip.label}</div>
          <div className="text-xs text-muted-foreground">{tooltip.ontology}</div>
        </div>
      )}

      {/* Controls hint */}
      <div className="absolute bottom-4 right-4 text-xs text-muted-foreground/70">
        Drag to rotate • Scroll to zoom • Shift+drag to pan
      </div>
    </div>
  );
}
