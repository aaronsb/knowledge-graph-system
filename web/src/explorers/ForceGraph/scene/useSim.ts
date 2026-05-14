/**
 * Module-scope dispatcher picking the GPU or CPU force-sim hook.
 *
 * React's rules of hooks require a stable hook identity across renders,
 * so this decision is made exactly once at module load based on
 * gpuSimSupported. A component calls `useSim(nodes, edges, params)`
 * and receives a ForceSimHandle regardless of which path was chosen.
 */

import { useForceSim, type ForceSimHandle, type ForceSimParams } from './useForceSim';
import { useGpuForceSim, gpuSimSupported } from './useGpuForceSim';
import type { EngineNode, EngineEdge } from '../types';

/** Whether the runtime picked the GPU path. Plugins can surface this in UI. */
export const simBackend: 'gpu' | 'cpu' = gpuSimSupported ? 'gpu' : 'cpu';

/** useSim — GPU if available, CPU otherwise. Stable across renders.  @verified c17bbeb9 */
export const useSim: (
  nodes: EngineNode[],
  edges: EngineEdge[],
  params?: ForceSimParams
) => ForceSimHandle = gpuSimSupported ? useGpuForceSim : useForceSim;
