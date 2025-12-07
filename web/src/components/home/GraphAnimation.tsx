/**
 * GraphAnimation
 *
 * A decorative animated graph visualization.
 * Renders ~18 nodes with edges, slowly rotating in 3D space.
 * Pure canvas-based, no external dependencies.
 */

import React, { useRef, useEffect } from 'react';

interface Node {
  x: number;
  y: number;
  z: number;
  radius: number;
  color: string;
}

interface Edge {
  from: number;
  to: number;
}

// Generate a random graph structure
const generateGraph = (): { nodes: Node[]; edges: Edge[] } => {
  const nodeCount = 18;
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  // Color palette (blues and purples)
  const colors = [
    'rgba(59, 130, 246, 0.8)',   // blue-500
    'rgba(99, 102, 241, 0.8)',   // indigo-500
    'rgba(139, 92, 246, 0.8)',   // violet-500
    'rgba(168, 85, 247, 0.8)',   // purple-500
    'rgba(14, 165, 233, 0.8)',   // sky-500
  ];

  // Create nodes in a roughly spherical distribution
  for (let i = 0; i < nodeCount; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const radius = 80 + Math.random() * 40; // Varying distance from center

    nodes.push({
      x: radius * Math.sin(phi) * Math.cos(theta),
      y: radius * Math.sin(phi) * Math.sin(theta),
      z: radius * Math.cos(phi),
      radius: 3 + Math.random() * 4,
      color: colors[Math.floor(Math.random() * colors.length)],
    });
  }

  // Create edges - connect nearby nodes
  for (let i = 0; i < nodeCount; i++) {
    // Connect to 2-3 other nodes
    const connectionCount = 2 + Math.floor(Math.random() * 2);
    const distances: { index: number; dist: number }[] = [];

    for (let j = 0; j < nodeCount; j++) {
      if (i !== j) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        const dz = nodes[i].z - nodes[j].z;
        distances.push({ index: j, dist: Math.sqrt(dx * dx + dy * dy + dz * dz) });
      }
    }

    // Sort by distance and connect to nearest
    distances.sort((a, b) => a.dist - b.dist);
    for (let k = 0; k < connectionCount && k < distances.length; k++) {
      const j = distances[k].index;
      // Avoid duplicate edges
      if (!edges.some(e => (e.from === i && e.to === j) || (e.from === j && e.to === i))) {
        edges.push({ from: i, to: j });
      }
    }
  }

  return { nodes, edges };
};

// Rotate point around Y axis
const rotateY = (x: number, z: number, angle: number): { x: number; z: number } => {
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  return {
    x: x * cos - z * sin,
    z: x * sin + z * cos,
  };
};

// Rotate point around X axis
const rotateX = (y: number, z: number, angle: number): { y: number; z: number } => {
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  return {
    y: y * cos - z * sin,
    z: y * sin + z * cos,
  };
};

interface GraphAnimationProps {
  className?: string;
  width?: number;
  height?: number;
}

export const GraphAnimation: React.FC<GraphAnimationProps> = ({
  className = '',
  width = 400,
  height = 400,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const graphRef = useRef<{ nodes: Node[]; edges: Edge[] } | null>(null);
  const animationRef = useRef<number>(0);
  const angleRef = useRef({ y: 0, x: 0.3 }); // Start with slight tilt

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Generate graph once
    if (!graphRef.current) {
      graphRef.current = generateGraph();
    }

    const { nodes, edges } = graphRef.current;
    const centerX = width / 2;
    const centerY = height / 2;
    const scale = 1.2;

    const render = () => {
      // Clear canvas
      ctx.clearRect(0, 0, width, height);

      // Update rotation angles (slow rotation)
      angleRef.current.y += 0.003;
      angleRef.current.x = 0.3 + Math.sin(angleRef.current.y * 0.5) * 0.1;

      // Project nodes to 2D
      const projected = nodes.map((node) => {
        // Apply rotations
        let { x, z } = rotateY(node.x, node.z, angleRef.current.y);
        let { y } = rotateX(node.y, z, angleRef.current.x);
        z = rotateX(node.y, z, angleRef.current.x).z;

        // Simple perspective projection
        const perspective = 300;
        const projScale = perspective / (perspective + z);

        return {
          x: centerX + x * scale * projScale,
          y: centerY + y * scale * projScale,
          z,
          scale: projScale,
          radius: node.radius * projScale,
          color: node.color,
        };
      });

      // Sort by z for proper depth rendering
      const sortedIndices = projected
        .map((_, i) => i)
        .sort((a, b) => projected[a].z - projected[b].z);

      // Draw edges first (behind nodes)
      ctx.lineWidth = 1;
      edges.forEach(({ from, to }) => {
        const p1 = projected[from];
        const p2 = projected[to];

        // Fade based on average depth
        const avgZ = (p1.z + p2.z) / 2;
        const alpha = 0.15 + ((avgZ + 120) / 240) * 0.25;

        ctx.strokeStyle = `rgba(148, 163, 184, ${alpha})`; // slate-400
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.stroke();
      });

      // Draw nodes (sorted by depth)
      sortedIndices.forEach((i) => {
        const p = projected[i];

        // Fade and shrink based on depth
        const depthFactor = (p.z + 120) / 240;
        const alpha = 0.4 + depthFactor * 0.6;

        // Glow effect
        const gradient = ctx.createRadialGradient(
          p.x, p.y, 0,
          p.x, p.y, p.radius * 2
        );
        gradient.addColorStop(0, p.color.replace(/[\d.]+\)$/, `${alpha})`));
        gradient.addColorStop(1, p.color.replace(/[\d.]+\)$/, '0)'));

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius * 2, 0, Math.PI * 2);
        ctx.fill();

        // Core node
        ctx.fillStyle = p.color.replace(/[\d.]+\)$/, `${alpha})`);
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fill();
      });

      animationRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationRef.current);
    };
  }, [width, height]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      className={`pointer-events-none ${className}`}
    />
  );
};

export default GraphAnimation;
