/**
 * Search Results Dropdown - Reusable component for displaying concept search results
 */

import React from 'react';
import { getZIndexClass } from '../../config/zIndex';

interface SearchResult {
  concept_id: string;
  label: string;
  description?: string;
  score: number;
  evidence_count: number;
}

interface SearchResultsDropdownProps {
  results: SearchResult[];
  onSelect: (result: SearchResult) => void;
}

export const SearchResultsDropdown: React.FC<SearchResultsDropdownProps> = ({ results, onSelect }) => {
  return (
    <div className={`absolute top-full left-0 right-0 mt-2 space-y-2 bg-background/95 backdrop-blur-sm rounded-lg p-2 shadow-lg max-h-80 overflow-y-auto ${getZIndexClass('searchResults')}`}>
      {results.map((result) => (
        <button
          key={result.concept_id}
          onClick={() => onSelect(result)}
          className="w-full text-left p-3 rounded-lg border border-border bg-muted hover:border-primary/50 transition-colors"
        >
          <div className="text-sm font-mono font-medium">{result.label}</div>
          {result.description && (
            <div className="text-xs text-muted-foreground mt-1">{result.description}</div>
          )}
          <div className="text-xs text-muted-foreground mt-1">
            Similarity: {(result.score * 100).toFixed(0)}% • {result.evidence_count} instances
          </div>
        </button>
      ))}
    </div>
  );
};
