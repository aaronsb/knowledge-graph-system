/**
 * Search Bar Component
 *
 * Provides concept search with autocomplete.
 */

import React, { useState, useEffect } from 'react';
import { Search, Loader2 } from 'lucide-react';
import { useSearchConcepts } from '../../hooks/useGraphData';
import { useGraphStore } from '../../store/graphStore';

export const SearchBar: React.FC = () => {
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const { setFocusedNodeId } = useGraphStore();

  const { data: searchResults, isLoading } = useSearchConcepts(debouncedQuery, {
    limit: 10,
    minSimilarity: 0.5, // Lower threshold for better results
  });

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query);
    }, 300);

    return () => clearTimeout(timer);
  }, [query]);

  const handleSelectConcept = (conceptId: string) => {
    setFocusedNodeId(conceptId);
    setQuery('');
  };

  return (
    <div className="relative">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-muted-foreground" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search concepts..."
          className="w-full pl-10 pr-10 py-2 rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-ring"
        />
        {isLoading && (
          <Loader2 className="absolute right-3 top-1/2 transform -translate-y-1/2 w-5 h-5 animate-spin text-muted-foreground" />
        )}
      </div>

      {/* Search Results Dropdown */}
      {debouncedQuery && searchResults && searchResults.results && searchResults.results.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-card border border-border rounded-lg shadow-lg max-h-80 overflow-y-auto z-50">
          {searchResults.results.map((result: any) => (
            <button
              key={result.concept_id}
              onClick={() => handleSelectConcept(result.concept_id)}
              className="w-full text-left px-4 py-3 hover:bg-accent transition-colors border-b border-border last:border-b-0"
            >
              <div className="font-medium">{result.label}</div>
              <div className="text-sm text-muted-foreground mt-1">
                Similarity: {(result.score * 100).toFixed(0)}% • {result.evidence_count} instances
              </div>
            </button>
          ))}
        </div>
      )}

      {debouncedQuery && searchResults && searchResults.results && searchResults.results.length === 0 && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-card border border-border rounded-lg shadow-lg p-4 z-50">
          <div className="text-center text-muted-foreground">
            {searchResults.below_threshold_count ? (
              <>
                <div className="font-medium mb-2">No results at 50% similarity</div>
                <div className="text-sm">
                  Found {searchResults.below_threshold_count} concept{searchResults.below_threshold_count > 1 ? 's' : ''} at lower similarity
                  {searchResults.suggested_threshold && (
                    <> (try {(searchResults.suggested_threshold * 100).toFixed(0)}%)</>
                  )}
                </div>
              </>
            ) : (
              'No results found'
            )}
          </div>
        </div>
      )}
    </div>
  );
};
