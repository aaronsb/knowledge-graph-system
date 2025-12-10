/**
 * Preferences Shared Components
 *
 * Reusable UI components for preferences tabs.
 */

import React from 'react';
import type { PreferencesTabType } from './types';

// Tab button component (matches admin style)
export const TabButton: React.FC<{
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}> = ({ active, onClick, icon, label }) => (
  <button
    onClick={onClick}
    className={`
      flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors
      ${active
        ? 'bg-primary text-primary-foreground'
        : 'text-muted-foreground hover:text-foreground hover:bg-muted'
      }
    `}
  >
    {icon}
    {label}
  </button>
);

// Section component
export const Section: React.FC<{
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  description?: string;
}> = ({ title, icon, children, description }) => (
  <section className="bg-card rounded-lg border border-border overflow-hidden">
    <div className="px-4 py-3 border-b border-border flex items-center gap-2">
      <span className="text-muted-foreground">{icon}</span>
      <div>
        <h2 className="font-semibold text-card-foreground">{title}</h2>
        {description && (
          <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
        )}
      </div>
    </div>
    <div className="px-4 divide-y divide-border">{children}</div>
  </section>
);

// Toggle switch component
export const Toggle: React.FC<{
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  label: string;
  description?: string;
  icon?: React.ReactNode;
}> = ({ enabled, onChange, label, description, icon }) => (
  <div className="flex items-start justify-between gap-4 py-3">
    <div className="flex items-start gap-3">
      {icon && (
        <div className="mt-0.5 text-muted-foreground">{icon}</div>
      )}
      <div>
        <div className="font-medium text-card-foreground">{label}</div>
        {description && (
          <div className="text-sm text-muted-foreground">{description}</div>
        )}
      </div>
    </div>
    <button
      onClick={() => onChange(!enabled)}
      className={`
        relative inline-flex h-6 w-11 items-center rounded-full transition-colors flex-shrink-0
        ${enabled ? 'bg-primary' : 'bg-muted-foreground/30'}
      `}
    >
      <span
        className={`
          inline-block h-4 w-4 transform rounded-full bg-white transition-transform shadow-sm
          ${enabled ? 'translate-x-6' : 'translate-x-1'}
        `}
      />
    </button>
  </div>
);

// Number input component
export const NumberInput: React.FC<{
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  label: string;
  description?: string;
  icon?: React.ReactNode;
}> = ({ value, onChange, min = 1, max = 1000, step = 1, label, description, icon }) => (
  <div className="flex items-start justify-between gap-4 py-3">
    <div className="flex items-start gap-3">
      {icon && (
        <div className="mt-0.5 text-muted-foreground">{icon}</div>
      )}
      <div>
        <div className="font-medium text-card-foreground">{label}</div>
        {description && (
          <div className="text-sm text-muted-foreground">{description}</div>
        )}
      </div>
    </div>
    <input
      type="number"
      value={value}
      onChange={(e) => {
        const v = parseInt(e.target.value, 10);
        if (!isNaN(v) && v >= min && v <= max) {
          onChange(v);
        }
      }}
      min={min}
      max={max}
      step={step}
      className="w-24 px-3 py-1.5 text-sm text-right bg-muted border border-border rounded-lg text-card-foreground focus:outline-none focus:ring-2 focus:ring-primary"
    />
  </div>
);

// Select component
export const Select: React.FC<{
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  label: string;
  description?: string;
  icon?: React.ReactNode;
}> = ({ value, onChange, options, label, description, icon }) => (
  <div className="flex items-start justify-between gap-4 py-3">
    <div className="flex items-start gap-3">
      {icon && (
        <div className="mt-0.5 text-muted-foreground">{icon}</div>
      )}
      <div>
        <div className="font-medium text-card-foreground">{label}</div>
        {description && (
          <div className="text-sm text-muted-foreground">{description}</div>
        )}
      </div>
    </div>
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="px-3 py-1.5 text-sm bg-muted border border-border rounded-lg text-card-foreground focus:outline-none focus:ring-2 focus:ring-primary"
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  </div>
);

