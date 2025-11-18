/**
 * NOT Block - Boolean negation gate (single input/output)
 */

import React from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Ban } from 'lucide-react';
import type { BlockData, NotBlockParams } from '../../types/blocks';

export const NotBlock: React.FC<NodeProps<BlockData>> = ({ data }) => {
  return (
    <div className="relative px-6 py-3 rounded-lg border-2 border-rose-500 dark:border-rose-600 bg-card dark:bg-gray-800/95 shadow-lg min-w-[160px]">
      <div className="flex items-center justify-center gap-2">
        <Ban className="w-4 h-4 text-rose-600 dark:text-rose-400" />
        <span className="font-bold text-sm text-rose-700 dark:text-rose-300">NOT</span>
      </div>

      {/* Single input handle */}
      <Handle
        type="target"
        position={Position.Left}
        className="w-3 h-3 bg-rose-500 dark:bg-rose-400"
      />

      {/* Single output handle */}
      <Handle
        type="source"
        position={Position.Right}
        className="w-3 h-3 bg-rose-500 dark:bg-rose-400"
      />
    </div>
  );
};
