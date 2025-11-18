/**
 * Epistemic Filter Block - Filter relationships by epistemic status (Smart Block)
 *
 * Filters graph edges based on their epistemic classification:
 * AFFIRMATIVE, CONTESTED, CONTRADICTORY, HISTORICAL, INSUFFICIENT_DATA, UNCLASSIFIED
 */

import React, { useState, useCallback } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Snowflake } from 'lucide-react';
import type { BlockData, EpistemicFilterBlockParams } from '../../types/blocks';

// ADR-065: Available epistemic statuses
const EPISTEMIC_STATUSES = [
  { value: 'AFFIRMATIVE', label: 'Affirmative', description: 'Well-established knowledge' },
  { value: 'CONTESTED', label: 'Contested', description: 'Debated or mixed validation' },
  { value: 'CONTRADICTORY', label: 'Contradictory', description: 'Contradicted knowledge' },
  { value: 'HISTORICAL', label: 'Historical', description: 'Temporal vocabulary' },
  { value: 'INSUFFICIENT_DATA', label: 'Insufficient Data', description: 'Limited measurements' },
  { value: 'UNCLASSIFIED', label: 'Unclassified', description: 'Not yet classified' },
] as const;

export const EpistemicFilterBlock: React.FC<NodeProps<BlockData>> = ({ data }) => {
  const params = data.params as EpistemicFilterBlockParams;
  const [includeStatuses, setIncludeStatuses] = useState<string[]>(params.includeStatuses || []);
  const [excludeStatuses, setExcludeStatuses] = useState<string[]>(params.excludeStatuses || []);
  const [showInclude, setShowInclude] = useState(true);

  const toggleIncludeStatus = useCallback((status: string) => {
    setIncludeStatuses(prev => {
      const newStatuses = prev.includes(status)
        ? prev.filter(s => s !== status)
        : [...prev, status];
      params.includeStatuses = newStatuses;
      return newStatuses;
    });
  }, [params]);

  const toggleExcludeStatus = useCallback((status: string) => {
    setExcludeStatuses(prev => {
      const newStatuses = prev.includes(status)
        ? prev.filter(s => s !== status)
        : [...prev, status];
      params.excludeStatuses = newStatuses;
      return newStatuses;
    });
  }, [params]);

  const activeCount = includeStatuses.length + excludeStatuses.length;

  return (
    <div className="px-4 py-3 rounded-lg border-2 border-indigo-500 dark:border-indigo-600 bg-card dark:bg-gray-800/95 shadow-lg min-w-[280px]">
      {/* Header with Smart Block indicator */}
      <div className="flex items-center gap-2 mb-3">
        <Snowflake className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
        <span className="font-medium text-sm text-card-foreground dark:text-gray-100">Epistemic Filter</span>
        <span className="ml-auto px-1.5 py-0.5 bg-indigo-100 dark:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300 rounded text-[10px] font-medium">
          SMART
        </span>
      </div>

      {/* Description */}
      <p className="text-xs text-muted-foreground dark:text-gray-400 mb-3">
        Filter edges by knowledge reliability
      </p>

      {/* Toggle between Include/Exclude */}
      <div className="flex gap-1 mb-3">
        <button
          onClick={() => setShowInclude(true)}
          className={`flex-1 px-2 py-1.5 text-xs rounded transition-colors ${
            showInclude
              ? 'bg-indigo-500 dark:bg-indigo-600 text-white'
              : 'bg-muted dark:bg-gray-700 text-muted-foreground dark:text-gray-300 hover:bg-accent dark:hover:bg-gray-600'
          }`}
        >
          Include Only
          {includeStatuses.length > 0 && (
            <span className="ml-1 px-1 bg-white/20 rounded text-[10px]">{includeStatuses.length}</span>
          )}
        </button>
        <button
          onClick={() => setShowInclude(false)}
          className={`flex-1 px-2 py-1.5 text-xs rounded transition-colors ${
            !showInclude
              ? 'bg-red-500 dark:bg-red-600 text-white'
              : 'bg-muted dark:bg-gray-700 text-muted-foreground dark:text-gray-300 hover:bg-accent dark:hover:bg-gray-600'
          }`}
        >
          Exclude
          {excludeStatuses.length > 0 && (
            <span className="ml-1 px-1 bg-white/20 rounded text-[10px]">{excludeStatuses.length}</span>
          )}
        </button>
      </div>

      {/* Status Checkboxes */}
      <div className="space-y-1.5 max-h-[200px] overflow-y-auto">
        {EPISTEMIC_STATUSES.map(status => {
          const isIncluded = includeStatuses.includes(status.value);
          const isExcluded = excludeStatuses.includes(status.value);
          const isActive = showInclude ? isIncluded : isExcluded;
          const toggle = showInclude ? toggleIncludeStatus : toggleExcludeStatus;

          return (
            <label
              key={status.value}
              className="flex items-start gap-2 cursor-pointer hover:bg-muted dark:hover:bg-gray-700/50 p-1 rounded"
            >
              <input
                type="checkbox"
                checked={isActive}
                onChange={() => toggle(status.value)}
                className={`mt-0.5 w-3.5 h-3.5 rounded focus:ring-2 ${
                  showInclude
                    ? 'text-indigo-600 dark:text-indigo-400 focus:ring-indigo-500'
                    : 'text-red-600 dark:text-red-400 focus:ring-red-500'
                }`}
              />
              <div className="flex-1 min-w-0">
                <span className="text-xs font-medium text-card-foreground dark:text-gray-200 block">
                  {status.label}
                </span>
                <span className="text-[10px] text-muted-foreground dark:text-gray-500 block truncate">
                  {status.description}
                </span>
              </div>
            </label>
          );
        })}
      </div>

      {/* Active filters summary */}
      {activeCount > 0 && (
        <div className="mt-2 pt-2 border-t border-border dark:border-gray-700 text-[10px] text-muted-foreground dark:text-gray-500">
          {includeStatuses.length > 0 && (
            <div>Include: {includeStatuses.join(', ')}</div>
          )}
          {excludeStatuses.length > 0 && (
            <div>Exclude: {excludeStatuses.join(', ')}</div>
          )}
        </div>
      )}

      {/* Input/Output Handles */}
      <Handle type="target" position={Position.Left} className="w-3 h-3 bg-indigo-500 dark:bg-indigo-400" />
      <Handle type="source" position={Position.Right} className="w-3 h-3 bg-indigo-500 dark:bg-indigo-400" />
    </div>
  );
};
