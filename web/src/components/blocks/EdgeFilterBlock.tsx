/**
 * Edge Filter Block - Filter edges by relationship type/name
 */

import React, { useState, useCallback } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { GitBranch, X } from 'lucide-react';
import type { BlockData, EdgeFilterBlockParams } from '../../types/blocks';

export const EdgeFilterBlock: React.FC<NodeProps<BlockData>> = ({ data }) => {
  const params = data.params as EdgeFilterBlockParams;
  const [selectedTypes, setSelectedTypes] = useState<string[]>(params.relationshipTypes || []);
  const [typeInput, setTypeInput] = useState('');
  const [useRegex, setUseRegex] = useState(false);
  const [regexError, setRegexError] = useState<string | null>(null);

  const handleAddType = useCallback(() => {
    const trimmed = typeInput.trim();
    if (!trimmed) return;

    // Validate regex if regex mode is enabled
    if (useRegex) {
      try {
        new RegExp(trimmed);
        setRegexError(null);
      } catch (e) {
        setRegexError('Invalid regex pattern');
        return;
      }
    }

    if (!selectedTypes.includes(trimmed)) {
      const newSelection = [...selectedTypes, trimmed];
      setSelectedTypes(newSelection);
      params.relationshipTypes = newSelection;
      setTypeInput('');
    }
  }, [typeInput, selectedTypes, params, useRegex]);

  const handleRemoveType = useCallback((type: string) => {
    const newSelection = selectedTypes.filter(t => t !== type);
    setSelectedTypes(newSelection);
    params.relationshipTypes = newSelection;
  }, [selectedTypes, params]);

  const handleTypeKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddType();
    }
  }, [handleAddType]);

  return (
    <div className="px-4 py-3 rounded-lg border-2 border-blue-500 dark:border-blue-600 bg-card dark:bg-gray-800/95 shadow-lg min-w-[280px]">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <GitBranch className="w-4 h-4 text-blue-600 dark:text-blue-400" />
        <span className="font-medium text-sm text-card-foreground dark:text-gray-100">Filter by Edge Type</span>
      </div>

      {/* Edge Type Filter */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-xs text-muted-foreground dark:text-gray-400">
            Relationship Types {!useRegex && '(case sensitive)'}
          </label>
          <label className="flex items-center gap-1 cursor-pointer">
            <input
              type="checkbox"
              checked={useRegex}
              onChange={(e) => {
                setUseRegex(e.target.checked);
                setRegexError(null);
              }}
              className="w-3 h-3 text-blue-500 dark:text-blue-400 rounded"
            />
            <span className="text-[10px] text-muted-foreground dark:text-gray-500">Regex</span>
          </label>
        </div>

        {/* Input field */}
        <div className="flex gap-1">
          <input
            type="text"
            value={typeInput}
            onChange={(e) => {
              setTypeInput(e.target.value);
              setRegexError(null);
            }}
            onKeyDown={handleTypeKeyDown}
            placeholder={useRegex ? "Regex pattern..." : "Type and press Enter..."}
            className={`flex-1 px-2 py-1 text-xs border ${regexError ? 'border-red-500 dark:border-red-400' : 'border-border dark:border-gray-600'} bg-background dark:bg-gray-900 text-foreground dark:text-gray-100 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 dark:focus:ring-blue-400`}
          />
          <button
            onClick={handleAddType}
            disabled={!typeInput.trim()}
            className="px-2 py-1 text-xs bg-blue-500 dark:bg-blue-600 text-white rounded hover:bg-blue-600 dark:hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Add
          </button>
        </div>

        {/* Regex error message */}
        {regexError && (
          <div className="text-[10px] text-red-500 dark:text-red-400">
            {regexError}
          </div>
        )}

        {/* Selected types as chips */}
        {selectedTypes.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {selectedTypes.map(type => (
              <div
                key={type}
                className="flex items-center gap-1 px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded text-xs font-mono"
              >
                <span>{type}</span>
                <button
                  onClick={() => handleRemoveType(type)}
                  className="hover:text-blue-900 dark:hover:text-blue-100"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Handles */}
      <Handle type="target" position={Position.Left} className="w-3 h-3 bg-blue-500 dark:bg-blue-400" />
      <Handle type="source" position={Position.Right} className="w-3 h-3 bg-blue-500 dark:bg-blue-400" />
    </div>
  );
};
