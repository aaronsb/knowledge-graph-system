/**
 * ForceGraph3D V2 — Main Component (scaffold)
 *
 * M1 task #6: plugin skeleton only. An r3f Canvas mounts and reports the
 * engine-shape data counts; scene primitives (instanced nodes, edges,
 * physics) arrive in subsequent M1/M2 tasks per ADR-702.
 *
 * The plugin contract (ADR-034) is honored: ExplorerProps in, selection
 * and click events emitted upward. Widgets (NodeInfoBox etc.) get wired
 * in M5.
 */

import React, { useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import type { ExplorerProps } from '../../types/explorer';
import type { ForceGraph3DV2Data, ForceGraph3DV2Settings } from './types';

/** ForceGraph3D V2 scaffold component — r3f Canvas + data summary overlay.  @verified c17bbeb9 */
export const ForceGraph3DV2: React.FC<
  ExplorerProps<ForceGraph3DV2Data, ForceGraph3DV2Settings>
> = ({ data, className }) => {
  const counts = useMemo(
    () => ({ nodes: data?.nodes?.length ?? 0, edges: data?.edges?.length ?? 0 }),
    [data]
  );

  return (
    <div
      className={className}
      style={{ position: 'relative', width: '100%', height: '100%', background: '#0a0a0f' }}
    >
      <Canvas
        camera={{ position: [0, 0, 400], fov: 60, near: 0.1, far: 5000 }}
        gl={{ antialias: true }}
      >
        <ambientLight intensity={0.5} />
        <color attach="background" args={['#0a0a0f']} />
      </Canvas>

      <div
        style={{
          position: 'absolute',
          top: 12,
          left: 12,
          padding: '8px 12px',
          background: 'rgba(10, 10, 15, 0.85)',
          border: '1px solid #26263a',
          borderRadius: 4,
          color: '#d7d7e0',
          fontFamily: 'SF Mono, Menlo, monospace',
          fontSize: 12,
          pointerEvents: 'none',
        }}
      >
        <div style={{ fontWeight: 600, marginBottom: 4 }}>
          ForceGraph3D V2 — scaffold
        </div>
        <div>
          {counts.nodes} nodes · {counts.edges} edges
        </div>
        <div style={{ opacity: 0.6, marginTop: 4 }}>
          Scene primitives land in M1 task #7
        </div>
      </div>
    </div>
  );
};
