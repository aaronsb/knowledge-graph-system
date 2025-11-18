/**
 * Block Context Menu
 *
 * Right-click context menu for block editor nodes and edges
 */

import React, { useCallback, useEffect } from 'react';
import { Trash2, Copy, HelpCircle } from 'lucide-react';

interface BlockContextMenuProps {
  id: string;
  top: number;
  left: number;
  onDelete: (id: string) => void;
  onDuplicate?: (id: string) => void;
  onHelp?: (id: string) => void;
  onClose: () => void;
}

export const BlockContextMenu: React.FC<BlockContextMenuProps> = ({
  id,
  top,
  left,
  onDelete,
  onDuplicate,
  onHelp,
  onClose,
}) => {
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
    const handleClickOutside = () => onClose();
    // Small delay to prevent immediate close from the right-click event
    setTimeout(() => {
      document.addEventListener('click', handleClickOutside);
    }, 0);
    return () => document.removeEventListener('click', handleClickOutside);
  }, [onClose]);

  const handleDelete = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    onDelete(id);
    onClose();
  }, [id, onDelete, onClose]);

  const handleDuplicate = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    if (onDuplicate) {
      onDuplicate(id);
    }
    onClose();
  }, [id, onDuplicate, onClose]);

  const handleHelp = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    if (onHelp) {
      onHelp(id);
    }
    onClose();
  }, [id, onHelp, onClose]);

  return (
    <div
      className="fixed bg-card dark:bg-gray-800 border border-border rounded-lg shadow-lg py-1 z-[9999] min-w-[160px]"
      style={{ top, left }}
      onContextMenu={(e) => e.preventDefault()}
    >
      {onHelp && (
        <button
          onClick={handleHelp}
          className="w-full px-4 py-2 text-left text-sm hover:bg-muted dark:hover:bg-gray-700 flex items-center gap-2 text-foreground"
        >
          <HelpCircle className="w-4 h-4" />
          Help
        </button>
      )}
      {onDuplicate && (
        <button
          onClick={handleDuplicate}
          className="w-full px-4 py-2 text-left text-sm hover:bg-muted dark:hover:bg-gray-700 flex items-center gap-2 text-foreground"
        >
          <Copy className="w-4 h-4" />
          Duplicate
        </button>
      )}
      <button
        onClick={handleDelete}
        className="w-full px-4 py-2 text-left text-sm hover:bg-destructive hover:text-destructive-foreground flex items-center gap-2 text-destructive"
      >
        <Trash2 className="w-4 h-4" />
        Delete
      </button>
    </div>
  );
};
