/**
 * ProgressIndicator - Job progress visualization
 *
 * Displays progress for ingestion jobs with chunk counts,
 * concept statistics, and hit rate.
 */

import React from 'react';
import { FileText, Lightbulb, Link2, TrendingUp } from 'lucide-react';
import type { JobProgress } from '../../../types/jobs';

interface ProgressIndicatorProps {
  progress?: JobProgress;
  variant?: 'bar' | 'detailed' | 'compact';
  className?: string;
}

// Calculate hit rate (existing concepts reused)
const calculateHitRate = (created: number, linked: number): number => {
  const total = created + linked;
  if (total === 0) return 0;
  return Math.round((linked / total) * 100);
};

export const ProgressIndicator: React.FC<ProgressIndicatorProps> = ({
  progress,
  variant = 'bar',
  className = '',
}) => {
  if (!progress) return null;

  const percent = progress.percent ?? 0;
  const chunksProcessed = progress.chunks_processed ?? 0;
  const chunksTotal = progress.chunks_total ?? 0;
  const conceptsCreated = progress.concepts_created ?? 0;
  const conceptsLinked = progress.concepts_linked ?? 0;
  const conceptsTotal = conceptsCreated + conceptsLinked;
  const hitRate = calculateHitRate(conceptsCreated, conceptsLinked);
  const relationships = progress.relationships_created ?? 0;

  // Compact: just the bar
  if (variant === 'compact') {
    return (
      <div className={`w-full ${className}`}>
        <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-status-info transition-all duration-300"
            style={{ width: `${percent}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-muted-foreground dark:text-gray-400 mt-1">
          <span>{percent}%</span>
          <span>{chunksProcessed}/{chunksTotal} chunks</span>
        </div>
      </div>
    );
  }

  // Bar: progress bar with summary
  if (variant === 'bar') {
    return (
      <div className={`space-y-2 ${className}`}>
        {/* Progress bar */}
        <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-status-info to-primary transition-all duration-300"
            style={{ width: `${percent}%` }}
          />
        </div>

        {/* Summary line */}
        <div className="flex justify-between text-sm">
          <span className="text-card-foreground dark:text-gray-200 font-medium">
            {percent}% complete
          </span>
          <span className="text-muted-foreground dark:text-gray-400">
            {chunksProcessed}/{chunksTotal} chunks
          </span>
        </div>

        {/* Stats row */}
        {conceptsTotal > 0 && (
          <div className="flex gap-4 text-xs text-muted-foreground dark:text-gray-400">
            <span className="flex items-center gap-1">
              <Lightbulb className="w-3 h-3" />
              {conceptsTotal} concepts
            </span>
            {hitRate > 0 && (
              <span className="flex items-center gap-1 text-status-active">
                <TrendingUp className="w-3 h-3" />
                {hitRate}% reused
              </span>
            )}
            {relationships > 0 && (
              <span className="flex items-center gap-1">
                <Link2 className="w-3 h-3" />
                {relationships} rels
              </span>
            )}
          </div>
        )}
      </div>
    );
  }

  // Detailed: full breakdown with grid
  return (
    <div className={`space-y-3 ${className}`}>
      {/* Progress bar */}
      <div>
        <div className="flex justify-between text-sm mb-1">
          <span className="font-medium text-card-foreground dark:text-gray-200">
            {progress.stage || 'Processing'}
          </span>
          <span className="text-muted-foreground dark:text-gray-400">{percent}%</span>
        </div>
        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-status-info to-primary transition-all duration-300 relative"
            style={{ width: `${percent}%` }}
          >
            {/* Animated shine effect */}
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-pulse" />
          </div>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-3">
        {/* Chunks */}
        <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-2">
          <div className="flex items-center gap-2 text-muted-foreground dark:text-gray-400 text-xs mb-1">
            <FileText className="w-3 h-3" />
            Chunks
          </div>
          <div className="text-lg font-semibold text-card-foreground dark:text-gray-200">
            {chunksProcessed}
            <span className="text-sm font-normal text-muted-foreground dark:text-gray-400">
              /{chunksTotal}
            </span>
          </div>
        </div>

        {/* Concepts */}
        <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-2">
          <div className="flex items-center gap-2 text-muted-foreground dark:text-gray-400 text-xs mb-1">
            <Lightbulb className="w-3 h-3" />
            Concepts
          </div>
          <div className="text-lg font-semibold text-card-foreground dark:text-gray-200">
            {conceptsTotal}
            {hitRate > 0 && (
              <span className="text-xs font-normal text-status-active ml-1">
                ({hitRate}% hit)
              </span>
            )}
          </div>
        </div>

        {/* Relationships */}
        <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-2">
          <div className="flex items-center gap-2 text-muted-foreground dark:text-gray-400 text-xs mb-1">
            <Link2 className="w-3 h-3" />
            Relationships
          </div>
          <div className="text-lg font-semibold text-card-foreground dark:text-gray-200">
            {relationships}
          </div>
        </div>

        {/* Hit Rate */}
        <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-2">
          <div className="flex items-center gap-2 text-muted-foreground dark:text-gray-400 text-xs mb-1">
            <TrendingUp className="w-3 h-3" />
            Reuse Rate
          </div>
          <div className={`text-lg font-semibold ${hitRate > 50 ? 'text-status-active' : 'text-card-foreground dark:text-gray-200'}`}>
            {hitRate}%
          </div>
        </div>
      </div>

      {/* Message if present */}
      {progress.message && (
        <div className="text-sm text-muted-foreground dark:text-gray-400 italic">
          {progress.message}
        </div>
      )}
    </div>
  );
};

// Simple progress bar only
export const ProgressBar: React.FC<{
  percent: number;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}> = ({ percent, size = 'md', className = '' }) => {
  const heightClass = {
    sm: 'h-1',
    md: 'h-2',
    lg: 'h-3',
  }[size];

  return (
    <div className={`w-full bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden ${className}`}>
      <div
        className={`${heightClass} bg-status-info transition-all duration-300`}
        style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
      />
    </div>
  );
};

export default ProgressIndicator;
