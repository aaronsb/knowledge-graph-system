/**
 * Filter Block - Filter results by ontology, relationship type, or confidence
 */

import React, { useState, useCallback } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Filter } from 'lucide-react';
import type { BlockData, FilterBlockParams } from '../../types/blocks';

export const FilterBlock: React.FC<NodeProps<BlockData>> = ({ data }) => {
  const params = data.params as FilterBlockParams;
  const [selectedOntologies, setSelectedOntologies] = useState<string[]>(params.ontologies || []);
  const [minConfidence, setMinConfidence] = useState(params.minConfidence || 0);

  const handleOntologyToggle = useCallback((ontology: string) => {
    setSelectedOntologies(prev => {
      const newSelection = prev.includes(ontology)
        ? prev.filter(o => o !== ontology)
        : [...prev, ontology];
      params.ontologies = newSelection;
      return newSelection;
    });
  }, [params]);

  const handleConfidenceChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newConfidence = parseFloat(e.target.value);
    setMinConfidence(newConfidence);
    params.minConfidence = newConfidence;
  }, [params]);

  // Hardcoded ontology options - could be fetched from API in production
  const availableOntologies = ['TBM Model', 'Research Papers', 'Default'];

  return (
    <div className="px-4 py-3 rounded-lg border-2 border-orange-500 bg-white shadow-lg min-w-[280px]">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <Filter className="w-4 h-4 text-orange-600" />
        <span className="font-medium text-sm">Filter Results</span>
      </div>

      {/* Ontology Filter */}
      <div className="space-y-2 mb-3">
        <label className="text-xs text-gray-600">Ontologies</label>
        <div className="space-y-1">
          {availableOntologies.map(ontology => (
            <label key={ontology} className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={selectedOntologies.includes(ontology)}
                onChange={() => handleOntologyToggle(ontology)}
                className="w-4 h-4 text-orange-500 rounded focus:ring-orange-500 accent-orange-500"
              />
              <span className="text-sm text-gray-700">{ontology}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Min Confidence Slider */}
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <label className="text-xs text-gray-600">Min Confidence</label>
          <span className="text-xs font-medium text-orange-600">
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
          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-orange-500"
        />
      </div>

      {/* Handles */}
      <Handle type="target" position={Position.Left} className="w-3 h-3 bg-orange-500" />
      <Handle type="source" position={Position.Right} className="w-3 h-3 bg-orange-500" />
    </div>
  );
};
