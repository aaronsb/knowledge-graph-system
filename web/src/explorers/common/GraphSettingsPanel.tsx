/**
 * Graph Settings Panel
 *
 * Common settings panel for physics, visual, and interaction controls.
 * Shared between 2D and 3D graph explorers.
 */

import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import type { ForceGraph2DSettings } from '../ForceGraph2D/types';

// Generic settings interface - both 2D and 3D settings must have these
interface GraphSettings {
  physics: {
    enabled: boolean;
    charge: number;
    linkDistance: number;
    gravity: number;
    friction: number;
  };
  visual: {
    nodeColorBy: string;
    edgeColorBy: string;
    showLabels: boolean;
    showArrows: boolean;
    showGrid: boolean;
    showShadows: boolean;
    nodeSize: number;
    linkWidth: number;
    nodeLabelSize?: number;
    edgeLabelSize?: number;
  };
  interaction: {
    enableDrag: boolean;
    enableZoom: boolean;
    enablePan: boolean;
    highlightNeighbors: boolean;
    showOriginNode: boolean;
  };
}

interface SliderRanges {
  physics: {
    charge: { min: number; max: number; step: number };
    linkDistance: { min: number; max: number; step: number };
    gravity: { min: number; max: number; step: number };
  };
  visual: {
    nodeSize: { min: number; max: number; step: number };
    linkWidth: { min: number; max: number; step: number };
    nodeLabelSize?: { min: number; max: number; step: number };
    edgeLabelSize?: { min: number; max: number; step: number };
  };
}

interface GraphSettingsPanelProps<T extends GraphSettings> {
  settings: T;
  onChange: (settings: T) => void;
  sliderRanges: SliderRanges;
}

