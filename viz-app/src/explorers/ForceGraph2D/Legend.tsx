/**
 * Legend Component
 *
 * Displays dynamic legend for node colors and edge colors
 * with collapsible sections and vertical resize capability.
 */

import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import * as d3 from 'd3';
import { categoryColors } from '../../config/categoryColors';
import type { GraphData } from '../../types/graph';

interface LegendProps {
  data: GraphData;
  nodeColorMode: 'ontology' | 'degree' | 'centrality';
}

export const Legend: React.FC<LegendProps> = ({ data, nodeColorMode }) => {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(['nodeColors', 'edgeColors'])
  );

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  };

  // Extract ontologies and their colors
  const ontologies = Array.from(new Set(data.nodes.map((n) => n.group))).sort();
  const ontologyColors = new Map<string, string>();
  data.nodes.forEach((n) => {
    if (!ontologyColors.has(n.group)) {
      ontologyColors.set(n.group, n.color);
    }
  });

  // Extract edge categories
  const categories = Array.from(new Set(data.links.map((l) => l.category).filter(Boolean))).sort();

  // Generate gradient string from D3 color scale
  const generateGradient = (interpolator: (t: number) => string, steps: number = 10) => {
    const colors = Array.from({ length: steps }, (_, i) => interpolator(i / (steps - 1)));
    return `linear-gradient(to right, ${colors.join(', ')})`;
  };

  // Render node color legend based on mode
  const renderNodeColorLegend = () => {
    if (nodeColorMode === 'ontology') {
      return (
        <div className="space-y-1.5">
          {ontologies.map((ontology) => (
            <div key={ontology} className="flex items-center gap-2 text-xs">
              <div
                className="w-3 h-3 rounded-full flex-shrink-0"
                style={{ backgroundColor: ontologyColors.get(ontology) || '#6b7280' }}
              />
              <span className="text-gray-200 truncate" title={ontology}>
                {ontology}
              </span>
            </div>
          ))}
        </div>
      );
    } else if (nodeColorMode === 'degree') {
      return (
        <div className="space-y-2">
          <div className="text-xs text-gray-300 font-medium">Degree (Connections)</div>
          <div
            className="h-4 rounded"
            style={{
              background: generateGradient(d3.interpolateViridis),
            }}
          />
          <div className="flex justify-between text-[10px] text-gray-400">
            <span>Low</span>
            <span>High</span>
          </div>
        </div>
      );
    } else if (nodeColorMode === 'centrality') {
      return (
        <div className="space-y-2">
          <div className="text-xs text-gray-300 font-medium">Centrality</div>
          <div
            className="h-4 rounded"
            style={{
              background: generateGradient(d3.interpolatePlasma),
            }}
          />
          <div className="flex justify-between text-[10px] text-gray-400">
            <span>Low</span>
            <span>High</span>
          </div>
        </div>
      );
    }
  };

  return (
    <div
      className="absolute top-4 left-4 bg-gray-800/95 border border-gray-600 rounded-lg shadow-xl z-10 flex flex-col"
      style={{ width: '240px', maxHeight: '95vh' }}
    >
      {/* Content */}
      <div className="overflow-y-auto overflow-x-hidden p-3 space-y-3">
        {/* Node Colors Section */}
        <div className="border-b border-gray-700 pb-3">
          <button
            onClick={() => toggleSection('nodeColors')}
            className="w-full flex items-center justify-between text-sm font-medium text-gray-200 hover:text-gray-100 transition-colors"
          >
            <span>Node Colors</span>
            {expandedSections.has('nodeColors') ? (
              <ChevronDown size={14} className="text-gray-500" />
            ) : (
              <ChevronRight size={14} className="text-gray-500" />
            )}
          </button>
          {expandedSections.has('nodeColors') && (
            <div className="mt-3">{renderNodeColorLegend()}</div>
          )}
        </div>

        {/* Edge Colors Section */}
        <div>
          <button
            onClick={() => toggleSection('edgeColors')}
            className="w-full flex items-center justify-between text-sm font-medium text-gray-200 hover:text-gray-100 transition-colors"
          >
            <span>Edge Categories</span>
            {expandedSections.has('edgeColors') ? (
              <ChevronDown size={14} className="text-gray-500" />
            ) : (
              <ChevronRight size={14} className="text-gray-500" />
            )}
          </button>
          {expandedSections.has('edgeColors') && (
            <div className="mt-3 space-y-1.5">
              {categories.map((category) => {
                const color = categoryColors[category || 'default'] || categoryColors.default;
                return (
                  <div key={category} className="text-xs">
                    <span style={{ color }} className="font-medium capitalize">
                      {category}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
