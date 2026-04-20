/**
 * ForceGraph3D V2 — Main Component
 *
 * Mounts the r3f Canvas and the scene composition (M1: instanced nodes +
 * indexed edges with seeded sphere positions, no physics yet). Consumes
 * the ExplorerPlugin contract from ADR-034; engine primitives come from
 * the scene/ subdirectory per ADR-702.
 *
 * Node palette: built per-dataset from the ontologies present
 * (createOntologyColorScale). Edge coloring at M1 is endpoint-gradient
 * through the same palette; M3 task #12 adds edge-type coloring.
 */

import React, { useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import type { ExplorerProps } from '../../types/explorer';
import type { ForceGraph3DV2Data, ForceGraph3DV2Settings } from './types';
import { Scene } from './scene/Scene';
import { simBackend } from './scene/useSim';
import { createOntologyColorScale } from '../../utils/colorScale';

/** ForceGraph3D V2 — r3f Canvas + scene composition.  @verified c17bbeb9 */
export const ForceGraph3DV2: React.FC<
  ExplorerProps<ForceGraph3DV2Data, ForceGraph3DV2Settings>
> = ({ data, settings, className }) => {
  const palette = useMemo(() => {
    const ontologies = [...new Set(data?.nodes?.map((n) => n.category) ?? [])].sort();
    return createOntologyColorScale(ontologies);
  }, [data?.nodes]);

  const counts = useMemo(
    () => ({ nodes: data?.nodes?.length ?? 0, edges: data?.edges?.length ?? 0 }),
    [data]
  );

  return (
    <div
      className={`relative w-full h-full ${className || ''}`}
      style={{ background: '#0a0a0f' }}
    >
      <Canvas
        camera={{ position: [0, 0, 400], fov: 60, near: 0.1, far: 5000 }}
        gl={{ antialias: true }}
        frameloop="demand"
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
      >
        <color attach="background" args={['#0a0a0f']} />
        <Scene
          nodes={data?.nodes ?? []}
          edges={data?.edges ?? []}
          palette={palette}
          nodeSize={settings?.visual?.nodeSize ?? 1}
          edgeOpacity={0.7}
        />
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
          ForceGraph3D V2{' '}
          <span
            style={{
              fontSize: 10,
              fontWeight: 400,
              padding: '1px 6px',
              marginLeft: 4,
              borderRadius: 3,
              background: simBackend === 'gpu' ? '#2a4d3a' : '#4d3a2a',
              color: simBackend === 'gpu' ? '#7aff9a' : '#ffb37a',
              textTransform: 'uppercase',
            }}
          >
            {simBackend}
          </span>
        </div>
        <div>
          {counts.nodes} nodes · {counts.edges} edges
        </div>
      </div>
    </div>
  );
};
