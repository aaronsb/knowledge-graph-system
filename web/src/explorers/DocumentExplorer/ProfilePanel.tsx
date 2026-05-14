/**
 * Document Explorer Settings Panel
 *
 * Controls for visual appearance, layout, and interaction.
 * Rendered inside the IconRailPanel settings tab.
 */

import React from 'react';
import type { SettingsPanelProps } from '../../types/explorer';
import type { DocumentExplorerSettings } from './types';
import { SLIDER_RANGES } from './types';

export const ProfilePanel: React.FC<SettingsPanelProps<DocumentExplorerSettings>> = ({
  settings,
  onChange,
}) => {
  if (!settings || !onChange) {
    return (
      <div className="p-4 text-sm text-muted-foreground">
        Load a query to configure settings.
      </div>
    );
  }

  const updateVisual = (key: keyof typeof settings.visual, value: boolean | number) => {
    onChange({ ...settings, visual: { ...settings.visual, [key]: value } });
  };

  const updateLayout = (key: keyof typeof settings.layout, value: number) => {
    onChange({ ...settings, layout: { ...settings.layout, [key]: value } });
  };

  const updateInteraction = (key: keyof typeof settings.interaction, value: boolean) => {
    onChange({ ...settings, interaction: { ...settings.interaction, [key]: value } });
  };

  return (
    <div className="space-y-5 p-3">
      {/* Projection */}
      <section>
        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
          Projection
        </h4>
        <label className="flex items-center gap-2 text-xs text-card-foreground py-1.5">
          <span className="flex-1 min-w-0 truncate font-medium">Camera</span>
          <select
            className="flex-[2] bg-card border border-border rounded px-1 py-0.5 text-xs"
            value={settings.projection}
            onChange={(e) =>
              onChange({ ...settings, projection: e.target.value as DocumentExplorerSettings['projection'] })
            }
          >
            <option value="3D">3D (perspective + orbit)</option>
            <option value="2D">2D (orthographic + pan/zoom)</option>
          </select>
        </label>
      </section>

      {/* Visual */}
      <section>
        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
          Visual
        </h4>
        <div className="space-y-3">
          <label className="flex items-center justify-between text-sm">
            <span>Show labels</span>
            <input
              type="checkbox"
              checked={settings.visual.showLabels}
              onChange={(e) => updateVisual('showLabels', e.target.checked)}
              className="rounded"
            />
          </label>
          <label className="flex items-center justify-between text-sm">
            <span>Show edges</span>
            <input
              type="checkbox"
              checked={settings.visual.showEdges}
              onChange={(e) => updateVisual('showEdges', e.target.checked)}
              className="rounded"
            />
          </label>
          <div>
            <div className="flex items-center justify-between text-sm mb-1">
              <span>Node size</span>
              <span className="text-xs text-muted-foreground">{settings.visual.nodeSize.toFixed(1)}x</span>
            </div>
            <input
              type="range"
              min={SLIDER_RANGES.visual.nodeSize.min}
              max={SLIDER_RANGES.visual.nodeSize.max}
              step={SLIDER_RANGES.visual.nodeSize.step}
              value={settings.visual.nodeSize}
              onChange={(e) => updateVisual('nodeSize', parseFloat(e.target.value))}
              className="w-full h-1.5 rounded-lg appearance-none bg-border accent-amber-500"
            />
          </div>
        </div>
      </section>

      {/* Layout */}
      <section>
        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
          Layout
        </h4>
        <div className="space-y-3">
          <div>
            <div className="flex items-center justify-between text-sm mb-1">
              <span>Document size</span>
              <span className="text-xs text-muted-foreground">{settings.layout.documentSize}px</span>
            </div>
            <input
              type="range"
              min={SLIDER_RANGES.layout.documentSize.min}
              max={SLIDER_RANGES.layout.documentSize.max}
              step={SLIDER_RANGES.layout.documentSize.step}
              value={settings.layout.documentSize}
              onChange={(e) => updateLayout('documentSize', parseInt(e.target.value))}
              className="w-full h-1.5 rounded-lg appearance-none bg-border accent-amber-500"
            />
          </div>
        </div>
      </section>

      {/* Interaction */}
      <section>
        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
          Interaction
        </h4>
        <div className="space-y-3">
          <label className="flex items-center justify-between text-sm">
            <span>Highlight on hover</span>
            <input
              type="checkbox"
              checked={settings.interaction.highlightOnHover}
              onChange={(e) => updateInteraction('highlightOnHover', e.target.checked)}
              className="rounded"
            />
          </label>
        </div>
      </section>
    </div>
  );
};
