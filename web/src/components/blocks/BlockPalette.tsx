/**
 * Block Palette - Sidebar with draggable block types
 * Organized into Cypher Blocks (generate openCypher) and Smart Blocks (use API calls)
 */

import React, { useState } from 'react';
import { Search, Network, Filter, GitBranch, Circle, Hash, Play, Square, Merge, Split, Ban, Sparkles, Snowflake, HelpCircle } from 'lucide-react';
import type { BlockType } from '../../types/blocks';
import { BlockHelpPopup } from './BlockHelpPopup';

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

interface PaletteSection {
  title: string;
  description?: string;
  blocks: PaletteBlock[];
}

const paletteSections: PaletteSection[] = [
  {
    title: 'Flow Control',
    blocks: [
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
    ],
  },
  {
    title: 'Cypher Blocks',
    description: 'Generate openCypher queries',
    blocks: [
      {
        type: 'search',
        icon: Search,
        label: 'Text Search',
        description: 'Find concepts by text match',
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
        type: 'filterOntology',
        icon: Filter,
        label: 'Filter Ontology',
        description: 'Filter by ontology name',
        color: 'orange',
      },
      {
        type: 'filterNode',
        icon: Circle,
        label: 'Filter Node',
        description: 'Filter by node label & confidence',
        color: 'purple',
      },
      {
        type: 'not',
        icon: Ban,
        label: 'Exclude (NOT)',
        description: 'Exclude matching concepts',
        color: 'rose',
      },
      {
        type: 'limit',
        icon: Hash,
        label: 'Limit',
        description: 'Limit number of results',
        color: 'gray',
      },
    ],
  },
  {
    title: 'Boolean Logic',
    description: 'Combine query branches',
    blocks: [
      {
        type: 'and',
        icon: Merge,
        label: 'AND',
        description: 'Intersection of inputs',
        color: 'amber',
      },
      {
        type: 'or',
        icon: Split,
        label: 'OR',
        description: 'Union of inputs',
        color: 'cyan',
      },
    ],
  },
  {
    title: 'Smart Blocks',
    description: 'Intelligent operations',
    blocks: [
      {
        type: 'vectorSearch',
        icon: Snowflake,
        label: 'Vector Search',
        description: 'Semantic search with embeddings',
        color: 'indigo',
      },
      {
        type: 'enrich',
        icon: Sparkles,
        label: 'Enrich',
        description: 'Fetch full concept details',
        color: 'teal',
      },
    ],
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
  indigo: {
    bg: 'bg-indigo-50 dark:bg-indigo-900/30',
    border: 'border-indigo-300 dark:border-indigo-700',
    text: 'text-indigo-700 dark:text-indigo-300',
    hover: 'hover:bg-indigo-100 dark:hover:bg-indigo-900/50',
  },
};

export const BlockPalette: React.FC<BlockPaletteProps> = ({ onAddBlock }) => {
  const [helpPopup, setHelpPopup] = useState<{ blockType: BlockType; position: { x: number; y: number } } | null>(null);

  const handleHelpClick = (e: React.MouseEvent, blockType: BlockType) => {
    e.stopPropagation();
    const rect = (e.target as HTMLElement).getBoundingClientRect();
    setHelpPopup({
      blockType,
      position: { x: rect.right + 10, y: rect.top },
    });
  };

  return (
    <div className="w-64 bg-muted dark:bg-gray-900 border-r border-border dark:border-gray-700 p-4 overflow-y-auto">
      <h3 className="text-sm font-semibold text-card-foreground dark:text-gray-100 mb-3">Block Palette</h3>

      {paletteSections.map((section, sectionIndex) => (
        <div key={section.title} className={sectionIndex > 0 ? 'mt-4' : ''}>
          {/* Section Header */}
          <div className="mb-2">
            <h4 className="text-xs font-semibold text-muted-foreground dark:text-gray-400 uppercase tracking-wide">
              {section.title}
            </h4>
            {section.description && (
              <p className="text-[10px] text-muted-foreground dark:text-gray-500">{section.description}</p>
            )}
          </div>

          {/* Section Blocks */}
          <div className="space-y-2">
            {section.blocks.map(block => {
              const Icon = block.icon;
              const colors = colorClasses[block.color];

              return (
                <div key={block.type} className="relative group">
                  <button
                    onClick={() => onAddBlock(block.type)}
                    className={`w-full p-3 rounded-lg border-2 ${colors.border} ${colors.bg} ${colors.hover} transition-colors text-left`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Icon className={`w-4 h-4 ${colors.text}`} />
                      <span className={`font-medium text-sm ${colors.text}`}>{block.label}</span>
                    </div>
                    <p className="text-xs text-muted-foreground dark:text-gray-400">{block.description}</p>
                  </button>
                  {/* Help button - appears on hover */}
                  <button
                    onClick={(e) => handleHelpClick(e, block.type)}
                    className="absolute top-2 right-2 p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-black/10 dark:hover:bg-white/10 transition-opacity"
                    title="Help"
                  >
                    <HelpCircle className="w-3.5 h-3.5 text-muted-foreground dark:text-gray-500" />
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      ))}

      {/* Help Popup */}
      {helpPopup && (
        <BlockHelpPopup
          blockType={helpPopup.blockType}
          position={helpPopup.position}
          onClose={() => setHelpPopup(null)}
        />
      )}

      <div className="mt-6 p-3 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded-lg">
        <p className="text-xs text-blue-800 dark:text-blue-300 font-medium mb-1">How to use:</p>
        <ul className="text-xs text-blue-700 dark:text-blue-300 space-y-1">
          <li>• Click a block to add it to canvas</li>
          <li>• Drag to reposition blocks</li>
          <li>• Connect outputs → inputs</li>
          <li>• Smart blocks use API calls</li>
        </ul>
      </div>
    </div>
  );
};
