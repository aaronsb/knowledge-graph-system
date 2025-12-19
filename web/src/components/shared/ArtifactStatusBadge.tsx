/**
 * Artifact Status Badge (ADR-083)
 *
 * Shows freshness/staleness status for artifacts.
 * Provides visual feedback when graph has changed since artifact was created.
 */

import React from 'react';
import { AlertCircle, CheckCircle, RefreshCw, Clock } from 'lucide-react';

interface ArtifactStatusBadgeProps {
  /** Whether the artifact is fresh (graph_epoch matches current) */
  isFresh: boolean;
  /** Whether a regeneration is in progress */
  isRegenerating?: boolean;
  /** Callback when regenerate button is clicked */
  onRegenerate?: () => void;
  /** Whether regeneration is available for this artifact type */
  canRegenerate?: boolean;
  /** Optional className for styling */
  className?: string;
  /** Show as compact badge or full status */
  variant?: 'badge' | 'inline' | 'full';
}

export const ArtifactStatusBadge: React.FC<ArtifactStatusBadgeProps> = ({
  isFresh,
  isRegenerating = false,
  onRegenerate,
  canRegenerate = true,
  className = '',
  variant = 'badge',
}) => {
  if (isRegenerating) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 text-xs text-muted-foreground ${className}`}
      >
        <RefreshCw className="w-3 h-3 animate-spin" />
        {variant !== 'badge' && <span>Regenerating...</span>}
      </span>
    );
  }

  if (isFresh) {
    if (variant === 'badge') {
      return (
        <span
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-500/10 text-green-600 text-xs ${className}`}
          title="Artifact is up to date with current graph"
        >
          <CheckCircle className="w-3 h-3" />
          Fresh
        </span>
      );
    }

    if (variant === 'inline') {
      return (
        <span
          className={`inline-flex items-center gap-1 text-xs text-green-600 ${className}`}
          title="Artifact is up to date with current graph"
        >
          <CheckCircle className="w-3 h-3" />
          Fresh
        </span>
      );
    }

    return (
      <div
        className={`flex items-center gap-2 px-3 py-2 rounded-lg bg-green-500/10 border border-green-500/20 ${className}`}
      >
        <CheckCircle className="w-4 h-4 text-green-600" />
        <span className="text-sm text-green-700">Artifact is up to date</span>
      </div>
    );
  }

  // Stale artifact
  if (variant === 'badge') {
    return (
      <span
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-yellow-500/10 text-yellow-600 text-xs cursor-help ${className}`}
        title="Graph has changed since this artifact was created"
      >
        <AlertCircle className="w-3 h-3" />
        Stale
      </span>
    );
  }

  if (variant === 'inline') {
    return (
      <span
        className={`inline-flex items-center gap-1 text-xs text-yellow-600 ${className}`}
        title="Graph has changed since this artifact was created"
      >
        <AlertCircle className="w-3 h-3" />
        Stale
        {canRegenerate && onRegenerate && (
          <button
            onClick={onRegenerate}
            className="ml-1 text-primary hover:underline"
          >
            Regenerate
          </button>
        )}
      </span>
    );
  }

  return (
    <div
      className={`flex items-center justify-between px-3 py-2 rounded-lg bg-yellow-500/10 border border-yellow-500/20 ${className}`}
    >
      <div className="flex items-center gap-2">
        <AlertCircle className="w-4 h-4 text-yellow-600" />
        <div>
          <span className="text-sm text-yellow-700">Artifact may be stale</span>
          <p className="text-xs text-yellow-600/80">
            Graph has changed since this was created
          </p>
        </div>
      </div>
      {canRegenerate && onRegenerate && (
        <button
          onClick={onRegenerate}
          className="flex items-center gap-1 px-3 py-1.5 text-sm bg-yellow-600 text-white rounded-md hover:bg-yellow-700 transition-colors"
        >
          <RefreshCw className="w-3 h-3" />
          Regenerate
        </button>
      )}
    </div>
  );
};

/**
 * Simple stale indicator icon for compact displays
 */
export const StaleIndicator: React.FC<{ isFresh: boolean; className?: string }> = ({
  isFresh,
  className = '',
}) => {
  if (isFresh) {
    return null;
  }

  return (
    <span title="Artifact may be stale - graph has changed">
      <Clock className={`w-3.5 h-3.5 text-yellow-500 ${className}`} />
    </span>
  );
};
