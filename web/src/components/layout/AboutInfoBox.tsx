/**
 * AboutInfoBox - Speech bubble style info box for application info
 *
 * Shows on right-click in the branding area.
 * Styled to match NodeInfoBox from the explorers.
 */

import React from 'react';
import { X, Github, BookOpen, Database, Brain, Sparkles, User, Bot } from 'lucide-react';

export interface AboutInfoBoxProps {
  x: number;
  y: number;
  onDismiss: () => void;
}

export const AboutInfoBox: React.FC<AboutInfoBoxProps> = ({ x, y, onDismiss }) => {
  return (
    <div
      className="fixed pointer-events-auto z-50"
      style={{
        left: `${x}px`,
        top: `${y}px`,
      }}
    >
      <div className="relative">
        {/* Info box content */}
        <div
          className="bg-card dark:bg-gray-800 rounded-lg border border-border dark:border-gray-600 shadow-xl"
          style={{
            minWidth: '280px',
            maxWidth: '320px',
          }}
        >
          {/* Header */}
          <div className="px-4 py-3 border-b border-border dark:border-gray-700 flex items-center justify-between">
            <div>
              <div className="font-semibold text-card-foreground text-base">
                Knowledge Graph System
              </div>
              <div className="text-xs text-muted-foreground dark:text-gray-400 mt-0.5">
                About this application
              </div>
            </div>
            <button
              onClick={onDismiss}
              className="p-1 hover:bg-muted dark:hover:bg-gray-700 rounded transition-colors"
            >
              <X className="w-4 h-4 text-muted-foreground" />
            </button>
          </div>

          {/* Content */}
          <div className="px-4 py-3 space-y-3 text-sm">
            <p className="text-muted-foreground dark:text-gray-400">
              Transform documents into interconnected concept graphs.
              Explore semantic relationships beyond sequential reading.
            </p>

            <p className="text-muted-foreground dark:text-gray-400 text-xs italic">
              "Honest architecture - it doesn't pretend continuity exists,
              but makes ideas persistent in a form we can genuinely engage with."
            </p>

            <div className="space-y-2">
              <div className="flex items-center gap-2 text-card-foreground">
                <Database className="w-4 h-4 text-blue-500" />
                <span>Apache AGE / PostgreSQL</span>
              </div>
              <div className="flex items-center gap-2 text-card-foreground">
                <Brain className="w-4 h-4 text-purple-500" />
                <span>LLM Concept Extraction</span>
              </div>
              <div className="flex items-center gap-2 text-card-foreground">
                <Sparkles className="w-4 h-4 text-amber-500" />
                <span>Vector Similarity Search</span>
              </div>
            </div>

            {/* Credits */}
            <div className="pt-2 border-t border-border dark:border-gray-700">
              <div className="text-xs text-muted-foreground dark:text-gray-500 mb-2">
                Created by
              </div>
              <div className="space-y-1.5">
                <div className="flex items-center gap-2 text-xs text-card-foreground">
                  <User className="w-3.5 h-3.5 text-blue-500" />
                  <span>Aaron Bockelie</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-card-foreground">
                  <Bot className="w-3.5 h-3.5 text-orange-500" />
                  <span>Claude Code (Anthropic)</span>
                </div>
              </div>
            </div>

            {/* Links */}
            <div className="pt-2 border-t border-border dark:border-gray-700 flex items-center gap-4">
              <a
                href="https://github.com/aaronsb/knowledge-graph-system"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-card-foreground transition-colors"
              >
                <Github className="w-3.5 h-3.5" />
                <span>GitHub</span>
              </a>
              <a
                href="https://aaronsb.github.io/knowledge-graph-system/"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-card-foreground transition-colors"
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span>Docs</span>
              </a>
            </div>

            <div className="text-xs text-muted-foreground dark:text-gray-500 text-center">
              Click the graph to perturb it ✨
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AboutInfoBox;
