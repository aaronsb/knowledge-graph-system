/**
 * End Block - Exit point for query flow (flowchart oval/terminator shape)
 */

import React from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Square } from 'lucide-react';
import type { BlockData, EndBlockParams } from '../../types/blocks';

export const EndBlock: React.FC<NodeProps<BlockData>> = ({ data }) => {
  return (
    <div className="px-6 py-3 rounded-full border-2 border-red-500 dark:border-red-600 bg-card dark:bg-gray-800/95 shadow-lg min-w-[160px]">
      <div className="flex items-center justify-center gap-2">
        <Square className="w-4 h-4 text-red-600 dark:text-red-400 fill-current" />
        <span className="font-medium text-sm text-card-foreground dark:text-gray-100">END</span>
        <span className="px-1.5 py-0.5 bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300 rounded text-[10px] font-medium">
          FLOW
        </span>
      </div>

      {/* Only input handle - no output for end block */}
      <Handle type="target" position={Position.Left} className="w-3 h-3 bg-red-500 dark:bg-red-400" />
    </div>
  );
};
