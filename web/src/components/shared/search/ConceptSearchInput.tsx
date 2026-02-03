import React from 'react';
import { LoadingSpinner } from '../LoadingSpinner';
import { SearchResultsDropdown } from '../SearchResultsDropdown';

interface ConceptSearchInputProps {
  query: string;
  onQueryChange: (query: string) => void;
  placeholder: string;
  icon: React.ComponentType<{ className?: string }>;
  isLoading: boolean;
  results: any[] | undefined;
  debouncedQuery: string;
  onSelect: (concept: any) => void;
  noResultsContent?: React.ReactNode;
}

export const ConceptSearchInput: React.FC<ConceptSearchInputProps> = ({
  query,
  onQueryChange,
  placeholder,
  icon: Icon,
  isLoading,
  results,
  debouncedQuery,
  onSelect,
  noResultsContent,
}) => (
  <div className="relative space-y-3">
    <div className="relative">
      <Icon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-muted-foreground" />
      <input
        type="text"
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        placeholder={placeholder}
        className="w-full pl-10 pr-10 py-2 rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-ring"
      />
      {isLoading && (
        <LoadingSpinner className="absolute right-3 top-1/2 transform -translate-y-1/2 text-muted-foreground" />
      )}
    </div>

    {debouncedQuery && results && results.length > 0 && (
      <SearchResultsDropdown
        results={results}
        onSelect={onSelect}
      />
    )}

    {debouncedQuery && results && results.length === 0 && noResultsContent}
  </div>
);
