/**
 * Sidebar Category Component
 *
 * Collapsible navigation category with chevron toggle.
 * Used in the main sidebar for workstation navigation.
 */

import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

interface SidebarCategoryProps {
  title: string;
  icon?: React.ComponentType<{ className?: string }>;
  defaultExpanded?: boolean;
  children: React.ReactNode;
}

export const SidebarCategory: React.FC<SidebarCategoryProps> = ({
  title,
  icon: Icon,
  defaultExpanded = false,
  children,
}) => {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div className="mb-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-sm font-semibold text-muted-foreground hover:text-foreground hover:bg-accent/50 rounded-lg transition-colors"
      >
        {expanded ? (
          <ChevronDown className="w-4 h-4 flex-shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 flex-shrink-0" />
        )}
        {Icon && <Icon className="w-4 h-4 flex-shrink-0" />}
        <span className="uppercase tracking-wide">{title}</span>
      </button>

      {expanded && (
        <div className="mt-1 ml-6 space-y-1">
          {children}
        </div>
      )}
    </div>
  );
};

interface SidebarItemProps {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  description?: string;
  isActive?: boolean;
  onClick?: () => void;
  disabled?: boolean;
  badge?: string;
}

export const SidebarItem: React.FC<SidebarItemProps> = ({
  icon: Icon,
  label,
  description,
  isActive = false,
  onClick,
  disabled = false,
  badge,
}) => {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`
        w-full flex items-center gap-3 px-3 py-2 rounded-lg
        transition-colors text-left
        ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        ${
          isActive
            ? 'bg-primary text-primary-foreground'
            : disabled
            ? ''
            : 'bg-muted/40 text-muted-foreground hover:bg-accent hover:text-accent-foreground'
        }
      `}
    >
      <Icon className="w-4 h-4 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm truncate">{label}</span>
          {badge && (
            <span className="px-1.5 py-0.5 text-[10px] font-medium bg-muted text-muted-foreground rounded">
              {badge}
            </span>
          )}
        </div>
        {description && (
          <div className="text-xs opacity-70 truncate">{description}</div>
        )}
      </div>
    </button>
  );
};
