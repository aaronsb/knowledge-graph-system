/**
 * End Block - Exit point for query flow (flowchart oval/terminator shape)
 *
 * Supports output formats:
 * - Visualization: Render to graph UI (current behavior)
 * - JSON/CSV: Return structured data (future - ADR-066)
 */

import React from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Square, BarChart3, FileJson, FileSpreadsheet } from 'lucide-react';
import type { BlockData, EndBlockParams } from '../../types/blocks';

export const EndBlock: React.FC<NodeProps<BlockData>> = ({ data }) => {
  const params = data.params as EndBlockParams;
  const outputFormat = params?.outputFormat || 'visualization';

  return (
    <div className="px-4 py-3 rounded-2xl border-2 border-red-500 dark:border-red-600 bg-card dark:bg-gray-800/95 shadow-lg min-w-[180px]">
      {/* Header */}
      <div className="flex items-center justify-center gap-2 mb-2">
        <Square className="w-4 h-4 text-red-600 dark:text-red-400 fill-current" />
        <span className="font-medium text-sm text-card-foreground dark:text-gray-100">END</span>
        <span className="px-1.5 py-0.5 bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300 rounded text-[10px] font-medium">
          FLOW
        </span>
      </div>

      {/* Output Format Control */}
      <div className="flex items-center justify-center gap-1 text-[10px]">
        <button
          className={`flex items-center gap-1 px-2 py-1 rounded ${
            outputFormat === 'visualization'
              ? 'bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300'
              : 'bg-muted dark:bg-gray-700 text-muted-foreground dark:text-gray-400'
          }`}
          title="Render results as interactive graph"
        >
          <BarChart3 className="w-3 h-3" />
          Graph
        </button>
        <button
          className="flex items-center gap-1 px-2 py-1 rounded bg-muted dark:bg-gray-700 text-muted-foreground dark:text-gray-400 opacity-50 cursor-not-allowed"
          title="Coming soon: Return JSON data (ADR-066)"
          disabled
        >
          <FileJson className="w-3 h-3" />
          JSON
        </button>
        <button
          className="flex items-center gap-1 px-2 py-1 rounded bg-muted dark:bg-gray-700 text-muted-foreground dark:text-gray-400 opacity-50 cursor-not-allowed"
          title="Coming soon: Return CSV data (ADR-066)"
          disabled
        >
          <FileSpreadsheet className="w-3 h-3" />
          CSV
        </button>
      </div>

      {/* Only input handle - no output for end block */}
      <Handle type="target" position={Position.Left} className="w-3 h-3 bg-red-500 dark:bg-red-400" />
    </div>
  );
};
