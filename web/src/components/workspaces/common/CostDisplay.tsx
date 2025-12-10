/**
 * CostDisplay - Format and display cost estimates
 *
 * Shows cost ranges for extraction and embedding operations.
 * Used in job approval workflow (ADR-014).
 */

import React from 'react';
import { DollarSign, Zap, Database } from 'lucide-react';
import type { CostEstimate, JobCost } from '../../../types/jobs';

interface CostDisplayProps {
  estimate?: CostEstimate;
  actual?: JobCost;
  compact?: boolean;
  className?: string;
}

// Format cost as currency string
const formatCost = (value: number): string => {
  if (value < 0.01) return '<$0.01';
  return `$${value.toFixed(2)}`;
};

// Format cost range
const formatCostRange = (low: number, high: number): string => {
  if (low === high) return formatCost(low);
  return `${formatCost(low)} - ${formatCost(high)}`;
};

export const CostDisplay: React.FC<CostDisplayProps> = ({
  estimate,
  actual,
  compact = false,
  className = '',
}) => {
  // Show actual costs if available
  if (actual) {
    if (compact) {
      return (
        <span className={`text-sm font-medium text-status-active ${className}`}>
          {actual.total}
        </span>
      );
    }

    return (
      <div className={`space-y-2 ${className}`}>
        <h4 className="text-sm font-semibold text-card-foreground dark:text-gray-200 flex items-center gap-2">
          <DollarSign className="w-4 h-4" />
          Actual Cost
        </h4>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div className="flex items-center gap-2">
            <Zap className="w-3 h-3 text-amber-500" />
            <span className="text-muted-foreground dark:text-gray-400">Extraction:</span>
          </div>
          <span className="text-card-foreground dark:text-gray-200">{actual.extraction}</span>

          <div className="flex items-center gap-2">
            <Database className="w-3 h-3 text-status-info" />
            <span className="text-muted-foreground dark:text-gray-400">Embeddings:</span>
          </div>
          <span className="text-card-foreground dark:text-gray-200">{actual.embeddings}</span>
        </div>
        <div className="pt-2 border-t border-border dark:border-gray-700">
          <div className="flex justify-between items-center">
            <span className="font-medium text-card-foreground dark:text-gray-200">Total:</span>
            <span className="font-bold text-status-active">{actual.total}</span>
          </div>
          {actual.extraction_model && (
            <div className="text-xs text-muted-foreground dark:text-gray-500 mt-1">
              {actual.extraction_model} / {actual.embedding_model}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Show estimate if available
  if (estimate) {
    const totalRange = formatCostRange(estimate.total.cost_low, estimate.total.cost_high);

    if (compact) {
      return (
        <span className={`text-sm font-medium text-amber-600 dark:text-amber-400 ${className}`}>
          ~{totalRange}
        </span>
      );
    }

    return (
      <div className={`space-y-2 ${className}`}>
        <h4 className="text-sm font-semibold text-card-foreground dark:text-gray-200 flex items-center gap-2">
          <DollarSign className="w-4 h-4" />
          Cost Estimate
        </h4>
        <div className="space-y-3 text-sm">
          {/* Extraction */}
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Zap className="w-3 h-3 text-amber-500" />
              <span className="font-medium text-card-foreground dark:text-gray-300">
                Extraction ({estimate.extraction.model})
              </span>
            </div>
            <div className="pl-5 text-muted-foreground dark:text-gray-400">
              <div>Tokens: {estimate.extraction.tokens_low.toLocaleString()} - {estimate.extraction.tokens_high.toLocaleString()}</div>
              <div>Cost: {formatCostRange(estimate.extraction.cost_low, estimate.extraction.cost_high)}</div>
            </div>
          </div>

          {/* Embeddings */}
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Database className="w-3 h-3 text-status-info" />
              <span className="font-medium text-card-foreground dark:text-gray-300">
                Embeddings ({estimate.embeddings.model})
              </span>
            </div>
            <div className="pl-5 text-muted-foreground dark:text-gray-400">
              <div>Concepts: {estimate.embeddings.concepts_low} - {estimate.embeddings.concepts_high}</div>
              <div>Cost: {formatCostRange(estimate.embeddings.cost_low, estimate.embeddings.cost_high)}</div>
            </div>
          </div>
        </div>

        {/* Total */}
        <div className="pt-2 border-t border-border dark:border-gray-700">
          <div className="flex justify-between items-center">
            <span className="font-medium text-card-foreground dark:text-gray-200">Estimated Total:</span>
            <span className="font-bold text-amber-600 dark:text-amber-400">{totalRange}</span>
          </div>
        </div>
      </div>
    );
  }

  return null;
};

// Simple inline cost badge
export const CostBadge: React.FC<{
  value: string | number;
  variant?: 'estimate' | 'actual';
  className?: string;
}> = ({ value, variant = 'actual', className = '' }) => {
  const colorClass = variant === 'estimate'
    ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300'
    : 'bg-status-active/20 text-status-active';

  const displayValue = typeof value === 'number' ? formatCost(value) : value;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${colorClass} ${className}`}>
      <DollarSign className="w-3 h-3" />
      {displayValue}
    </span>
  );
};

export default CostDisplay;
