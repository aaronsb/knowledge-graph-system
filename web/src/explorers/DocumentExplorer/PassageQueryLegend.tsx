/**
 * Passage Query Legend
 *
 * Shows committed passage search queries with color swatches,
 * visibility toggles, and delete buttons.
 */

import React from 'react';
import { Eye, EyeOff, X } from 'lucide-react';
import type { PassageQuery } from './types';

interface PassageQueryLegendProps {
  queries: PassageQuery[];
  onToggle: (id: string) => void;
  onDelete: (id: string) => void;
}

export const PassageQueryLegend: React.FC<PassageQueryLegendProps> = ({
  queries,
  onToggle,
  onDelete,
}) => {
  if (queries.length === 0) return null;

  return (
    <div className="border-b border-border">
      <div className="px-3 py-1.5 text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
        Queries
      </div>
      <div className="px-2 pb-2 space-y-0.5">
        {queries.map((q) => (
          <div
            key={q.id}
            className={`flex items-center gap-1.5 px-1.5 py-1 rounded text-xs group ${
              q.visible ? '' : 'opacity-40'
            }`}
          >
            <span
              className="inline-block w-2.5 h-2.5 rounded-full shrink-0"
              style={{ background: q.color }}
            />
            <span className="flex-1 truncate" title={q.text}>
              {q.text}
            </span>
            <span className="text-[10px] text-muted-foreground shrink-0">
              {q.results.length}
            </span>
            <button
              onClick={() => onToggle(q.id)}
              className="p-0.5 rounded hover:bg-accent text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity"
              title={q.visible ? 'Hide' : 'Show'}
            >
              {q.visible ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
            </button>
            <button
              onClick={() => onDelete(q.id)}
              className="p-0.5 rounded hover:bg-destructive/20 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity"
              title="Remove"
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};
