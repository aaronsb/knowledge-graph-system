/**
 * Icon Rail Panel Component
 *
 * A collapsible side panel that minimizes to an icon rail.
 * Reusable pattern for workspace sidebars throughout the app.
 */

import React, { useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface PanelTab {
  id: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  content: React.ReactNode;
}

interface IconRailPanelProps {
  tabs: PanelTab[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
  defaultExpanded?: boolean;
  expandedWidth?: string;
  position?: 'left' | 'right';
}

export const IconRailPanel: React.FC<IconRailPanelProps> = ({
  tabs,
  activeTab,
  onTabChange,
  defaultExpanded = false,
  expandedWidth = 'w-72',
  position = 'left',
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const borderClass = position === 'left' ? 'border-r' : 'border-l';

  // VS Code-style toggle: clicking same icon collapses, different icon switches
  const handleIconClick = (tabId: string) => {
    if (isExpanded && activeTab === tabId) {
      // Clicking same icon - collapse
      setIsExpanded(false);
    } else {
      // Clicking different icon or when collapsed - expand and switch
      onTabChange(tabId);
      setIsExpanded(true);
    }
  };

  return (
    <div className={`${borderClass} border-border bg-card flex h-full`}>
      {/* Icon Rail - always visible */}
      <div className="w-12 flex flex-col border-r border-border">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id && isExpanded;
          return (
            <button
              key={tab.id}
              onClick={() => handleIconClick(tab.id)}
              className={`p-3 transition-colors ${
                isActive
                  ? 'text-primary bg-primary/10 border-l-2 border-primary'
                  : 'text-muted-foreground hover:text-foreground hover:bg-accent border-l-2 border-transparent'
              }`}
              title={tab.label}
            >
              <Icon className="w-5 h-5" />
            </button>
          );
        })}
      </div>

      {/* Content Panel - shown when expanded */}
      {isExpanded && (
        <div className={`${expandedWidth} flex flex-col`}>
          {/* Tab header */}
          <div className="h-10 border-b border-border px-3 flex items-center">
            <span className="text-sm font-medium">
              {tabs.find((t) => t.id === activeTab)?.label}
            </span>
          </div>
          {/* Content */}
          <div className="flex-1 overflow-y-auto">
            {tabs.find((t) => t.id === activeTab)?.content}
          </div>
        </div>
      )}
    </div>
  );
};