export const GraphSettingsPanel = <T extends GraphSettings>({
  settings,
  onChange,
  sliderRanges,
}: GraphSettingsPanelProps<T>) => {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  };

  const updatePhysics = (key: keyof ForceGraph2DSettings['physics'], value: number | boolean) => {
    onChange({
      ...settings,
      physics: { ...settings.physics, [key]: value },
    });
  };

  const updateVisual = (key: keyof ForceGraph2DSettings['visual'], value: any) => {
    onChange({
      ...settings,
      visual: { ...settings.visual, [key]: value },
    });
  };

  const updateInteraction = (key: keyof ForceGraph2DSettings['interaction'], value: boolean) => {
    onChange({
      ...settings,
      interaction: { ...settings.interaction, [key]: value },
    });
  };

  return (
    <div
      className="bg-card/95 dark:bg-gray-800/95 border border-border dark:border-gray-600 rounded-lg shadow-xl flex flex-col"
      style={{ width: '280px', maxHeight: '95vh' }}
    >
      {/* Content */}
      <div className="overflow-y-auto overflow-x-hidden p-3 space-y-3">
        {/* Physics Section */}
        <div className="border-b border-border dark:border-gray-700 pb-3">
          <button
            onClick={() => toggleSection('physics')}
            className="w-full flex items-center justify-between text-sm font-medium text-card-foreground hover:text-foreground dark:hover:text-gray-100 transition-colors"
          >
            <span>Physics</span>
            {expandedSections.has('physics') ? (
              <ChevronDown size={14} className="text-muted-foreground dark:text-gray-500" />
            ) : (
              <ChevronRight size={14} className="text-muted-foreground dark:text-gray-500" />
            )}
          </button>
          {expandedSections.has('physics') && (
            <div className="mt-3 space-y-3">
              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={settings.physics.enabled}
                  onChange={(e) => updatePhysics('enabled', e.target.checked)}
                  className="rounded"
                />
                <span className="text-card-foreground">Enable Physics</span>
              </label>

              {settings.physics.enabled && (
                <>
                  <div>
                    <label className="block text-xs text-foreground dark:text-gray-300 mb-1">
                      Charge: {settings.physics.charge}
                    </label>
                    <input
                      type="range"
                      min={sliderRanges.physics.charge.min}
                      max={sliderRanges.physics.charge.max}
                      step={sliderRanges.physics.charge.step}
                      value={settings.physics.charge}
                      onChange={(e) => updatePhysics('charge', parseInt(e.target.value))}
                      className="w-full"
                    />
                  </div>

                  <div>
                    <label className="block text-xs text-foreground dark:text-gray-300 mb-1">
                      Link Distance: {settings.physics.linkDistance}
                    </label>
                    <input
                      type="range"
                      min={sliderRanges.physics.linkDistance.min}
                      max={sliderRanges.physics.linkDistance.max}
                      step={sliderRanges.physics.linkDistance.step}
                      value={settings.physics.linkDistance}
                      onChange={(e) => updatePhysics('linkDistance', parseInt(e.target.value))}
                      className="w-full"
                    />
                  </div>

                  <div>
                    <label className="block text-xs text-foreground dark:text-gray-300 mb-1">
                      Gravity: {settings.physics.gravity.toFixed(2)}
                    </label>
                    <input
                      type="range"
                      min={sliderRanges.physics.gravity.min}
                      max={sliderRanges.physics.gravity.max}
                      step={sliderRanges.physics.gravity.step}
                      value={settings.physics.gravity}
                      onChange={(e) => updatePhysics('gravity', parseFloat(e.target.value))}
                      className="w-full"
                    />
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* Visual Section */}
        <div className="border-b border-border dark:border-gray-700 pb-3">
          <button
            onClick={() => toggleSection('visual')}
            className="w-full flex items-center justify-between text-sm font-medium text-card-foreground hover:text-foreground dark:hover:text-gray-100 transition-colors"
          >
            <span>Visual</span>
            {expandedSections.has('visual') ? (
              <ChevronDown size={14} className="text-muted-foreground dark:text-gray-500" />
            ) : (
              <ChevronRight size={14} className="text-muted-foreground dark:text-gray-500" />
            )}
          </button>
          {expandedSections.has('visual') && (
            <div className="mt-3 space-y-3">
              <div>
                <label className="block text-xs text-foreground dark:text-gray-300 mb-1">Node Color By</label>
                <select
                  value={settings.visual.nodeColorBy}
                  onChange={(e) => updateVisual('nodeColorBy', e.target.value)}
                  className="w-full rounded border border-border dark:border-gray-600 bg-muted dark:bg-gray-700 text-card-foreground p-1 text-xs"
                >
                  <option value="ontology">Ontology</option>
                  <option value="degree">Degree (Connections)</option>
                  <option value="centrality">Centrality</option>
                </select>
              </div>

              <div>
                <label className="block text-xs text-foreground dark:text-gray-300 mb-1">Edge Color By</label>
                <select
                  value={settings.visual.edgeColorBy}
                  onChange={(e) => updateVisual('edgeColorBy', e.target.value)}
                  className="w-full rounded border border-border dark:border-gray-600 bg-muted dark:bg-gray-700 text-card-foreground p-1 text-xs"
                >
                  <option value="category">Category</option>
                  <option value="confidence">Confidence</option>
                  <option value="uniform">Uniform</option>
                </select>
              </div>

              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={settings.visual.showLabels}
                  onChange={(e) => updateVisual('showLabels', e.target.checked)}
                  className="rounded"
                />
                <span className="text-card-foreground">Show Labels</span>
              </label>

              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={settings.visual.showArrows}
                  onChange={(e) => updateVisual('showArrows', e.target.checked)}
                  className="rounded"
                />
                <span className="text-card-foreground">Show Arrows</span>
              </label>

              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={settings.visual.showGrid}
                  onChange={(e) => updateVisual('showGrid', e.target.checked)}
                  className="rounded"
                />
                <span className="text-card-foreground">Show Grid</span>
              </label>

              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={settings.visual.showShadows}
                  onChange={(e) => updateVisual('showShadows', e.target.checked)}
                  className="rounded"
                />
                <span className="text-card-foreground">Shadows</span>
              </label>

              <div>
                <label className="block text-xs text-foreground dark:text-gray-300 mb-1">
                  Node Size: {settings.visual.nodeSize.toFixed(2)}x
                </label>
                <input
                  type="range"
                  min={sliderRanges.visual.nodeSize.min}
                  max={sliderRanges.visual.nodeSize.max}
                  step={sliderRanges.visual.nodeSize.step}
                  value={settings.visual.nodeSize}
                  onChange={(e) => updateVisual('nodeSize', parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>

              <div>
                <label className="block text-xs text-foreground dark:text-gray-300 mb-1">
                  Link Width: {settings.visual.linkWidth.toFixed(1)}x
                </label>
                <input
                  type="range"
                  min={sliderRanges.visual.linkWidth.min}
                  max={sliderRanges.visual.linkWidth.max}
                  step={sliderRanges.visual.linkWidth.step}
                  value={settings.visual.linkWidth}
                  onChange={(e) => updateVisual('linkWidth', parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>

              <div>
                <label className="block text-xs text-foreground dark:text-gray-300 mb-1">
                  Node Label Size: {settings.visual.nodeLabelSize}px
                </label>
                <input
                  type="range"
                  min={sliderRanges.visual.nodeLabelSize.min}
                  max={sliderRanges.visual.nodeLabelSize.max}
                  step={sliderRanges.visual.nodeLabelSize.step}
                  value={settings.visual.nodeLabelSize}
                  onChange={(e) => updateVisual('nodeLabelSize', parseInt(e.target.value))}
                  className="w-full"
                />
              </div>

              <div>
                <label className="block text-xs text-foreground dark:text-gray-300 mb-1">
                  Edge Label Size: {settings.visual.edgeLabelSize}px
                </label>
                <input
                  type="range"
                  min={sliderRanges.visual.edgeLabelSize.min}
                  max={sliderRanges.visual.edgeLabelSize.max}
                  step={sliderRanges.visual.edgeLabelSize.step}
                  value={settings.visual.edgeLabelSize}
                  onChange={(e) => updateVisual('edgeLabelSize', parseInt(e.target.value))}
                  className="w-full"
                />
              </div>
            </div>
          )}
        </div>

        {/* Interaction Section */}
        <div>
          <button
            onClick={() => toggleSection('interaction')}
            className="w-full flex items-center justify-between text-sm font-medium text-card-foreground hover:text-foreground dark:hover:text-gray-100 transition-colors"
          >
            <span>Interaction</span>
            {expandedSections.has('interaction') ? (
              <ChevronDown size={14} className="text-muted-foreground dark:text-gray-500" />
            ) : (
              <ChevronRight size={14} className="text-muted-foreground dark:text-gray-500" />
            )}
          </button>
          {expandedSections.has('interaction') && (
            <div className="mt-3 space-y-2">
              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={settings.interaction.enableDrag}
                  onChange={(e) => updateInteraction('enableDrag', e.target.checked)}
                  className="rounded"
                />
                <span className="text-card-foreground">Enable Drag</span>
              </label>

              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={settings.interaction.enableZoom}
                  onChange={(e) => updateInteraction('enableZoom', e.target.checked)}
                  className="rounded"
                />
                <span className="text-card-foreground">Enable Zoom</span>
              </label>

              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={settings.interaction.enablePan}
                  onChange={(e) => updateInteraction('enablePan', e.target.checked)}
                  className="rounded"
                />
                <span className="text-card-foreground">Enable Pan</span>
              </label>

              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={settings.interaction.highlightNeighbors}
                  onChange={(e) => updateInteraction('highlightNeighbors', e.target.checked)}
                  className="rounded"
                />
                <span className="text-card-foreground">Highlight Neighbors</span>
              </label>

              <label className="flex items-center space-x-2 text-xs">
                <input
                  type="checkbox"
                  checked={settings.interaction.showOriginNode}
                  onChange={(e) => updateInteraction('showOriginNode', e.target.checked)}
                  className="rounded"
                />
                <span className="text-card-foreground">Show Origin</span>
              </label>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
