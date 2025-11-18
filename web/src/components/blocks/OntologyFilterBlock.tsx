/**
 * Ontology Filter Block - Filter results by ontology
 */

import React, { useState, useCallback } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Filter, X } from 'lucide-react';
import type { BlockData, OntologyFilterBlockParams } from '../../types/blocks';

export const OntologyFilterBlock: React.FC<NodeProps<BlockData>> = ({ data }) => {
  const params = data.params as OntologyFilterBlockParams;
  const [selectedOntologies, setSelectedOntologies] = useState<string[]>(params.ontologies || []);
  const [ontologyInput, setOntologyInput] = useState('');
  const [useRegex, setUseRegex] = useState(false);
  const [regexError, setRegexError] = useState<string | null>(null);

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

  return (
    <div className="px-4 py-3 rounded-lg border-2 border-orange-500 dark:border-orange-600 bg-card dark:bg-gray-800/95 shadow-lg min-w-[280px]">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <Filter className="w-4 h-4 text-orange-600 dark:text-orange-400" />
        <span className="font-medium text-sm text-card-foreground dark:text-gray-100">Filter by Ontology</span>
      </div>

      {/* Ontology Filter */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-xs text-muted-foreground dark:text-gray-400">
            Ontologies {!useRegex && '(case sensitive)'}
          </label>
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

      {/* Handles */}
      <Handle type="target" position={Position.Left} className="w-3 h-3 bg-orange-500 dark:bg-orange-400" />
      <Handle type="source" position={Position.Right} className="w-3 h-3 bg-orange-500 dark:bg-orange-400" />
    </div>
  );
};