// Slider component for range values
export const Slider: React.FC<{
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step?: number;
  label: string;
  description?: string;
  icon?: React.ReactNode;
  formatValue?: (value: number) => string;
}> = ({ value, onChange, min, max, step = 1, label, description, icon, formatValue }) => (
  <div className="py-3">
    <div className="flex items-start gap-3 mb-3">
      {icon && (
        <div className="mt-0.5 text-muted-foreground">{icon}</div>
      )}
      <div className="flex-1">
        <div className="flex items-center justify-between">
          <div className="font-medium text-card-foreground">{label}</div>
          <div className="text-sm font-mono text-muted-foreground">
            {formatValue ? formatValue(value) : value}
          </div>
        </div>
        {description && (
          <div className="text-sm text-muted-foreground">{description}</div>
        )}
      </div>
    </div>
    <input
      type="range"
      value={value}
      onChange={(e) => onChange(parseFloat(e.target.value))}
      min={min}
      max={max}
      step={step}
      className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
    />
  </div>
);

// Color swatch button
export const ColorSwatch: React.FC<{
  color: string;
  selected: boolean;
  onClick: () => void;
  label?: string;
}> = ({ color, selected, onClick, label }) => (
  <button
    onClick={onClick}
    className={`
      relative w-10 h-10 rounded-lg transition-all
      ${selected ? 'ring-2 ring-primary ring-offset-2 ring-offset-background scale-110' : 'hover:scale-105'}
    `}
    style={{ backgroundColor: color }}
    title={label}
  >
    {selected && (
      <span className="absolute inset-0 flex items-center justify-center">
        <svg className="w-5 h-5 text-white drop-shadow-md" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
        </svg>
      </span>
    )}
  </button>
);

// Hue slider component
export const HueSlider: React.FC<{
  value: number;
  onChange: (value: number) => void;
  label: string;
  description?: string;
}> = ({ value, onChange, label, description }) => (
  <div className="py-3">
    <div className="flex items-center justify-between mb-3">
      <div>
        <div className="font-medium text-card-foreground">{label}</div>
        {description && (
          <div className="text-sm text-muted-foreground">{description}</div>
        )}
      </div>
      <div className="text-sm font-mono text-muted-foreground">{value}°</div>
    </div>
    <div className="relative">
      <input
        type="range"
        value={value}
        onChange={(e) => onChange(parseInt(e.target.value, 10))}
        min={0}
        max={360}
        step={1}
        className="w-full h-3 rounded-lg appearance-none cursor-pointer"
        style={{
          background: `linear-gradient(to right,
            hsl(0, 70%, 50%),
            hsl(60, 70%, 50%),
            hsl(120, 70%, 50%),
            hsl(180, 70%, 50%),
            hsl(240, 70%, 50%),
            hsl(300, 70%, 50%),
            hsl(360, 70%, 50%)
          )`,
        }}
      />
    </div>
  </div>
);

// Stepped hue grid (12 hues at 30° intervals)
export const HueGrid: React.FC<{
  value: number;
  onChange: (value: number) => void;
  lightness?: number;
  saturation?: number;
  label?: string;
}> = ({ value, onChange, lightness = 50, saturation = 70, label }) => {
  // Find nearest hue step
  const nearestStep = Math.round(value / 30) * 30;

  return (
    <div className="py-2">
      {label && (
        <div className="text-xs text-muted-foreground mb-2 font-mono uppercase tracking-wide">
          {label}
        </div>
      )}
      <div className="grid grid-cols-12 gap-0.5">
        {Array.from({ length: 12 }, (_, i) => {
          const hue = i * 30;
          const isSelected = nearestStep === hue || (nearestStep === 360 && hue === 0);
          return (
            <button
              key={hue}
              onClick={() => onChange(hue)}
              className={`
                aspect-[2/1] transition-all
                ${isSelected ? 'ring-2 ring-foreground ring-offset-1 ring-offset-background scale-105 z-10' : 'hover:scale-105'}
              `}
              style={{ backgroundColor: `hsl(${hue}, ${saturation}%, ${lightness}%)` }}
              title={`${hue}°`}
            />
          );
        })}
      </div>
    </div>
  );
};

