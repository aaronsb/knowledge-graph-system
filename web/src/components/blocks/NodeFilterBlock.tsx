/**
 * Node Filter Block - Filter nodes by label/name and confidence
 */

import React, { useState, useCallback } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Circle, X } from 'lucide-react';
import type { BlockData, NodeFilterBlockParams } from '../../types/blocks';

export const NodeFilterBlock: React.FC<NodeProps<BlockData>> = ({ data }) => {
  const params = data.params as NodeFilterBlockParams;
  const [selectedLabels, setSelectedLabels] = useState<string[]>(params.nodeLabels || []);
  const [minConfidence, setMinConfidence] = useState(params.minConfidence || 0);
  const [labelInput, setLabelInput] = useState('');
  const [useRegex, setUseRegex] = useState(false);
  const [regexError, setRegexError] = useState<string | null>(null);

  const handleAddLabel = useCallback(() => {
    const trimmed = labelInput.trim();
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

    if (!selectedLabels.includes(trimmed)) {
      const newSelection = [...selectedLabels, trimmed];
      setSelectedLabels(newSelection);
      params.nodeLabels = newSelection;
      setLabelInput('');
    }
  }, [labelInput, selectedLabels, params, useRegex]);

  const handleRemoveLabel = useCallback((label: string) => {
    const newSelection = selectedLabels.filter(l => l !== label);
    setSelectedLabels(newSelection);
    params.nodeLabels = newSelection;
  }, [selectedLabels, params]);

  const handleLabelKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddLabel();
    }
  }, [handleAddLabel]);

  const handleConfidenceChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newConfidence = parseFloat(e.target.value);
    setMinConfidence(newConfidence);
    params.minConfidence = newConfidence;
  }, [params]);

  return (
    <div className="px-4 py-3 rounded-lg border-2 border-purple-500 dark:border-purple-600 bg-card dark:bg-gray-800/95 shadow-lg min-w-[280px]">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <Circle className="w-4 h-4 text-purple-600 dark:text-purple-400" />
        <span className="font-medium text-sm text-card-foreground dark:text-gray-100">Filter by Node</span>
      </div>

      {/* Node Label Filter */}
      <div className="space-y-2 mb-3">
        <div className="flex items-center justify-between">
          <label className="text-xs text-muted-foreground dark:text-gray-400">
            Node Labels {!useRegex && '(case sensitive)'}
          </label>
          <label className="flex items-center gap-1 cursor-pointer">
            <input
              type="checkbox"
              checked={useRegex}
              onChange={(e) => {
                setUseRegex(e.target.checked);
                setRegexError(null);
              }}
              className="w-3 h-3 text-purple-500 dark:text-purple-400 rounded"
            />
            <span className="text-[10px] text-muted-foreground dark:text-gray-500">Regex</span>
          </label>
        </div>

        {/* Input field */}
        <div className="flex gap-1">
          <input
            type="text"
            value={labelInput}
            onChange={(e) => {
              setLabelInput(e.target.value);
              setRegexError(null);
            }}
            onKeyDown={handleLabelKeyDown}
            placeholder={useRegex ? "Regex pattern..." : "Type and press Enter..."}
            className={`flex-1 px-2 py-1 text-xs border ${regexError ? 'border-red-500 dark:border-red-400' : 'border-border dark:border-gray-600'} bg-background dark:bg-gray-900 text-foreground dark:text-gray-100 rounded focus:outline-none focus:ring-1 focus:ring-purple-500 dark:focus:ring-purple-400`}
          />
          <button
            onClick={handleAddLabel}
            disabled={!labelInput.trim()}
            className="px-2 py-1 text-xs bg-purple-500 dark:bg-purple-600 text-white rounded hover:bg-purple-600 dark:hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed"
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

        {/* Selected labels as chips */}
        {selectedLabels.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {selectedLabels.map(label => (
              <div
                key={label}
                className="flex items-center gap-1 px-2 py-0.5 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded text-xs font-mono"
              >
                <span>{label}</span>
                <button
                  onClick={() => handleRemoveLabel(label)}
                  className="hover:text-purple-900 dark:hover:text-purple-100"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Min Confidence Slider */}
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <label className="text-xs text-muted-foreground dark:text-gray-400">Min Confidence</label>
          <span className="text-xs font-medium text-purple-600 dark:text-purple-400">
            {minConfidence > 0 ? `${Math.round(minConfidence * 100)}%` : 'Any'}
          </span>
        </div>
        <input
          type="range"
          min="0"
          max="1"
          step="0.01"
          value={minConfidence}
          onChange={handleConfidenceChange}
          className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-purple-500 dark:accent-purple-400"
        />
      </div>

      {/* Handles */}
      <Handle type="target" position={Position.Left} className="w-3 h-3 bg-purple-500 dark:bg-purple-400" />
      <Handle type="source" position={Position.Right} className="w-3 h-3 bg-purple-500 dark:bg-purple-400" />
    </div>
  );
};
