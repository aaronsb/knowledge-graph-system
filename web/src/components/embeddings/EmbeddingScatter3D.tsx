/**
 * 3D Scatter Plot for Embedding Landscape (ADR-078)
 *
 * Uses Three.js for WebGL rendering of concept embeddings in 3D space.
 * Supports multiple ontologies with different colors, hover labels, and camera controls.
 */

import { useRef, useEffect, useCallback, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { EmbeddingPoint } from './types';

interface Props {
  points: EmbeddingPoint[];
  onSelectPoint: (point: EmbeddingPoint | null) => void;
  selectedPoint: EmbeddingPoint | null;
}

export function EmbeddingScatter3D({ points, onSelectPoint, selectedPoint }: Props) {
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
      (pointsRef.current.material as THREE.PointsMaterial).dispose();
    }

    if (points.length === 0) {
      pointDataRef.current = [];
      return;
    }

    pointDataRef.current = points;

    // Create geometry
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(points.length * 3);
    const colors = new Float32Array(points.length * 3);
    const sizes = new Float32Array(points.length);

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
        ? 3 + Math.abs(point.grounding) * 4
        : 5;
    });

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

    // Create material with vertex colors
    const material = new THREE.PointsMaterial({
      size: 5,
      vertexColors: true,
      sizeAttenuation: true,
      transparent: true,
      opacity: 0.85,
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
        onSelectPoint(point || null);
      }
    } else {
      onSelectPoint(null);
    }
  }, [onSelectPoint]);

  return (
    <div
      ref={containerRef}
      className="w-full h-full relative"
      onMouseMove={handleMouseMove}
      onClick={handleClick}
    >
      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute pointer-events-none z-10 px-2 py-1 bg-gray-900/95 border border-gray-700 rounded text-sm shadow-lg"
          style={{
            left: tooltip.x + 10,
            top: tooltip.y + 10,
          }}
        >
          <div className="text-white font-medium">{tooltip.label}</div>
          <div className="text-xs text-gray-400">{tooltip.ontology}</div>
        </div>
      )}

      {/* Controls hint */}
      <div className="absolute bottom-4 right-4 text-xs text-gray-500">
        Drag to rotate • Scroll to zoom • Shift+drag to pan
      </div>
    </div>
  );
}
