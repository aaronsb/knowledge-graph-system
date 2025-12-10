/**
 * Stats Panel - Shows node and edge count in upper right
 * Shared component for both 2D and 3D explorers
 */

import React from 'react';

export interface StatsPanelProps {
  nodeCount: number;
  edgeCount: number;
  className?: string;
}

export const StatsPanel: React.FC<StatsPanelProps> = ({ nodeCount, edgeCount, className }) => {
  return (
    <div className={`bg-card/95 border border-border rounded-lg shadow-xl px-3 py-2 text-sm ${className || ''}`}>
      <div className="text-card-foreground">
        {nodeCount} nodes • {edgeCount} edges
      </div>
    </div>
  );
};
