import React from 'react';
import { LoadingSpinner } from '../LoadingSpinner';

interface PathResultsProps {
  pathResults: any;
  selectedPath: any;
  isLoading: boolean;
  onSelectPath: (path: any) => void;
  onLoadClean: () => void;
  onLoadAdd: () => void;
}

export const PathResults: React.FC<PathResultsProps> = ({
  pathResults,
  selectedPath,
  isLoading,
  onSelectPath,
  onLoadClean,
  onLoadAdd,
}) => {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-4 text-sm text-muted-foreground">
        <LoadingSpinner />
        Searching...
      </div>
    );
  }

  if (!pathResults) return null;

  if (pathResults.error) {
    return (
      <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-lg text-center text-destructive text-sm">
        {pathResults.error}
      </div>
    );
  }

  if (pathResults.count === 0) {
    return (
      <div className="p-4 bg-muted rounded-lg text-center text-muted-foreground text-sm">
        No paths found. Try lowering similarity or increasing max hops.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="text-sm text-muted-foreground">
        Found {pathResults.count} path{pathResults.count > 1 ? 's' : ''} ({pathResults.paths[0].hops} hop{pathResults.paths[0].hops > 1 ? 's' : ''})
      </div>

      <div className="space-y-2">
        <div className="text-xs text-muted-foreground uppercase tracking-wide">Select a path:</div>
        {pathResults.paths.map((path: any, index: number) => (
          <button
            key={index}
            onClick={() => onSelectPath(path)}
            className={`w-full text-left p-3 rounded-lg border transition-colors ${
              selectedPath === path
                ? 'border-primary bg-primary/10'
                : 'border-border bg-muted hover:border-primary/50'
            }`}
          >
            <div className="text-sm font-mono">
              {path.nodes
                .filter((node: any) => node.id && node.id !== '')
                .map((node: any, i: number) => (
                  <span key={i}>
                    {i > 0 && <span className="text-muted-foreground"> &rarr; </span>}
                    <span className="font-medium">{node.label}</span>
                  </span>
                ))}
            </div>
            {path.score && (
              <div className="text-xs text-muted-foreground mt-1">
                Score: {(path.score * 100).toFixed(1)}%
              </div>
            )}
          </button>
        ))}
      </div>

      {selectedPath && (
        <div className="flex gap-2">
          <button
            onClick={onLoadClean}
            className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-sm font-medium"
          >
            Load into Clean Graph
          </button>
          <button
            onClick={onLoadAdd}
            className="flex-1 px-4 py-2 bg-secondary text-secondary-foreground rounded-lg hover:bg-secondary/80 transition-colors text-sm font-medium"
          >
            Add to Existing Graph
          </button>
        </div>
      )}
    </div>
  );
};
