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
  const [similarity, setSimilarity] = useState(0.5); // 50% default
  const { setFocusedNodeId } = useGraphStore();

  const { data: searchResults, isLoading } = useSearchConcepts(debouncedQuery, {
    limit: 10,
    minSimilarity: similarity,
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
    <div className="relative space-y-3">
      {/* Search Input */}
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

      {/* Threshold Slider */}
      <div className="flex items-center gap-3 px-1">
        <label className="text-sm text-muted-foreground whitespace-nowrap">
          Similarity:
        </label>
        <input
          type="range"
          min="0"
          max="100"
          value={similarity * 100}
          onChange={(e) => setSimilarity(parseInt(e.target.value) / 100)}
          className="flex-1 h-2 bg-muted rounded-lg appearance-none cursor-pointer
                     [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
                     [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary
                     [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4
                     [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-0"
        />
        <span className="text-sm font-medium min-w-[3ch] text-right">
          {(similarity * 100).toFixed(0)}%
        </span>
        {searchResults && searchResults.results && (
          <span className="text-xs text-muted-foreground whitespace-nowrap">
            ({searchResults.results.length} results)
          </span>
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
          <div className="text-center">
            {searchResults.below_threshold_count ? (
              <div className="space-y-3">
                <div className="text-muted-foreground">
                  <div className="font-medium mb-2">No results at {(similarity * 100).toFixed(0)}% similarity</div>
                  <div className="text-sm">
                    Found {searchResults.below_threshold_count} concept{searchResults.below_threshold_count > 1 ? 's' : ''} at lower similarity
                  </div>
                </div>
                {searchResults.suggested_threshold && (
                  <button
                    onClick={() => setSimilarity(searchResults.suggested_threshold)}
                    className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-sm font-medium"
                  >
                    Try {(searchResults.suggested_threshold * 100).toFixed(0)}% Similarity
                  </button>
                )}
                {searchResults.top_match && (
                  <div className="text-left p-3 bg-muted rounded-lg">
                    <div className="text-xs text-muted-foreground mb-1">Top match:</div>
                    <div className="font-medium">{searchResults.top_match.label}</div>
                    <div className="text-sm text-muted-foreground mt-1">
                      {(searchResults.top_match.score * 100).toFixed(0)}% similarity
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-muted-foreground">No results found</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
