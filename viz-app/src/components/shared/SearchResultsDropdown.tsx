/**
 * Search Results Dropdown - Reusable component for displaying concept search results
 */

import React from 'react';

interface SearchResult {
  concept_id: string;
  label: string;
  score: number;
  evidence_count: number;
}

interface SearchResultsDropdownProps {
  results: SearchResult[];
  onSelect: (result: SearchResult) => void;
}

export const SearchResultsDropdown: React.FC<SearchResultsDropdownProps> = ({ results, onSelect }) => {
  return (
    <div className="absolute top-full left-0 right-0 mt-2 bg-card border border-border rounded-lg shadow-lg max-h-80 overflow-y-auto z-50">
      {results.map((result) => (
        <button
          key={result.concept_id}
          onClick={() => onSelect(result)}
          className="w-full text-left px-4 py-3 hover:bg-accent transition-colors border-b border-border last:border-b-0"
        >
          <div className="font-medium">{result.label}</div>
          <div className="text-sm text-muted-foreground mt-1">
            Similarity: {(result.score * 100).toFixed(0)}% • {result.evidence_count} instances
          </div>
        </button>
      ))}
    </div>
  );
};
