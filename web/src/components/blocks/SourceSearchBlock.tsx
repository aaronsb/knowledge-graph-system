/**
 * Source Search Block - Search source text passages using embeddings (ADR-068 Phase 5)
 *
 * This is a Smart Block that uses the API's source search endpoint
 * to find source document passages by semantic similarity.
 * Unlike concept search, this searches the actual source text chunks.
 */

import React, { useState, useCallback } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { FileText } from 'lucide-react';
import type { BlockData, SourceSearchBlockParams } from '../../types/blocks';

export const SourceSearchBlock: React.FC<NodeProps<BlockData>> = ({ data }) => {
  const params = data.params as SourceSearchBlockParams;
  const [query, setQuery] = useState(params.query || '');
  const [similarity, setSimilarity] = useState(params.similarity || 0.7);
  const [limit, setLimit] = useState(params.limit || 10);
  const [ontology, setOntology] = useState(params.ontology || '');

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

  const handleLimitChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newLimit = parseInt(e.target.value, 10);
    setLimit(newLimit);
    params.limit = newLimit;
  }, [params]);

  const handleOntologyChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newOntology = e.target.value;
    setOntology(newOntology);
    params.ontology = newOntology;
  }, [params]);

  return (
    <div className="px-4 py-3 rounded-lg border-2 border-amber-500 dark:border-amber-600 bg-card dark:bg-gray-800/95 shadow-lg min-w-[280px]">
      {/* Header with Smart Block indicator */}
      <div className="flex items-center gap-2 mb-3">
        <FileText className="w-4 h-4 text-amber-600 dark:text-amber-400" />
        <span className="font-medium text-sm text-card-foreground dark:text-gray-100">Source Search</span>
        <span className="ml-auto px-1.5 py-0.5 bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300 rounded text-[10px] font-medium">
          SMART
        </span>
      </div>

      {/* Description */}
      <p className="text-xs text-muted-foreground dark:text-gray-400 mb-3">
        Search source text passages (ADR-068)
      </p>

      {/* Search Input */}
      <input
        type="text"
        value={query}
        onChange={handleQueryChange}
        onPointerDown={(e) => e.stopPropagation()}
        onMouseDown={(e) => e.stopPropagation()}
        placeholder="Enter search phrase..."
        className="w-full px-2 py-1.5 text-sm border border-border dark:border-gray-600 bg-background dark:bg-gray-900 text-foreground dark:text-gray-100 rounded mb-3 focus:outline-none focus:ring-2 focus:ring-amber-500 dark:focus:ring-amber-400 nodrag"
      />

      {/* Ontology Filter (Optional) */}
      <input
        type="text"
        value={ontology}
        onChange={handleOntologyChange}
        onPointerDown={(e) => e.stopPropagation()}
        onMouseDown={(e) => e.stopPropagation()}
        placeholder="Filter by ontology (optional)..."
        className="w-full px-2 py-1.5 text-sm border border-border dark:border-gray-600 bg-background dark:bg-gray-900 text-foreground dark:text-gray-100 rounded mb-3 focus:outline-none focus:ring-2 focus:ring-amber-500 dark:focus:ring-amber-400 nodrag"
      />

      {/* Similarity Threshold Slider */}
      <div className="space-y-1 mb-3">
        <div className="flex items-center justify-between">
          <label className="text-xs text-muted-foreground dark:text-gray-400">Similarity</label>
          <span className="text-xs font-medium text-amber-600 dark:text-amber-400">{Math.round(similarity * 100)}%</span>
        </div>
        <input
          type="range"
          min="0.5"
          max="1"
          step="0.01"
          value={similarity}
          onChange={handleSimilarityChange}
          onPointerDown={(e) => e.stopPropagation()}
          onMouseDown={(e) => e.stopPropagation()}
          className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-amber-500 dark:accent-amber-400 nodrag"
        />
      </div>

      {/* Result Count */}
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <label className="text-xs text-muted-foreground dark:text-gray-400">Max Results</label>
          <span className="text-xs font-medium text-amber-600 dark:text-amber-400">{limit}</span>
        </div>
        <input
          type="range"
          min="1"
          max="50"
          step="1"
          value={limit}
          onChange={handleLimitChange}
          onPointerDown={(e) => e.stopPropagation()}
          onMouseDown={(e) => e.stopPropagation()}
          className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-amber-500 dark:accent-amber-400 nodrag"
        />
      </div>

      {/* Input/Output Handles */}
      <Handle type="target" position={Position.Left} className="w-3 h-3 bg-amber-500 dark:bg-amber-400" />
      <Handle type="source" position={Position.Right} className="w-3 h-3 bg-amber-500 dark:bg-amber-400" />
    </div>
  );
};
