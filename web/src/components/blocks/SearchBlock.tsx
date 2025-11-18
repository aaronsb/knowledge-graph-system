/**
 * Search Block - Find concepts by text query + similarity threshold
 */

import React, { useState, useCallback } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Search } from 'lucide-react';
import type { BlockData, SearchBlockParams } from '../../types/blocks';

export const SearchBlock: React.FC<NodeProps<BlockData>> = ({ data }) => {
  const params = data.params as SearchBlockParams;
  const [query, setQuery] = useState(params.query || '');
  const [similarity, setSimilarity] = useState(params.similarity || 0.6);

  const handleQueryChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newQuery = e.target.value;
    setQuery(newQuery);
    params.query = newQuery;
  }, [params]);

  const handleSimilarityChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newSimilarity = parseFloat(e.target.value);
    setSimilarity(newSimilarity);
    params.similarity = newSimilarity;
  }, [params]);

  return (
    <div className="px-4 py-3 rounded-lg border-2 border-blue-500 dark:border-blue-600 bg-card dark:bg-gray-800/95 shadow-lg min-w-[280px]">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <Search className="w-4 h-4 text-blue-600 dark:text-blue-400" />
        <span className="font-medium text-sm text-card-foreground dark:text-gray-100">Search Concepts</span>
      </div>

      {/* Search Input */}
      <input
        type="text"
        value={query}
        onChange={handleQueryChange}
        placeholder="Enter search term..."
        className="w-full px-2 py-1.5 text-sm border border-border dark:border-gray-600 bg-background dark:bg-gray-900 text-foreground dark:text-gray-100 rounded mb-3 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
      />

      {/* Similarity Slider */}
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <label className="text-xs text-muted-foreground dark:text-gray-400">Similarity</label>
          <span className="text-xs font-medium text-blue-600 dark:text-blue-400">{Math.round(similarity * 100)}%</span>
        </div>
        <input
          type="range"
          min="0"
          max="1"
          step="0.01"
          value={similarity}
          onChange={handleSimilarityChange}
          className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500 dark:accent-blue-400"
        />
      </div>

      {/* Input/Output Handles */}
      <Handle type="target" position={Position.Left} className="w-3 h-3 bg-blue-500 dark:bg-blue-400" />
      <Handle type="source" position={Position.Right} className="w-3 h-3 bg-blue-500 dark:bg-blue-400" />
    </div>
  );
};
