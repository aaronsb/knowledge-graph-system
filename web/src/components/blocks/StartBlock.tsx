/**
 * Start Block - Entry point for query flow (flowchart oval/terminator shape)
 */

import React from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Play } from 'lucide-react';
import type { BlockData, StartBlockParams } from '../../types/blocks';

export const StartBlock: React.FC<NodeProps<BlockData>> = ({ data }) => {
  return (
    <div className="px-6 py-3 rounded-full border-2 border-green-500 dark:border-green-600 bg-card dark:bg-gray-800/95 shadow-lg min-w-[160px]">
      <div className="flex items-center justify-center gap-2">
        <Play className="w-4 h-4 text-green-600 dark:text-green-400 fill-current" />
        <span className="font-medium text-sm text-card-foreground dark:text-gray-100">START</span>
        <span className="px-1.5 py-0.5 bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300 rounded text-[10px] font-medium">
          FLOW
        </span>
      </div>

      {/* Only output handle - no input for start block */}
      <Handle type="source" position={Position.Right} className="w-3 h-3 bg-green-500 dark:bg-green-400" />
    </div>
  );
};
