/**
 * Neighborhood Block - Expand N hops from current concepts
 */

import React, { useState, useCallback } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Network } from 'lucide-react';
import type { BlockData, NeighborhoodBlockParams } from '../../types/blocks';

export const NeighborhoodBlock: React.FC<NodeProps<BlockData>> = ({ data }) => {
  const params = data.params as NeighborhoodBlockParams;
  const [depth, setDepth] = useState(params.depth || 2);
  const [direction, setDirection] = useState(params.direction || 'both');

  const handleDepthChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newDepth = parseInt(e.target.value, 10);
    setDepth(newDepth);
    params.depth = newDepth;
  }, [params]);

  const handleDirectionChange = useCallback((newDirection: 'outgoing' | 'incoming' | 'both') => {
    setDirection(newDirection);
    params.direction = newDirection;
  }, [params]);

  return (
    <div className="px-4 py-3 rounded-lg border-2 border-purple-500 bg-white shadow-lg min-w-[280px]">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <Network className="w-4 h-4 text-purple-600" />
        <span className="font-medium text-sm">Expand Neighborhood</span>
      </div>

      {/* Depth Control */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-sm text-gray-700">Depth:</span>
        <input
          type="number"
          min="1"
          max="5"
          value={depth}
          onChange={handleDepthChange}
          className="w-16 px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-purple-500"
        />
        <span className="text-xs text-gray-600">hops</span>
      </div>

      {/* Direction Buttons */}
      <div className="space-y-1">
        <label className="text-xs text-gray-600">Direction</label>
        <div className="flex gap-1">
          <button
            onClick={() => handleDirectionChange('outgoing')}
            className={`flex-1 px-2 py-1.5 text-xs rounded transition-colors ${
              direction === 'outgoing'
                ? 'bg-purple-500 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            Out →
          </button>
          <button
            onClick={() => handleDirectionChange('incoming')}
            className={`flex-1 px-2 py-1.5 text-xs rounded transition-colors ${
              direction === 'incoming'
                ? 'bg-purple-500 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            ← In
          </button>
          <button
            onClick={() => handleDirectionChange('both')}
            className={`flex-1 px-2 py-1.5 text-xs rounded transition-colors ${
              direction === 'both'
                ? 'bg-purple-500 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            ↔ Both
          </button>
        </div>
      </div>

      {/* Handles */}
      <Handle type="target" position={Position.Left} className="w-3 h-3 bg-purple-500" />
      <Handle type="source" position={Position.Right} className="w-3 h-3 bg-purple-500" />
    </div>
  );
};
