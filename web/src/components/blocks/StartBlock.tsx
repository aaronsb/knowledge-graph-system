/**
 * Start Block - Entry point for query flow (flowchart oval/terminator shape)
 *
 * Supports execution modes:
 * - Interactive: Run query in UI (current behavior)
 * - Published: Expose as API endpoint (future - ADR-066)
 */

import React from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Play, Globe, Monitor } from 'lucide-react';
import type { BlockData, StartBlockParams } from '../../types/blocks';

export const StartBlock: React.FC<NodeProps<BlockData>> = ({ data }) => {
  const params = data.params as StartBlockParams;
  const executionMode = params?.executionMode || 'interactive';

  return (
    <div className="px-4 py-3 rounded-2xl border-2 border-green-500 dark:border-green-600 bg-card dark:bg-gray-800/95 shadow-lg min-w-[180px]">
      {/* Header */}
      <div className="flex items-center justify-center gap-2 mb-2">
        <Play className="w-4 h-4 text-green-600 dark:text-green-400 fill-current" />
        <span className="font-medium text-sm text-card-foreground dark:text-gray-100">START</span>
        <span className="px-1.5 py-0.5 bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300 rounded text-[10px] font-medium">
          FLOW
        </span>
      </div>

      {/* Execution Mode Control */}
      <div className="flex items-center justify-center gap-1 text-[10px]">
        <button
          className={`flex items-center gap-1 px-2 py-1 rounded ${
            executionMode === 'interactive'
              ? 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300'
              : 'bg-muted dark:bg-gray-700 text-muted-foreground dark:text-gray-400'
          }`}
          title="Run query interactively in the UI"
        >
          <Monitor className="w-3 h-3" />
          Interactive
        </button>
        <button
          className="flex items-center gap-1 px-2 py-1 rounded bg-muted dark:bg-gray-700 text-muted-foreground dark:text-gray-400 opacity-50 cursor-not-allowed"
          title="Coming soon: Expose as API endpoint (ADR-066)"
          disabled
        >
          <Globe className="w-3 h-3" />
          Published
        </button>
      </div>

      {/* Only output handle - no input for start block */}
      <Handle type="source" position={Position.Right} className="w-3 h-3 bg-green-500 dark:bg-green-400" />
    </div>
  );
};
