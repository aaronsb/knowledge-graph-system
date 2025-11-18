/**
 * OR Block - Boolean logic gate that accepts multiple inputs
 */

import React from 'react';
import { Handle, Position, type NodeProps, useEdges } from 'reactflow';
import type { BlockData, OrBlockParams } from '../../types/blocks';

export const OrBlock: React.FC<NodeProps<BlockData>> = ({ id }) => {
  // Count incoming connections
  const edges = useEdges();
  const inputCount = edges.filter(edge => edge.target === id).length;

  return (
    <div className="relative px-6 py-4 rounded-lg border-2 border-cyan-500 dark:border-cyan-600 bg-card dark:bg-gray-800/95 shadow-lg min-w-[160px]">
      <div className="flex flex-col items-center justify-center gap-1">
        <span className="font-bold text-base text-cyan-700 dark:text-cyan-300">OR</span>
        <span className="text-xs text-cyan-600 dark:text-cyan-400">
          {inputCount} input{inputCount !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Single input handle (accepts multiple connections) */}
      <Handle
        type="target"
        position={Position.Left}
        className="w-3 h-3 bg-cyan-500 dark:bg-cyan-400"
      />

      {/* Single output handle */}
      <Handle
        type="source"
        position={Position.Right}
        className="w-3 h-3 bg-cyan-500 dark:bg-cyan-400"
      />
    </div>
  );
};
