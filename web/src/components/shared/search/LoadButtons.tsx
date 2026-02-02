import React from 'react';

interface LoadButtonsProps {
  onLoadClean: () => void;
  onLoadAdd: () => void;
  disabled?: boolean;
}

export const LoadButtons: React.FC<LoadButtonsProps> = ({
  onLoadClean,
  onLoadAdd,
  disabled = false,
}) => (
  <div className="flex gap-2">
    <button
      onClick={onLoadClean}
      disabled={disabled}
      className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
    >
      Load into Clean Graph
    </button>
    <button
      onClick={onLoadAdd}
      disabled={disabled}
      className="flex-1 px-4 py-2 bg-secondary text-secondary-foreground rounded-lg hover:bg-secondary/80 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
    >
      Add to Existing Graph
    </button>
  </div>
);
