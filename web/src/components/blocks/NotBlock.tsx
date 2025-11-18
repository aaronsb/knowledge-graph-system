/**
 * NOT Block - Exclude concepts matching a pattern
 */

import React, { useState, useCallback } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Ban } from 'lucide-react';
import type { BlockData, NotBlockParams } from '../../types/blocks';

export const NotBlock: React.FC<NodeProps<BlockData>> = ({ data }) => {
  const params = data.params as NotBlockParams;
  const [excludePattern, setExcludePattern] = useState(params.excludePattern || '');
  const [excludeProperty, setExcludeProperty] = useState(params.excludeProperty || 'label');

  const handlePatternChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newPattern = e.target.value;
    setExcludePattern(newPattern);
    params.excludePattern = newPattern;
  }, [params]);

  const handlePropertyChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const newProperty = e.target.value as 'label' | 'ontology';
    setExcludeProperty(newProperty);
    params.excludeProperty = newProperty;
  }, [params]);

  return (
    <div className="px-4 py-3 rounded-lg border-2 border-rose-500 dark:border-rose-600 bg-card dark:bg-gray-800/95 shadow-lg min-w-[280px]">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <Ban className="w-4 h-4 text-rose-600 dark:text-rose-400" />
        <span className="font-medium text-sm text-card-foreground dark:text-gray-100">Exclude (NOT)</span>
      </div>

      {/* Property Selector */}
      <div className="mb-3">
        <label className="text-xs text-muted-foreground dark:text-gray-400">Exclude by</label>
        <select
          value={excludeProperty}
          onChange={handlePropertyChange}
          onPointerDown={(e) => e.stopPropagation()}
          onMouseDown={(e) => e.stopPropagation()}
          className="w-full px-2 py-1.5 text-sm border border-border dark:border-gray-600 bg-background dark:bg-gray-900 text-foreground dark:text-gray-100 rounded focus:outline-none focus:ring-2 focus:ring-rose-500 dark:focus:ring-rose-400 nodrag"
        >
          <option value="label">Label</option>
          <option value="ontology">Ontology</option>
        </select>
      </div>

      {/* Exclude Pattern Input */}
      <div>
        <label className="text-xs text-muted-foreground dark:text-gray-400">Pattern to exclude</label>
        <input
          type="text"
          value={excludePattern}
          onChange={handlePatternChange}
          onPointerDown={(e) => e.stopPropagation()}
          onMouseDown={(e) => e.stopPropagation()}
          placeholder="e.g., deprecated, test"
          className="w-full px-2 py-1.5 text-sm border border-border dark:border-gray-600 bg-background dark:bg-gray-900 text-foreground dark:text-gray-100 rounded focus:outline-none focus:ring-2 focus:ring-rose-500 dark:focus:ring-rose-400 nodrag"
        />
      </div>

      {/* Input/Output Handles */}
      <Handle type="target" position={Position.Left} className="w-3 h-3 bg-rose-500 dark:bg-rose-400" />
      <Handle type="source" position={Position.Right} className="w-3 h-3 bg-rose-500 dark:bg-rose-400" />
    </div>
  );
};
