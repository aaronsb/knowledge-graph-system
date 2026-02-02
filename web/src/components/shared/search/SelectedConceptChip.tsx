import React from 'react';

interface SelectedConceptChipProps {
  label: string;
  conceptLabel: string;
  onClear: () => void;
}

export const SelectedConceptChip: React.FC<SelectedConceptChipProps> = ({
  label,
  conceptLabel,
  onClear,
}) => (
  <div className="p-3 bg-muted rounded-lg">
    <div className="flex items-start justify-between">
      <div>
        <div className="text-xs text-muted-foreground mb-1">{label}</div>
        <div className="font-medium">{conceptLabel}</div>
      </div>
      <button
        onClick={onClear}
        className="text-sm text-muted-foreground hover:text-foreground"
      >
        Change
      </button>
    </div>
  </div>
);
