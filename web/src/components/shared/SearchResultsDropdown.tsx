/**
 * Search Results Dropdown - Reusable component for displaying concept search results
 */

import React from 'react';
import { getZIndexValue } from '../../config/zIndex';
import { formatGroundingWithConfidence } from '../../explorers/common/utils';
import type { ConceptSearchResult } from '../../types/polarity';

interface SearchResultsDropdownProps {
  results: ConceptSearchResult[];
  onSelect: (result: ConceptSearchResult) => void;
}

export const SearchResultsDropdown: React.FC<SearchResultsDropdownProps> = ({ results, onSelect }) => {
  return (
    <div
      className="absolute top-full left-0 right-0 mt-2 space-y-2 bg-background/95 backdrop-blur-sm rounded-lg p-2 shadow-lg max-h-80 overflow-y-auto"
      style={{ zIndex: getZIndexValue('searchResults') }}
    >
      {results.map((result) => {
        // Use score or similarity, whichever is available
        const similarityScore = result.score ?? result.similarity;
        // Format grounding with confidence (two-dimensional epistemic model)
        const grounding = formatGroundingWithConfidence(
          result.grounding_strength,
          result.grounding_display,
          result.confidence_score
        );
        return (
          <button
            key={result.concept_id}
            onClick={() => onSelect(result)}
            className="w-full text-left p-3 rounded-lg border border-border bg-muted hover:border-primary/50 transition-colors"
          >
            <div className="flex justify-between items-start">
              <div className="text-sm font-mono font-medium">{result.label}</div>
              {grounding && (
                <span className="text-xs font-medium ml-2 whitespace-nowrap" style={{ color: grounding.color }}>
                  {grounding.emoji} {grounding.label}
                </span>
              )}
            </div>
            {result.description && (
              <div className="text-xs text-muted-foreground mt-1">{result.description}</div>
            )}
            <div className="text-xs text-muted-foreground mt-1">
              {similarityScore !== undefined && `Similarity: ${(similarityScore * 100).toFixed(0)}%`}
              {similarityScore !== undefined && result.evidence_count !== undefined && ' • '}
              {result.evidence_count !== undefined && `${result.evidence_count} instances`}
              {grounding?.confidenceScore && ` • ${grounding.confidenceScore}`}
            </div>
          </button>
        );
      })}
    </div>
  );
};
