/**
 * Filter Block - Filter results by ontology, relationship type, or confidence
 */

import React, { useState, useCallback } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Filter, X, HelpCircle } from 'lucide-react';
import type { BlockData, FilterBlockParams } from '../../types/blocks';

export const FilterBlock: React.FC<NodeProps<BlockData>> = ({ data }) => {
  const params = data.params as FilterBlockParams;
  const [selectedOntologies, setSelectedOntologies] = useState<string[]>(params.ontologies || []);
  const [minConfidence, setMinConfidence] = useState(params.minConfidence || 0);
  const [ontologyInput, setOntologyInput] = useState('');
  const [useRegex, setUseRegex] = useState(false);
  const [regexError, setRegexError] = useState<string | null>(null);
  const [showRegexHelp, setShowRegexHelp] = useState(false);

  const handleAddOntology = useCallback(() => {
    const trimmed = ontologyInput.trim();
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

    if (!selectedOntologies.includes(trimmed)) {
      const newSelection = [...selectedOntologies, trimmed];
      setSelectedOntologies(newSelection);
      params.ontologies = newSelection;
      setOntologyInput('');
    }
  }, [ontologyInput, selectedOntologies, params, useRegex]);

  const handleRemoveOntology = useCallback((ontology: string) => {
    const newSelection = selectedOntologies.filter(o => o !== ontology);
    setSelectedOntologies(newSelection);
    params.ontologies = newSelection;
  }, [selectedOntologies, params]);

  const handleOntologyKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddOntology();
    }
  }, [handleAddOntology]);

  const handleConfidenceChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newConfidence = parseFloat(e.target.value);
    setMinConfidence(newConfidence);
    params.minConfidence = newConfidence;
  }, [params]);

  return (
    <div className="px-4 py-3 rounded-lg border-2 border-orange-500 dark:border-orange-600 bg-card dark:bg-gray-800/95 shadow-lg min-w-[280px]">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <Filter className="w-4 h-4 text-orange-600 dark:text-orange-400" />
        <span className="font-medium text-sm text-card-foreground dark:text-gray-100">Filter Results</span>
        <span className="ml-auto px-1.5 py-0.5 bg-orange-100 dark:bg-orange-900/50 text-orange-700 dark:text-orange-300 rounded text-[10px] font-medium">
          CYPHER
        </span>
      </div>

      {/* Ontology Filter */}
      <div className="space-y-2 mb-3">
        <div className="flex items-center justify-between">
          <label className="text-xs text-muted-foreground dark:text-gray-400">
            Ontologies {!useRegex && '(case sensitive)'}
          </label>
          <div className="flex items-center gap-1">
            <label className="flex items-center gap-1 cursor-pointer">
              <input
                type="checkbox"
                checked={useRegex}
                onChange={(e) => {
                  setUseRegex(e.target.checked);
                  setRegexError(null);
                }}
                className="w-3 h-3 text-orange-500 dark:text-orange-400 rounded"
              />
              <span className="text-[10px] text-muted-foreground dark:text-gray-500">Regex</span>
            </label>
            {useRegex && (
              <div className="relative">
                <button
                  onClick={() => setShowRegexHelp(!showRegexHelp)}
                  onPointerDown={(e) => e.stopPropagation()}
                  className="p-0.5 hover:bg-orange-100 dark:hover:bg-orange-900/30 rounded"
                  title="Regex help"
                >
                  <HelpCircle className="w-3 h-3 text-muted-foreground dark:text-gray-500" />
                </button>
                {showRegexHelp && (
                  <div className="absolute right-0 top-5 z-50 w-48 p-2 bg-card dark:bg-gray-800 border border-border dark:border-gray-600 rounded shadow-lg text-[10px]">
                    <div className="font-medium text-card-foreground dark:text-gray-100 mb-1">Regex Examples</div>
                    <div className="space-y-0.5 text-muted-foreground dark:text-gray-400">
                      <div><code className="text-orange-600 dark:text-orange-400">.*</code> any characters</div>
                      <div><code className="text-orange-600 dark:text-orange-400">^prefix</code> starts with</div>
                      <div><code className="text-orange-600 dark:text-orange-400">suffix$</code> ends with</div>
                      <div><code className="text-orange-600 dark:text-orange-400">a|b</code> a or b</div>
                      <div><code className="text-orange-600 dark:text-orange-400">(?i)</code> case insensitive</div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Input field */}
        <div className="flex gap-1">
          <input
            type="text"
            value={ontologyInput}
            onChange={(e) => {
              setOntologyInput(e.target.value);
              setRegexError(null);
            }}
            onKeyDown={handleOntologyKeyDown}
            placeholder={useRegex ? "Regex pattern..." : "Type and press Enter..."}
            className={`flex-1 px-2 py-1 text-xs border ${regexError ? 'border-red-500 dark:border-red-400' : 'border-border dark:border-gray-600'} bg-background dark:bg-gray-900 text-foreground dark:text-gray-100 rounded focus:outline-none focus:ring-1 focus:ring-orange-500 dark:focus:ring-orange-400`}
          />
          <button
            onClick={handleAddOntology}
            disabled={!ontologyInput.trim()}
            className="px-2 py-1 text-xs bg-orange-500 dark:bg-orange-600 text-white rounded hover:bg-orange-600 dark:hover:bg-orange-500 disabled:opacity-50 disabled:cursor-not-allowed"
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

        {/* Selected ontologies as chips */}
        {selectedOntologies.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {selectedOntologies.map(ontology => (
              <div
                key={ontology}
                className="flex items-center gap-1 px-2 py-0.5 bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300 rounded text-xs font-mono"
              >
                <span>{ontology}</span>
                <button
                  onClick={() => handleRemoveOntology(ontology)}
                  className="hover:text-orange-900 dark:hover:text-orange-100"
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
          <span className="text-xs font-medium text-orange-600 dark:text-orange-400">
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
          className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-orange-500 dark:accent-orange-400"
        />
      </div>

      {/* Handles */}
      <Handle type="target" position={Position.Left} className="w-3 h-3 bg-orange-500 dark:bg-orange-400" />
      <Handle type="source" position={Position.Right} className="w-3 h-3 bg-orange-500 dark:bg-orange-400" />
    </div>
  );
};
