/**
 * Limit Block - Limit the number of results returned
 */

import React, { useState, useCallback } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Hash } from 'lucide-react';
import type { BlockData, LimitBlockParams } from '../../types/blocks';

export const LimitBlock: React.FC<NodeProps<BlockData>> = ({ data }) => {
  const params = data.params as LimitBlockParams;
  const [count, setCount] = useState(params.count || 10);

  const handleCountChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newCount = parseInt(e.target.value, 10);
    if (!isNaN(newCount) && newCount > 0) {
      setCount(newCount);
      params.count = newCount;
    }
  }, [params]);

  const presetValues = [10, 25, 50, 100];

  return (
    <div className="px-4 py-3 rounded-lg border-2 border-gray-500 dark:border-gray-600 bg-card dark:bg-gray-800/95 shadow-lg min-w-[280px]">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <Hash className="w-4 h-4 text-gray-600 dark:text-gray-400" />
        <span className="font-medium text-sm text-card-foreground dark:text-gray-100">Limit Results</span>
      </div>

      {/* Count Input */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-sm text-card-foreground dark:text-gray-100">Count:</span>
        <input
          type="number"
          min="1"
          max="1000"
          value={count}
          onChange={handleCountChange}
          className="flex-1 px-2 py-1.5 text-sm border border-border dark:border-gray-600 bg-background dark:bg-gray-900 text-foreground dark:text-gray-100 rounded focus:outline-none focus:ring-2 focus:ring-gray-500 dark:focus:ring-gray-400"
        />
      </div>

      {/* Preset Buttons */}
      <div className="space-y-1">
        <label className="text-xs text-muted-foreground dark:text-gray-400">Presets</label>
        <div className="grid grid-cols-4 gap-1">
          {presetValues.map(value => (
            <button
              key={value}
              onClick={() => {
                setCount(value);
                params.count = value;
              }}
              className={`px-2 py-1 text-xs rounded transition-colors ${
                count === value
                  ? 'bg-gray-500 dark:bg-gray-600 text-white'
                  : 'bg-muted dark:bg-gray-700 text-muted-foreground dark:text-gray-300 hover:bg-accent dark:hover:bg-gray-600'
              }`}
            >
              {value}
            </button>
          ))}
        </div>
      </div>

      {/* Input/Output Handles */}
      <Handle type="target" position={Position.Left} className="w-3 h-3 bg-gray-500 dark:bg-gray-400" />
      <Handle type="source" position={Position.Right} className="w-3 h-3 bg-gray-500 dark:bg-gray-400" />
    </div>
  );
};
