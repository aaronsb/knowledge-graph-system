/**
 * Context Menu Component
 *
 * Right-click menu for graph nodes and edges.
 * Supports nested submenus with flyout behavior.
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { ChevronRight } from 'lucide-react';
import { getZIndexClass } from '../../config/zIndex';

export interface ContextMenuItem {
  label: string;
  onClick?: () => void;
  icon?: React.ComponentType<{ className?: string }>;
  disabled?: boolean;
  submenu?: ContextMenuItem[]; // Support nested submenus
}

interface ContextMenuProps {
  x: number;
  y: number;
  items: ContextMenuItem[];
  onClose: () => void;
}

export const ContextMenu: React.FC<ContextMenuProps> = ({ x, y, items, onClose }) => {
  const menuRef = useRef<HTMLDivElement>(null);
  const submenuRef = useRef<HTMLDivElement>(null);
  const closeTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const [openSubmenu, setOpenSubmenu] = useState<number | null>(null);
  const [submenuPosition, setSubmenuPosition] = useState<{ top: number; left: number } | null>(null);

  // Helper to cancel any pending close timeout
  const cancelCloseTimeout = useCallback(() => {
    if (closeTimeoutRef.current) {
      clearTimeout(closeTimeoutRef.current);
      closeTimeoutRef.current = null;
    }
  }, []);

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      const isOutsideMenu = menuRef.current && !menuRef.current.contains(target);
      const isOutsideSubmenu = !submenuRef.current || !submenuRef.current.contains(target);

      // Only close if click is outside BOTH main menu and submenu
      if (isOutsideMenu && isOutsideSubmenu) {
        onClose();
      }
    };

    // Close on escape key
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
      // Cancel any pending close timeout on unmount
      cancelCloseTimeout();
    };
  }, [onClose, cancelCloseTimeout]);

  return (
    <>
      <div
        ref={menuRef}
        className={`fixed bg-card dark:bg-gray-800 border border-border dark:border-gray-600 rounded-lg shadow-xl py-1 ${getZIndexClass('contextMenu')} min-w-[180px]`}
        style={{ left: x, top: y }}
      >
        {items.map((item, index) => {
          const Icon = item.icon;
          const hasSubmenu = item.submenu && item.submenu.length > 0;

          return (
            <div
              key={index}
              className="relative"
              onMouseEnter={(e) => {
                if (hasSubmenu) {
                  // Cancel any pending close timeout
                  cancelCloseTimeout();

                  const rect = e.currentTarget.getBoundingClientRect();
                  setOpenSubmenu(index);
                  setSubmenuPosition({
                    top: rect.top,
                    left: rect.right,
                  });
                }
              }}
              onMouseLeave={() => {
                if (hasSubmenu) {
                  // Delay closing to allow moving to submenu
                  closeTimeoutRef.current = setTimeout(() => {
                    setOpenSubmenu(null);
                  }, 150);
                }
              }}
            >
              <button
                onClick={() => {
                  if (!item.disabled && !hasSubmenu && item.onClick) {
                    item.onClick();
                    onClose();
                  }
                }}
                disabled={item.disabled}
                className={`
                  w-full text-left px-4 py-2 flex items-center gap-3
                  transition-colors text-card-foreground dark:text-gray-100
                  ${
                    item.disabled
                      ? 'opacity-50 cursor-not-allowed'
                      : 'hover:bg-muted dark:hover:bg-gray-700 cursor-pointer'
                  }
                `}
              >
                {Icon && <Icon className="w-4 h-4" />}
                <span className="text-sm flex-1">{item.label}</span>
                {hasSubmenu && <ChevronRight className="w-4 h-4 text-muted-foreground dark:text-gray-400" />}
              </button>
            </div>
          );
        })}
      </div>

      {/* Render submenu */}
      {openSubmenu !== null && items[openSubmenu]?.submenu && submenuPosition && (
        <div
          ref={submenuRef}
          className={`fixed bg-card dark:bg-gray-800 border border-border dark:border-gray-600 rounded-lg shadow-xl py-1 ${getZIndexClass('contextMenu')} min-w-[180px]`}
          style={{ left: submenuPosition.left, top: submenuPosition.top }}
          onMouseEnter={() => {
            // Cancel any pending close timeout when entering submenu
            cancelCloseTimeout();
          }}
          onMouseLeave={() => {
            // Close submenu when mouse leaves it
            setOpenSubmenu(null);
          }}
        >
          {items[openSubmenu].submenu!.map((subitem, subindex) => {
            const SubIcon = subitem.icon;
            return (
              <button
                key={subindex}
                onClick={() => {
                  if (!subitem.disabled && subitem.onClick) {
                    subitem.onClick();
                    onClose();
                  }
                }}
                disabled={subitem.disabled}
                className={`
                  w-full text-left px-4 py-2 flex items-center gap-3
                  transition-colors text-card-foreground dark:text-gray-100
                  ${
                    subitem.disabled
                      ? 'opacity-50 cursor-not-allowed'
                      : 'hover:bg-muted dark:hover:bg-gray-700 cursor-pointer'
                  }
                `}
              >
                {SubIcon && <SubIcon className="w-4 h-4" />}
                <span className="text-sm">{subitem.label}</span>
              </button>
            );
          })}
        </div>
      )}
    </>
  );
};