// Saturation grid (6 steps)
export const SaturationGrid: React.FC<{
  value: number;
  onChange: (value: number) => void;
  hue: number;
  lightness?: number;
  steps?: number[];
  label?: string;
}> = ({ value, onChange, hue, lightness = 35, steps = [0, 6, 12, 18, 24, 30], label }) => {
  // Find nearest saturation step
  const nearestStep = steps.reduce((prev, curr) =>
    Math.abs(curr - value) < Math.abs(prev - value) ? curr : prev
  );

  return (
    <div className="py-2">
      {label && (
        <div className="text-xs text-muted-foreground mb-2 font-mono uppercase tracking-wide">
          {label}
        </div>
      )}
      <div className="grid grid-cols-6 gap-0.5">
        {steps.map((sat) => {
          const isSelected = nearestStep === sat;
          return (
            <button
              key={sat}
              onClick={() => onChange(sat)}
              className={`
                aspect-[3/1] transition-all
                ${isSelected ? 'ring-2 ring-foreground ring-offset-1 ring-offset-background scale-105 z-10' : 'hover:scale-105'}
              `}
              style={{ backgroundColor: `hsl(${hue}, ${sat}%, ${lightness}%)` }}
              title={`${sat}%`}
            />
          );
        })}
      </div>
    </div>
  );
};

// Lightness grid (mode-dependent stops)
export const LightnessGrid: React.FC<{
  value: number;
  onChange: (value: number) => void;
  hue: number;
  saturation: number;
  stops: number[];
  label?: string;
}> = ({ value, onChange, hue, saturation, stops, label }) => {
  // Find nearest lightness stop
  const nearestStop = stops.reduce((prev, curr) =>
    Math.abs(curr - value) < Math.abs(prev - value) ? curr : prev
  );

  return (
    <div className="py-2">
      {label && (
        <div className="text-xs text-muted-foreground mb-2 font-mono uppercase tracking-wide">
          {label}
        </div>
      )}
      <div className="grid grid-cols-6 gap-0.5">
        {stops.map((light) => {
          const isSelected = nearestStop === light;
          return (
            <button
              key={light}
              onClick={() => onChange(light)}
              className={`
                aspect-[3/1] transition-all
                ${isSelected ? 'ring-2 ring-foreground ring-offset-1 ring-offset-background scale-105 z-10' : 'hover:scale-105'}
              `}
              style={{ backgroundColor: `hsl(${hue}, ${saturation}%, ${light}%)` }}
              title={`${light}%`}
            />
          );
        })}
      </div>
    </div>
  );
};

// Saturation/Lightness grid for accent color (6x4 grid)
export const SVGrid: React.FC<{
  hue: number;
  saturation: number;
  lightness: number;
  onChange: (sat: number, light: number) => void;
  label?: string;
}> = ({ hue, saturation, lightness, onChange, label }) => {
  const saturations = [40, 55, 70, 85, 100, 100];
  const lightnesses = [35, 45, 55, 65];

  return (
    <div className="py-2">
      {label && (
        <div className="text-xs text-muted-foreground mb-2 font-mono uppercase tracking-wide">
          {label}
        </div>
      )}
      <div className="grid grid-cols-6 gap-0.5">
        {lightnesses.map((l) =>
          saturations.map((s, si) => {
            const isSelected = s === saturation && l === lightness;
            return (
              <button
                key={`${s}-${l}-${si}`}
                onClick={() => onChange(s, l)}
                className={`
                  aspect-[2.5/1] transition-all
                  ${isSelected ? 'ring-2 ring-foreground ring-offset-1 ring-offset-background scale-105 z-10' : 'hover:scale-105'}
                `}
                style={{ backgroundColor: `hsl(${hue}, ${s}%, ${l}%)` }}
                title={`S:${s}% L:${l}%`}
              />
            );
          })
        )}
      </div>
    </div>
  );
};

// Color preview with HSL values
export const ColorPreview: React.FC<{
  hue: number;
  saturation: number;
  lightness: number;
  hex: string;
  compact?: boolean;
}> = ({ hue, saturation, lightness, hex, compact = false }) => (
  <div className={`flex items-center gap-3 bg-surface-2 rounded ${compact ? 'p-2' : 'p-3'}`}>
    <div
      className={`flex-shrink-0 border border-border ${compact ? 'w-6 h-6' : 'w-8 h-8'}`}
      style={{ backgroundColor: `hsl(${hue}, ${saturation}%, ${lightness}%)` }}
    />
    <div className="font-mono text-xs text-muted-foreground">
      <div className="text-card-foreground font-medium">{hex}</div>
      <div>H:{hue} S:{saturation} L:{lightness}</div>
    </div>
  </div>
);

// Subsection header for grouped controls
export const Subsection: React.FC<{
  title: string;
  children: React.ReactNode;
}> = ({ title, children }) => (
  <div className="py-4">
    <div className="text-xs font-mono uppercase tracking-wider text-primary mb-3">{title}</div>
    {children}
  </div>
);
