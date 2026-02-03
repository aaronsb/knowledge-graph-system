import React, { useState } from 'react';

interface LoadButtonsProps {
  onLoadClean: () => void;
  onLoadAdd: () => void;
  disabled?: boolean;
}

export const LoadButtons: React.FC<LoadButtonsProps> = ({
  onLoadClean,
  onLoadAdd,
  disabled = false,
}) => {
  const [lastUsed, setLastUsed] = useState<'clean' | 'add' | null>(null);

  const base = "flex-1 px-4 py-2 rounded-lg transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed";
  const active = "bg-primary text-primary-foreground hover:bg-primary/90";
  const inactive = "bg-secondary text-secondary-foreground hover:bg-secondary/80";

  return (
    <div className="flex gap-2">
      <button
        onClick={() => { setLastUsed('clean'); onLoadClean(); }}
        disabled={disabled}
        className={`${base} ${lastUsed === 'clean' ? active : inactive}`}
      >
        Load into Clean Graph
      </button>
      <button
        onClick={() => { setLastUsed('add'); onLoadAdd(); }}
        disabled={disabled}
        className={`${base} ${lastUsed === 'add' ? active : inactive}`}
      >
        Add to Existing Graph
      </button>
    </div>
  );
};
