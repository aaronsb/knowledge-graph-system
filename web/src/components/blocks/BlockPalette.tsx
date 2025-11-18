/**
 * Block Palette - Sidebar with draggable block types
 */

import React from 'react';
import { Search, Network, Filter, GitBranch, Circle, Hash, Play, Square, Merge, Split, Ban, Sparkles } from 'lucide-react';
import type { BlockType } from '../../types/blocks';

interface BlockPaletteProps {
  onAddBlock: (type: BlockType) => void;
}

interface PaletteBlock {
  type: BlockType;
  icon: React.ElementType;
  label: string;
  description: string;
  color: string;
}

const paletteBlocks: PaletteBlock[] = [
  // Flow Control
  {
    type: 'start',
    icon: Play,
    label: 'Start',
    description: 'Query entry point',
    color: 'green',
  },
  {
    type: 'end',
    icon: Square,
    label: 'End',
    description: 'Query exit point',
    color: 'red',
  },
  // Query Blocks
  {
    type: 'search',
    icon: Search,
    label: 'Search',
    description: 'Find concepts by text query',
    color: 'blue',
  },
  {
    type: 'neighborhood',
    icon: Network,
    label: 'Neighborhood',
    description: 'Expand N hops from concepts',
    color: 'purple',
  },
  // Filter Blocks
  {
    type: 'filterOntology',
    icon: Filter,
    label: 'Filter Ontology',
    description: 'Filter by ontology name',
    color: 'orange',
  },
  {
    type: 'filterEdge',
    icon: GitBranch,
    label: 'Filter Edge',
    description: 'Filter by relationship type',
    color: 'blue',
  },
  {
    type: 'filterNode',
    icon: Circle,
    label: 'Filter Node',
    description: 'Filter by node label & confidence',
    color: 'purple',
  },
  // Boolean Logic
  {
    type: 'and',
    icon: Merge,
    label: 'AND',
    description: 'Combine multiple inputs',
    color: 'amber',
  },
  {
    type: 'or',
    icon: Split,
    label: 'OR',
    description: 'Alternative inputs',
    color: 'cyan',
  },
  {
    type: 'not',
    icon: Ban,
    label: 'NOT',
    description: 'Negate input',
    color: 'rose',
  },
  // Utility
  {
    type: 'limit',
    icon: Hash,
    label: 'Limit',
    description: 'Limit number of results',
    color: 'gray',
  },
  {
    type: 'enrich',
    icon: Sparkles,
    label: 'Enrich',
    description: 'Fetch full concept details',
    color: 'teal',
  },
];

const colorClasses: Record<string, { bg: string; border: string; text: string; hover: string }> = {
  blue: {
    bg: 'bg-blue-50 dark:bg-blue-900/30',
    border: 'border-blue-300 dark:border-blue-700',
    text: 'text-blue-700 dark:text-blue-300',
    hover: 'hover:bg-blue-100 dark:hover:bg-blue-900/50',
  },
  purple: {
    bg: 'bg-purple-50 dark:bg-purple-900/30',
    border: 'border-purple-300 dark:border-purple-700',
    text: 'text-purple-700 dark:text-purple-300',
    hover: 'hover:bg-purple-100 dark:hover:bg-purple-900/50',
  },
  orange: {
    bg: 'bg-orange-50 dark:bg-orange-900/30',
    border: 'border-orange-300 dark:border-orange-700',
    text: 'text-orange-700 dark:text-orange-300',
    hover: 'hover:bg-orange-100 dark:hover:bg-orange-900/50',
  },
  green: {
    bg: 'bg-green-50 dark:bg-green-900/30',
    border: 'border-green-300 dark:border-green-700',
    text: 'text-green-700 dark:text-green-300',
    hover: 'hover:bg-green-100 dark:hover:bg-green-900/50',
  },
  red: {
    bg: 'bg-red-50 dark:bg-red-900/30',
    border: 'border-red-300 dark:border-red-700',
    text: 'text-red-700 dark:text-red-300',
    hover: 'hover:bg-red-100 dark:hover:bg-red-900/50',
  },
  amber: {
    bg: 'bg-amber-50 dark:bg-amber-900/30',
    border: 'border-amber-300 dark:border-amber-700',
    text: 'text-amber-700 dark:text-amber-300',
    hover: 'hover:bg-amber-100 dark:hover:bg-amber-900/50',
  },
  cyan: {
    bg: 'bg-cyan-50 dark:bg-cyan-900/30',
    border: 'border-cyan-300 dark:border-cyan-700',
    text: 'text-cyan-700 dark:text-cyan-300',
    hover: 'hover:bg-cyan-100 dark:hover:bg-cyan-900/50',
  },
  rose: {
    bg: 'bg-rose-50 dark:bg-rose-900/30',
    border: 'border-rose-300 dark:border-rose-700',
    text: 'text-rose-700 dark:text-rose-300',
    hover: 'hover:bg-rose-100 dark:hover:bg-rose-900/50',
  },
  gray: {
    bg: 'bg-gray-50 dark:bg-gray-900/30',
    border: 'border-gray-300 dark:border-gray-700',
    text: 'text-gray-700 dark:text-gray-300',
    hover: 'hover:bg-gray-100 dark:hover:bg-gray-900/50',
  },
  teal: {
    bg: 'bg-teal-50 dark:bg-teal-900/30',
    border: 'border-teal-300 dark:border-teal-700',
    text: 'text-teal-700 dark:text-teal-300',
    hover: 'hover:bg-teal-100 dark:hover:bg-teal-900/50',
  },
};

export const BlockPalette: React.FC<BlockPaletteProps> = ({ onAddBlock }) => {
  return (
    <div className="w-64 bg-muted dark:bg-gray-900 border-r border-border dark:border-gray-700 p-4 overflow-y-auto">
      <h3 className="text-sm font-semibold text-card-foreground dark:text-gray-100 mb-3">Block Palette</h3>

      <div className="space-y-2">
        {paletteBlocks.map(block => {
          const Icon = block.icon;
          const colors = colorClasses[block.color];

          return (
            <button
              key={block.type}
              onClick={() => onAddBlock(block.type)}
              className={`w-full p-3 rounded-lg border-2 ${colors.border} ${colors.bg} ${colors.hover} transition-colors text-left`}
            >
              <div className="flex items-center gap-2 mb-1">
                <Icon className={`w-4 h-4 ${colors.text}`} />
                <span className={`font-medium text-sm ${colors.text}`}>{block.label}</span>
              </div>
              <p className="text-xs text-muted-foreground dark:text-gray-400">{block.description}</p>
            </button>
          );
        })}
      </div>

      <div className="mt-6 p-3 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded-lg">
        <p className="text-xs text-blue-800 dark:text-blue-300 font-medium mb-1">How to use:</p>
        <ul className="text-xs text-blue-700 dark:text-blue-300 space-y-1">
          <li>• Click a block to add it to canvas</li>
          <li>• Drag to reposition blocks</li>
          <li>• Connect outputs → inputs</li>
          <li>• Configure each block's settings</li>
        </ul>
      </div>
    </div>
  );
};
