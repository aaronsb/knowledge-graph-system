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
    <div className={`bg-gray-800/95 border border-gray-600 rounded-lg shadow-xl px-3 py-2 text-sm ${className || ''}`}>
      <div className="text-gray-200">
        {nodeCount} nodes • {edgeCount} edges
      </div>
    </div>
  );
};
