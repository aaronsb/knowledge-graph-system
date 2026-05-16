/**
 * ForceGraph Settings Panel
 *
 * Settings surface for the unified rendering engine (ADR-702):
 * projection, repulsion / attraction / damping / center gravity,
 * node-color mode, edge-color mode, label visibility radius, etc.
 *
 * The Reheat button lives on the on-canvas info overlay inside
 * ForceGraph.tsx so it can drive a simHandleRef that's only writable
 * from inside the r3f Canvas tree.
 */

import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import type { SettingsPanelProps } from '../../types/explorer';
import type { ForceGraphSettings } from './types';
import { SLIDER_RANGES } from './types';
import { simBackend } from './scene/useSim';
import { useGraphStore } from '../../store/graphStore';

type Section = 'physics' | 'visual' | 'interaction' | 'filters';

export const SettingsPanel: React.FC<SettingsPanelProps<ForceGraphSettings>> = ({
  settings,
  onChange,
}) => {
  const [expanded, setExpanded] = useState<Set<Section>>(new Set(['physics', 'visual']));
  // Filters live in the shared store, not in per-plugin settings, so they
  // apply universally across every explorer that consumes rawGraphData.
  const minConfidence = useGraphStore((s) => s.filters.minConfidence);
  const selectedRelationshipTypes = useGraphStore((s) => s.filters.relationshipTypes);
  const selectedOntologies = useGraphStore((s) => s.filters.ontologies);
  const filterOptions = useGraphStore((s) => s.filterOptions);
  const setFilters = useGraphStore((s) => s.setFilters);

  const toggle = (section: Section) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(section)) next.delete(section);
      else next.add(section);
      return next;
    });

  const updatePhysics = (patch: Partial<ForceGraphSettings['physics']>) =>
    onChange({ ...settings, physics: { ...settings.physics, ...patch } });
  const updateVisual = (patch: Partial<ForceGraphSettings['visual']>) =>
    onChange({ ...settings, visual: { ...settings.visual, ...patch } });
  const updateInteraction = (patch: Partial<ForceGraphSettings['interaction']>) =>
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

  // Multi-select checkbox list for the universal relationship-type /
  // ontology filters. Empty selection = show all (matches the store
  // convention used by minConfidence/visibleEdgeCategories).
  const checkboxList = (
    label: string,
    options: string[],
    selected: string[],
    onChange: (next: string[]) => void
  ) => (
    <div className="pt-1">
      <div className="text-[11px] font-medium text-foreground mb-1">{label}</div>
      {options.length === 0 ? (
        <span className="text-[10px] text-muted-foreground">None in current data</span>
      ) : (
        <div className="flex flex-col gap-1 max-h-40 overflow-y-auto pr-1">
          {options.map((opt) => {
            const checked = selected.includes(opt);
            return (
              <label
                key={opt}
                className="flex items-center gap-1.5 text-[11px] cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() =>
                    onChange(
                      checked
                        ? selected.filter((s) => s !== opt)
                        : [...selected, opt]
                    )
                  }
                />
                <span className="truncate">{opt}</span>
              </label>
            );
          })}
        </div>
      )}
    </div>
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
      {/* Projection — top-level switch since it remounts the Canvas */}
      <section>
        <label className="flex items-center gap-2 text-xs text-card-foreground py-1.5">
          <span className="flex-1 min-w-0 truncate font-medium">Projection</span>
          <select
            className="flex-[2] bg-card border border-border rounded px-1 py-0.5 text-xs"
            value={settings.projection}
            onChange={(e) =>
              onChange({ ...settings, projection: e.target.value as ForceGraphSettings['projection'] })
            }
          >
            <option value="3D">3D (perspective + orbit)</option>
            <option value="2D">2D (orthographic + pan/zoom)</option>
          </select>
        </label>
      </section>

      {/* Physics */}
      <section>
        {sectionHeader('physics', 'Physics')}
        {expanded.has('physics') && (
          <div className="space-y-2 mt-1 pl-4">
            <div className="flex items-center gap-2 text-xs text-card-foreground">
              <span className="flex-1 min-w-0 truncate">Backend</span>
              <span
                className={`font-mono text-[10px] uppercase px-1.5 py-0.5 rounded ${
                  simBackend === 'gpu'
                    ? 'bg-emerald-900/40 text-emerald-300'
                    : 'bg-amber-900/40 text-amber-300'
                }`}
                title="Sim backend chosen at module load by capability detection"
              >
                {simBackend}
              </span>
            </div>
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
            {row(
              'Show node labels',
              settings.visual.showNodeLabels ? 'on' : 'off',
              toggle_(settings.visual.showNodeLabels, (v) => updateVisual({ showNodeLabels: v }))
            )}
            <label className="flex items-center gap-2 text-xs text-card-foreground">
              <span className="flex-1 min-w-0 truncate">Node color</span>
              <select
                className="flex-[2] bg-card border border-border rounded px-1 py-0.5 text-xs"
                value={settings.visual.nodeColorBy}
                onChange={(e) =>
                  updateVisual({ nodeColorBy: e.target.value as ForceGraphSettings['visual']['nodeColorBy'] })
                }
              >
                <option value="ontology">By ontology</option>
                <option value="degree">By degree</option>
                <option value="centrality">By centrality</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-xs text-card-foreground">
              <span className="flex-1 min-w-0 truncate">Edge color</span>
              <select
                className="flex-[2] bg-card border border-border rounded px-1 py-0.5 text-xs"
                value={settings.visual.edgeColorBy}
                onChange={(e) =>
                  updateVisual({ edgeColorBy: e.target.value as ForceGraphSettings['visual']['edgeColorBy'] })
                }
              >
                <option value="type">By edge type</option>
                <option value="confidence">By confidence</option>
                <option value="endpoint">Endpoint gradient</option>
                <option value="uniform">Uniform</option>
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
              settings.visual.linkWidth.toFixed(1),
              slider(
                settings.visual.linkWidth,
                SLIDER_RANGES.visual.linkWidth.min,
                SLIDER_RANGES.visual.linkWidth.max,
                SLIDER_RANGES.visual.linkWidth.step,
                (v) => updateVisual({ linkWidth: v })
              )
            )}
            {row(
              'Node label size',
              settings.visual.nodeLabelSize.toFixed(2),
              slider(
                settings.visual.nodeLabelSize,
                SLIDER_RANGES.visual.nodeLabelSize.min,
                SLIDER_RANGES.visual.nodeLabelSize.max,
                SLIDER_RANGES.visual.nodeLabelSize.step,
                (v) => updateVisual({ nodeLabelSize: v })
              )
            )}
            {row(
              'Edge label size',
              settings.visual.edgeLabelSize.toFixed(2),
              slider(
                settings.visual.edgeLabelSize,
                SLIDER_RANGES.visual.edgeLabelSize.min,
                SLIDER_RANGES.visual.edgeLabelSize.max,
                SLIDER_RANGES.visual.edgeLabelSize.step,
                (v) => updateVisual({ edgeLabelSize: v })
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

      {/* Filters — shared-store fields, universal across explorers */}
      <section>
        {sectionHeader('filters', 'Filters')}
        {expanded.has('filters') && (
          <div className="space-y-2 mt-1 pl-4">
            {row(
              'Min confidence',
              minConfidence.toFixed(2),
              slider(minConfidence, 0, 1, 0.01, (v) => setFilters({ minConfidence: v }))
            )}
            {checkboxList(
              'Relationship types',
              filterOptions.relationshipTypes,
              selectedRelationshipTypes,
              (next) => setFilters({ relationshipTypes: next })
            )}
            {checkboxList(
              'Ontologies',
              filterOptions.ontologies,
              selectedOntologies,
              (next) => setFilters({ ontologies: next })
            )}
            <p className="text-[10px] text-muted-foreground">
              Min confidence filters edges by weight; relationship-type and
              ontology selections narrow to the checked values (empty = show
              all). All apply to every explorer reading the shared graph data.
            </p>
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
