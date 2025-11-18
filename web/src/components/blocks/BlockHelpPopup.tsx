/**
 * Block Help Popup - Displays help information for blocks
 * Used in both palette (via ? button) and canvas (via context menu)
 */

import React, { useEffect, useRef } from 'react';
import { X, Lightbulb } from 'lucide-react';
import type { BlockType } from '../../types/blocks';
import { blockHelpContent } from './blockHelpContent';

interface BlockHelpPopupProps {
  blockType: BlockType;
  position: { x: number; y: number };
  onClose: () => void;
}

const tagColors: Record<string, { bg: string; text: string }> = {
  FLOW: { bg: 'bg-green-100 dark:bg-green-900/50', text: 'text-green-700 dark:text-green-300' },
  CYPHER: { bg: 'bg-blue-100 dark:bg-blue-900/50', text: 'text-blue-700 dark:text-blue-300' },
  LOGIC: { bg: 'bg-amber-100 dark:bg-amber-900/50', text: 'text-amber-700 dark:text-amber-300' },
  SMART: { bg: 'bg-indigo-100 dark:bg-indigo-900/50', text: 'text-indigo-700 dark:text-indigo-300' },
};

export const BlockHelpPopup: React.FC<BlockHelpPopupProps> = ({ blockType, position, onClose }) => {
  const popupRef = useRef<HTMLDivElement>(null);
  const content = blockHelpContent[blockType];

  // Close on escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (popupRef.current && !popupRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    // Delay to prevent immediate close on the click that opened it
    setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside);
    }, 100);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  if (!content) {
    return null;
  }

  const tagStyle = tagColors[content.tag] || tagColors.CYPHER;

  return (
    <div
      ref={popupRef}
      className="fixed z-50 bg-card dark:bg-gray-800 rounded-lg border border-border dark:border-gray-600 shadow-xl"
      style={{
        left: `${position.x}px`,
        top: `${position.y}px`,
        minWidth: '320px',
        maxWidth: '400px',
      }}
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-border dark:border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-card-foreground dark:text-gray-100">{content.title}</span>
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${tagStyle.bg} ${tagStyle.text}`}>
            {content.tag}
          </span>
        </div>
        <button
          onClick={onClose}
          className="text-muted-foreground hover:text-foreground dark:text-gray-400 dark:hover:text-gray-200"
        >
          <X size={16} />
        </button>
      </div>

      {/* Content */}
      <div className="px-4 py-3 space-y-3 max-h-[400px] overflow-y-auto">
        {/* Description */}
        <p className="text-sm text-foreground dark:text-gray-300">{content.description}</p>

        {/* Parameters */}
        {content.parameters && content.parameters.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-muted-foreground dark:text-gray-400 uppercase tracking-wide mb-2">
              Parameters
            </h4>
            <div className="space-y-1.5">
              {content.parameters.map((param) => (
                <div key={param.name} className="text-sm">
                  <span className="font-medium text-card-foreground dark:text-gray-200">{param.name}:</span>
                  <span className="text-muted-foreground dark:text-gray-400 ml-1">{param.description}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Example */}
        {content.example && (
          <div className="bg-muted dark:bg-gray-900 rounded p-2 text-xs text-muted-foreground dark:text-gray-400 italic">
            {content.example}
          </div>
        )}

        {/* Tips */}
        {content.tips && content.tips.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-muted-foreground dark:text-gray-400 uppercase tracking-wide mb-2 flex items-center gap-1">
              <Lightbulb size={12} />
              Tips
            </h4>
            <ul className="space-y-1">
              {content.tips.map((tip, index) => (
                <li key={index} className="text-xs text-muted-foreground dark:text-gray-400 flex items-start gap-1.5">
                  <span className="text-muted-foreground dark:text-gray-500">•</span>
                  <span>{tip}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-border dark:border-gray-700 text-xs text-muted-foreground dark:text-gray-500">
        Press Esc or click outside to close
      </div>
    </div>
  );
};
