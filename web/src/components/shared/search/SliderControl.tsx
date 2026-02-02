import React from 'react';

interface SliderControlProps {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
  displayValue?: string;
  unit?: string;
}

export const SliderControl: React.FC<SliderControlProps> = ({
  label,
  value,
  min,
  max,
  onChange,
  displayValue,
  unit,
}) => (
  <div className="flex items-center gap-3 px-1">
    <label className="text-sm text-muted-foreground whitespace-nowrap">
      {label}
    </label>
    <input
      type="range"
      min={min}
      max={max}
      value={value}
      onChange={(e) => onChange(parseInt(e.target.value))}
      className="flex-1 h-2 bg-muted rounded-lg appearance-none cursor-pointer
                 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
                 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary
                 [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4
                 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-0"
    />
    <span className="text-sm font-medium min-w-[3ch] text-right">
      {displayValue ?? value}
    </span>
    {unit && (
      <span className="text-xs text-muted-foreground whitespace-nowrap">
        {unit}
      </span>
    )}
  </div>
);
