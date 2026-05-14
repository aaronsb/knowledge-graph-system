import React, { useEffect, useState } from 'react';
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
  /**
   * True when the parent has a locked selection for this input. When set,
   * the suggestion dropdown is dismissed — picking a result is a terminal
   * action, not a hover-preview. Pressing Enter on a selected, filled input
   * re-opens the dropdown for reconsidering without clearing the text or
   * selection.
   */
  isSelected?: boolean;
}

/**
 * Concept autocomplete input.
 *
 * Dropdown lifecycle:
 *  - User types        → `onQueryChange` fires; parent typically clears any
 *                        locked selection, so `isSelected` flips to false and
 *                        the dropdown reflects the fresh search.
 *  - User picks        → `onSelect` fires; parent sets selection; dropdown
 *                        dismisses on the next render.
 *  - User presses Enter on a selected, non-empty input → dropdown re-opens
 *                        with the existing (cached) results so they can
 *                        reconsider without retyping. Picking again or
 *                        editing the text closes it.
 *
 * @verified 084b7288
 */
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
  isSelected = false,
}) => {
  // Tracks an explicit "show me the suggestions again" request that survives
  // until the next selection or text edit. Independent from `isSelected` so
  // Enter can override the auto-dismiss.
  const [reopenRequested, setReopenRequested] = useState(false);

  // When a fresh selection locks in, drop any pending reopen state so the
  // dropdown actually dismisses.
  useEffect(() => {
    if (isSelected) setReopenRequested(false);
  }, [isSelected]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && isSelected && debouncedQuery) {
      e.preventDefault();
      setReopenRequested(true);
    }
  };

  const handleSelect = (concept: any) => {
    setReopenRequested(false);
    onSelect(concept);
  };

  const showDropdown =
    !!debouncedQuery &&
    !!results &&
    results.length > 0 &&
    (!isSelected || reopenRequested);

  // Empty-state content only fires while actively searching — not after a
  // selection lands.
  const showEmpty =
    !!debouncedQuery && !!results && results.length === 0 && !isSelected;

  return (
    <div className="relative space-y-3">
      <div className="relative">
        <Icon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-muted-foreground" />
        <input
          type="text"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="w-full pl-10 pr-10 py-2 rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-ring"
        />
        {isLoading && (
          <LoadingSpinner className="absolute right-3 top-1/2 transform -translate-y-1/2 text-muted-foreground" />
        )}
      </div>

      {showDropdown && (
        <SearchResultsDropdown results={results!} onSelect={handleSelect} />
      )}

      {showEmpty && noResultsContent}
    </div>
  );
};
