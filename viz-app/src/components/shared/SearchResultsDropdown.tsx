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
    <div className="absolute top-full left-0 right-0 mt-2 bg-gray-50 dark:bg-gray-800 border-2 border-gray-300 dark:border-gray-600 rounded-lg shadow-xl max-h-80 overflow-y-auto z-50">
      {results.map((result) => (
        <button
          key={result.concept_id}
          onClick={() => onSelect(result)}
          className="w-full text-left px-4 py-3 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors border-b border-gray-200 dark:border-gray-700 last:border-b-0"
        >
          <div className="font-medium text-gray-900 dark:text-gray-100">{result.label}</div>
          <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Similarity: {(result.score * 100).toFixed(0)}% • {result.evidence_count} instances
          </div>
        </button>
      ))}
    </div>
  );
};
