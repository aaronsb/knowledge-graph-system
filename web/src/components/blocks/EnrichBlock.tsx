/**
 * Enrich Block - Fetch full concept details for proper visualization
 *
 * This block marks that the query results should be enriched with
 * full concept details (ontology, grounding strength, search terms)
 * to match Smart Search visualization quality.
 */

import React, { useState, useCallback } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Sparkles } from 'lucide-react';
import type { BlockData, EnrichBlockParams } from '../../types/blocks';

export const EnrichBlock: React.FC<NodeProps<BlockData>> = ({ data }) => {
  const params = data.params as EnrichBlockParams;
  const [fetchOntology, setFetchOntology] = useState(params.fetchOntology ?? true);
  const [fetchGrounding, setFetchGrounding] = useState(params.fetchGrounding ?? true);
  const [fetchSearchTerms, setFetchSearchTerms] = useState(params.fetchSearchTerms ?? false);

  const handleOntologyChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const checked = e.target.checked;
    setFetchOntology(checked);
    params.fetchOntology = checked;
  }, [params]);

  const handleGroundingChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const checked = e.target.checked;
    setFetchGrounding(checked);
    params.fetchGrounding = checked;
  }, [params]);

  const handleSearchTermsChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const checked = e.target.checked;
    setFetchSearchTerms(checked);
    params.fetchSearchTerms = checked;
  }, [params]);

  return (
    <div className="px-4 py-3 rounded-lg border-2 border-teal-500 dark:border-teal-600 bg-card dark:bg-gray-800/95 shadow-lg min-w-[280px]">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <Sparkles className="w-4 h-4 text-teal-600 dark:text-teal-400" />
        <span className="font-medium text-sm text-card-foreground dark:text-gray-100">Enrich Data</span>
      </div>

      {/* Description */}
      <p className="text-xs text-muted-foreground dark:text-gray-400 mb-3">
        Fetch full concept details for visualization
      </p>

      {/* Enrichment Options */}
      <div className="space-y-2">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={fetchOntology}
            onChange={handleOntologyChange}
            className="w-4 h-4 text-teal-600 dark:text-teal-400 rounded focus:ring-teal-500 dark:focus:ring-teal-400"
          />
          <div className="flex-1">
            <span className="text-sm text-card-foreground dark:text-gray-100">Ontology</span>
            <p className="text-[10px] text-muted-foreground dark:text-gray-500">Color-code by source document</p>
          </div>
        </label>

        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={fetchGrounding}
            onChange={handleGroundingChange}
            className="w-4 h-4 text-teal-600 dark:text-teal-400 rounded focus:ring-teal-500 dark:focus:ring-teal-400"
          />
          <div className="flex-1">
            <span className="text-sm text-card-foreground dark:text-gray-100">Grounding</span>
            <p className="text-[10px] text-muted-foreground dark:text-gray-500">Confidence/reliability score</p>
          </div>
        </label>

        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={fetchSearchTerms}
            onChange={handleSearchTermsChange}
            className="w-4 h-4 text-teal-600 dark:text-teal-400 rounded focus:ring-teal-500 dark:focus:ring-teal-400"
          />
          <div className="flex-1">
            <span className="text-sm text-card-foreground dark:text-gray-100">Search Terms</span>
            <p className="text-[10px] text-muted-foreground dark:text-gray-500">Alternative labels/aliases</p>
          </div>
        </label>
      </div>

      {/* Input/Output Handles */}
      <Handle type="target" position={Position.Left} className="w-3 h-3 bg-teal-500 dark:bg-teal-400" />
      <Handle type="source" position={Position.Right} className="w-3 h-3 bg-teal-500 dark:bg-teal-400" />
    </div>
  );
};
