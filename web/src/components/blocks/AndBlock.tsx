/**
 * AND Block - Boolean logic gate that accepts multiple inputs
 */

import React from 'react';
import { Handle, Position, type NodeProps, useEdges } from 'reactflow';
import type { BlockData, AndBlockParams } from '../../types/blocks';

export const AndBlock: React.FC<NodeProps<BlockData>> = ({ id }) => {
  // Count incoming connections
  const edges = useEdges();
  const inputCount = edges.filter(edge => edge.target === id).length;

  return (
    <div className="relative px-6 py-4 rounded-lg border-2 border-amber-500 dark:border-amber-600 bg-card dark:bg-gray-800/95 shadow-lg min-w-[160px]">
      <div className="flex flex-col items-center justify-center gap-1">
        <div className="flex items-center gap-2">
          <span className="font-bold text-base text-amber-700 dark:text-amber-300">AND</span>
          <span className="px-1.5 py-0.5 bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300 rounded text-[10px] font-medium">
            LOGIC
          </span>
        </div>
        <span className="text-xs text-amber-600 dark:text-amber-400">
          {inputCount} input{inputCount !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Single input handle (accepts multiple connections) */}
      <Handle
        type="target"
        position={Position.Left}
        className="w-3 h-3 bg-amber-500 dark:bg-amber-400"
      />

      {/* Single output handle */}
      <Handle
        type="source"
        position={Position.Right}
        className="w-3 h-3 bg-amber-500 dark:bg-amber-400"
      />
    </div>
  );
};
