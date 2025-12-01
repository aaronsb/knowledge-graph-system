/**
 * Polarity Explorer Help Modal
 * Displays comprehensive help for statistical measures and usage
 */

import React, { useState } from 'react';
import { X, HelpCircle, BookOpen, BarChart3, Lightbulb } from 'lucide-react';
import { polarityHelpContent, polarityHelpCategories } from './polarityHelpContent';

interface PolarityHelpModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const categoryIcons = {
  concept: BookOpen,
  statistics: BarChart3,
  usage: Lightbulb,
};

export const PolarityHelpModal: React.FC<PolarityHelpModalProps> = ({ isOpen, onClose }) => {
  const [selectedTopic, setSelectedTopic] = useState<string>('overview');

  if (!isOpen) return null;

  const topic = polarityHelpContent[selectedTopic];
  const Icon = categoryIcons[topic.category];

  // Group topics by category
  const topicsByCategory = Object.entries(polarityHelpContent).reduce(
    (acc, [id, content]) => {
      if (!acc[content.category]) {
        acc[content.category] = [];
      }
      acc[content.category].push({ id, ...content });
      return acc;
    },
    {} as Record<string, any[]>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-card dark:bg-gray-800 rounded-lg border border-border dark:border-gray-600 shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-border dark:border-gray-700 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <HelpCircle size={20} className="text-primary" />
            <h2 className="text-lg font-semibold text-card-foreground dark:text-gray-100">
              Polarity Explorer Help
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar - Topic List */}
          <div className="w-64 border-r border-border dark:border-gray-700 overflow-y-auto bg-muted/30 dark:bg-gray-900/30">
            <div className="p-3 space-y-4">
              {Object.entries(topicsByCategory).map(([category, topics]) => {
                const CategoryIcon = categoryIcons[category as keyof typeof categoryIcons];
                return (
                  <div key={category}>
                    <div className="flex items-center gap-1.5 mb-2 px-2">
                      <CategoryIcon size={14} className="text-muted-foreground dark:text-gray-500" />
                      <h3 className="text-xs font-semibold text-muted-foreground dark:text-gray-400 uppercase tracking-wide">
                        {polarityHelpCategories[category as keyof typeof polarityHelpCategories]}
                      </h3>
                    </div>
                    <div className="space-y-1">
                      {topics.map((t) => (
                        <button
                          key={t.id}
                          onClick={() => setSelectedTopic(t.id)}
                          className={`w-full text-left px-3 py-2 rounded text-sm transition-colors ${
                            selectedTopic === t.id
                              ? 'bg-primary/10 dark:bg-primary/20 text-primary font-medium'
                              : 'text-card-foreground dark:text-gray-300 hover:bg-muted dark:hover:bg-gray-800'
                          }`}
                        >
                          {t.title}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Main Content */}
          <div className="flex-1 overflow-y-auto p-6">
            <div className="max-w-2xl">
              {/* Topic Header */}
              <div className="mb-6">
                <div className="flex items-center gap-2 mb-2">
                  <Icon size={24} className="text-primary" />
                  <h3 className="text-xl font-bold text-card-foreground dark:text-gray-100">
                    {topic.title}
                  </h3>
                </div>
                <p className="text-base text-foreground dark:text-gray-300 leading-relaxed">
                  {topic.description}
                </p>
              </div>

              {/* Interpretation */}
              {topic.interpretation && topic.interpretation.length > 0 && (
                <div className="mb-6">
                  <h4 className="text-sm font-semibold text-muted-foreground dark:text-gray-400 uppercase tracking-wide mb-3">
                    Interpretation
                  </h4>
                  <ul className="space-y-2">
                    {topic.interpretation.map((item, index) => (
                      <li
                        key={index}
                        className="text-sm text-foreground dark:text-gray-300 flex items-start gap-2"
                      >
                        <span className="text-primary mt-1">•</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Tips */}
              {topic.tips && topic.tips.length > 0 && (
                <div className="mb-6">
                  <h4 className="text-sm font-semibold text-muted-foreground dark:text-gray-400 uppercase tracking-wide mb-3 flex items-center gap-1.5">
                    <Lightbulb size={14} />
                    Tips
                  </h4>
                  <ul className="space-y-2">
                    {topic.tips.map((tip, index) => (
                      <li
                        key={index}
                        className="text-sm text-muted-foreground dark:text-gray-400 flex items-start gap-2"
                      >
                        <span className="text-muted-foreground dark:text-gray-500 mt-1">💡</span>
                        <span>{tip}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Example */}
              {topic.example && (
                <div className="bg-muted dark:bg-gray-900 rounded-lg p-4 border border-border dark:border-gray-700">
                  <h4 className="text-xs font-semibold text-muted-foreground dark:text-gray-400 uppercase tracking-wide mb-2">
                    Example
                  </h4>
                  <p className="text-sm text-muted-foreground dark:text-gray-300 italic">
                    {topic.example}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-border dark:border-gray-700 flex items-center justify-between bg-muted/30 dark:bg-gray-900/30">
          <div className="text-xs text-muted-foreground dark:text-gray-500">
            Press Esc or click outside to close
          </div>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  );
};
