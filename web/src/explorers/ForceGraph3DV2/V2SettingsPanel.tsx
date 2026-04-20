/**
 * V2 Settings Panel
 *
 * Settings surface for the unified rendering engine (ADR-702). Mirrors
 * the collapsible-sections layout of V1's GraphSettingsPanel but against
 * V2's settings shape (repulsion/attraction/damping/centerGravity, node
 * mode, edge-color-by, label visibility radius, etc.).
 *
 * Sim action buttons (reheat / simmer / freeze) live on a separate
 * on-canvas overlay inside ForceGraph3DV2.tsx, next to the sim-backend
 * badge — they drive a simHandleRef that can only be read inside the
 * r3f Canvas tree.
 */

import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import type { SettingsPanelProps } from '../../types/explorer';
import type { ForceGraph3DV2Settings } from './types';
import { SLIDER_RANGES } from './types';

type Section = 'physics' | 'visual' | 'interaction';

export const V2SettingsPanel: React.FC<SettingsPanelProps<ForceGraph3DV2Settings>> = ({
  settings,
  onChange,
}) => {
  const [expanded, setExpanded] = useState<Set<Section>>(new Set(['physics', 'visual']));

  const toggle = (section: Section) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(section)) next.delete(section);
      else next.add(section);
      return next;
    });

  const updatePhysics = (patch: Partial<ForceGraph3DV2Settings['physics']>) =>
    onChange({ ...settings, physics: { ...settings.physics, ...patch } });
  const updateVisual = (patch: Partial<ForceGraph3DV2Settings['visual']>) =>
    onChange({ ...settings, visual: { ...settings.visual, ...patch } });
  const updateInteraction = (patch: Partial<ForceGraph3DV2Settings['interaction']>) =>
    onChange({ ...settings, interaction: { ...settings.interaction, ...patch } });

  const sectionHeader = (id: Section, title: string) => (
    <button
      className="flex items-center gap-1.5 w-full text-left py-1.5 text-sm font-medium text-foreground hover:text-primary transition-colors"
      onClick={() => toggle(id)}
    >
      {expanded.has(id) ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
      {title}
    </button>
  );

  const row = (label: string, value: React.ReactNode, control: React.ReactNode) => (
    <label className="flex items-center gap-2 text-xs text-card-foreground">
      <span className="flex-1 min-w-0 truncate">{label}</span>
      <span className="font-mono text-muted-foreground tabular-nums w-12 text-right text-[10px]">{value}</span>
      {control}
    </label>
  );

  const slider = (
    value: number,
    min: number,
    max: number,
    step: number,
    onInput: (v: number) => void
  ) => (
    <input
      type="range"
      className="flex-[2]"
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(e) => onInput(parseFloat(e.target.value))}
    />
  );

  const toggle_ = (value: boolean, onInput: (v: boolean) => void) => (
    <input
      type="checkbox"
      className="ml-auto"
      checked={value}
      onChange={(e) => onInput(e.target.checked)}
    />
  );

  return (
    <div className="space-y-3">
      {/* Physics */}
      <section>
        {sectionHeader('physics', 'Physics')}
        {expanded.has('physics') && (
          <div className="space-y-2 mt-1 pl-4">
            {row(
              'Enabled',
              settings.physics.enabled ? 'on' : 'off',
              toggle_(settings.physics.enabled, (v) => updatePhysics({ enabled: v }))
            )}
            {row(
              'Repulsion',
              settings.physics.repulsion.toFixed(0),
              slider(
                settings.physics.repulsion,
                SLIDER_RANGES.physics.repulsion.min,
                SLIDER_RANGES.physics.repulsion.max,
                SLIDER_RANGES.physics.repulsion.step,
                (v) => updatePhysics({ repulsion: v })
              )
            )}
            {row(
              'Attraction',
              settings.physics.attraction.toFixed(3),
              slider(
                settings.physics.attraction,
                SLIDER_RANGES.physics.attraction.min,
                SLIDER_RANGES.physics.attraction.max,
                SLIDER_RANGES.physics.attraction.step,
                (v) => updatePhysics({ attraction: v })
              )
            )}
            {row(
              'Center gravity',
              settings.physics.centerGravity.toFixed(3),
              slider(
                settings.physics.centerGravity,
                SLIDER_RANGES.physics.centerGravity.min,
                SLIDER_RANGES.physics.centerGravity.max,
                SLIDER_RANGES.physics.centerGravity.step,
                (v) => updatePhysics({ centerGravity: v })
              )
            )}
            {row(
              'Damping',
              settings.physics.damping.toFixed(2),
              slider(
                settings.physics.damping,
                SLIDER_RANGES.physics.damping.min,
                SLIDER_RANGES.physics.damping.max,
                SLIDER_RANGES.physics.damping.step,
                (v) => updatePhysics({ damping: v })
              )
            )}
          </div>
        )}
      </section>

      {/* Visual */}
      <section>
        {sectionHeader('visual', 'Visual')}
        {expanded.has('visual') && (
          <div className="space-y-2 mt-1 pl-4">
            {row(
              'Show arrows',
              settings.visual.showArrows ? 'on' : 'off',
              toggle_(settings.visual.showArrows, (v) => updateVisual({ showArrows: v }))
            )}
            {row(
              'Show edge labels',
              settings.visual.showLabels ? 'on' : 'off',
              toggle_(settings.visual.showLabels, (v) => updateVisual({ showLabels: v }))
            )}
            <label className="flex items-center gap-2 text-xs text-card-foreground">
              <span className="flex-1 min-w-0 truncate">Edge color</span>
              <select
                className="flex-[2] bg-card border border-border rounded px-1 py-0.5 text-xs"
                value={settings.visual.edgeColorBy}
                onChange={(e) =>
                  updateVisual({ edgeColorBy: e.target.value as ForceGraph3DV2Settings['visual']['edgeColorBy'] })
                }
              >
                <option value="type">By edge type</option>
                <option value="endpoint">Endpoint gradient</option>
              </select>
            </label>
            {row(
              'Node size',
              settings.visual.nodeSize.toFixed(2),
              slider(
                settings.visual.nodeSize,
                SLIDER_RANGES.visual.nodeSize.min,
                SLIDER_RANGES.visual.nodeSize.max,
                SLIDER_RANGES.visual.nodeSize.step,
                (v) => updateVisual({ nodeSize: v })
              )
            )}
            {row(
              'Link width',
              settings.visual.linkWidth.toFixed(2),
              slider(
                settings.visual.linkWidth,
                SLIDER_RANGES.visual.linkWidth.min,
                SLIDER_RANGES.visual.linkWidth.max,
                SLIDER_RANGES.visual.linkWidth.step,
                (v) => updateVisual({ linkWidth: v })
              )
            )}
            {row(
              'Label radius',
              settings.visual.labelVisibilityRadius.toFixed(0),
              slider(
                settings.visual.labelVisibilityRadius,
                SLIDER_RANGES.visual.labelVisibilityRadius.min,
                SLIDER_RANGES.visual.labelVisibilityRadius.max,
                SLIDER_RANGES.visual.labelVisibilityRadius.step,
                (v) => updateVisual({ labelVisibilityRadius: v })
              )
            )}
          </div>
        )}
      </section>

      {/* Interaction */}
      <section>
        {sectionHeader('interaction', 'Interaction')}
        {expanded.has('interaction') && (
          <div className="space-y-2 mt-1 pl-4">
            {row(
              'Drag',
              settings.interaction.enableDrag ? 'on' : 'off',
              toggle_(settings.interaction.enableDrag, (v) => updateInteraction({ enableDrag: v }))
            )}
            {row(
              'Highlight neighbors',
              settings.interaction.highlightNeighbors ? 'on' : 'off',
              toggle_(settings.interaction.highlightNeighbors, (v) =>
                updateInteraction({ highlightNeighbors: v })
              )
            )}
          </div>
        )}
      </section>
    </div>
  );
};
