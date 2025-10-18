/**
 * Block Palette - Sidebar with draggable block types
 */

import React from 'react';
import { Search, Network, Filter, Hash } from 'lucide-react';
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
  {
    type: 'filter',
    icon: Filter,
    label: 'Filter',
    description: 'Filter by ontology or confidence',
    color: 'orange',
  },
  {
    type: 'limit',
    icon: Hash,
    label: 'Limit',
    description: 'Limit number of results',
    color: 'green',
  },
];

const colorClasses: Record<string, { bg: string; border: string; text: string; hover: string }> = {
  blue: {
    bg: 'bg-blue-50',
    border: 'border-blue-300',
    text: 'text-blue-700',
    hover: 'hover:bg-blue-100',
  },
  purple: {
    bg: 'bg-purple-50',
    border: 'border-purple-300',
    text: 'text-purple-700',
    hover: 'hover:bg-purple-100',
  },
  orange: {
    bg: 'bg-orange-50',
    border: 'border-orange-300',
    text: 'text-orange-700',
    hover: 'hover:bg-orange-100',
  },
  green: {
    bg: 'bg-green-50',
    border: 'border-green-300',
    text: 'text-green-700',
    hover: 'hover:bg-green-100',
  },
};

export const BlockPalette: React.FC<BlockPaletteProps> = ({ onAddBlock }) => {
  return (
    <div className="w-64 bg-gray-50 border-r border-gray-200 p-4 overflow-y-auto">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">Block Palette</h3>

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
              <p className="text-xs text-gray-600">{block.description}</p>
            </button>
          );
        })}
      </div>

      <div className="mt-6 p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-xs text-blue-800 font-medium mb-1">How to use:</p>
        <ul className="text-xs text-blue-700 space-y-1">
          <li>• Click a block to add it to canvas</li>
          <li>• Drag to reposition blocks</li>
          <li>• Connect outputs → inputs</li>
          <li>• Configure each block's settings</li>
        </ul>
      </div>
    </div>
  );
};
